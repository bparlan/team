# Prompt 2 – Fix orphaned_schedules()

## Baseline (verified)
- `theteam/tasks/repository.py:245‑250` filters on `self.get(task_id) is None`.
- `self.get()` falls back to the legacy registry, which still contains
  `folder-monitoring`.  Therefore `orphaned_schedules()` incorrectly
  returns `[]`.

## Target
Change the filter to consider a task orphaned only if it does **not**
exist in the *real* sources:
- `_yaml` (YAML files in `tasks/`)
- `_order` (TASK_ORDER list)

## Acceptance
1. `TaskRepository('.').orphaned_schedules()` → `['folder-monitoring']`.
2. The change is covered by a new test that asserts the above.
3. `theteam tasks` (no `--json`) still lists 4 tasks and prints the orphan
   in a human‑readable "legacy_tasks" section.
4. All 619 tests pass.

## Skills
- `/ponytail` – single‑line filter change.

## Commit
- One commit with a message such as
  `fix(repository): correct orphaned_schedules logic`.