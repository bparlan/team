#!/usr/bin/env python3
"""
Infrastructure validation runner for theteam task loop.

Validates Python version, required scripts exist, directory layout is intact,
and runtime dependencies are available.
"""

import os
import sys
import json
from pathlib import Path

#: The executor's phase-outcome taxonomy (mirrored from
#: `theteam.tasks.executor` rather than imported: this script runs inside the
#: isolation container, where the `theteam` package is importable but adding an
#: import edge from a check script to the executor it is checked by would make
#: the exit-code contract circular and untestable). Duplicated deliberately,
#: and asserted equal in `theteam/tests/test_project_integrity_taxonomy.py` so
#: the two copies cannot drift apart silently.
FINDINGS_EXIT_CODE = 3

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_SCRIPTS = [
    "scripts/loop_health_check.py",
    "scripts/loop_maintenance.py",
    "scripts/loop_infrastructure_check.py",
    "bin/theteam_config.py",
    "bin/theteam_report.py",
]

# `git` was here and has been removed. It was never used by this check —
# `check_tools` only probes PATH presence — but the isolation image
# `theteam:p4final` has no `git` in it, so this phase exited 1 on every
# containerised run, on every machine, since it was written. It passed
# standalone only because the *host* has git, which is why nobody saw it.
#
# A check that can only fail is not a check. This is the same defect shape as
# the `tasks/TASK_ORDER` entry below: a requirement no code path can satisfy.
# Verified: `docker run --entrypoint sh theteam:p4final -c 'command -v git'`
# is empty; rc 1 in the container, rc 0 on the host.
#
# If the image should carry git instead, that is a Dockerfile change, not a
# task change — and then this entry belongs back, because an infrastructure
# check that cannot see the VCS it is meant to verify is checking a fiction.
REQUIRED_TOOLS = ["python3"]

REQUIRED_LOOP_FILES = [
    # `tasks/TASK_ORDER` used to be required here. It stopped existing when
    # ordering moved into each task's own `order:` key (M1), and this check kept
    # demanding it — so `infrastructure-check` failed unconditionally, on a
    # file no code path could produce. A check that can only fail is not a
    # check; it is a task guaranteed to report a red that nobody can action.
    ".loop-state.json",
]

# The directories this repo actually has. `docs` was previously listed here and
# has never existed — no directory, no deletion commit — so the check reported a
# missing directory that nobody could create. Hoisted to module scope so the
# summary line below counts the list it validates rather than a hardcoded `9`
# that had stopped matching it.
REQUIRED_DIRS = [
    "tasks", "scripts", "bin", "theteam", "prompts",
    ".loop-log", ".loop-archive",
]

MIN_PYTHON = (3, 12)


def check_python_version() -> list:
    errors = []
    v = sys.version_info
    if (v.major, v.minor) < MIN_PYTHON:
        errors.append(
            f"Python {v.major}.{v.minor} is below minimum {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
        )
    return errors


def check_required_scripts() -> list:
    missing = []
    for rel in REQUIRED_SCRIPTS:
        path = PROJECT_ROOT / rel
        if not path.is_file():
            missing.append(rel)
    return [f"Missing required script: {s}" for s in missing]


def check_loop_files() -> list:
    missing = []
    for rel in REQUIRED_LOOP_FILES:
        path = PROJECT_ROOT / rel
        if not path.is_file():
            missing.append(rel)
    return [f"Missing required loop file: {rel}" for rel in missing]


def check_tools() -> list:
    errors = []
    for tool in REQUIRED_TOOLS:
        if not _which(tool):
            errors.append(f"Required tool not found in PATH: {tool}")
    return errors


def _which(name: str) -> bool:
    """Check if an executable exists in PATH."""
    path_env = os.environ.get("PATH", "")
    for p in path_env.split(":"):
        candidate = Path(p) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return True
    return False


def check_directory_layout() -> list:
    """Check the directories this repo actually has.

    `docs` was listed here and has never existed in this repository — no
    deletion commit, no directory. Asking for it meant this check reported a
    missing directory that no one could create, for the same reason
    `tasks/TASK_ORDER` did.
    """
    missing = []
    for d in REQUIRED_DIRS:
        path = PROJECT_ROOT / d
        if not path.is_dir():
            missing.append(d)
    return [f"Missing directory: {d}" for d in missing]



def main():
    errors = []
    errors.extend(check_python_version())
    errors.extend(check_required_scripts())
    errors.extend(check_loop_files())
    errors.extend(check_tools())
    errors.extend(check_directory_layout())

    if errors:
        for err in errors:
            print(f"FINDING: {err}")
        # 3, not 1. Exit 1 is what an uncaught exception produces, so the
        # executor cannot tell a check that found a problem from a check that
        # crashed — and it must. `TaskExecutor.execute_phase` maps 3 to
        # "ran, found something, did not break", which keeps a working monitor
        # from tripping its own breaker. Exiting 1 here meant five genuine
        # detections opened the breaker permanently and the task stopped
        # running: the project's real defect became permanently unmonitored.
        print(f"{len(errors)} finding(s); the check itself completed.")
        sys.exit(FINDINGS_EXIT_CODE)

    print("Infrastructure check passed: all systems operational")
    print(f"  Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"  Scripts checked: {len(REQUIRED_SCRIPTS)}")
    print(f"  Tools checked: {len(REQUIRED_TOOLS)}")
    print(f"  Directories checked: {len(REQUIRED_DIRS)}")
    sys.exit(0)


if __name__ == "__main__":
    main()