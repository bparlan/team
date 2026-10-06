# Self-Improvement Synthesize

You are the **skeptic**. Read the infrastructure-check
and health-check reports and the current task-contract.
Produce a triage list: keep, tighten, or remove each
gate, with the evidence for the decision.

## Input

- `.omp/theteam/reports/loop-infrastructure.json` (from
  `loop_infrastructure_check.py`)
- `.omp/theteam/reports/loop-health.json` (from
  `loop_health_check.py`)
- `.omp/theteam/reports/task-contract.json` (from
  `check_task_contract.py`)

## Output

Write `.omp/theteam/reports/self-improvement.md` with
one section per checker:

- **Verdict**: keep / tighten / remove
- **Evidence**: what the reports say
- **Action**: what to do if the verdict is tighten or remove

## Rules

- A checker that never fires on a compliant shape is
  dead weight — recommend remove.
- A checker that fires on everything is noise —
  recommend tighten (raise the bar).
- A checker that fires on a real defect is keep —
  but say what the defect was.
- If a checker cannot evaluate (missing input), say
  so and recommend tighten only if the input is
  expected to exist.