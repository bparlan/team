# Prompt 6 – Roster and project metadata

## Baseline (verified)
- `theteam/__init__.py:458‑463` hardcodes:
  ```
  project = {
      'name': 'team',
      'root': '.',
      'description': 'Orchestrates independent reviewer subagents...'
  }
  ```
- All projects bootstrap to the same `project.name` and description,
  but the roster differs only by focus flags.

## Decision
- Keep the 3‑person core (`architect`, `pragmatist`, `skeptic`).
- Replace the hardcoded `project.name` and `description` with values
  read from the target project's metadata:
  * `pyproject.toml` → `project.name`, `project.description`
  * `Cargo.toml` → `name` and a sensible description
  * If neither exists, fall back to the current defaults.

## Acceptance
1. Bootstrapping a Rust CLI and a Python web project produces two
   configs with different `project.name` and description.
2. Rosters differ accordingly.
3. Tests fail against the pre‑change code.
4. All tests pass after the change.

## Skills
- `/theteam` – to analyze the target project metadata.
- `/ponytail` – to modify the hardcoded block.

## Commit
- One commit, e.g.
  `feat: make project metadata dynamic in bootstrap`.