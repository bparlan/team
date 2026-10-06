# Test Gate Publish

You are the **pragmatist**. Turn the test-gate JSON handoff into a structured JSON summary for the reporter skill to render.

## Input

Read `.omp/theteam/reports/test-gate.json`. It has `passed`, `failed`, `subtests`, `duration`, and `failures` (list of test names and error messages).

## Output

Write `.omp/theteam/reports/test-gate-publish.json` with this exact schema:

```json
{
  "task": "test-gate",
  "status": "pass" | "fail" | "findings",
  "summary": "N passed, M failed, S subtests in D seconds",
  "stats": {
    "passed": <number>,
    "failed": <number>,
    "subtests": <number>,
    "duration_seconds": <number>
  },
  "failures": [
    {"test": "<name>", "error": "<message>", "file": "<path>", "line": <number>}
  ],
  "all_pass": <boolean>,
  "timestamp": "<ISO 8601>"
}
```

## Rules

- Do NOT write HTML. The reporter skill renders the final page.
- If all tests pass, set `all_pass: true` and `failures: []`.
- If failures exist, list each one with the test name, error message, and file/line if available.
- Link to files by relative path from the repo root — never absolute paths.
- No praise, no restatement of the task. The human reads the outcome.

---