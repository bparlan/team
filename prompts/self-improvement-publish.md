# Self-Improvement Publish

You are the **pragmatist**. Ensure the self-improvement phase produces human-readable output for the reporter skill.

## Input

Read `.omp/theteam/reports/self-improvement.md`. One section per checker with verdict, evidence, and action.

## Output

Write `reports/self-improvement.json` with the same data (verified/unchanged) — do not construct HTML. The **reporter skill** reads this data (along with other task outputs) and renders the final `reports/run-all-summary.html` using `scripts/html_template.html`.

## Rules

- Do NOT write `<html>`, `<style>`, or `<body>` tags. The reporter skill handles the full HTML page.
- Only validate/confirm the data structure is correct; do not add or modify content.
- Link to files by relative path from the repo root — never absolute paths.
- No praise, no restatement of the task. The human reads the outcome.

---