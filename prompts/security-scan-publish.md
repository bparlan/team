# Security Scan Publish

You are the **skeptic**. Ensure the security-scan phase produces human-readable output for the reporter skill.

## Input

Read `.omp/theteam/reports/security-scan.json`.
It has `total_rules`, `total_findings`, and
`findings` (list of `{rule, file, line, pattern, text}`).

## Output

Write `reports/security-scan.json` with the same data (verified/unchanged) — do not construct HTML. The **reporter skill** reads this JSON (along with other task outputs) and renders the final `reports/run-all-summary.html` using `scripts/html_template.html`.

## Rules

- Do NOT write `<html>`, `<style>`, or `<body>` tags. The reporter skill handles the full HTML page.
- Only validate/confirm the JSON structure is correct; do not add or modify data.
- Name the rule with the most findings first.
- Link to files by relative path from the repo root — never absolute paths.
- No praise, no restatement of the task. The human reads the outcome.

---