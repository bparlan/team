"""
The engineering invariant gate runs as part of the suite.

`scripts/check_invariants.sh` was wired into CI and nowhere else. M5's own
baseline is `pytest` alone, so the gate was invisible to the session that had
to honour it: a regression it exists to catch - a hardcoded path, an upward
path-index expression, a `MockAPI` back in the package - would have shown a
green suite and a red CI run, and the session that fixed it would have been
told the suite was clean.

This file closes that gap with the smallest thing that works: run the gate,
assert the exit code. No parsing, no per-check mirroring, no second
implementation of the rules in Python. The script is the gate; this only
executes it.

A missing or unrunnable script fails the test rather than skipping it. A gate
that silently reports green when it did not run is the exact false-green
pattern this suite already contains one of.
"""

import subprocess
from pathlib import Path

import pytest

# The repository root, resolved from this file rather than from the working
# directory. A test that depends on pytest being invoked from the root passes
# locally and fails in CI, which is the opposite of what it is for.
#
# `parent` walked by hand rather than indexed: check 4 of the gate this file
# runs forbids the index form in the package, and a gate-enforcing test that
# trips the gate is not a test anyone can fix quietly.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = REPO_ROOT / "scripts" / "check_invariants.sh"


@pytest.fixture(scope="module")
def gate_result():
    """
    Run the gate once for the module.

    One run, not one per test: the script takes about a second and every test
    here asserts the same property of the same exit code.
    """
    if not GATE.exists():
        pytest.fail(
            f"the invariant gate is missing: {GATE}. It is part of the "
            f"repository, and a suite that cannot find it cannot honour it."
        )
    return subprocess.run(
        ["bash", str(GATE)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def test_the_invariant_gate_passes(gate_result):
    """
    Every check holds. The stdout is in the failure message on purpose: when
    the gate goes red, which check fired and why is the first thing anyone
    needs, and scrolling to CI logs to find it is how a red gate gets ignored.
    """
    assert gate_result.returncode == 0, (
        f"scripts/check_invariants.sh exited {gate_result.returncode}\n"
        f"--- stdout ---\n{gate_result.stdout}\n"
        f"--- stderr ---\n{gate_result.stderr}"
    )


def test_the_gate_reports_every_check_rather_than_only_the_failing_one(gate_result):
    """
    The script numbers its checks, and a gate that stopped reporting one would
    go quiet about it. Six checks, all named in the output.
    """
    assert gate_result.returncode == 0
    for n in range(1, 7):
        assert f"check {n} " in gate_result.stdout, (
            f"check {n} is no longer reported:\n{gate_result.stdout}"
        )


def test_a_green_run_says_it_passed(gate_result):
    """
    A zero exit with no verdict is a gate nobody can trust at a glance in CI
    output. It states the outcome.
    """
    if gate_result.returncode == 0:
        assert "invariant gate PASSED" in gate_result.stdout
    else:
        assert "invariant gate FAILED" in gate_result.stdout
