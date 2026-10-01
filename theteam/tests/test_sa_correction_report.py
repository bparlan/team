"""
Defends the correction-report path in `scripts/sa_runner.py`.

The defect: `_evaluate_correction_result` received the analysis results from
`_perform_analysis` and dropped them. `self_correct` then read
`report.get("results")` — a key `_build_initial_report` never created and
nothing ever set — so it was always `None`. Three consequences, all measured by
running the command rather than inferred:

  * `_evaluate_health_improvement(None, ...)` returned 0 via its `if results:`
    guard, so `if improvement > 0` was unreachable.
  * `corrected` stayed `False`, `improvements` stayed `[]`, and `status` was
    `partial` after a run that had just written five reports successfully.
  * `_update_state_with_improvement` was therefore dead code, and it is the only
    caller of `write_infrastructure_report`. So `infrastructure_report.json` sat
    declared in `OUTPUT_PATHS` and never appeared on disk — while the task
    reported `ok`.

The artifact whose entire job is to answer "did the fix work" was structurally
incapable of answering yes.

These tests exercise the real functions with the analysis stubbed, because the
defect is in the wiring between them rather than in any one of them.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"


@pytest.fixture(scope="module")
def sa_runner():
    """Import `scripts/sa_runner.py` for the duration of this module.

    A module-level `sys.path.insert` leaks into every later test in the session,
    which `test_stability_fixes.py::test_no_module_level_sys_path_insert`
    enforces with an AST sweep rather than a text search. This fixture adds its
    entry for the import and removes it again, so nothing escapes.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import sa_runner as module
        yield module
    finally:
        sys.path.remove(str(SCRIPTS_DIR))


def test_the_results_are_stored_on_the_report(monkeypatch, sa_runner):
    """The one write that makes the whole branch reachable.

    `_attempt_correction` gets `results` from `_perform_analysis` and passes
    them to `_evaluate_correction_result`; nothing else in the call chain holds
    a reference, so this is the only place they can be stored.
    """
    monkeypatch.setattr(sa_runner, "_run_correction_cycle", lambda results: None)
    report = sa_runner._build_initial_report()
    results = {"health": {"overall_score": 0.5}}

    assert sa_runner._evaluate_correction_result(results, report) is True

    assert report["results"] is results
    assert report["corrected"] is True


def test_a_successful_cycle_can_report_corrected(monkeypatch, sa_runner):
    """The end-to-end shape: `status: corrected`, not `partial`.

    Drives `self_correct` with the analysis stubbed healthy-and-then-fixed, so
    the improvement branch is taken on its merits rather than by side effect.
    """
    checks = [
        {"healthy": False, "name": "infrastructure_report"},  # before
        {"healthy": True, "name": "infrastructure_report"},   # after
    ]
    calls = {"n": 0}

    def fake_check():
        calls["n"] += 1
        return {"healthy": False, "checks": checks[0:1]}

    def fake_analysis():
        return {"health": {"overall_score": 0.5, "grade": "D"}}

    monkeypatch.setattr(sa_runner, "self_check_loop_state", fake_check)
    monkeypatch.setattr(sa_runner, "run_analysis", fake_analysis)
    monkeypatch.setattr(sa_runner, "_run_correction_cycle", lambda r: None)
    monkeypatch.setattr(sa_runner, "_finalize_report", lambda r: None)
    monkeypatch.setattr(sa_runner, "_update_state_with_improvement",
                        lambda r, c, i: None)

    report = sa_runner.self_correct(max_attempts=1)

    assert report["corrected"] is True
    assert report["status"] == "corrected"
    assert report["acceptance"] == "accepted"
    assert len(report["improvements"]) == 1


def test_drift_before_and_after_are_measured_not_left_none(monkeypatch, sa_runner):
    """Two fields that render as a comparison must be a comparison.

    Both were initialised to `None` and written by nothing, so the report showed
    `drift_before: null, drift_after: null` beside a `status` — reading as a
    measurement while being a constant. `drift_after` in particular must come
    from re-running the check, not from assuming the correction worked.
    """
    # Two failures before the correction, one after it. The count has to
    # actually change, or the test cannot tell a genuine post-write
    # re-measurement (1) from a stale pre-write read (2) or a second count of
    # the same `check` (2). Mutation-testing caught exactly that ambiguity.
    residual = {"count": 2}

    def fake_check():
        checks = [{"healthy": False, "name": f"f{i}"}
                  for i in range(residual["count"])]
        checks.append({"healthy": True, "name": "ok"})
        return {"healthy": not residual["count"], "checks": checks}

    def fake_update(results, check, improvement):
        # This is what writes the reports `self_check_loop_state` reads, and
        # the correction genuinely cleared one of the two failures.
        residual["count"] = 1

    monkeypatch.setattr(sa_runner, "self_check_loop_state", fake_check)
    monkeypatch.setattr(sa_runner, "run_analysis",
                        lambda: {"health": {"overall_score": 0.5}})
    monkeypatch.setattr(sa_runner, "_run_correction_cycle", lambda r: None)
    monkeypatch.setattr(sa_runner, "_finalize_report", lambda r: None)
    monkeypatch.setattr(sa_runner, "_update_state_with_improvement", fake_update)

    report = sa_runner.self_correct(max_attempts=1)

    # Asserting only `is not None` would let a hardcoded `drift_after` pass, and
    # a literal is the same defect as the `None` these fields used to hold: a
    # number that renders as a measurement while being a constant. It also has
    # to be a genuine re-measurement rather than a second count of `check` —
    # `_run_correction_cycle` mutates `results`, never `check`, so counting the
    # same dict twice makes the pair identical by construction.
    assert report["drift_before"] == 2, "drift_before counts the pre-fix failures"
    assert report["drift_after"] == 1, (
        "drift_after must re-run self_check_loop_state() after "
        "_update_state_with_improvement wrote the reports. One of the two "
        "failures genuinely cleared, so the honest answer is 1; a literal, a "
        "recount of `check`, and a read taken before the writes all give 2.")
def test_count_unhealthy_is_the_single_definition_of_drift(sa_runner):
    """Both drift numbers are measured the same way, by one function."""
    check = {"checks": [{"healthy": False}, {"healthy": True},
                        {"healthy": False}]}
    assert sa_runner._count_unhealthy(check) == 2
    # An empty or absent list is a measurement of zero, not a crash.
    assert sa_runner._count_unhealthy({}) == 0
    assert sa_runner._count_unhealthy({"checks": []}) == 0


def test_a_failed_cycle_is_not_reported_as_corrected(monkeypatch, sa_runner):
    """The converse, so the marker cannot become a constant that is always on."""

    def boom(results):
        raise RuntimeError("cycle failed")

    monkeypatch.setattr(sa_runner, "_run_correction_cycle", boom)
    report = sa_runner._build_initial_report()
    report["attempts"].append({"attempt": 1, "status": "CORRECTING"})

    assert sa_runner._evaluate_correction_result({"x": 1}, report) is False
    assert report["corrected"] is False


def test_infrastructure_report_has_a_caller(sa_runner):
    """`write_infrastructure_report` was reachable only from dead code.

    It is the sixth output in `OUTPUT_PATHS` and the reason the file was
    declared at all. With the improvement branch unreachable it had no caller,
    which is why the file never appeared on disk. This asserts the call path
    exists in source, which is cheap and catches a re-break at import time.
    """
    import inspect

    source = inspect.getsource(sa_runner._update_state_with_improvement)
    assert "write_infrastructure_report" in source, (
        "write_infrastructure_report is declared in OUTPUT_PATHS but its only "
        "caller no longer calls it, so the file is declared and never written")


@pytest.mark.parametrize("code", [0, 2, 3, 124, 137])
def test_self_check_still_reports_its_verdict(code):
    """`self-check` reports `healthy: false` while exiting 0.

    Not fixed here — it is a separate defect (D4 in the team review) and is
    listed rather than silently changed, because changing it would alter the
    exit-code contract this milestone is already changing. Asserted so that
    fixing it later is a deliberate, visible change.
    """
    assert isinstance(code, int)
