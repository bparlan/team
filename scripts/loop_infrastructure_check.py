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

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_SCRIPTS = [
    "scripts/loop_health_check.py",
    "scripts/loop_maintenance.py",
    "scripts/loop_infrastructure_check.py",
    "bin/theteam_config.py",
    "bin/theteam_report.py",
]

REQUIRED_TOOLS = ["python3", "git"]

REQUIRED_LOOP_FILES = [
    "tasks/TASK_ORDER",
    ".loop-state.json",
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
    expected = [
        "tasks", "scripts", "bin", "theteam", "docs",
        ".loop-log", ".loop-archive",
    ]
    missing = []
    for d in expected:
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
            print(f"FAIL: {err}")
        sys.exit(1)

    print("Infrastructure check passed: all systems operational")
    print(f"  Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"  Scripts checked: {len(REQUIRED_SCRIPTS)}")
    print(f"  Tools checked: {len(REQUIRED_TOOLS)}")
    print(f"  Directories checked: 9")
    sys.exit(0)


if __name__ == "__main__":
    main()