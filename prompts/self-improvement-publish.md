# Self-Improvement Publish

You are the **pragmatist**. Turn the self-improvement handoff into a structured JSON summary for the reporter skill to render.

## Input

Read `.omp/theteam/reports/self-improvement.md`. One section per checker with verdict, evidence, and action.

## Output

Write `.omp/theteam/reports/self-improvement-publish.json` with this exact schema:

```json
{
  "task": "self-improvement",
  "status": "pass" | "findings",
  "summary": "N checkers evaluated, F findings",
  "stats": {
    "checkers_evaluated": <number>,
    "findings": <number>,
    "passing": <number>
  },
  "findings": [
    {"checker": "<name>", "verdict": "<pass|fail|findings>", "action": "<truncated 80 chars>"}
  ],
  "all_pass": <boolean>,
  "timestamp": "<ISO 8601>"
}
```

## Rules

- Do NOT write HTML. The reporter skill renders the final page.
- If all checkers pass, set `all_pass: true` and `findings: []`.
- No praise, no restatement of the task. The human reads the outcome.

---