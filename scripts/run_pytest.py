#!/usr/bin/env python3
"""
Run this project's test suite, for `native-feature-loop`'s test phase.

M9 Phase 4 keeps the test phase a `script:` rather than `runner: llm`, and
this script is the reason: a test suite is deterministic, and a model
judging whether a test suite passed is the `MockAPI` defect in a new place.
This reports the real exit code of a real pytest run.

It resolves the suite from its own location rather than from `$PWD`, because a
task phase runs with the project root mounted at `/workspace` inside the
container and a `tests/` relative to wherever the process happened to start
would be a different directory or none at all.
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS = PROJECT_ROOT / "theteam" / "tests"


def main() -> int:
    if not TESTS.is_dir():
        print(f"no test directory at {TESTS}", file=sys.stderr)
        return 2

    command = [sys.executable, "-m", "pytest", str(TESTS), "-q"]
    if os.environ.get("THETEAM_PYTEST_ARGS"):
        command.extend(os.environ["THETEAM_PYTEST_ARGS"].split())

    # The real exit code, propagated. A wrapper that returns 0 on failure
    # would make `native-feature-loop` report success for a red suite, which
    # is the exact failure the phase exists to catch.
    return subprocess.call(command, cwd=str(PROJECT_ROOT))


if __name__ == "__main__":
    sys.exit(main())
