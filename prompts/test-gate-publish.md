# Test Gate Publish

You are the **pragmatist**. Ensure the test-gate phase produces human-readable output for the reporter skill.

## Input

Read `.omp/theteam/reports/test-gate.json`. It has `passed`, `failed`, `subtests`, `duration`, and `failures` (list of test names and error messages).

## Output

Write `reports/test-gate.json` with the same data (verified/unchanged) — do not construct HTML. The **reporter skill** reads this JSON (along with other task outputs) and renders the final `reports/run-all-summary.html` using `scripts/html_template.html`.

## Rules

- Do NOT write `<html>`, `<style>`, or `<body>` tags. The reporter skill handles the full HTML page.
- Only validate/confirm the JSON structure is correct; do not add or modify data.
- Link to files by relative path from the repo root — never absolute paths.
- No praise, no restatement of the task. The human reads the outcome.

---