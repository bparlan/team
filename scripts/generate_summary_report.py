#!/usr/bin/env python3
"""Generate a summary HTML report for the run-all.json output.
"""
import json
from pathlib import Path
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
HTML_TEMPLATE = ROOT / "scripts" / "html_template.html"
RUN_ALL_JSON = ROOT / ".omp" / "theteam" / "reports" / "run-all.json"  # Corrected path

def generate_summary_report():
    if not RUN_ALL_JSON.exists():
        return "Error: run-all.json not found at: " + str(RUN_ALL_JSON)

    data = json.loads(RUN_ALL_JSON.read_text(encoding="utf-8"))

    total_tasks = data.get("total", 0)
    passed_tasks = data.get("passed", 0)
    failed_tasks = data.get("failed", 0)
    task_results = data.get("results", [])

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Generate task details
    task_details_html = []
    for task in task_results:
        task_id = task.get("id", "unknown")
        ok = task.get("ok", False)
        detail = task.get("detail", "No detail provided.")
        status_class = "ok" if ok else "bad"
        status_text = "Passed" if ok else "Failed"

        task_details_html.append(f"""
      <div class="card {status_class}">
        <h3>{task_id}</h3>
        <p><span class="tag t-{status_class}">{status_text}</span></p>
        <details>
          <summary>Details</summary>
          <p class="why"><b>Reason:</b> {detail}</p>
        </details>
      </div>
""")

    content = f"""
  <h1>Run All Tasks Summary</h1>
  <p class="sub">Overview of the latest full task cycle</p>

  <div class="grid">
    <div class="stat"><span class="n n-ok">{passed_tasks}</span><span class="l">Passed Tasks</span></div>
    <div class="stat"><span class="n n-bad">{failed_tasks}</span><span class="l">Failed Tasks</span></div>
    <div class="stat"><span class="n">{total_tasks}</span><span class="l">Total Tasks</span></div>
  </div>

  <h2>Task Breakdown</h2>
  <div class="grid">
    {''.join(task_details_html)}
  </div>

  <h2>Critical Issues Identified in Previous Cycle</h2>
  <div class="card bad">
    <h3>HTML Report Generation Failure</h3>
    <p>All HTML reports generated in the `reports/` directory are currently broken, containing JSON or partial JSON output instead of rich HTML. This prevents human users from easily reading and understanding the reports.</p>
    <details>
      <summary>Root Cause & Impact</summary>
      <p class="why"><b>Root Cause:</b> The prompts for the `publish` phases are instructing LLM agents to output summary text or JSON directly, instead of generating the full HTML structure with the intended CSS classes and formatting from `scripts/html_template.html`.</p>
      <p class="why"><b>Impact:</b> Human users cannot easily read and understand the generated reports, negating the purpose of rich HTML reporting.</p>
    </details>
  </div>

  <div class="card bad">
    <h3>`root-organization` Task Failure</h3>
    <p>The `root-organization` task's `decide` phase failed because the `classify` output was aggregate metadata instead of per-entry ask classifications.</p>
    <details>
      <summary>Root Cause & Impact</summary>
      <p class="why"><b>Root Cause:</b> The `classify` output (from `reports/.handoff/root-organization-classify.md`) was aggregate metadata instead of per-entry ask classifications as required by the `decide` phase's prompt for the `skeptic` agent.</p>
      <p class="why"><b>Impact:</b> The `root-organization` task cannot complete its decision-making process.</p>
    </details>
  </div>

  <div class="card bad">
    <h3>`native-feature-loop` Task Failure</h3>
    <p>The `native-feature-loop` task's `implement` phase failed to return results in the expected schema.</p>
    <details>
      <summary>Root Cause & Impact</summary>
      <p class="why"><b>Root Cause:</b> The `implement` phase of the `native-feature-loop` task failed to return results in the expected schema (`{{'result': {{'data': <output>}}}}` for success or `{{'result': {{'error': 'message'}}}}` for failure).</p>
      <p class="why"><b>Impact:</b> This task cannot progress.</p>
    </details>
  </div>

  <div class="meta">Report generated on: {current_time}</div>
"""

    with open(HTML_TEMPLATE) as f:
        template = f.read()

    # Replace the {title} and {content} placeholders in the template
    final_html = template.replace("{title}", "Run All Tasks Summary").replace("{content}", content)
    return final_html

if __name__ == "__main__":
    output_path = REPORTS_DIR / "run-all-summary.html"
    html_report = generate_summary_report()
    if html_report.startswith("Error"):
        print(html_report, file=sys.stderr)
        sys.exit(1)
    output_path.write_text(html_report, encoding="utf-8")
    print(f"Summary report generated at: {output_path}")