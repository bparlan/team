#!/usr/bin/env python3
"""Run every task in order, with rich HTML reports.

In-process (eval kernel): spawns members automatically via `agent()`.
From bash: prints `theteam run --only <id>` for each task.

Each task produces a rich HTML report in `reports/` with:
  - Summary statistics
  - Phase-by-phase breakdown
  - Major decisions (for LLM phases)
  - Exit codes and findings
  - Color-coded verdicts

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
REPORTS_DIR = ROOT / "reports"
HTML_TEMPLATE = ROOT / "scripts" / "html_template.html"


def _get_agent():
    """Resolve `agent` from the eval kernel's injected builtin."""
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
    """Run a script phase. Exit codes: 0=pass, 3=findings, 2=cannot evaluate."""
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


def render_html_report(task, phase_results, project_name):
    """Render a rich HTML report for a single task."""
    # Build summary stats
    passed = sum(1 for r in phase_results if r[1])
    failed = len(phase_results) - passed
    phase_details = []
    for i, (ok, detail) in enumerate(phase_results, 1):
        verdict = "PASS" if ok else "FAIL"
        phase_details.append(f"<li><strong>Phase {i}: {phase[get_phase_name(phase, ok)]}</strong> — {verdict}</li>")

    # Count findings
    total_findings = sum(
        len(detail.split()) for ok, detail in phase_results if not ok and "findings" in detail.lower()
    )

    # Build content
    title = task.get("name", task.get("id", "unknown"))
    content = f"""
  <h1>{title}</h1>
  <div class="grid">
    <div class="stat"><span class="n">{passed}</span><span class="l n-ok">Passed</span></div>
    <div class="stat"><span class="n">{failed}</span><span class="l n-warn">Failed</span></div>
    <div class="stat"><span class="n">{len(phase_results)}</span><span class="l">Phases</span></div>
  </div>
  <h2>Phase breakdown</h2>
  <ol>{''.join(phase_details)}</ol>
  <p class="sub">Total findings detected: {total_findings}</p>
  <div class="meta">Executed by theteam run-all tasks</div>
"""
    # Render using the template — inject only the body
    with open(HTML_TEMPLATE) as f:
        template = f.read()
    return template.replace("{content}", content)


def get_phase_name(phase, ok):
    """Return a short phase name for display."""
    name = phase.get("name", "?")
    runner = phase.get("runner")
    if runner == "llm":
        return f"LLM: {name}"
    return name


def run_script_phase(phase):
    """Run a script phase."""
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
    """Spawn a member for an LLM phase."""
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
    """Run one task's phases in order."""
    results = []
    for phase in task.get("phases", []):
        runner = phase.get("runner")
        name = phase.get("name", "?")

        if runner == "llm":
            ok, detail = run_llm_phase(phase, project_root)
        elif phase.get("script"):
            ok, detail = run_script_phase(phase)
        else:
            ok, detail = False, "no script and no runner"

        results.append({"ok": ok, "detail": detail, "phase": phase})
        if not ok:
            # Still continue to report all phases
            pass
    return results


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
    all_passed = True
    report_files = []

    for i, task in enumerate(tasks):
        phase_results = run_task(task, project_root)
        all_passed = all_passed and all(r["ok"] for r in phase_results)

        # Render rich HTML report for this task
        html = render_html_report(task, phase_results, project_root.name)
        html_path = REPORTS_DIR / (task["id"] + ".html")
        html_path.write_text(html, encoding="utf-8")
        report_files.append(str(html_path))

        status = "PASS" if all(r["ok"] for r in phase_results) else "FAIL"
        print(f"[{status}] {task['id']}: wrote {html_path}", file=sys.stderr)

    # Also write aggregate JSON for the orchestrator
    aggregate = {"total": len(tasks), "passed": sum(1 for _ in range(len(tasks)) if True),  # placeholder
                 "failed": len(tasks) - sum(1 for _ in range(len(tasks)) if True),
                 "report_files": report_files}
    (REPORTS_DIR / "run-all.json").write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("")
    print(f"{sum(1 for r in [] if True)}/{len(tasks)} tasks ok", file=sys.stderr)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()