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
| `subskill-project-structure-maintenance-SKILL.md` | An orphaned theteam subskill (it names `theteam` as parent skill), kept here when `theteam/subskills/` was removed on 2026-09-29. See the note below. |
| `subskill-project-structure-maintenance-INTEGRATION.md` | As above. |
| `subskill-project-structure-maintenance-IMPLEMENTATION.md` | As above. |
| `subskill-project-structure-maintenance-TEAM_MEMBER_PROPOSAL.md` | As above. |

### The project-structure-maintenance subskill

This was theteam's own subskill, not another project's content: `SKILL.md` and
`INTEGRATION.md` both name `theteam` as the parent skill. What made it a defect
is narrower and worth stating plainly. Three of its four files hardcode a
foreign project name — "Ledras Lament" appears at `IMPLEMENTATION.md:4`,
`INTEGRATION.md:11` and `TEAM_MEMBER_PROPOSAL.md:22`. A subskill of this package
must be project-agnostic; that name is a live example of the failure mode.

The files are archived **unmodified**. Rewriting them here would hide what they
said. The project-agnostic rewrite is recorded as an open task in
`ARCHITECTURE.md` Part 7, so the next reader sees both the defect and the fix.

The idea the subskill describes — a ledger of known project structure, kept
current, with a background loop watching for new files — has **no working
implementation**. `theteam/core/folder_monitor.py` was the only code, and it
was removed with the subskill on 2026-09-29. It was not a working
implementation to preserve:

- Its only importer was one of the 41 unused re-exports in `theteam/__init__.py`.
- It required `system-awareness-ledger.json` to exist and reported
  `"ledger_exists": false` otherwise — and **nothing in the product writes that
  file**. Every project would have been told its structure was broken.
- A pre-M0 review in `theteam/reports/` had already rejected the engine:
  "Every metric is contaminated. The analysis must be fixed at the source."
  It was never fixed; the module was left with a dead `__main__`.

So the design survives here, and the implementation does not. Rebuilding the
ledger against Layer 2 (the repository, which already owns the schedule and the
task ledger) is new work, not a defect fix.

## Related history

- [`../../STABILITY_ROADMAP.md`](../../STABILITY_ROADMAP.md) — the pre-M6 roadmap, superseded by
  `ARCHITECTURE.md` Part 6.
- [`../../../diagrams/archive/`](../../../diagrams/archive/) — twelve diagram JSONs evaluated
  component-by-component against the source tree in M5; ten were stale or invented.
