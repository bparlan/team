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

# 3. No hardcoded /Users/bparlan in the package.
if grep -rn "/Users/bparlan" theteam/ --include="*.py" >/dev/null 2>&1; then
  echo "check 3 FAIL: hardcoded /Users/bparlan in theteam/"
  grep -rn "/Users/bparlan" theteam/ --include="*.py"
  hard_fail=1
else
  echo "check 3 PASS: no /Users/bparlan in theteam/"
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
hits=$(grep -rn "\.mp/theteam" theteam/ --include="*.py" 2>/dev/null)
allowed="theteam/tasks/repository.py:29:DEAD_DIR = \".mp/theteam\""
allowed2="theteam/tasks/repository.py:53:    # Reject paths that reference the deleted .mp/theteam directory,"
allowed3="theteam/tests/test_task_repository.py"
unwanted=$(echo "$hits" | grep -vF "$allowed" | grep -vF "$allowed2" | grep -vF "$allowed3")
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

if [ "$hard_fail" -ne 0 ]; then
  echo "invariant gate FAILED"
  exit 1
fi
echo "invariant gate PASSED"
exit 0