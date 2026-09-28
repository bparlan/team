# System Architecture — Source of Truth

**Status:** the single source of truth for `theteam`. Replaces `ACTIVE_USAGE_ROADMAP.md` (deleted) and `STABILITY_ROADMAP.md` (archived to `archive/`).
**Scope:** what the product does, what the user can rely on, the command surface, the code layers, and the milestone order it is built in.
**Diagrams:** the rendered view of this document. Both are regenerated from the structure below and are authoritative for shape:

| Diagram | Renders | File |
|---|---|---|
| System architecture | Part 5 §5.2 package layout, §5.1 layers, the three command entry points | `diagrams/active-usage-architecture.html` |
| Delivery order | Part 6, all six milestones and their gates | `diagrams/active-usage-milestones.html` |

Sources of truth, in conflict order: this document defines intent; the two HTML diagrams define the rendered shape; the YAML task files define task content. If this document and a diagram disagree, this document wins. If this document and the running code disagree, **the code is the defect** — that is the next milestone's work, not a reason to edit the intent.

**Start here:** §2 lists every command. §3 is the trust surface. §6 is the milestone order. Nothing is implemented past M0.

---

# Part 1 — The Product

## 1.1 What it does

`theteam` puts a small panel of expert reviewers in your working session and keeps your scheduled project tasks running.

Two capabilities:

**Commentary.** A roster of specialists watches your session and speaks when there is something to say. They read your real session, not a guess at it. They are individually addressable. They do not speak when they have nothing to add.

**Tasks.** Tasks live in plain YAML files you can read and edit. A single `theteam run` executes whatever is due. Every execution is bounded, isolated, audited, and reversible.

## 1.2 What you can rely on

These are the product's promises. Each is a test.

| Promise | You can check it by |
|---|---|
| The team reads your real session | `theteam status` shows the session file path, its event count, and the digest the team last saw |
| The team is silent rather than filler | Every tick reports `spoke: false` with a reason, or up to 2 opinions. Never a third. |
| Opinions are never invented | Running `theteam discuss` outside OMP **fails with an error naming the command to run inside OMP.** It never returns an opinion. |
| Tasks cannot run away | Every phase has a mandatory memory bound. A phase that exceeds it is killed and reported, not left running. |
| A failing task stops burning cycles | A task failing repeatedly trips a circuit breaker. `theteam tasks` shows the trip. |
| Nothing changes unrecorded | Every task create, edit, delete, and execution is in a hash-chained audit log. `theteam status` verifies the chain. |
| Your tasks are yours | Tasks are YAML in your repo. `theteam run` holds no state you cannot delete. |

## 1.3 The four requirements, mapped

| You said | It is |
|---|---|
| Bootstrap into any project | `theteam bootstrap` — M1 |
| In-context team commentary | `theteam comment` — M5 |
| Create, edit, delete tasks | `theteam tasks` — M3 |
| Loop and manage tasks | `theteam run` + `theteam tasks` — M2, M4 |

---

# Part 2 — The Command Surface

Commands are named for what the user wants, not for the internal mechanism. `theteam run` runs due tasks. It is not called `loop tick`, because "loop" is an implementation detail and "tick" is a unit of time the user does not control.

```
theteam bootstrap [project_root]      generate a team for this project
theteam comment on|off|status         continuous in-context commentary
theteam discuss <topic>               one-shot team discussion, this turn only
theteam tasks                         list every task and its state
theteam task create|edit|delete|show  single-task operations
theteam run                           execute everything currently due
theteam history                       per-task success rate, last run, last failure
theteam status                        trust surface — see §3
theteam serve                         metrics endpoint
```

| Command | Arguments | Output you can predict |
|---|---|---|
| `bootstrap` | `[project_root]`, `--interactive`, `--json` | Path to written config. Non-interactive by default. |
| `comment on` | `--max-members N` (default 3, cap 4) | Starts commentary for the session. |
| `comment off` | — | Writes the stop sentinel. Takes effect next tick. |
| `comment status` | — | Whether commentary is on, last digest, last opinion, tick count. |
| `discuss` | `<topic>`, `--json` | The synthesized verdict. Or an error, if outside OMP. |
| `tasks` | `--json` | One row per task: id, order, next run, last result, breaker state. |
| `task create` | `<path.yaml>` or flags, `--json` | The task id. Rejects invalid tasks at write time. |
| `task edit` | `<id> --patch <file>` | The new task state. Refuses orphaning a schedule. |
| `task delete` | `<id> --yes` | Lists everything it will clean up, then does. |
| `run` | `--json`, `--only <id>` | `{ran: N, skipped: M, failures: K}` with per-task results. Idempotent. |
| `history` | `--task <id>`, `--json` | Success rate, last run, last failure, consecutive failures. |
| `status` | `--json` | Roster, session binding, audit chain integrity, breaker states. |
| `serve` | `--port` | Prometheus endpoint. Nothing else starts a server. |

Every command takes an explicit `project_root`. Every command returns a real exit code. Every command supports `--json`.

---

# Part 3 — Trust and Failure Modes

The previous failure in this product was not a crash. It was a system that returned confident output with nothing behind it. Design against that class of failure, not against exceptions.

## 3.1 `theteam status` is the trust surface

```
$ theteam status
roster          5 members active
session         ~/.omp/agent/sessions/-myproject/2026-09-27T09-32-48.jsonl
session events  289 message events, 1.85 MB, last read 14s ago
commentary      on, last spoke 3 turns ago, digest a4f2...
tasks           4 registered, 1 due, 0 breaker trips
audit chain     intact, 142 entries, last verified 14s ago
```

If the session file is missing, `session` reads `not found` and commentary reports `{spoke: false, reason: "no_session"}`. It does not fall back to a guess.

## 3.2 Failure modes are named, never swallowed

| Condition | Behaviour |
|---|---|
| No OMP session file | `{spoke: false, reason: "no_session"}` + the path it looked for |
| Session file unreadable or malformed | Raise. Name the file and the line. |
| Session file empty or subagent file | `{spoke: false, reason: "no_session"}`. Never comment on a subagent transcript. |
| Advisory engine errors inside OMP | Propagate. Do not catch and continue. |
| Digest unchanged | `{spoke: false, reason: "no_change"}` |
| Stop signal | `{spoke: false, reason: "stopped"}` |
| Member count exceeds cap | Truncate to the cap, record `truncated: true`. |
| Proposal cannot be written | Raise. Never write a proposal without a proposal file. |
| Task script missing | Rejected at `task create`. Also reported by `run` if it disappeared after creation. |
| Phase exceeds memory bound | Killed, reported with the exit code. Task marked failed. |
| Circuit breaker tripped | Task skipped, reason `breaker_open`, visible in `tasks` and `history`. |
| Audit chain broken | `status` reports it. Writes continue but every entry is marked `chain_broken`. |

## 3.3 The one rule

**No code path returns a synthesized opinion, a default value standing in for a real one, or a placeholder that reads like a result.** This is the `MockAPI` defect, generalised into a constraint the whole system obeys.

The compliance test is: grep the tree for functions that return a plausible-looking value on a failure path. A default is fine when it is a default the user asked for. It is not fine when it looks like a measurement.

---

# Part 4 — The Advisory Layer

The layer with the least existing code and the most design risk.

## 4.1 One discussion path

`advisory/engine.py` holds the existing one-shot discussion: task tool, `{id, role, verdict, note}` contract, validator, synthesizer. **It is not modified.**

`advisory/commentary.py` is a controller whose tick body is a call to `engine`. It adds a relevance filter, a cadence, a budget, and a stop signal. It does not reimplement selection, prompting, validation, or synthesis. Two discussion systems cannot drift because there is one.

## 4.2 When the team speaks, and when it does not

| Trigger | Result |
|---|---|
| Digest changed, or a new user message arrived | Select members, call them, render at most 2 fragments |
| Digest unchanged, no new user message | `{spoke: false, reason: "no_change"}` |
| Latest user message is `stop` / `halt` / `quiet` / `enough` / `that's all` | `{spoke: false, reason: "stopped"}` |
| `.omp/theteam/commentary.stop` exists | `{spoke: false, reason: "stopped"}` |
| Session file missing or is a subagent transcript | `{spoke: false, reason: "no_session"}` |
| More than 4 members selected | Truncate to 4, record `truncated: true` |
| More than 2 opinions produced | Render 2, record `suppressed: N` |

The stop word is matched as the entire leading clause only. "stop the current phase" does not silence the team.

Silence is always reported with a reason. That is what makes silence distinguishable from filler.

## 4.3 Session reading is a file read

The blocking unknown in the previous plan — "does OMP expose a session-history API?" — is resolved by inspection:

```
~/.omp/agent/sessions/<slug>/<timestamp>_<uuid>.jsonl
~/.omp/agent/sessions/<slug>/<timestamp>_<uuid>/__advisor.jsonl   (subagents)
```

The top-level `.jsonl` is the main session. Lines are JSON objects discriminated by `type`. Events of interest:

| `type` | carries |
|---|---|
| `message` | `message.role` ∈ `user` / `assistant` / `toolResult` / `developer`, and `message.content[]` parts of `text` / `toolCall` / `thinking` |
| `custom` | structured payload — 169 events in a live session |
| `custom_message` | rendered note — 31 events |

Measured on a live session: 289 message events, 1.85 MB, roles `{assistant: 204, toolResult: 317, user: 11, developer: 1}`, parts `{thinking: 129, text: 432, toolCall: 318}`.

Three consequences:

1. Reading it is a file read. No new dependency, no API to version.
2. A session directory holds one main file plus a `__advisor.jsonl` per subagent. **The reader must select the top-level `.jsonl` and refuse any file inside a subdirectory.** Otherwise the team comments on a subagent's transcript and presents it as the user's session.
3. **1.85 MB is the entire cost risk.** Reading the file is cheap. Reading its contents into a prompt is not. The reader returns structure, not payload.

## 4.4 `SessionReader` returns four small things

```python
@dataclass
class SessionSlice:
    last_user_messages: list[str]   # last 3 user texts, truncated 400 chars each
    recent_activity: list[str]      # last 8 tool NAMES, never tool results
    touched_paths: list[str]        # file paths from recent toolCall args
    digest: str                     # sha256 over the above
```

Tool **results** are never returned. A `read` result can be an entire file. Tool **names** and the paths they were given are enough to know what kind of work is happening, and cost under 200 tokens for 8 events.

K defaults to 4 messages, hard-capped at 8.

## 4.5 Active member selection, no LLM

The orchestrator picks which roster members speak, capped at **4**, using signals already in hand:

| Signal | Source |
|---|---|
| File extensions in `touched_paths` | `.tsx`/`.css` → Designer; `.py`/`.rs` → DevOps; `.sql` → Architect |
| The latest user message | case-insensitive token match against each member's declared focus |
| The active task's `type` | `analysis` → Architect, Skeptic; `ops` → DevOps |
| Current phase | executing → DevOps; planning → Skeptic |

Selection is deterministic. Zero LLM calls, zero cost, reproducible — the same session state selects the same members, so a test can assert it.

If no signal fires, the **skeptic** speaks alone. A lone skeptic is the correct default; the alternative is a unanimous chorus that is one voice repeated.

## 4.6 Per-turn context budget

Each selected member receives, and nothing more:

| Input | Source | Cap |
|---|---|---|
| Last 3 user messages | `SessionReader` | 400 chars each |
| Recent tool names | `SessionReader` | 8 names |
| What the user asked the team | the team-call prompt | user-supplied |
| Project awareness digest | cache | 400 tokens |
| File-structure digest | cache | 400 tokens |

The two digests are cached and recomputed only when the project root's mtime changes, or on `theteam comment status --refresh`. They are the single largest token saving in the layer: recomputing a project digest per turn is what would make this feature unaffordable.

**Ceiling: 4 member calls per turn, ~2k tokens each, ~8k tokens per turn.** In a quiet session: zero calls.

## 4.7 Task proposals, never task creation

When 2 or more members independently raise the same untracked concern, `CommentaryController` writes a **proposal** to `.omp/theteam/proposals/<digest>.yaml` — member ids, verbatim notes, a proposed task stub.

It never registers, schedules, or executes anything. Proposals are a review surface. Auto-creating tasks from model output is the same defect class as `MockAPI`: confident output from no verified source.

---

# Part 5 — Code Structure

## 5.1 Layer contract

Seven layers. Dependencies point downward only. No layer reaches past the one below.

| # | Layer | Owns | Must not know about |
|---|---|---|---|
| 0 | **Entry** | argument parsing, exit codes, JSON output | any domain object |
| 1 | **Control** | tick cadence, pause, idempotency, orchestration order | file formats, subprocesses |
| 2 | **Task** | task schema, validation, persistence, schedule | loops, safety state |
| 3 | **Execution** | running one phase, collecting its result | the schedule, the CLI |
| 4 | **Safety** | bounds, trips, audit, health | task semantics |
| 5 | **Telemetry** | event publication, metrics | who is listening |
| 6 | **Advisory** | roster, selection, discussion, proposals | execution internals |

**The invariant that matters: Layer 3 may not call `subprocess` without a Layer 4 guard in the same call frame.** `AgentIsolation` was built for this and never received a caller. Do not weaken it.

## 5.2 Target package layout

```
theteam/
  cli.py                     # Layer 0. the only entry point.
  state.py                   # the single state directory resolver.
  __init__.py                # skill entry point: bootstrap, discussion, context analysis.
  core/
    unified_loop.py          # Layer 1. already correct — keep as-is.
    circuit_breaker.py       # Layer 4.
    resource_limiter.py      # Layer 4.
    agent_isolation.py       # Layer 4. proven live.
    audit.py                 # Layer 4.
    health_monitor.py        # Layer 4.
    event_bus.py             # Layer 5.
    metrics.py               # Layer 5.
    # … plus the other Layer 4/5 modules (backup, state_manager, event_log, …).
  tasks/                     # NEW. absorbs subskills/task_stack/.
    repository.py            # YAML canonical. ONE store. Schema, schedule, and
                             # due/next-run all live here; no separate schema.py or
                             # scheduler.py. Gains the M4 safety wrapper on executor.
    executor.py              # runs one phase, collects its result. Gains the
                             # mandatory Layer 4 safety wrapper in M4.
  workflow/                  # discussion and member management.
    discussion_manager_refactored.py
    discussion_interface.py
    team_member_manager.py
    context_aggregator.py
  ui/                        # panel widgets. The terminal UI entry point the
                             # orchestrator used to call was deleted in M4;
                             # no TUI is wired into the product.
    components/              # panel widgets: roster, activity, metrics, …
    web_dashboard/           # optional reflex dashboard (extra). Reads through
                             # state.py; absent unless the reflex extra is
                             # installed, and it is not in the tree today.
  security/                  # path validation, audit logging, secrets handling.
```

`subskills/task_stack/` is not a package anyone may extend. Its contents move; the directory goes.

## 5.3 Removals

| Path | Reason |
|---|---|
| `subskills/task_stack/registry.py` | replaced by `tasks/repository.py` |
| `subskills/task_stack/core.py` | third `TaskManager`, globs `*.json` against a directory of `.md`. Matches zero files. |
| `subskills/task_stack/daemon.py` | superseded by in-session `run` |
| `scripts/run_task_loop.py` | broken three ways, no callers |
| `scripts/task_archive.py` | orphaned, duplicates parsing |
| `MockAPI` in `__init__.py:3-25` | fabricates consensus |
| `__init__.py.corrupted`, `event_bus.py.backup`, `test_*.backup` | dead weight |
| `theteam/__main__.py` as entry point | it is a metrics server, not an orchestrator |

## 5.4 One task format

```
tasks/
  <id>.yaml                  # canonical. human-editable. version-controlled.
```

`tasks/*.md` and the JSON registry are deleted. The registry survives only as a derived cache under the state directory, never hand-edited, rebuildable from YAML with no information loss.

```yaml
id: system-awareness
name: System Architecture Awareness
order: 3
type: analysis
priority: high
schedule:
  cron: "0 * * * *"
  enabled: true
  retry_on_failure: true
phases:
  - name: inventory
    script: tasks/system-awareness/analyze_system_awareness.py
    args: ["--json"]
    timeout_seconds: 120
    memory_limit_mb: 64
outputs:
  - path: .omp/theteam/reports/system-awareness.md
```

`order` replaces `tasks/TASK_ORDER` as a file. `memory_limit_mb` is mandatory per phase — a phase without a bound is rejected at write time, not discovered mid-run.

Validation runs on write. `TaskRepository` rejects a phase without
`memory_limit_mb` at the write that creates it (`tasks/repository.py:72-80`), and
`theteam run` reports a task whose `script` is missing rather than silently
skipping it as a success. The line that said `executor.py:22-24` discovers this
mid-loop named imports, not validation; that pointer was stale.

## 5.5 State

One directory: `.omp/theteam/` under the project root. `.mp/theteam/` is migrated and deleted.

All resolution goes through one function in `theteam/state.py`, which takes an explicit `project_root`. There is no default and no module-level constant — the current hardcoded paths are absolute literals and `parents[N]` expressions that resolve correctly in this repo and point at the `theteam` checkout everywhere else.

```
.omp/theteam/
  state.json                   # StateStore.state_file
  task-registry.json           # derived, rebuildable from tasks/*.yaml
  task-schedule.json           # schedule and per-task last_run
  task-execution.log           # bounded by EXECUTION_LOG_MAX_LINES
  audit/audit.jsonl            # hash-chained
  event_log.json               # EventBus log
  folder-monitor.log
  commentary.stop
  reports/
  proposals/
```

Every name above is one `theteam/state.py` resolves. The list is not exhaustive:
`StateStore` also resolves `tasks_dir`, `events_dir`, `members`, `discussions`,
`task_stack`, `task_daemon_status`, `task_daemon_pid` and `tool_manifest`, and
those are omitted here because this section is about the core layout, not a
property index. Three earlier entries were wrong and are corrected here:
`loop/state.json` (there is no `loop/` directory),
`tasks/registry.cache.json` (the registry is `task-registry.json` at the state
root, and §5.4 made `tasks/*.yaml` the canonical store), and `audit/chain.jsonl`
(`AuditLogger` hardcodes `audit.jsonl`; `audit_chain.audit_file()` is the one
resolver and the component's name wins). The execution log is bounded by
`EXECUTION_LOG_MAX_LINES` in `tasks/executor.py`, not by `ResourceLimiter`, which
is a counter registry with no file retention path.

Measured baseline for the removal work: **7** occurrences of `/Users/bparlan`, **5** of `parents[`, **7** of `.mp/theteam`, **3** of `MockAPI` in `theteam/**/*.py`. The roadmap claimed four paths. It is seven.

---

# Part 6 — Delivery Order

Six milestones, ordered by user-visible outcome, not by subsystem. Each is a command the user can run. Each has a falsification test.

The ordering rule: **at every intermediate commit, all four existing tasks still execute.** The switch from the current store to the YAML repository is the one place that can silently break that, and it gets an explicit guard.

## M0 — The team cannot lie

Pure deletion. No dependencies on any other milestone, and it removes the most dangerous defect in the codebase: a system whose entire value is honest opinion, silently returning fake opinion.

### Delete

| Target | Verified state |
|---|---|
| `MockAPI` — `theteam/__init__.py:4-18` | Fabricates `"Insight from {id}: System appears stable after fixes."` and `{"next_action": "proceed_with_plan"}` |
| `default_api` fallback — `theteam/__init__.py:20-25` | Binds `MockAPI` whenever OMP does not inject a provider |
| Orphan comment — `theteam/__init__.py:868` | Trailing duplicate of the comment at line 3 |
| `scripts/run_task_loop.py` | Broken three ways, **zero importers** (grep across `theteam/` returns nothing) |
| `scripts/task_archive.py` | Orphaned, duplicates YAML parsing, **zero importers** |
| `theteam/core/event_bus.py.backup` | Duplicate of a live module |
| `theteam/core/loop_manager.py.bak` | 25,558 bytes, superseded |
| `theteam/core/rate_limiting.py.bak` | 16,814 bytes, superseded |
| `theteam/tests/test_state_validator.py.backup` | Not collected by pytest |
| `test_final_validation.py.backup` | Not collected by pytest |
| `test_unified_loop.py.backup` | Not collected by pytest |
| `theteam/ui/web_dashboard/.web.backup` | Empty directory |

### Guard placement — corrected

The first implementation put the guard at **module scope**, which killed all 28 test files at import time. That was wrong. The requirement is "a caller with no provider raises rather than fabricates" — satisfied by guarding at the point of use.

Correct form, verified live:

```python
def _require_provider():
    if "default_api" not in globals():
        raise ProviderUnavailable(
            "theteam requires an OMP session. Run this inside OMP, "
            "or import it from an OMP-hosted agent."
        )

def run_discussion(project_root, topic):
    """Run a team discussion on a specific topic with actual task spawning."""
    _require_provider()          # first statement, before any orchestration
    ...
```

Two traps this avoids:

1. **Module-scope guard kills the test suite.** 28 files import `theteam` for its safety components (`UnifiedLoop`, `CircuitBreaker`, …), not for discussion. A module-scope raise turns 584 passing tests into 0 collection errors.
2. **Guard must precede config loading.** `run_discussion` calls `load_config` and prints "Failed to load config" before reaching any `default_api` site. A guard placed after config load is inert — the function returns `False` before ever touching the provider.

All five `default_api` call sites live inside `run_discussion`, so one entry guard covers every path.

### Verified, do not assert

1. `grep -rn "MockAPI" theteam/` returns nothing.
2. `import theteam` succeeds. `theteam.run_discussion(...)` raises `ProviderUnavailable` naming the OMP requirement. No fabricated result.
3. `grep -rn "run_task_loop\|task_archive" theteam/` returns nothing.
4. **584 tests pass**, matching the pre-M0 baseline exactly. The suite imports cleanly.
5. The four registered tasks still report: `TaskStackOrchestrator().list_tasks()` returns 4.

### Corrections to this document

Three claims in the earlier draft were wrong and are corrected here:

- **"613 tests"** — the actual count is **584**. The 613 figure came from a prior phase's report and was never re-measured. Recorded here so the next milestone does not inherit a false baseline.
- **"The full test suite still passes"** — unattainable with a module-scope guard, and the guard was the wrong design anyway. The correct claim is the one above: import succeeds, `run_discussion` raises, 584 tests pass.
- **"Four registered tasks still execute"** — cannot be verified outside OMP, because executing a task requires a provider. The measurable claim is that the four tasks still **report**, which they do.

**Do not** start M1 in the same session. M0 must be a clean, reviewable, revertable commit on its own.

## M1 — Reach it from a shell

`cli.py`. Repoint `pyproject.toml`. `state.py`. Migrate `.mp/theteam` to `.omp/theteam`. Remove all hardcoded paths. Delete `__main__.py` as an entry point.

`theteam bootstrap <path>` becomes reachable, which is requirement 1.

**Falsification test:** every command in §2 runs from a clean shell in a fresh directory. No `/Users/bparlan` and no `parents[` remains in the installed package. One state directory. Bootstrap a Python web project and a Rust CLI — **the rosters differ**, because `analyze_project_context` currently declares five focus flags that are never assigned.

**The guard that matters:** `state.py` must land in M1, not later. It is assigned to no milestone in the earlier draft and every later milestone resolves a path through it.

## M2 — Your tasks are visible and run

Convert `tasks/*.md` to `tasks/*.yaml`. Build `tasks/repository.py` with a **dual-read** path: it reads YAML and the old registry, and serves both. Migrate the four tasks. Then a single-commit switch to YAML-only. Then delete the old loader.

Add the minimum `theteam tasks` and `theteam run` to make this observable.

**Falsification test:** `theteam tasks` lists all 4 tasks in the right order. `theteam run` with nothing due returns `{ran: 0, skipped: 0}` and does nothing. Two consecutive `run` calls produce identical output.

**The guard that matters:** after the YAML-only switch commit, and before deleting anything, run `theteam tasks` and assert it returns exactly 4. If the count is not 4, the switch is not done. Deleting the old loader before that assertion is the one step that silently stops all four tasks — `orchestrator list` would return empty rather than error.

Delete `subskills/task_stack/core.py` only after grepping its importers. It is a third `TaskManager` matching zero files, but `orchestrator.py` may still import from it.

## M3 — Create, edit, delete

`repository.update` with conflict detection, `repository.delete` with referential cleanup across every file that names the task, `scheduler.unschedule`. Schema validation on write. CLI surface `theteam task create|edit|delete|show`.

A rename must not orphan a schedule. A delete must not leave a schedule entry firing forever at a missing task.

**Falsification test:** create, edit, delete a task. The edit survives a restart. The delete leaves no dangling reference. Each operation has a test that fails against the pre-change code.

## M4 — The loop is safe

Wire `CircuitBreaker` into task execution. Wire `ResourceLimiter` and `AgentIsolation` into phase execution. Wire `AuditLogger` into the task lifecycle. Bound the execution log. `theteam history`.

A scheduled task running arbitrary project scripts is the exact threat `AgentIsolation` was written for. It currently has no caller.

**Falsification test:** a task failing 5 consecutive times trips a breaker and stops burning cycles. A phase exceeding 64 MB is killed at exit 137, not left running. Every task mutation appears in the audit chain and `theteam status` verifies it.

## M5 — The team comments

`advisory/` with `session_reader`, `selector`, `commentary`. `theteam comment on|off|status`.

**Conditional.** Three gates must pass first:

1. `session_reader` reads a live session and its `digest` changes when the session changes. Verified against a real file, not a fixture.
2. `selector` picks different members for a frontend session and a database session. Deterministic, no LLM.
3. A tick over 10 events produces at most 2 rendered fragments, and a quiet tick costs zero calls.

If any gate fails, cut M5. `engine.py`, `selector.py`, and `roster.py` still ship — one-shot discussion, member selection, and bootstrap are useful without the loop.

**Falsification test:** run commentary for 10 turns. At most 2 fragments per turn. `stop` in the user message produces `{spoke: false, reason: "stopped"}`. `theteam status` shows the session path and event count.

**Guard:** `advisory/engine.py` must be byte-identical before and after M5. If it changed, the controller forked the discussion path and the whole premise of the layer is broken.

# Part 7 — Invariants

## 7.1 Product invariants

A user can check every one of these by running a command.

1. `theteam status` on a bootstrapped project shows a roster, a bound session, and an intact audit chain.
2. `theteam discuss` outside OMP fails with the exact command to run inside OMP, and returns no opinion.
3. Two bootstraps of structurally different projects produce different rosters.
4. `theteam run` with nothing due returns `{ran: 0}` and runs nothing. Two consecutive calls are identical.
5. A task failing 5 times trips a breaker, visible in `theteam tasks` and `theteam history`.
6. A phase over its memory bound is killed and reported, never left running.
7. `theteam history` shows per-task success rate, last run, last failure.
8. Every tick reports `spoke: true` with at most 2 fragments, or `spoke: false` with a reason.

## 7.2 Engineering invariants

1. `grep -rl "CircuitBreaker|ResourceLimiter|AgentIsolation|AuditLogger" theteam/tasks/` returns a non-empty list. The safety layer has a consumer.
2. `grep -rn "subprocess" theteam/tasks/executor.py` shows every call site inside a Layer 4 guard.
3. `grep -rn "/Users/bparlan" theteam/` returns nothing.
4. `grep -rn "parents\[" theteam/` returns nothing.
5. `grep -rn "\.mp/theteam" theteam/` returns nothing.
6. `grep -rn "MockAPI" theteam/` returns nothing.
7. `advisory/engine.py` is byte-identical after M5.
8. Layer 3 contains no `subprocess` call without a Layer 4 guard in the same call frame.

---

# Part 8 — Diagram Inventory

12 pre-existing diagram JSONs, evaluated component-by-component against the source tree. All 12 archived to `diagrams/archive/`.

| File | Verdict |
|---|---|
| `architecture-candidate.json` | stale. names `TaskManager`/`UnifiedLoop` correctly; no `TaskStore`. predates the task surface. |
| `architecture-simple.json` | placeholder. `User` → `System` → `Database` describes nothing here. |
| `lifecycle-candidate.json` | placeholder. `stopped`/`running`/`completed`. |
| `lifecycle-simple.json` | placeholder, near-duplicate of the above. |
| `management-candidate.json` | **fabricated.** `TaskStore`, `TaskManager`, `TaskExecutor` as a connected unit — they live in two packages that do not import each other. |
| `monitoring-candidate.json` | **fabricated.** `MetricsStore` and `Alerting` do not exist anywhere in the tree. |
| `stability-lifecycle.json` | the only non-trivial existing diagram. states match the real loop. |
| `stability-workflow.json` | the only other non-trivial one. |
| `target-stability-architecture.json` | aspirational. mixes real (`UnifiedLoop`, `EventBus`) with invented (`Task Contract`). |
| `team_architecture_candidate.json` | **fabricated.** `theteam_cli` never existed. |
| `workflow-candidate.json` | schema v2. lanes name real modules, no system behind them. |
| `workflow-simple.json` | placeholder. near-duplicate. |

**Component names verified absent from the entire tree:**

`StateStore` · `ConfigStore` · `ToolManifest` · `AgentRegistry` · `MetricsStore` · `Alerting` · `theteam_cli`

**Real components the diagrams missed:** `AgentIsolation`, `ResourceLimiter`, `AuditLogger`, `UnifiedTask`, `SimpleTaskExecutor`, `SimpleTaskScheduler`, `InMemoryTaskStore`.

Ten of twelve were stale or invented. `management-candidate.json` was the most dangerous artifact in `diagrams/`: it rendered a task subsystem as wired together, and the two halves of that subsystem do not import each other.
