# Changelog

The honest history of this project is the milestone order in
[`ARCHITECTURE.md`](../ARCHITECTURE.md) Part 6. This file records what each one changed and
what it falsified. The previous version of this file was a 435-line pre-M0 changelog ending
2026-09-20 describing a system that no longer exists: a `subskills/task-stack/` daemon, a curses
`ui/terminal_ui.py`, a `discussion_manager.py` that was renamed, and a "Phase 4 Optimization"
roadmap that was never planned. Those entries were removed rather than carried forward. The
pre-M0 reports they described are preserved in
`archive/docs-theteam/pre-m0-reports/`, where they are history rather than documentation.

## M7 — The documentation tells the truth

Every document audited against the code it names. Where a document and the code disagreed, the
code won and the document changed.

- `README.md` rewritten. It previously documented `src/`, `tests/`, `config/`, PostgreSQL,
  `npm install -g @oh-my-pi/archify`, `npm run test:archify`, five deleted
  `diagrams/*-candidate.json` files, and `python -m src.main`. None of those exist. It now
  carries the complete command surface, exit codes, environment variables, and the output
  honesty contract, plus the plan evaluation.
- **Code change:** `theteam watch` gained `--json` on its own subparser. It was the one command
  whose `--json` had to precede the subcommand, because it was declared only on the parent —
  `theteam watch status --json` was a usage error. `cmd_watch` gained the branch that prints
  the payload the frame draws. This is the one code change the milestone made, to satisfy a
  documented promise; everything else was documents and diagram JSON.
- `ARCHITECTURE.md` Part 2 completed: `loop` was implemented (`cli.py:158`) and documented
  nowhere. Exit codes, failure shapes, and the environment variables added as §2.1 and §2.2.
- `diagrams/active-usage-milestones.json`: added `m6` and the `m5 → m6` edge, a `Terminal`
  lane, and the "Seven milestones" subtitle. The diagram had stopped one milestone behind the
  plan.
- `diagrams/active-usage-architecture.json`: re-derived from the actual import graph. Its
  subtitle grounded itself in `theteam/subskills/task_stack`, deleted in M2, and its components
  listed `TaskStore` and `TaskManager`, which are not modules in the tree. Every component now
  cites the file it came from, verified against git.
- `theteam/CLI.md` rewritten against the parser. `theteam/README.md` reduced to a pointer.
  `theteam/ONBOARDING.md` rewritten; it named a deleted daemon, TUI, and `loop_controller.py`.
  `theteam/SKILL.md` corrected: the `.omp/theteam/tool-manifest.json` it told the agent to
  read does not exist, and the `bin/` scripts need `PYTHONPATH=theteam`.
- Seven pre-M0 reports archived to `archive/docs-theteam/pre-m0-reports/`.

## M6 — The terminal shows the truth

`theteam/ui/terminal.py` and `theteam watch status|tasks|history`. Deferred by the M5 review
until after M4, so that what the renderer displays is real. Stdlib only: `rich` is installed
transitively in one developer's environment and declared nowhere, so a module-scope import is
green locally and red in CI. The same measurement found that `pyproject.toml` declared no
dependencies while `theteam/__init__.py` imports `yaml` at module scope, and fixed it.

The invariant test: in a project with no audit chain and no run tasks, the frame shows `absent`
and `never run`, and never the literal `closed`, `intact`, or `0%`.

## M5 — The team comments

`advisory/` with `session_reader`, `selector`, and `commentary`; `theteam comment on|off|status`.
Conditional on three gates: the session reader's digest must change when a real session changes;
the selector must pick different members for a frontend and a database session; a tick must
produce at most two fragments. The one-shot discussion path, `run_discussion()` in
`theteam/__init__.py`, is byte-identical before and after — if it had changed, the controller
would have forked the discussion path.

## M4 — The loop is safe

`CircuitBreaker`, `ResourceLimiter`, and `AgentIsolation` wired into execution for the first
time; `AuditLogger` into the task lifecycle; the execution log bounded; `theteam history` added.
`AgentIsolation` had been written and had no caller, which was the standing risk in a system
that runs project scripts.

Falsified: a task failing five consecutive times trips a breaker; a phase exceeding 64 MB is
killed at exit 137 rather than left running.

## M3 — Create, edit, delete

The single-task write surface, validated at write time rather than at run time. `task create`
rejects an invalid definition before it reaches disk.

## M2 — Tasks are YAML

One task store, in your repo. The legacy loader and the `subskills/task_stack/` tree were
deleted, taking `task_stack_adapter.py` with them — the adapter existed only because two task
stores did.

## M1 — Reach it from a shell

`cli.py` as the single entry point, one state-directory resolver replacing hardcoded absolute
paths, and `theteam bootstrap`. `__main__.py` was deleted here, which is why
`python -m theteam` does not work.

## M0 — The team cannot lie

`MockAPI` removed, along with every code path that could return a plausible-looking value on a
failure path, and the planning documents that described a system that was never built. This is
the milestone every later one assumes: the product's core failure was not a crash, it was a
system that returned confident output with nothing behind it.
