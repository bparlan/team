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

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS = PROJECT_ROOT / "theteam" / "tests"
REPORTS_DIR = PROJECT_ROOT / ".omp" / "theteam" / "reports"


def main() -> int:
    if not TESTS.is_dir():
        print(f"no test directory at {TESTS}", file=sys.stderr)
        return 2

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "test-gate.json"

    command = [sys.executable, "-m", "pytest", str(TESTS), "-v"]
    if os.environ.get("THETEAM_PYTEST_ARGS"):
        command.extend(os.environ["THETEAM_PYTEST_ARGS"].split())

    start_time = time.time()
    process = subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    output = ""
    if process.stdout:
        for line in process.stdout:
            print(line, end="")
            output += line

    exit_code = process.wait()
    duration = time.time() - start_time

    # Parse summary
    # Example: "1 failed, 828 passed in 22.26s"
    passed = 0
    failed = 0
    summary_match = re.search(r"==+ (.*) in [\d.]+s ==+", output)
    if not summary_match:
        # Try simpler match at the end
        summary_match = re.search(r"(\d+) failed, (\d+) passed", output)
        if summary_match:
            failed = int(summary_match.group(1))
            passed = int(summary_match.group(2))
    else:
        parts = summary_match.group(1).split(",")
        for part in parts:
            part = part.strip()
            if "passed" in part:
                passed = int(part.split()[0])
            elif "failed" in part:
                failed = int(part.split()[0])

    # Parse failures
    failures = []
    failure_blocks = re.split(r"_+ (.*) _+", output)
    # The regex above splits by "____ test_name ____"
    # failure_blocks[0] is everything before first failure
    # failure_blocks[1] is name, failure_blocks[2] is content, etc.
    if len(failure_blocks) > 1:
        for i in range(1, len(failure_blocks), 2):
            name = failure_blocks[i]
            content = failure_blocks[i+1]
            # Extract error message - usually first few lines after the header
            # until next section or end
            error_lines = []
            for line in content.strip().splitlines():
                if line.startswith("E "):
                    error_lines.append(line[2:])
                if line.startswith(">"):
                    continue
                if "AssertionError" in line:
                    error_lines.append(line)
            
            message = " ".join(error_lines) if error_lines else "Unknown error"
            failures.append({
                "name": name,
                "message": message
            })

    report = {
        "passed": passed,
        "failed": failed,
        "subtests": passed + failed, # Approximation
        "duration": round(duration, 2),
        "failures": failures
    }

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return exit_code



if __name__ == "__main__":
    sys.exit(main())
