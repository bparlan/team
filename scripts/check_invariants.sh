#!/usr/bin/env bash
# Engineering invariants from ARCHITECTURE.md §7.2. Exit 1 on any failure.
# Checks 1 and 2 are M4's falsification tests: they are expected to fail
# until M4 lands. The exemption lives in the source as a `# TODO(M4)`
# comment, not by deleting the check.
set -u
cd "$(dirname "$0")/.."

fail=0

# 1. The safety layer has a consumer in tasks/. Match imports and calls, so a
# name in a docstring does not count as a consumer. M4 wires it.
if grep -rE "from theteam\.core\.(circuit_breaker|resource_limiter|agent_isolation|audit)|(CircuitBreaker|ResourceLimiter|AgentIsolation|AuditLogger)\(" theteam/tasks/ >/dev/null 2>&1; then
  echo "check 1 PASS: safety layer has a consumer in theteam/tasks/"
else
  echo "check 1 FAIL: no CircuitBreaker/ResourceLimiter/AgentIsolation/AuditLogger consumer in theteam/tasks/ — owns M4"
  grep -rn "# TODO(M4)" theteam/tasks/ >/dev/null 2>&1 || echo "  (no # TODO(M4) exemption present)"
  fail=1
fi

# 2. Every subprocess site in executor.py sits inside a Layer 4 guard. M4.
if grep -q "subprocess" theteam/tasks/executor.py 2>/dev/null; then
  if grep -q "# TODO(M4)" theteam/tasks/executor.py; then
    echo "check 2 PASS: subprocess sites in theteam/tasks/executor.py carry a # TODO(M4) exemption"
  else
    echo "check 2 FAIL: subprocess call site in theteam/tasks/executor.py without a Layer 4 guard — owns M4"
    grep -n "subprocess" theteam/tasks/executor.py
    fail=1
  fi
else
  echo "check 2 PASS: no subprocess sites in theteam/tasks/executor.py"
fi

# 3. No hardcoded /Users/bparlan in the package.
if grep -rn "/Users/bparlan" theteam/ --include="*.py" >/dev/null 2>&1; then
  echo "check 3 FAIL: hardcoded /Users/bparlan in theteam/"
  grep -rn "/Users/bparlan" theteam/ --include="*.py"
  fail=1
else
  echo "check 3 PASS: no /Users/bparlan in theteam/"
fi

# 4. No parents[ index trickery.
if grep -rn "parents\[" theteam/ --include="*.py" >/dev/null 2>&1; then
  echo "check 4 FAIL: parents[ usage in theteam/"
  grep -rn "parents\[" theteam/ --include="*.py"
  fail=1
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
  fail=1
fi

# 6. No MockAPI in the package.
if grep -rn "MockAPI" theteam/ --include="*.py" >/dev/null 2>&1; then
  echo "check 6 FAIL: MockAPI in theteam/"
  grep -rn "MockAPI" theteam/ --include="*.py"
  fail=1
else
  echo "check 6 PASS: no MockAPI in theteam/"
fi

if [ "$fail" -ne 0 ]; then
  echo "invariant gate FAILED"
  exit 1
fi
echo "invariant gate PASSED"
exit 0