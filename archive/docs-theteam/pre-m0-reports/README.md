# Pre-M0 reports

Documents written before M0, describing systems this project no longer has. They are kept for
engineering history and moved here in M7 so that no live document in `theteam/` or the repo
root names code that has been deleted.

**Nothing in this directory is documentation.** Do not follow it, do not link to it as if it
described current behavior, and do not treat a claim in one of these files as a requirement. If
a current-behavior question is answered here, the answer is stale — check the root
[`README.md`](../../../README.md) and [`ARCHITECTURE.md`](../../../ARCHITECTURE.md), and verify
against the code.

## What is here, and why it moved

| File | Why it was archived |
|---|---|
| `ANALYSIS.md` | Pre-M0 technical analysis of a system that has since been cut down to `cli.py`, `tasks/`, and `core/`. |
| `DEPLOYMENT.md` | Documented a `subskills/task-stack/` daemon, `ui/terminal_ui.py`, and a `.env` template full of settings (`TASK_STACK_MONITORING_INTERVAL`, `TUI_REFRESH_INTERVAL`, `REFLEX_FRONTEND_PORT`) that nothing reads. |
| `DISCUSSION_WORKFLOW_DESIGN.md` | Design for the pre-M0 discussion flow. The design survived in spirit; the file described a `discussion_manager.py` that was renamed to `discussion_manager_refactored.py`. |
| `FINAL_REPORT.md` | A "comprehensive enhancement" report claiming a modular task stack, a running daemon, and a verified task loop. None of it survived M0–M2. |
| `IMPLEMENTATION_GUIDE.md` | Implementation instructions for the pre-M0 tree. |
| `Phase4_LOOP_MANAGER_VALIDATION.md` | Validation of a "Phase 4 optimization" that was never planned. |
| `VALIDATION_DOCUMENTATION.md` | Validation of the pre-M0 surface. |
| `.team_todo_phase1.md` | A checkbox planning list for a phase that was never executed. It named `theteam.core.loop_manager.LoopManager` and a second `UnifiedTask` class in `unified_loop.py`; neither exists. The only surviving item is real history: it recorded that the "562-line LoopController" never existed and that `save_configuration()` never existed either. |
| `.team-discussion-context.md` | A dated (2026-09-23) stability analysis. It catalogued five byte-duplicate and stub variants of `scripts/sa_runner.py` that have since been deleted, and seven top-level report `.md` files that no longer exist. Its one durable finding: the `test_theteam.py` bootstrap test loads `theteam/__init__.py` via `spec_from_file_location` with a bare name, so its relative imports fail — a test-harness bug, not a production bug. |

## Related history

- [`../../STABILITY_ROADMAP.md`](../../STABILITY_ROADMAP.md) — the pre-M6 roadmap, superseded by
  `ARCHITECTURE.md` Part 6.
- [`../../../diagrams/archive/`](../../../diagrams/archive/) — twelve diagram JSONs evaluated
  component-by-component against the source tree in M5; ten were stale or invented.
