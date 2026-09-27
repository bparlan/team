#!/usr/bin/env python3
"""
Health check runner for theteam task loop.

Verifies project file integrity, config validity, required directories,
and that .loop-state.json is not stale.
"""

import os
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DIRS = ["tasks", "scripts", "bin", "theteam"]
REQUIRED_CONFIGS = ["theteam.config", "system-awareness-config.json"]
LOOP_STATE = PROJECT_ROOT / ".loop-state.json"
STALE_THRESHOLD_SECONDS = 86400  # 24 hours


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
    """Check .loop-state.json exists, is valid, and not stale."""
    errors = []
    if not LOOP_STATE.is_file():
        errors.append(f"Loop state file not found: {LOOP_STATE}")
        return errors

    try:
        state = json.loads(LOOP_STATE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        errors.append(f"Loop state file is invalid: {e}")
        return errors

    last_exec = state.get("last_execution")
    if last_exec:
        try:
            last_time = datetime.fromisoformat(last_exec)
            age = (datetime.now(timezone.utc) - last_time).total_seconds()
            if age > STALE_THRESHOLD_SECONDS:
                errors.append(
                    f"Loop state is stale: last execution {age:.0f}s ago "
                    f"(threshold: {STALE_THRESHOLD_SECONDS}s)"
                )
        except (ValueError, TypeError) as e:
            errors.append(f"Loop state has invalid last_execution timestamp: {e}")

    return errors


def main():
    errors = []
    errors.extend(check_project_root())
    errors.extend(check_required_dirs())
    errors.extend(check_required_configs())
    errors.extend(check_loop_state())

    if errors:
        for err in errors:
            print(f"FAIL: {err}")
        sys.exit(1)

    print(f"Health check passed: {PROJECT_ROOT}")
    print(f"  Dirs checked: {len(REQUIRED_DIRS)}")
    print(f"  Configs checked: {len(REQUIRED_CONFIGS)}")
    print(f"  Loop state: OK")
    sys.exit(0)


if __name__ == "__main__":
    main()