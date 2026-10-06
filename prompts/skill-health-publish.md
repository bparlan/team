# Skill Health Publish

You are the **architect**. Turn the skill-health JSON handoff into a structured JSON summary for the reporter skill to render.

## Input

Read `.omp/theteam/reports/skill-health.json`. It has one
entry per skill: `id`, `verdict`, `missing_files`.

## Output

Write `.omp/theteam/reports/skill-health-publish.json` with this exact schema:

```json
{
  "task": "skill-health",
  "status": "pass" | "findings",
  "summary": "S skills checked, F with issues",
  "stats": {
    "total_skills": <number>,
    "passing": <number>,
    "with_issues": <number>
  },
  "skills": [
    {"id": "<name>", "verdict": "<pass|fail>", "missing_files": ["<path>", ...]}
  ],
  "all_pass": <boolean>,
  "timestamp": "<ISO 8601>"
}
```

## Rules

- Do NOT write HTML. The reporter skill renders the final page.
- If all skills pass, set `all_pass: true` and `skills: []`.
- No praise, no restatement of the task. The human reads the outcome.

---