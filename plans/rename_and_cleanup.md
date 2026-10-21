# Final Renaming & Cleaning Plan

**Goal**: Eliminate the legacy *task* surface, unify terminology around *routine*, remove the `theteam/ui` terminal renderer, and update all tests and CI accordingly. The plan is split into phases with explicit dependencies, target files, and expected outcomes.

---

## 0 Baseline Verification
- **Run** entire test suite to capture current failures.
- **Audit** command line surface: ensure all current subcommands (`bootstrap`, `status`, `discuss`, `serve`, `loop`, `routine`, `history`, `task`, `comment`, `watch`, `manager`) are parsed without NameError.
- **Identify** dangling parser definitions: `run` is referenced before being declared.
- **Generate** a list of all `task` or `tasks` references across code and tests.

## 1 Remove `theteam/ui`
- **Delete** the entire `theteam/ui` package (including `terminal.py` and component renders).
- **Delete** associated tests: `test_terminal.py`, `test_monitor.py`, `test_design_tokens.py`, `test_activity_stream.py`, `test_disclosure.py`.
- **Delete** any imports of `theteam.ui` in production modules.
- **Update** shebangs and module docstrings to remove UI mentions.
- **Outcome**: Zero UI code left, 1,418 lines removed, 218 tests dropped.

## 2 Rename *task* → *routine*
- **Folder & File Refactor**: rename `tasks` directory to `routines`. Update `routines/repository.py` constants: `TASKS_DIRNAME` → `ROUTINES_DIRNAME`; `SCHEDULE_FILENAME` → `ROUTINE_SCHEDULE_FILENAME`.
- **CLI Parser**:
  - Replace all `task` subparsers with `routine` subparsers.
  - Delete `cmd_task` implementation; keep a thin delegating alias for backward compatibility: `def cmd_task(...): return cmd_routines(...)`.
  - Ensure `run` parser is created: `run = sub.add_parser("run", …)` before its `add_argument` calls.
- **State Manager**: rename `TaskState` to `RoutineState`; update all references.
- **Tests**: rename `test_task_repository.py`, `test_task_executor_isolation.py`, etc. Update command names in test fixtures (`theteam tasks` → `theteam routine`).
- **Documentation**: Update `ARCHITECTURE.md`, `AGENTS.md`, README, and test data references.
- **Outcome**: Clear terminology conflict resolution, tests updated.

## 3 CLI Surface Consolidation
- **Remove** the `task` command completely; only `routine` remains.
- **Ensure** `run` command exists and is functional: define `run = sub.add_parser("run", …)` before adding options `--dry-run`, `--json`. Utilize `cmd_run` as handler.
- **Fix** `watch` parser to use the new `routine` option names properly.
- **Re‑run** `pytest theteam/tests/test_cli_surface.py` to confirm all expected subcommands are present.
- **Outcome**: command parity with the new surface.

## 4 Test Suite Overhaul
- **Delete** all legacy task‑related tests that no longer apply.
- **Add** new unit tests that ensure `routine_payload`, `routine` subcommand, and `run` command work.
- **Adjust** CI configuration: Update GitHub Actions tests matrix to run on Python 3.12 and ensure YAML linting on renamed files.
- **Verify** that `pytest -q` now reports full pass.

## 5 CI & Documentation
- **Update** `.github/workflows/test.yml` to reference the updated command names and remove unused steps.
- **Add** a lint‑check step to verify there are no remaining `task` string literals.
- **Publish** the final plan under `~/devcode/team/plans/rename_and_cleanup.md` and push commit.

---

## Acceptance Criteria
1. **All tests pass** (`pytest -q` returns 0).
2. **CLI Surface**: `theteam tasks` and `theteam task` subcommands are removed; `theteam routine` replaces them.
3. **UI package** completely gone.
4. **No lingering `task` references** in source or tests.
5. **Run command** is defined and functional without NameError.

---

# Implementation Grid
| Step | File(s) | Action | Notes |
|---|---|---|---|
| 0 | *all* | Verify baseline | Run tests, grep for `run` refs |
| 1 | `theteam/ui/**` | Delete | Use `git rm -r theteam/ui` |
| 2 | `theteam/routines/repository.py`, `tasks`, `cli.py`, `state_manager.py` | Rename constants, classes, parser subparsers | Update imports; keep alias for backward support |
| 3 | `theteam/cli.py` | Define `run` parser, replace `task` parser | Add `run = sub.add_parser("run")` |
| 4 | `theteam/tests/**` | Update command names, delete legacy tests | Use `pytest` filtering |
| 5 | `.github/workflows/**` | Update test matrix, lint step | Validate after commit |

---

*All edits will be performed via `edit` tool*