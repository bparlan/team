# Skill Health Publish

You are the **architect**. Turn the skill-health JSON
handoff into a single-page HTML report a human can read.

## Input

Read `.omp/theteam/reports/skill-health.json`. It has one
entry per skill: `id`, `verdict`, `missing_files`.

## Output

Write `reports/skill-health.html`. One table, one row per
skill. Columns: skill, verdict, missing_files. A finding row
is highlighted; a pass row is dimmed.

## Rules

- Do not editorialize. Report what the JSON says.
- If all skills pass, say so in one sentence and stop.
- If any skill has missing references, name the skill
  and the missing file.