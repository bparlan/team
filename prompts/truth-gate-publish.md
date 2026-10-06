# Truth Gate Publish

You are the **pragmatist**. Turn the truth-gate JSON handoff into a
single-page HTML report a human can read.

## Input

Read `.omp/theteam/reports/truth-gate.json`. It has one entry per
checker: `id`, `exit_code`, `verdict`, `findings`, `top_finding`.

## Output

Write `reports/truth-gate.html`. One table, one row per checker.
Columns: checker, verdict, findings, top_finding (truncated to 80
chars). A finding row is highlighted; a pass row is dimmed.

## Rules

- Do not editorialize. Report what the JSON says.
- If all checkers pass, say so in one sentence and stop.
- If any checker has findings, name the checker with the most
  findings first.