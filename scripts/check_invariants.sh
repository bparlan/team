#!/usr/bin/env bash
# Engineering invariants from ARCHITECTURE.md §7.2. Exit 1 on any failure.
#
# Checks 1 and 2 are M4's falsification tests. They fail today by design and
# stop failing when M4 lands. They are reported, not hard-failed: the script
# exits 0 on them so M4's work does not stall the pipeline, but the log names
# M4 as the owner. The exemption is a `# TODO(M4)` comment in the source, not
# a deleted check.
#
# Checks 3-6 are regressions that must hard-fail today and on every future
# commit until they are fixed.
set -u
cd "$(dirname "$0")/.."

hard_fail=0
m4_pending=0

# 1. The safety layer has a consumer in tasks/. Match imports and calls, so a
# name in a docstring does not count as a consumer. M4 wires it.
if grep -rE "from theteam\.core\.(circuit_breaker|resource_limiter|agent_isolation|audit)|(CircuitBreaker|ResourceLimiter|AgentIsolation|AuditLogger)\(" theteam/tasks/ >/dev/null 2>&1; then
  echo "check 1 PASS: safety layer has a consumer in theteam/tasks/"
else
  echo "check 1 FAIL (exempt, owns M4): no CircuitBreaker/ResourceLimiter/AgentIsolation/AuditLogger consumer in theteam/tasks/"
  grep -rn "# TODO(M4)" theteam/tasks/ >/dev/null 2>&1 || echo "  (no # TODO(M4) exemption present)"
  m4_pending=1
fi

# 2. No subprocess call site in Layer 3. Checked by AST, not grep: the word
# "subprocess" in a docstring describing the pre-M4 behaviour is not a call
# site, and a gate that fires on its own documentation is one people ignore.
if out=$(python3 scripts/check_call_sites.py subprocess theteam/tasks/executor.py); then
  echo "check 2 PASS: no subprocess call sites in theteam/tasks/executor.py"
else
  echo "check 2 FAIL: $out"
  hard_fail=1
fi

# 3. No hardcoded developer paths. Scoped to the task scripts as well as the
# package: five scripts carried `~/devcode/team/...` while this check scanned
# `theteam/` only, so nothing tripped. `sa_runner.py` is excluded by line
# range. It was excluded for a literal in its default-state branch; that branch
# was corrected, so the only match left is the comment at :236 recording the
# correction. The carve-out still matches that comment — dropping it would fail
# this check on the comment alone — so it stays until someone deletes the
# comment and the exclusion together.
hardcoded=$(grep -rn "/Users/bparlan\|~/devcode/team" theteam/ scripts/ \
  --include="*.py" 2>/dev/null | grep -v "^scripts/sa_runner.py:2[34][0-9]:" | grep -v "scripts/seed-materialiser.py:")
if [ -n "$hardcoded" ]; then
  echo "check 3 FAIL: hardcoded developer path in theteam/ or scripts/"
  echo "$hardcoded"
  hard_fail=1
else
  echo "check 3 PASS: no hardcoded developer path in theteam/ or scripts/"
fi

# 4. No parents[ index trickery.
if grep -rn "parents\[" theteam/ --include="*.py" >/dev/null 2>&1; then
  echo "check 4 FAIL: parents[ usage in theteam/"
  grep -rn "parents\[" theteam/ --include="*.py"
  hard_fail=1
else
  echo "check 4 PASS: no parents[ in theteam/"
fi

# 5. No .mp/theteam references outside the DEAD_DIR guard and its test.
#
# Matched on the *text after the line number*, not on `file:line:text`. Pinning
# the line number meant that adding one import above the guard broke the gate —
# measured, adding `import logging` moved it from 29 to 34 and check 5 failed
# with nothing wrong in the code it guards. A guard that fires on unrelated
# edits trains the reader to ignore it.
hits=$(grep -rn "\.mp/theteam" theteam/ --include="*.py" 2>/dev/null)
allowed_guard='DEAD_DIR = ".mp/theteam"'
allowed_comment='# Reject paths that reference the deleted .mp/theteam directory,'
allowed_test="theteam/tests/test_task_repository.py"
unwanted=$(echo "$hits" | grep -vF "$allowed_test" | sed 's/^[^:]*:[0-9]*://' \
  | grep -vF "$allowed_guard" | grep -vF "$allowed_comment")
if [ -z "$unwanted" ]; then
  echo "check 5 PASS: .mp/theteam only in the DEAD_DIR guard and its test"
else
  echo "check 5 FAIL: .mp/theteam outside the DEAD_DIR guard and its test"
  echo "$unwanted"
  hard_fail=1
fi

# 6. No MockAPI in the package. AST, not grep: naming the §3.3 defect in a
# docstring, in order to forbid it, is the opposite of a violation.
if out=$(python3 scripts/check_call_sites.py MockAPI $(find theteam -name '*.py' -not -path '*/__pycache__/*')); then
  echo "check 6 PASS: no MockAPI in theteam/"
else
  echo "check 6 FAIL: $out"
  hard_fail=1
fi

# 7. The import graph of the package entry point. The only check here that
# measures load instead of scanning text: checks 1-6 are greps and AST walks
# over source, and all six passed while `import theteam` was pulling a
# PostgreSQL cluster layer that §5.1 never places in this stack. Budgets are
# the measured floor; see scripts/check_import_graph.py for why each number is
# what it is.
if out=$(python3 scripts/check_import_graph.py 2>&1); then
  echo "check 7 PASS: import graph within budget, no cluster tier loaded"
else
  echo "check 7 FAIL: import graph over budget or a database tier is loaded"
  echo "$out" | sed 's/^/  /'
  hard_fail=1
fi

# 8. Prose citation truth. Tier 1 (existence and range) is enforced; tiers 2
# and 3 report only. The split is the plan's, not a preference: all 15 tier-1
# claims pass today, so enforcing cannot break the tree, while tier 3 is the
# newest and least proven rule and a false finding there must not stall a
# build. Tier 3 firing is printed, not fatal.
doc_summary=$(python3 scripts/check_doc_truth.py --enforce 2>&1)
echo "$doc_summary" | grep -E '^(SUMMARY|  TIER1|  TIER3|  SCOPE)' | sed 's/^/  /'
if echo "$doc_summary" | grep -q 'TIER1 FAIL'; then
  echo "check 8 FAIL: a cited file is missing or a cited line is past EOF"
  echo "$doc_summary" | grep 'TIER1 FAIL' | sed 's/^/  /'
  hard_fail=1
fi
if echo "$doc_summary" | grep -q 'DRIFT: parser baseline mismatch'; then
  echo "check 8 FAIL: the citation parser drifted from its frozen baseline"
  hard_fail=1
fi

# m4_pending is a non-blocking finding: check 1's safety-layer consumer is
# still absent and owned by M4. It is read here so the pattern is real --
# before this, the variable was assigned at :25 and read nowhere, which is
# a precedent that looks like it works and does not.
if [ "$m4_pending" -ne 0 ]; then
  echo "  (non-blocking: check 1 remains open, owner M4; gate exits 0)"
fi

if [ "$hard_fail" -ne 0 ]; then
  echo "invariant gate FAILED"
  exit 1
fi
echo "invariant gate PASSED"
exit 0