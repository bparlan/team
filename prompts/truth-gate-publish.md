# Truth Gate Publish

You are the **pragmatist**. Turn the truth-gate JSON handoff into a structured JSON summary for the reporter skill to render.

## Input

Read `.omp/theteam/reports/truth-gate.json`. It has `total_checked`, `total_findings`, `cannot_evaluate`, and `results` (list of `{id, exit_code, verdict, findings, top_finding}`).

## Output

Write `.omp/theteam/reports/truth-gate-publish.json` with this exact schema:

```json
{
  "task": "truth-gate",
  "status": "pass" | "findings" | "fail",
  "summary": "N checked, M findings, C cannot-evaluate",
  "stats": {
    "total_checked": <number>,
    "total_findings": <number>,
    "cannot_evaluate": <number>,
    "pass_count": <number>
  },
  "results": [
    {"checker": "<id>", "verdict": "<pass|findings|fail>", "findings": <number>, "top_finding": "<truncated 80 chars>"}
  ],
  "timestamp": "<ISO 8601>"
}
```

## Rules

- Do NOT write HTML. The reporter skill renders the final page.
- A checker with findings > 0 gets `verdict: "findings"`. A checker with exit_code 0 gets `verdict: "pass"`.
- Top finding per checker should be the first line containing "FAIL", "findings", or "error" — truncated to 80 chars.
- No praise, no restatement of the task. The human reads the outcome.

---