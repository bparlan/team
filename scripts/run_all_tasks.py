#!/usr/bin/env python3
"""Run every task in order, with per-task context isolation.

In-process (eval kernel): spawns members automatically via `agent()`.
From bash: prints `theteam run --only <id>` for each task.

Each task runs in a fresh subagent context so the orchestrator never
blools — the parent only keeps per-task verdicts, not member notes.

Usage:
    python3 scripts/run_all_tasks.py [--project-root .]
"""
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "tasks"
REPORTS_DIR = ROOT / ".omp/theteam" / "reports"


def _get_agent():
    """Resolve `agent` from the eval kernel's injected builtin.

    The eval kernel injects `agent` as a builtin visible in cell
    scope, but not in imported module scope. Walk the frame stack
    to find it in a caller's globals.
    """
    frame = sys._getframe(1)
    while frame is not None:
        if "agent" in frame.f_globals and callable(frame.f_globals["agent"]):
            return frame.f_globals["agent"]
        frame = frame.f_back
    return None


def load_tasks():
    tasks = []
    for path in sorted(TASKS_DIR.glob("task-*.yaml")):
        task = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(task, dict):
            tasks.append(task)
    tasks.sort(key=lambda t: t.get("order", 99))
    return tasks


def run_script_phase(phase):
    """Run a script phase. Exit codes follow the executor taxonomy:

    0 = nothing found, 3 = findings (check WORKING), 2 = cannot evaluate
    (phase defective). Only 2 means the phase failed.
    """
    script = ROOT / phase["script"]
    if not script.exists():
        return False, "script not found: " + phase["script"]
    try:
        r = subprocess.run(
            ["python3", str(script)] + [str(a) for a in phase.get("args", [])],
            capture_output=True, text=True,
            timeout=phase.get("timeout_seconds", 300),
            cwd=str(ROOT),
        )
        if r.returncode == 2:
            return False, "cannot evaluate: " + (r.stdout + r.stderr).strip()[:200]
        return True, (r.stdout + r.stderr).strip()[:200]
    except subprocess.TimeoutExpired:
        return False, "timeout: " + phase["name"]
    except Exception as e:
        return False, "error: " + str(e)


def run_llm_phase(phase, project_root):
    """Spawn a member for an LLM phase. The member runs in its own
    isolated context — it never sees the orchestrator's state, and
    the orchestrator never keeps its notes. Only the written file
    survives.
    """
    agent_fn = _get_agent()
    if agent_fn is None:
        return False, "no agent available (run from eval kernel, not bash)"

    prompt_path = ROOT / phase["prompt_file"]
    if not isinstance(project_root, Path):
        project_root = Path(project_root)
    output_path = project_root / phase["output"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not prompt_path.exists():
        return False, "prompt not found: " + phase["prompt_file"]

    prompt = prompt_path.read_text(encoding="utf-8")
    agent_type = phase.get("agent_type", "task")

    try:
        result = agent_fn(prompt, agent=agent_type, handle=True)
        text = result.get("text", str(result)) if isinstance(result, dict) else str(result)
        output_path.write_text(text, encoding="utf-8")
        return True, "wrote " + phase["output"]
    except Exception as e:
        return False, "spawn failed: " + str(e)


def run_task(task, project_root):
    """Run one task's phases in order. Each LLM phase spawns a fresh
    subagent — the orchestrator keeps only the verdict, not the notes.
    """
    for phase in task.get("phases", []):
        runner = phase.get("runner")
        name = phase.get("name", "?")

        if runner == "llm":
            ok, detail = run_llm_phase(phase, project_root)
        elif phase.get("script"):
            ok, detail = run_script_phase(phase)
        else:
            ok, detail = False, "no script and no runner"

        if not ok:
            return task["id"], False, name + ": " + detail
    return task["id"], True, "ok"


def main():
    project_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    tasks = load_tasks()

    agent_fn = _get_agent()
    if agent_fn is None:
        for t in tasks:
            print("theteam run --only " + t["id"])
        print("")
        print(str(len(tasks)) + " tasks. Run them in order.", file=sys.stderr)
        return 0

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for task in tasks:
        # Each task is a fresh scope — member notes from the previous
        # task are not carried forward. Only the verdict is.
        tid, ok, detail = run_task(task, project_root)
        results.append({"id": tid, "ok": ok, "detail": detail})
        print("[" + ("PASS" if ok else "FAIL") + "] " + tid + ": " + detail,
              file=sys.stderr)

    passed = sum(1 for r in results if r["ok"])
    report = {"total": len(tasks), "passed": passed,
              "failed": len(tasks) - passed, "results": results}
    (REPORTS_DIR / "run-all.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("")
    print(str(passed) + "/" + str(len(tasks)) + " tasks ok", file=sys.stderr)
    sys.exit(0 if passed == len(tasks) else 1)


if __name__ == "__main__":
    main()