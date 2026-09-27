#!/usr/bin/env python3
"""
Maintenance runner for theteam task loop.

Cleans __pycache__ directories, .pyc files, rotates old loop logs,
and removes temp files older than 24 hours.
"""

import os
import sys
import time
import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_LOG_AGE_SECONDS = 7 * 86400  # 7 days
MAX_ARCHIVE_AGE_SECONDS = 30 * 86400  # 30 days

LOG_DIRS = [".loop-log", ".loop-archive"]
TEMP_GLOBS = ["*.pyc", "*.pyo", "__pycache__"]


def clean_pycache() -> list:
    """Remove all __pycache__ directories and .pyc/.pyo files."""
    removed = []
    for pycache in PROJECT_ROOT.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache, ignore_errors=True)
            removed.append(str(pycache))
    for pyc in PROJECT_ROOT.rglob("*.pyc"):
        if pyc.is_file():
            pyc.unlink(missing_ok=True)
            removed.append(str(pyc))
    for pyo in PROJECT_ROOT.rglob("*.pyo"):
        if pyo.is_file():
            pyo.unlink(missing_ok=True)
            removed.append(str(pyo))
    return removed


def rotate_log_files(log_dir_name: str, max_age: int) -> list:
    """Remove log entries older than max_age seconds."""
    removed = []
    log_dir = PROJECT_ROOT / log_dir_name
    if not log_dir.is_dir():
        return removed

    now = time.time()
    for entry in log_dir.iterdir():
        if entry.is_file():
            age = now - entry.stat().st_mtime
            if age > max_age:
                entry.unlink()
                removed.append(str(entry))
    return removed


def clean_empty_dirs() -> list:
    """Remove empty directories in .loop-log and .loop-archive."""
    removed = []
    for log_dir_name in LOG_DIRS:
        log_dir = PROJECT_ROOT / log_dir_name
        if not log_dir.is_dir():
            continue
        for entry in log_dir.iterdir():
            if entry.is_dir():
                try:
                    entry.rmdir()
                    removed.append(str(entry))
                except OSError:
                    pass
    return removed


def main():
    removed_pycache = clean_pycache()
    rotated_logs = rotate_log_files(".loop-log", MAX_LOG_AGE_SECONDS)
    rotated_archives = rotate_log_files(".loop-archive", MAX_ARCHIVE_AGE_SECONDS)
    empty_dirs = clean_empty_dirs()

    print("Routine maintenance complete: cache cleaned, logs rotated")
    print(f"  Removed __pycache__ / .pyc files: {len(removed_pycache)}")
    print(f"  Rotated old loop-log entries: {len(rotated_logs)}")
    print(f"  Rotated old loop-archive entries: {len(rotated_archives)}")
    print(f"  Cleaned empty directories: {len(empty_dirs)}")

    if removed_pycache:
        for path in removed_pycache[:5]:
            print(f"    Removed: {path}")
        if len(removed_pycache) > 5:
            print(f"    ... and {len(removed_pycache) - 5} more")

    sys.exit(0)


if __name__ == "__main__":
    main()