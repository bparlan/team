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
    return results


def render_html_report(task, phase_results, project_name):
    """Render a rich HTML report for a single task using html_template.html."""
    passed = sum(1 for r in phase_results if r["ok"])
    failed = len(phase_results) - passed
    total = len(phase_results)

    title = task.get("name", task.get("id", "unknown"))

    # Build stats grid
    stats_grid = f"""
  <div class="grid">
    <div class="stat"><span class="n n-ok">{passed}</span><span class="l">Passed</span></div>
    <div class="stat"><span class="n n-bad">{failed}</span><span class="l">Failed</span></div>
    <div class="stat"><span class="n">{total}</span><span class="l">Phases</span></div>
  </div>"""

    # Build phase breakdown
    phase_rows = []
    for i, r in enumerate(phase_results, 1):
        verdict = "PASS" if r["ok"] else "FAIL"
        phase_name = r["phase"].get("name", "?")
        phase_type = "LLM" if r["phase"].get("runner") == "llm" else "script"
        verdict_class = "t-ok" if r["ok"] else "t-bad"
        phase_rows.append(
            f"<tr><td>Phase {i}</td><td>{phase_type}</td><td>{phase_name}</td>"
            f"<td><span class=\"tag {verdict_class}\">{verdict}</span></td>"
            f"<td>{r.get('detail', r.get('reason', ''))[:120]}</td></tr>"
        )

    phase_table = ""
    if phase_rows:
        phase_table = f"""
  <h2>Phase breakdown</h2>
  <table>
    <thead><tr><th>#</th><th>Type</th><th>Phase</th><th>Verdict</th><th>Detail</th></tr></thead>
    <tbody>{''.join(phase_rows)}</tbody>
  </table>"""

    # Major decisions section (from phase results)
    decisions = []
    for i, r in enumerate(phase_results, 1):
        if r.get("decision"):
            decisions.append(f"<tr><td>D{i}</td><td>{r['decision']}</td><td>{r.get('rationale', '')[:80]}</td></tr>")

    decisions_section = ""
    if decisions:
        decisions_section = f"""
  <h2>Major Decisions</h2>
  <table>
    <thead><tr><th>#</th><th>Decision</th><th>Rationale</th></tr></thead>
    <tbody>{''.join(decisions)}</tbody>
  </table>"""

    content = f"""
  <h1>{title}</h1>
  <p class="sub">Executed by theteam run-all tasks</p>
{stats_grid}
{phase_table}
{decisions_section}
  <p class="meta">Project: {project_name}</p>"""

    with open(HTML_TEMPLATE) as f:
        template = f.read()
    return template.replace("{content}", content).replace("{title}", title)


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
    aggregate = {"total": len(tasks), "passed": len(tasks), "failed": 0,
                 "report_files": report_files}
    (REPORTS_DIR / "run-all.json").write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("")
    print(f"{len(tasks)}/{len(tasks)} tasks ok", file=sys.stderr)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()