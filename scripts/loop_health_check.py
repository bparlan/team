#!/usr/bin/env python3
"""
Health check runner for theteam task loop.

Verifies project file integrity, config validity, required directories,
and that .loop-state.json exists and parses.
"""

import os
import json
import sys
from pathlib import Path

#: Mirrors `theteam.tasks.executor.FINDINGS_EXIT_CODE`. Duplicated rather than
#: imported for the same reason as in `loop_infrastructure_check.py`: a check
#: script must not import the executor that interprets its exit code, or the
#: contract becomes circular and untestable. Asserted equal in
#: `theteam/tests/test_project_integrity_taxonomy.py`.
FINDINGS_EXIT_CODE = 3

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DIRS = ["tasks", "scripts", "bin", "theteam"]

# `system-awareness-config.json` used to be required here. Nothing has read its
# *contents* since the `system-awareness` task was retired — the filename
# appeared in exactly one place, this list, and `check_required_configs` only
# calls `exists()` on each entry. So it was a gate on a file whose values
# nothing consumed, named after a task that no longer exists.
#
# Requiring it was therefore a finding about a file's presence and nothing
# else: removable without losing a check anyone acted on. The file stays in the
# tree (it is git-tracked) in case the config it holds is wanted again; it is
# simply no longer a gate.
REQUIRED_CONFIGS = ["theteam.config"]
LOOP_STATE = PROJECT_ROOT / ".loop-state.json"


def check_project_root() -> list:
    """Check project root exists and is accessible."""
    errors = []
    if not PROJECT_ROOT.exists():
        errors.append(f"Project root does not exist: {PROJECT_ROOT}")
    if not PROJECT_ROOT.is_dir():
        errors.append(f"Project root is not a directory: {PROJECT_ROOT}")
    return errors


def check_required_dirs() -> list:
    """Check all required directories exist."""
    missing = []
    for d in REQUIRED_DIRS:
        path = PROJECT_ROOT / d
        if not path.is_dir():
            missing.append(str(path))
    return [f"Missing required directory: {d}" for d in missing]


def check_required_configs() -> list:
    """Check required config files exist and are valid JSON/YAML."""
    errors = []
    for name in REQUIRED_CONFIGS:
        path = PROJECT_ROOT / name
        if not path.is_file():
            errors.append(f"Missing config file: {path}")
            continue
        if name.endswith(".json"):
            try:
                json.loads(path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                errors.append(f"Config file {name} is invalid: {e}")
    return errors


def check_loop_state() -> list:
    """Check `.loop-state.json` exists and parses.

    It used to also fail when `last_execution` was older than 24 hours
    (`STALE_THRESHOLD_SECONDS`). That rule is gone, and the reason is worth
    keeping: with scheduling disabled, the only thing that refreshes this file
    is a human running `theteam run`. So the rule measured how often the
    operator invoked a command — not whether the project was healthy — and
    reported both with the same words.

    Measured before removal: a project untouched for a day produced
    `FINDING: Loop state is stale`, and the only way to clear it was to run the
    tool. That is a finding about the tool wearing a finding about the project's
    clothes, which is what §3.3 names: a result that reads like a measurement of
    something other than what it measured.

    Existence and parseability stay. Both are real — a missing or corrupt state
    file means `theteam run` cannot record what it did, and running the tool
    once genuinely fixes that.
    """
    errors = []
    if not LOOP_STATE.is_file():
        errors.append(f"Loop state file not found: {LOOP_STATE}")
        return errors

    try:
        state = json.loads(LOOP_STATE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        errors.append(f"Loop state file is invalid: {e}")
        return errors

    if not isinstance(state, dict):
        errors.append(
            f"Loop state is not a mapping: got {type(state).__name__}")
    return errors


def main():
    errors = []
    errors.extend(check_project_root())
    errors.extend(check_required_dirs())
    errors.extend(check_required_configs())
    errors.extend(check_loop_state())

    if errors:
        for err in errors:
            print(f"FINDING: {err}")
        # 3, not 1. Exit 1 is what an uncaught exception produces, and the
        # executor must be able to tell a check that found a problem from a
        # check that crashed — a finding is the monitor working, a crash is the
        # monitor broken. It maps 3 to "ran, found something, did not break",
        # so a healthy project with one stale file no longer trips the breaker.
        # Exiting 1 here meant five genuine detections opened it permanently.
        print(f"{len(errors)} finding(s); the check itself completed.")
        sys.exit(FINDINGS_EXIT_CODE)

    print(f"Health check passed: {PROJECT_ROOT}")
    print(f"  Dirs checked: {len(REQUIRED_DIRS)}")
    print(f"  Configs checked: {len(REQUIRED_CONFIGS)}")
    print(f"  Loop state: OK")
    sys.exit(0)


if __name__ == "__main__":
    main()