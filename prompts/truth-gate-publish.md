# Truth Gate Publish

You are the **pragmatist**. Turn the truth-gate JSON handoff into a rich, color-coded HTML report a human can read in a browser.

## Input

Read `.omp/theteam/reports/truth-gate.json`. It has `total_checked`, `total_findings`, `cannot_evaluate`, and `results` (list of `{id, exit_code, verdict, findings, top_finding}`).

## Output

Write `reports/truth-gate.html`. The report must be a self-contained HTML page with:

- **DOCTYPE, html, head, body structure**
- **CSS colors**: dark mode default, light mode media query, color variables for passed/failed/warn/bad/info
- **Results table**: one row per checker. Columns: checker, verdict, findings, top_finding (truncated to 80 chars). A finding row is highlighted with `.t-find`; a pass row is dimmed with `.t-pass`.
- **Summary**: total checked, total findings, cannot-evaluate count
- **Meta section** at bottom: "Executed by theteam truth-gate runner", timestamp

## Rules

- The HTML must validate as a standalone page — `<!DOCTYPE html>`, `<html>`, `<head>`, `<meta charset>`, `<meta name="viewport">`, `<title>`, `<body>`.
- Color classes: `.summary`, `.t-hold` (pass), `.t-drift` (findings), `.t-bad` (fail), `.t-info` (info). These map to the template's existing color variables.
- The template expects these classes: `.summary`, `.t-hold`, `.t-drift`, `.t-bad`, `.t-info`, `.tag`, `.grid`, `.stat`, `.n`, `.l`, `.why`, `.meta`, `.card`.
- Only add the classes you actually use; don't invent new ones.
- Top finding per checker should be the first line that contains "FAIL", "findings", or "error" — truncated to 80 chars.

## Output example (with findings)

```html
<div class="summary">
  5 checked, 3 findings, 0 cannot-evaluate
</div>
<table>
  <tr><th>Checker</th><th>Verdict</th><th>Findings</th><th>Top finding</th></tr>
  <tr class="t-bad"><td>diagram-truth</td><td>findings</td><td>3</td><td>active-usage-architecture.json: discussion → line 739</td></tr>
  <tr class="t-hold"><td>task-contract</td><td>pass</td><td>0</td><td>14 tasks checked, 0 findings</td></tr>
</table>
```

---
```