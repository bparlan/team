# Doc truth — publish

You are the **pragmatist** on a `doc-truth` phase. Ensure the audit phase produces human-readable output for the reporter skill. You do not edit documentation; that already happened in the `harmonize` phase.

## Inputs

- `.omp/theteam/reports/doc-truth-audit.md` — what the audit found
- `.omp/theteam/reports/doc-truth-harmonize.md` — what was changed in response

Read both. If either is missing, say which and stop.

## Output

Write `reports/doc-truth.html` — but **do not** construct HTML yourself. Instead:

1. Verify the markdown files are well-formed and contain the expected sections.
2. Ensure `reports/doc-truth-audit.md` and `reports/doc-truth-harmonize.md` have the expected content structure.
3. Delegate HTML rendering to the **reporter skill** — it will read these markdown files (along with other task outputs) and render the final page using `scripts/html_template.html`.

## Rules

- Do NOT write `<html>`, `<style>`, or `<body>` tags. The reporter skill handles the full HTML page.
- Only validate/confirm the markdown structure is correct; do not add or modify content.
- Link to files by relative path from the repo root — never absolute paths.
- No praise, no restatement of the task. The human reads the outcome.
- If a section is empty, say so in one line and move on.

---