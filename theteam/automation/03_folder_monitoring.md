# Prompt 3 – Resolve folder-monitoring

## Baseline (verified)
- `tasks/system-awareness/folder-monitoring.yaml` is not in `TASK_ORDER`,
  not a `task-*.yaml`, and writes to `.mp/theteam/` (dead dir).
- It is scheduled every 30 min in `.omp/theteam/task-schedule.json`.

## Decision
**Retire** the task:
- Delete the entry from `task-schedule.json`.
- Archive the YAML file (e.g. move to `archive/tasks/`).
- No change to `TASK_ORDER`.

## Acceptance
1. `TaskRepository('.').orphaned_schedules()` → `[]`.
2. `theteam tasks` shows 4 tasks, no phantom.
3. `grep -rn "\.mp/theteam" tasks/` → nothing.
4. All tests pass.

## Skills
- `/theteam` – for the product‑level decision.
- `/ponytail` – delete the schedule entry, move the YAML.

## Commit
- One commit, e.g.
  `docs: retire folder‑monitoring task and clean schedule`.