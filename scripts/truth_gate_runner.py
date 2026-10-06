#!/usr/bin/env python3
"""
Run every truth checker and report the result.

Each checker is a script phase: it exits 0 on pass, non-zero on
findings or cannot-evaluate. This runner collects the exit codes
and finding counts so a single `theteam run` tells you whether
the truth infrastructure itself is healthy.

Checkers run in dependency order: task-contract first (it validates
the task files that schedule the other checkers), then the
document/diagram/prompt checkers, then invariants last (it is the
broadest sweep and its output is the hardest to parse).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECKERS = [
    {
        "id": "task-contract",
        "script": "scripts/check_task_contract.py",
        "args": [str(ROOT)],
        "parse": "json",
    },
    {
        "id": "prompt-truth",
        "script": "scripts/check_prompt_truth.py",
        "args": [],
        "parse": "stdout",
    },
    {
        "id": "doc-truth",
        "script": "scripts/check_doc_truth.py",
        "args": [],
        "parse": "stdout",
    },
    {
        "id": "diagram-truth",
        "script": "scripts/check_diagram_truth.py",
        "args": [],
        "parse": "stdout",
    },
    {
        "id": "invariants",
        "script": "scripts/check_invariants.sh",
        "args": [],
        "parse": "stdout",
    },
]


def run_checker(checker):
    script = ROOT / checker["script"]
    if not script.exists():
        return 2, f"checker not found: {checker['script']}"

    cmd = ["python3"] if checker["script"].endswith(".py") else ["bash"]
    cmd += [str(script)] + checker["args"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(ROOT),
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 2, f"checker timed out: {checker['id']}"
    except Exception as e:
        return 2, f"checker error: {checker['id']}: {e}"


def parse_findings(checker, exit_code, output):
    """Extract finding count from a checker's output.

    Each checker reports differently. This function
    handles the known formats and falls back to the
    exit code when it cannot.
    """
    if checker["id"] == "task-contract" and exit_code == 0:
        report_path = ROOT / ".omp/theteam/reports/task-contract.json"
        if report_path.exists():
            try:
                data = json.loads(report_path.read_text())
                return data.get("findings", 0)
            except (json.JSONDecodeError, OSError):
                pass
        return 0

    # diagram-truth: "check_diagram_truth: N finding(s)"
    m = re.search(r"check_diagram_truth:\s*(\d+)\s+finding", output)
    if m:
        return int(m.group(1))

    # prompt-truth: "N claims in M prompts, N findings"
    m = re.search(r"(\d+)\s+claims in \d+ prompts[,;]\s*(\d+)\s+findings", output)
    if m:
        return int(m.group(2))

    # invariants: report-only, never a finding
    if checker["id"] == "invariants":
        return 0

    # Generic fallback: "N findings"
    m = re.search(r"(\d+)\s+findings?", output)
    if m:
        return int(m.group(1))

    # verdict= pattern
    m = re.search(r"verdict=(\S+)", output)
    if m and m.group(1) != "ok":
        return 1

    if exit_code != 0:
        return 1

    return 0


def main():
    results = []
    total_findings = 0
    cannot_evaluate = 0

    for checker in CHECKERS:
        exit_code, output = run_checker(checker)
        findings = parse_findings(checker, exit_code, output)

        if exit_code == 2:
            verdict = "cannot-evaluate"
            cannot_evaluate += 1
        elif findings > 0 or exit_code == 3:
            verdict = "findings"
            total_findings += findings
        else:
            verdict = "pass"

        top_finding = None
        for line in output.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("Wall time"):
                if "FAIL" in line or "findings" in line.lower() or "error" in line.lower():
                    top_finding = line[:200]
                    break

        results.append({
            "id": checker["id"],
            "exit_code": exit_code,
            "verdict": verdict,
            "findings": findings,
            "top_finding": top_finding,
        })

    report = {
        "total_checked": len(CHECKERS),
        "total_findings": total_findings,
        "cannot_evaluate": cannot_evaluate,
        "results": results,
    }

    out_dir = ROOT / ".omp/theteam/reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "truth-gate.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"truth-gate: {len(CHECKERS)} checked, {total_findings} findings, "
          f"{cannot_evaluate} cannot-evaluate")
    for r in results:
        print(f"  {r['id']}: verdict={r['verdict']}, exit_code={r['exit_code']}, "
              f"findings={r['findings']}")
        if r["top_finding"]:
            print(f"    {r['top_finding']}")

    if total_findings > 0:
        sys.exit(3)
    if cannot_evaluate > 0:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()