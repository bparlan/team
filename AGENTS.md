# AGENTS.md — team project

Project-specific rules for the `team` repository. These supplement the global
`~/.omp/agent/AGENTS.md`. Closest wins on conflict.

## Context Management

**The problem:** Long conversations accumulate stale context. The agent starts
answering from memory instead of current files. This causes drift — standalone
modules created but never integrated, checkboxes marked done without code,
planning documents instead of fixes.

**The solution:** Single-focus turns with mandatory re-grounding.

### Before Every Phase

1. Re-read `archive/tasks/INDEX.yaml` — the forward-work index, and the entry point for anything not yet built
2. Re-read `AGENTS.md` — these rules
3. Run `find theteam/core/ -name "*.py" | sort` — see what actually exists
4. Check integration: `grep -l "import <module>" theteam/core/*.py` for each new module

### During Every Phase

- One task at a time. Complete it. Verify it. Move to the next.
- After each `write` or `edit`, re-read the file you changed to confirm it's correct.
- After each code change, run the affected tests.
- Do not create `.md` files. The plans are the only planning artifacts, and they are YAML in `archive/tasks/`.

### Before Yielding

1. Re-read the files you modified
2. Run the test suite
3. Update `archive/tasks/INDEX.yaml` status ONLY for plans where code exists AND is integrated AND tests pass
4. Summarize in 3 lines max

## Implementation Discipline

**No planning documents.**
- No `PHASE*.md`, `*_PLAN.md`, `*_STATUS.md`, `*_STRATEGY.md`, `*_SUMMARY.md`
- No `IMPLEMENTATION_*.md`, `*_REPORT.md`, `*_ANALYSIS.md`
- `archive/tasks/INDEX.yaml` is the index of forward work; `archive/STABILITY_ROADMAP.md` is the finished stability milestone and is history, not the contract.
- The only output of an implementation turn is: code changes + test results + 3-line summary.

**No orphaned files.**
- A new module that nothing imports is waste, not progress.
- After creating a file, verify it's imported by at least one existing module.
- If no file imports it, either delete it or wire it in.
- **Never duplicate a class inline when a standalone module exists.** If `theteam/core/circuit_breaker.py` exists, import it. Do not write `class CircuitBreaker` inside `unified_loop.py`.

## Forward work (stacked plans)

Plans are YAML in `archive/tasks/`, one file per milestone, indexed by `INDEX.yaml`.
Start at the index; do not read the plans in isolation — each states its own status
and what it waits on. They are executed in a fresh context, so an index is the only
thing a new session is guaranteed to find.

| Plan | Status | Waits on |
|---|---|---|
| `human-report-surface.yaml` | not-started | — |
| `project-convention-infra.yaml` | awaiting-input | an example project |
| `system-awareness-injection.yaml` | not-started | — (only p3 needs a project) |
| `diagram-citation-truth.yaml` | not-started | — |

`awaiting-input` is defined in the index: it cannot begin without a user decision.
It is not a failure, and it is unrelated to the run statuses the executor uses.

**No skipped tests.**
- Run existing tests after every code change.
- Do not say "tests require API updates" — fix the API or fix the tests.
- A failing test is a blocker, not a note.
- Before yielding, show actual test output.

**Roadmap checkboxes are truth.**
- Mark a task `[X]` only when: code exists AND is integrated AND tests pass.
- A `[X]` on a task that isn't done is worse than a `[ ]`.
- Never mark all checkboxes done to appear complete.

**Scope discipline.**
- Do not fix unrelated bugs during a phase.
- Do not refactor outside the roadmap scope.
- If a task seems ambiguous, ask. Do not invent a reasonable interpretation.

## Tool Usage

**ponytail** — Run after every phase to detect orphaned files, code duplication,
and unnecessary abstractions. If ponytail finds issues, fix them before the next phase.

**theteam** — Use for independent review at phase boundaries, not for implementation.

**todo** — Use for phase tracking. Init at phase start, mark done after each sub-task,
never leave in_progress when yielding.

## Anti-Drift Rules

1. **No planning documents.** The roadmap is the plan. Implementation turns write code.
2. **No orphaned files.** Every new module must be imported and used.
3. **No inline duplication.** If a standalone module exists, import it. Don't rewrite it.
4. **No skipped tests.** Run them, show output, fix failures.
5. **No false checkboxes.** Only mark done when code + integration + tests all pass.
6. **No scope creep.** Fix only what the roadmap says, nothing else.
7. **No status reports.** A 3-line summary is the maximum output format.
8. **Re-ground before every phase.** Re-read roadmap, re-read files, check integration.