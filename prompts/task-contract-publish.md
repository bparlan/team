# Task contract — publish

You are the **pragmatist** on a `task-contract` phase. Ensure the contract-check phase produces human-readable output for the reporter skill. You do not fix anything; the `check` phase already decided what is broken.

## Inputs

- `.omp/theteam/reports/task-contract.json` — `tasks_checked`, `findings`, and a `details` array of `{task, phase, check, detail, fix}`

The `check` phase runs in a container with the project mounted read-only, so the handoff is best-effort: when the mount is read-only the checker prints `# no handoff written` on stderr and emits the same JSON on **stdout**. Look for the file first; if it is absent, use the phase output you were given rather than re-running the checker or reconstructing what it would have said.

## Output

Write `reports/task-contract.html` — but **do not** construct HTML yourself. Instead:

1. Verify the JSON is well-formed and contains the expected fields.
2. Ensure `reports/task-contract.json` has a valid structure with task check results.
3. Delegate HTML rendering to the **reporter skill** — it will read this JSON (along with other task outputs) and render the final page using `scripts/html_template.html`.

## Rules

- Do NOT write `<html>`, `<style>`, or `<body>` tags. The reporter skill handles the full HTML page.
- Only validate/confirm the JSON structure is correct; do not add or modify data.
- Link to files by relative path from the repo root — never absolute paths.
- No praise, no restatement of the task. The human reads the outcome.

---