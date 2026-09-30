# Changelog

The honest history of this project is the milestone order in
[`ARCHITECTURE.md`](../ARCHITECTURE.md) Part 6. This file records what each one changed and
what it falsified. The previous version of this file was a 435-line pre-M0 changelog ending
2026-09-20 describing a system that no longer exists: a `subskills/task-stack/` daemon, a curses
`ui/terminal_ui.py`, a `discussion_manager.py` that was renamed, and a "Phase 4 Optimization"
roadmap that was never planned. Those entries were removed rather than carried forward. The
pre-M0 reports they described are preserved in
`archive/docs-theteam/pre-m0-reports/`, where they are history rather than documentation.

## M9 Phase 1 — Wire the selector

`theteam/advisory/selector.py` was live, tested, deterministic code with **no production
caller**. `theteam discuss` spawned every `enabled` member for every topic. This phase
connects the two, and closes two defects found on the way. Later phases (manager,
context efficiency, `runner: llm`, diagrams) are not in this entry.

**1.1 — Members are told which tools they may use.** The code read
`.omp/theteam/tool-manifest.json` and defaulted to the literal string `"N/A"`. That file
does not exist, so *every* member prompt carried `## Tool Inventory` / `N/A`. A boundary
the constrained party cannot see is enforced by luck. `spawn_member_task`'s fourth
argument is now `permitted_skills`, read from the project's own `theteam.config` and
rendered under the same heading. An empty list renders as
`none declared by this project's theteam.config` rather than a blank section, because a
blank boundary is still an invisible one.
Falsified by: `test_m9_selection_wiring.py::TestToolInventoryIsTheRealBoundary`, and by
executing the pre-change `spawn_member_task` directly — its prompt contained `N/A` and
named none of the configured skills.

**1.2 — Selection decides who speaks.** `run_discussion` builds a minimal `SessionSlice`
from the topic and calls `select_members` unchanged. No fifth signal was added: the topic
arrives as `last_user_messages` (signal 2 in §4.5) and any source file it names arrives as
`touched_paths` (signal 1). Adding a topic-scoring heuristic is the dead end
`selector.py:201-207` records — a gate that cannot fail is not a gate. The intro spawn was
**also** re-deriving "every enabled member", so a capped discussion would have reported one
roster and paid for another; it now honours the same selection.
Measured, on this project's 5-member roster, via a recording provider injected into
`run_discussion`:

```
refactor scheduler.py            -> Selector chose 1 member(s): devops
should we ship or simplify scope -> Selector chose 1 member(s): pragmatist
the docker deploy pipeline ...   -> Selector chose 1 member(s): devops
hm                               -> Selector chose 1 member(s): skeptic
```

Five enabled members; one speaks. That is the observable M9 exists to change.

**1.3 — The cap is enforced and reported.** `select_members` already truncated to
`MEMBER_CAP = 4` and returned `truncated: True`, but a caller that reports the overflow
cannot recover the number: re-deriving it from `len(members)` after the slice is zero **by
construction**, so a "1 suppressed" line is a line that can never fire. The selector now
returns `suppressed` and the caller prints from it. Falsified by
`test_advisory.py::test_truncation_reports_how_many_were_suppressed`, and by running the
selector against a 9-member roster where 4 speak and the rest are counted.

**Two pre-existing defects found and fixed in the path being edited.** Neither was
introduced by M9; both are why `theteam discuss` had never been observed to work.

- `run_discussion` called `aggregate_project_context` and **it was imported nowhere in the
  package.** `git log -S` finds no commit that ever added the import. Every discussion that
  got past `_require_provider` would have died on a `NameError` two lines into the
  function. No test caught it because no test runs this path with a provider. Imported at
  point of use, as check 7 requires.
- `theteam/core/state_manager.py` calls `self._notify_listeners` 12 times; the method is
  defined on `UnifiedStateManager`, not on `DiscussionState` or its siblings, so
  `start_discussion` raises `AttributeError`. **Not fixed here** — it is a different module
  and outside Phase 1's scope. It is recorded in Part 8 below as a real defect, not
  worked around in the product code.

**Invariant 7 broken deliberately, with the reason, in the same change.** `run_discussion`
was byte-identical from M5 until now; §7.2 item 7 is updated in place to state what the
invariant was *for* and what now holds instead.

**Import budget.** A module-scope `from .advisory.selector import ...` pushed `import
theteam` to 91 modules and failed check 7. The selector is imported at point of use; the
entry point now loads **88** modules against a budget of 90.

`789 passed` (772 + 17 new), gate 7/7, `import theteam` succeeds.

## M8 — The docs tell the truth, and one of them is a lie in the code

A follow-up audit, run after the `--monitor` flag landed. The M7 report claimed `--monitor` was
undocumented in both `README.md` and `ARCHITECTURE.md`; it was already documented in both, in
detail. The real findings were elsewhere. Most were documents disagreeing with the code. The last
one was the reverse — and it was the only one that mattered, because it was a control promising
an effect it did not have.

- `--monitor` was missing from `theteam/CLI.md`'s command table. It is the only doc of the three
  that enumerates the surface, and it listed the flag nowhere. Now documented there, with a
  pointer to the full semantics.
- **Stale counts.** `README.md` said 744 tests and "6 checks"; `theteam/ONBOARDING.md` said 744
  tests. The measured numbers are **772** and **7** (gate check 7, the import-graph budget, was
  added in the M7 review and the docs were never updated for it).
- **`ARCHITECTURE.md:14` claimed "Nothing is implemented past M0."** Six milestones and a
  documentation milestone have shipped since. The line was a leftover from the draft, in a
  document whose first page is otherwise accurate.
- **Four wrong rows in the §5.2.1 reachability table**, each verified by grep before correction:
  `audit.py` was attributed to `tasks/audit_chain.py` (it lives in `core/`; `tasks/` has no such
  module), `audit_chain.py` was attributed to `tasks/executor.py` only (five importers),
  `team_member_manager.py` to `workflow/discussion_manager_refactored.py` (it is
  `workflow/discussion_interface.py` that imports it), and `unified_loop.py` to
  `theteam/__init__.py` (nothing there imports it; `cli.py` and `integrated_orchestrator.py` do).
  `task_contract.py` and `backup.py` were also wrong and were corrected in the same pass.
- **Part 8 listed `StateStore` as a component "verified absent from the entire tree."** It is
  `theteam/state.py:35`, and every path in the product resolves through it. Conversely it listed
  `SimpleTaskExecutor`, `SimpleTaskScheduler`, and `InMemoryTaskStore` as real components the
  diagrams missed; none is in the tree, and `git log -S` finds each only in the commit that
  deleted it. Corrected in place, with the correction stated.
- **`SKILL.md` claimed the selection prompt presents four options "defined in `selection_options`
  (see `theteam.config`)."** It does not: the key is optional per `REQUIRED_TOP_KEYS`, absent
  from both the shipped template and this project's config, and `theteam/__init__.py:692` carried
  a divergent three-option fallback. An agent following SKILL.md literally would show the user a
  prompt the code never produced.
- **That prompt lied, and it is deleted.** `run_discussion` offered "Abort Discussion — Stop the
  current discussion loop", printed the answer at `__init__.py:712`, and then ran the discussion
  to completion regardless, under the comment "For now, we'll proceed with a default path." A
  control that reports an effect it does not have is the `MockAPI` defect class §3.3 forbids, so
  this was a code defect the documentation pass uncovered, not a documentation defect.
  `run_discussion` no longer offers a choice: the `ask` call, the three-option fallback, and the
  `option_selection_required` gate that drove them are gone. `SKILL.md` step 3 is now a plain
  gate, and the discussion's step list was renumbered 1–10 after removing the one that described
  the prompt. `option_selection_required` is no longer required by the schema and is no longer
  emitted by bootstrap or the template, but the validator ignores unknown keys, so every config
  written before this change still validates — verified against this project's own config, which
  still carries the key. Falsified: `theteam discuss` outside OMP still raises
  `ProviderUnavailable` naming the OMP requirement, and `grep -rn "Abort Discussion" theteam/`
  returns nothing outside `CHANGELOG.md`.

`772 passed`, gate 7/7.

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
