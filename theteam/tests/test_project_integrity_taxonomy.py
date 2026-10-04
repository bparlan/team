"""
Defends the phase-outcome taxonomy added when `project-integrity` began
exiting 3 for findings and 2 for "cannot evaluate".

The defect this closes: `loop_infrastructure_check.py` and
`loop_health_check.py` exited 1 when they found a problem. `execute_phase`
read exit 1 as failure and `execute_task` passed it to
`breaker.record_failure()`, so five *correct* detections opened the breaker
permanently and the task stopped running. The monitor disabled itself by
working correctly — it looked healthy in `theteam tasks` while checking
nothing. Measured before the fix: 5 correct detections ->
`allow_request() == False`, state OPEN.

The exit codes are duplicated in the check scripts rather than imported, so
these tests also assert the copies have not drifted.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from theteam.tasks.executor import (
    CANNOT_EVALUATE_EXIT_CODE,
    FINDINGS_EXIT_CODE,
    BAD_CITATION_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    OOM_KILL_EXIT_CODE,
)


SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"


def _taxonomy_from_script(name: str) -> dict:
    """Read the constant out of a check script without importing it."""
    tree = ast.parse((SCRIPTS_DIR / name).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "FINDINGS_EXIT_CODE":
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} does not define FINDINGS_EXIT_CODE")


@pytest.mark.parametrize("script", [
    "loop_health_check.py",
    "loop_infrastructure_check.py",
])
def test_check_scripts_agree_with_the_executor_on_the_findings_code(script):
    """The two copies must not drift.

    A check script cannot import the executor that interprets its exit code
    without making the contract circular, so the constant is duplicated. This
    is the test that pays for that decision.
    """
    assert _taxonomy_from_script(script) == FINDINGS_EXIT_CODE


def test_findings_code_is_not_the_crash_code():
    """Exit 1 is what Python raises for an uncaught exception.

    A findings code of 1 would make a traceback indistinguishable from a
    clean measurement — the exact defect class this taxonomy exists to close.
    """
    assert FINDINGS_EXIT_CODE != 1
    assert CANNOT_EVALUATE_EXIT_CODE != 1
    # And they must not collide with the two codes isolation already reserves.
    assert FINDINGS_EXIT_CODE not in (TIMEOUT_EXIT_CODE, OOM_KILL_EXIT_CODE)
    assert CANNOT_EVALUATE_EXIT_CODE not in (
        TIMEOUT_EXIT_CODE, OOM_KILL_EXIT_CODE, FINDINGS_EXIT_CODE)


def test_a_finding_does_not_trip_the_breaker(tmp_path, monkeypatch):
    """The regression itself: repeated correct detections leave the breaker closed.

    Before the fix this asserted the opposite — five findings and the breaker
    was OPEN, permanently disabling the monitor. `allow_request()` is the exact
    call `execute_task` makes before running a task, so it is the right thing
    to assert on: not an internal counter, but the question "will this run?".
    """
    from theteam.core.circuit_breaker import (
        CircuitBreaker, CircuitBreakerConfig)
    from theteam.tasks.executor import TaskExecutor

    # Drive the real aggregation rather than reimplementing it, so this test
    # breaks if someone reintroduces the breaker call on a findings phase.
    monkeypatch.setattr(
        TaskExecutor, "execute_phase",
        lambda self, p, task=None, on_output=None: {
            "success": True, "findings": True,
            "findings_output": "FINDING: something",
            "returncode": FINDINGS_EXIT_CODE, "phase": p["name"]})

    executor = TaskExecutor(str(tmp_path))
    result = None
    for _ in range(6):
        result = executor.execute_task({"id": "project-integrity", "phases": [
            {"name": "directories configs and loop state"}]})

    assert result["overall_success"] is True
    assert result["has_findings"] is True

    # The question `execute_task` actually asks before running anything. Before
    # the fix, six correct detections left this False and the task stopped
    # running for good — the monitor disabling itself by working correctly.
    breaker = executor._breaker("project-integrity")
    assert breaker.allow_request() is True, (
        "repeated findings opened the breaker, so project-integrity stopped "
        "running. A check that finds a real problem must not be punished for it.")


def test_findings_are_reported_separately_from_success(tmp_path, monkeypatch):
    """`overall_success` and `has_findings` answer different questions.

    A green task that keeps finding real problems is not a green project.
    Collapsing the two facts is how a monitor reporting the same problem for a
    week still renders as `ok`.
    """
    from theteam.tasks.executor import TaskExecutor

    monkeypatch.setattr(
        TaskExecutor, "execute_phase",
        lambda self, p, task=None, on_output=None: {
            "success": True, "findings": True,
            "findings_output": "FINDING: something",
            "returncode": FINDINGS_EXIT_CODE, "phase": p["name"]})

    executor = TaskExecutor(str(tmp_path))
    result = executor.execute_task({"id": "project-integrity", "phases": [
        {"name": "check"}]})

    assert result["overall_success"] is True
    assert result["has_findings"] is True


def test_a_clean_run_has_no_findings(tmp_path, monkeypatch):
    """The converse, so the marker cannot be a constant that is always on."""
    from theteam.tasks.executor import TaskExecutor

    monkeypatch.setattr(
        TaskExecutor, "execute_phase",
        lambda self, p, task=None, on_output=None: {
            "success": True, "returncode": 0, "phase": p["name"]})

    executor = TaskExecutor(str(tmp_path))
    result = executor.execute_task({"id": "project-integrity", "phases": [
        {"name": "check"}]})
    assert result["overall_success"] is True
    assert result["has_findings"] is False


@pytest.mark.parametrize("script_name,required_dirs", [
    ("loop_health_check.py", ["tasks", "bin", "theteam"]),
    ("loop_infrastructure_check.py", ["tasks", "scripts", "bin", "theteam",
                                       "prompts"]),
])
def test_the_check_reports_findings_with_exit_three(
        script_name, required_dirs, tmp_path):
    """End-to-end through each real script: a finding exits 3, not 1.

    Driven against a throwaway project that is genuinely missing required
    files, so the check has real findings to report rather than mocked ones.
    Both scripts are covered because they are separate implementations of the
    same contract, and mutation-testing caught one of them reverting to exit 1
    while the other's test still passed.
    """
    probe = tmp_path / "probe"
    (probe / "scripts").mkdir(parents=True, exist_ok=True)
    for d in required_dirs:
        (probe / d).mkdir(parents=True, exist_ok=True)
    # Every directory the script checks for is deliberately absent, so there is
    # at least one genuine finding either way.
    script = SCRIPTS_DIR / script_name
    (probe / "scripts" / script.name).write_text(script.read_text())

    result = subprocess.run(
        [sys.executable, str(probe / "scripts" / script.name)],
        capture_output=True, text=True, cwd=probe)

    assert result.returncode == FINDINGS_EXIT_CODE, (
        f"expected findings exit {FINDINGS_EXIT_CODE}, got {result.returncode}: "
        f"{result.stdout}{result.stderr}")
    assert "FINDING:" in result.stdout


# The tests above stub `execute_phase`, so they defend the aggregation but not
# the classification itself. Mutation-testing found that gap: deleting the
# `elif exit_code == FINDINGS_EXIT_CODE:` branch outright left every one of them
# green, because a stubbed phase never reaches the real code. These drive
# `execute_phase` for real.

def _fake_isolation(exit_code):
    """Build a stand-in for AgentIsolation that returns a chosen exit code.

    Reaches the classification chain without needing Docker: the container is
    not what is under test, the reading of its exit code is. `available` has to
    be carried on the same object because `execute_phase` checks it through the
    class it imported.
    """

    class _Fake:
        available = staticmethod(lambda: True)

        def __init__(self, policy, _code=exit_code):
            self.policy = policy
            self._code = _code

        def run(self, command, **kwargs):
            return {"success": self._code == 0, "exit_code": self._code,
                    "stdout": "FINDING: something\n", "stderr": "",
                    "isolated": True}

    return _Fake


@pytest.mark.parametrize("exit_code,expect_success,expect_key", [
    (0, True, None),
    (FINDINGS_EXIT_CODE, True, "findings"),
    (BAD_CITATION_EXIT_CODE, True, "findings"),
    (CANNOT_EVALUATE_EXIT_CODE, False, "cannot_evaluate"),
    (TIMEOUT_EXIT_CODE, False, None),
    (OOM_KILL_EXIT_CODE, False, None),
])
def test_execute_phase_classifies_every_exit_code(
        exit_code, expect_success, expect_key, tmp_path, monkeypatch):
    """Each code in the taxonomy produces its own outcome.

    Asserting the marker key directly is what makes deleting a classification
    branch detectable; asserting only `success` would not, because a findings
    phase is also a success.
    """
    from theteam.tasks.executor import TaskExecutor

    monkeypatch.setattr("theteam.tasks.executor.AgentIsolation",
                        _fake_isolation(exit_code))

    script = tmp_path / "scripts" / "probe.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("print('ok')\n")

    phase = {"name": "probe", "script": "scripts/probe.py", "args": [],
             "timeout_seconds": 5, "memory_limit_mb": 128}
    outcome = TaskExecutor(str(tmp_path)).execute_phase(phase, {"id": "t"})

    assert outcome["success"] is expect_success
    assert outcome["returncode"] == exit_code
    if expect_key is None:
        assert expect_key not in outcome
    else:
        assert outcome.get(expect_key) is True


def test_bad_citation_is_distinguishable_from_a_changed_file(tmp_path, monkeypatch):
    """Exit 3 and exit 4 are both successes with findings, but they need
    different repairs: 3 means re-derive the node, 4 means fix the number.

    Asserting only `findings` would let the BAD_CITATION branch be deleted
    and leave the suite green, because FINDINGS already sets that key.
    """
    from theteam.tasks.executor import TaskExecutor

    def outcome_for(code):
        monkeypatch.setattr("theteam.tasks.executor.AgentIsolation",
                            _fake_isolation(code))
        script = tmp_path / "scripts" / "probe.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("print('ok')\n")
        phase = {"name": "probe", "script": "scripts/probe.py", "args": [],
                 "timeout_seconds": 5, "memory_limit_mb": 128}
        return TaskExecutor(str(tmp_path)).execute_phase(phase, {"id": "t"})

    bad = outcome_for(BAD_CITATION_EXIT_CODE)
    changed = outcome_for(FINDINGS_EXIT_CODE)

    assert bad.get("bad_citation") is True
    assert changed.get("bad_citation") is None, (
        "a changed cited file must not be reported as a bad citation; the "
        "two need different repairs")
    assert bad["findings"] is True and changed["findings"] is True


def test_a_crash_is_never_read_as_findings(tmp_path, monkeypatch):
    """The specific confusion the code choice exists to prevent.

    An uncaught exception exits 1. If 1 meant findings, a traceback would be
    recorded as a clean measurement with a result attached.
    """
    from theteam.tasks.executor import TaskExecutor

    monkeypatch.setattr("theteam.tasks.executor.AgentIsolation",
                        _fake_isolation(1))

    script = tmp_path / "scripts" / "probe.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("raise RuntimeError('boom')\n")

    outcome = TaskExecutor(str(tmp_path)).execute_phase(
        {"name": "probe", "script": "scripts/probe.py", "args": [],
         "timeout_seconds": 5, "memory_limit_mb": 128}, {"id": "t"})

    assert outcome["success"] is False
    assert "findings" not in outcome
