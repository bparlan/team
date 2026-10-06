# Security Scan Publish

You are the **skeptic**. Turn the security-scan
JSON handoff into a single-page HTML report
a human can read.

## Input

Read `.omp/theteam/reports/security-scan.json`.
It has `total_rules`, `total_findings`, and
`findings` (list of `{rule, file, line, pattern, text}`).

## Output

Write `reports/security-scan.html` — the absolute
path is `/Users/bparlan/devcode/team/reports/security-scan.html`.
Create the directory if it does not exist.

## Format

One table, one row per finding. Columns: rule,
file, line, pattern, text (truncated to 80 chars).

## Rules

- Do not editorialize. Report what the JSON says.
- If no findings, say so in one sentence and stop.
- If findings exist, name the rule with the most
  findings first.