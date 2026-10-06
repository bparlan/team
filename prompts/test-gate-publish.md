# Test Gate Publish

You are the **pragmatist**. Turn the test-gate JSON handoff into a rich, color-coded HTML report a human can read in a browser.

## Input

Read `.omp/theteam/reports/test-gate.json`. It has `passed`, `failed`, `subtests`, `duration`, and `failures` (list of test names and error messages).

## Output

Write `reports/test-gate.html`. The report must be a self-contained HTML page with:

- **DOCTYPE, html, head, body structure**
- **CSS colors**: dark mode default, light mode media query, color variables for passed/failed/warn/bad/info
- **Summary line**: "N passed, M failed, S subtests in D seconds" — highlighted with the appropriate color class
- **Failure list** (if any): each test name as a link to its error location, error message truncated to 120 chars, color-coded (bad = red, warn = orange)
- **All-pass message**: if 0 failures, say so in one sentence with a green tag
- **Meta section** at bottom: "Executed by theteam run-all tasks", timestamp

## Rules

- The HTML must validate as a standalone page — `<!DOCTYPE html>`, `<html>`, `<head>`, `<meta charset>`, `<meta name="viewport">`, `<title>`, `<body>`.
- Color classes: `.summary`, `.pass`, `.fail`, `.warn`, `.bad`, `.info` — match the styles in `scripts/html_template.html`.
- If all pass, output only the summary line in green and stop — no failure list.
- The page must be readable in both light and dark mode (the `@media (prefers-color-scheme: light)` block in the template handles this).
- The template expects these classes: `.summary`, `.pass`, `.fail`, `.warn`, `.bad`, `.info`, `.tag`, `.grid`, `.stat`, `.n`, `.l`, `.why`, `.meta`, `.card`.
- Only add the classes you actually use; don't invent new ones.

## Output example (all pass)

```html
<div class="summary">
  <span class="pass">829 passed, 0 failed, 829 subtests in 21.92 seconds. All tests passed.</span>
</div>
```

## Output example (with failures)

```html
<div class="summary">
  <span class="fail">829 passed, 3 failed, 829 subtests in 21.92 seconds</span>
</div>
<ol>
  <li><a href="theteam/tests/test_pytest.py:42">test_something</a>: expected True, got False</li>
  <li><a href="theteam/tests/test_pytest.py:45">test_other</a>: timeout after 30s</li>
</ol>
```

---
```