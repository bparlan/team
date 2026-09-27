# Prompt 4 – Reject dead state paths at load

## Baseline (verified)
- `_load_yaml()` in `theteam/tasks/repository.py` already validates
  the YAML structure.
- No check exists for paths that refer to the deleted `.mp/theteam/`.

## Target
Add a guard that raises `TaskDefinitionError` when any `outputs[].path`
or `phases[].script` resolves to a directory that `state_dir()` does **not**
return.

## Acceptance
1. A task with `outputs[].path: .mp/theteam/…` raises
   `TaskDefinitionError` naming the offending file and path.
2. The guard does **not** reject the four real tasks (their scripts are
   in `scripts/` or `theteam/`).
3. All tests pass.

## Skills
- `/ponytail` – modify the single line in `_load_yaml()`.

## Commit
- One commit, e.g.
  `fix(repository): add dead‑state path guard`.