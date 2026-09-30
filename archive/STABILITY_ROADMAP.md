# Stability Architecture Roadmap

## Overview

This roadmap establishes a stable, maintainable architecture for theteam. It addresses the core issues: fractured components, drift, and lack of clear order.

## Core Architecture Principles

1. **Single Source of Truth** - One canonical loop implementation, one task contract
2. **Event-Driven Communication** - EventBus-only integration between components
3. **State Integrity** - Atomic state persistence with write-ahead logging
4. **Safety Nets** - Health monitoring, circuit breakers, resource limits
5. **Production Readiness** - Containerization, CI/CD, observability

## Database Requirements

The roadmap requires a **unified database** as the single source of truth for all state. The current architecture uses raw file persistence with no transactions, no locking, and no backups. The database must provide:

- **Atomic transactions** - All-or-nothing state updates
- **Write-ahead logging** - All state changes logged before applied
- **Connection pooling** - Efficient multi-agent access
- **Backup and restore** - State safety and disaster recovery
- **Schema versioning** - Forward/backward compatibility
- **Checksums** - Corruption detection

**Target:** PostgreSQL (or SQLite for Phase 1-2 prototyping, upgrade to PostgreSQL in Phase 4)

## Phase 1: Consolidate (Weeks 1-2)

**Objective:** Establish a single source of truth for the loop and task definitions.

> **Corrected 2026-10-01 by measurement.** Six boxes in this phase and Phase 2 were `[X]`
> on the strength of a file existing, not on the strength of a caller existing. M10
> collapsed three schedulers into one and measured every module by AST import scan plus a
> runtime `sys.modules` check. The rule now applied throughout: **a box is `[X]` only when
> a named, currently-passing check confirms it.** `[~]` means the code exists and is wired
> to something, but that something has no production caller. Corrections cite the check that
> falsified the original claim.

### Tasks
- [X] Map existing stability architecture (analyze LoopManager, LoopController, task_manager, state_manager) — analysis task, no code deliverable
- [ ] **Define target architecture contract (formalize Task Contract and UnifiedLoop interface)** — *was `[X]` citing `task_contract.py`, `unified_loop.py`.* Both deleted by M10: the only task model with a production caller is the YAML store in `theteam/tasks/repository.py`, and the only scheduler is `tasks/scheduler.py`. Superseded, not completed.
- [X] Delete LoopController (562 lines) — removed; also removed `loop_manager.py`
- [X] **Single loop implementation (no competing variants)** — *corrected.* Not `unified_loop.py`: M10 found **three** schedulers, not one. `core/unified_loop.py` and `routine-engine/` were both unreachable and are deleted. The surviving scheduler is `theteam/tasks/scheduler.py`, and `theteam loop`, `theteam run` and `theteam serve` all route through one `run_due_tasks()`. Verified by `grep -rn "UnifiedLoop\|UnifiedTask" theteam/` returning docstrings only.
- [ ] **Define unified Task contract (canonical Task data structure)** — *was `[X]` citing `UnifiedTask`.* `task_contract.py` and `UnifiedTask` deleted by M10: zero production importers. The canonical task is the YAML document in `tasks/*.yaml`, read by `TaskRepository`.
- [X] **Add state file validation on load** — *corrected, in part.* `state_manager.load_state` does verify checksums via `checksum.py` (live: `state_manager` imports it). But `state_validator.py` was cited as "wired into the package" and had **two test importers and zero production** — deleted by M10. The checksum half of this box is real; the `state_validator` half was not.
- [X] Fix save_configuration() - stop swallowing exceptions — re-raises
- [X] Add basic file locking for concurrent access — `threading.Lock` guards state writes

### Deliverables
- ~~`theteam/core/unified_loop.py` — Single loop implementation~~ — **deleted M10** (no producer; its metrics read `0.0` forever)
- ~~`theteam/core/task_contract.py` — Unified task definition~~ — **deleted M10** (no importer)
- `theteam/tasks/scheduler.py` — the single scheduler, M10
- State validation module — the checksum half survives in `checksum.py`; the `state_validator` half is gone

## Phase 2: Harden State (Weeks 3-4)

**Objective:** Implement robust state management and event handling.

> The Phase 2 problem was not wrong checkboxes but **wiring through a dead module**. Three
> boxes below are literally true — the code exists and is imported — and useless in
> production, because the importing module itself has no caller. Measured: `event_bus.py`
> has zero production importers, and it is the *only* path to `event_log.py` and
> `rate_limiting.py`. That is the shape of claim that let a second and third scheduler
> coexist unnoticed for nine milestones.

### Tasks
- [X] Implement Write-Ahead Logging (WAL) — `wal.py`, invoked before state writes; live via `UnifiedStateManager.__init__`
- [~] **Implement Event Sourcing (store all state changes as events)** — *qualified.* `event_log.py` exists and is imported, but its only importer is `core/event_bus.py`, which has **zero production importers**. Reachable from itself only. Not wired; not deleted either — see `ARCHITECTURE.md` §5.2.1.
- [ ] **Add schema versioning for state files and events** — *was `[X]` citing `schema_versioning.py`.* **Zero importers anywhere, including tests.** Deleted by M10.
- [X] Add checksums for state files — `checksum.py`, verified on load; live via `state_manager`
- [X] Set up database with migrations and connection pooling — `database.py` (SQLite; Postgres is Phase 4); live via `UnifiedStateManager.db`
- [X] Implement atomic transactions for state updates — `transactions.py`; live via `UnifiedStateManager.tx`
- [X] Add correlation IDs for structured observability — `correlation.py`; live via `state_manager.correlation` — **the one genuinely-wired module in this phase**
- [~] **Add event rate limiting (prevent event storms)** — *qualified.* "wired via `event_bus.py`" is true and the wire goes nowhere: `event_bus.py` has no production importer. Same dead path as `event_log.py`.

### Deliverables
- `theteam/core/state_manager.py` - Atomic state persistence (roadmap named `state_store.py`; the implementation lives in `state_manager.py`)
- ~~`theteam/core/event_log.py`~~ - exists, unreachable in production (see `[~]` above)
- ~~Schema versioning module~~ - **deleted M10**, no importers
- Database configuration and migration scripts

## Phase 3: Add Safety Nets (Weeks 5-6)

**Objective:** Introduce resilience mechanisms and proactive monitoring.

> Two boxes here named `UnifiedLoop` as the thing that made them live. M10 deleted it, so
> both need re-verification against what is actually wired now.

### Tasks
- [~] **Implement Health Monitoring (HealthMonitor component)** — *reopened.* `health_monitor.py` exists and was surfaced through `UnifiedLoop.get_status()['health']`, which is gone. It now has **zero production importers**, and `ui/components/health_dashboard.py` reads a health score from whatever it is handed — currently nothing. The fix is wiring the dashboard, not deleting the input.
- [X] Implement Circuit Breakers (protect against cascading failures) — `circuit_breaker.py`; live via `tasks/executor.py`
- [~] **Implement Resource Limiter (prevent runaway resource consumption)** — *corrected: my first pass here was wrong.* `resource_limiter.py` exists and `tasks/executor.py` names `ResourceLimiter` twice — but both are **comments** (lines 31 and 50), not imports. Measured: zero production importers, and `import theteam.cli` does not load it. The bounds it provides are therefore declared but not enforced on the live execution path. Enforcement, not deletion, is the fix.
- [X] Add CI/CD pipeline (automate validation and deployment) — `.github/workflows/ci.yml` runs the full test suite plus import and entry-point checks
- [ ] **Add dead-letter queues for failed events** — *was `[X]` citing the `UnifiedLoop` DLQ.* The DLQ went with `unified_loop.py`. `tasks/scheduler.py` publishes a `dead_letter_queue` from tasks the breaker skipped, which is a real but much narrower thing; there is no retry or retention behaviour behind it.
- [X] Implement proper error handling (eliminate silent failures) — save paths re-raise; `health_monitor` corruption block removed
- [X] Add bounded growth policies (retention for metrics, logs, ledger) — alert retention + execution-log trim to newest 1000 lines

### Deliverables
- `theteam/core/health_monitor.py` - exists, unwired (see `[~]` above)
- `theteam/core/circuit_breaker.py` - live via `tasks/executor.py`
- `theteam/core/resource_limiter.py` - exists, not enforced (see `[~]` above)
- CI/CD configuration files
- Rate limiting and observability modules — `rate_limiting.py` exists behind a dead wire; `correlation.py` is live

## Phase 4: Productionize (Weeks 7-8)

**Objective:** Prepare the system for reliable production deployment.

### Tasks
- [X] Containerize with Docker (isolate agents and dependencies) — multi-stage `Dockerfile` (non-root `app` user, `HEALTHCHECK`); image builds and reports `healthy`; `requirements.txt`, `pyproject.toml`, `theteam/__main__.py` added so the build and `CMD` work
- [X] Add Prometheus/Grafana monitoring (observability) — `theteam/core/metrics.py` (stdlib exposition, `/metrics` + `/health`); `prometheus.yml`, Grafana datasource/dashboard provisioning, `theteam Production` dashboard; verified scraping live
- [X] Implement backup and restore (state safety) — `theteam/core/backup.py` with real sha256 manifest, verify-before-restore, and `prune()` retention; `scripts/backup.py` delegates to it (was triplicated, with `"checksum": "TODO"`). **M10 note:** this module looked orphaned once `UnifiedLoop` went, and is not — `scripts/backup.py` is a working operator CLI, verified by running `create`.
- [X] Add audit logging (track all state changes and agent actions) — `theteam/core/audit.py` (hash-chained, `verify_chain()`, `max_entries` retention). **M10 note:** was wired into `UnifiedLoop.add_task`; that call site is gone, so the wiring needs re-establishing on the live execution path (`tasks/executor.py` is the candidate).
- [X] Set up production database (PostgreSQL with failover) — `theteam/core/postgres_cluster.py`: `FailoverManager` promotes standby on primary loss; `DatabaseManager` gains `pg_config`, pooled `connection_pool`, `get_failover_status()`
- [X] Add read replicas for scaling — `ReadReplicaRouter` round-robins reads across healthy replicas, falls back to primary, never reads from the standby
- [X] Separate production and development environments — `docker-compose.prod.yml` (primary + standby + 2 replicas) and `docker-compose.dev.yml` (SQLite, source-mounted, relaxed limits); both validate with `docker compose config`
- [X] Add resource bounds and retention policies — `ResourceLimiter.from_env()` honours `THETEAM_LIMIT_*`; alerts and history are bounded deques; honoured by the compose env

### Deliverables
- `Dockerfile`, `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.dev.yml`
- `theteam/core/metrics.py`, `prometheus.yml`, `grafana/` (provisioning + dashboard)
- `theteam/core/backup.py`, `scripts/backup.py` (CLI over the canonical module)
- `theteam/core/audit.py`
- `theteam/core/postgres_cluster.py` (pool, replicas, failover)

## UI & Visibility Layer (Phase 5)

**Objective:** Provide user-facing visibility into system state and autonomous behavior.

### Tasks
- [X] Add real-time ActivityStream component (renders agency events chronologically, color-coded by severity, with drill-down) — `theteam/ui/components/activity_stream.py`; bounded retention, newest-first ordering, severity ramp, drill-down detail; rendered at `/activity`
- [X] Add health status dashboard (circuit breaker states, health scores, recovery actions) — `theteam/ui/components/health_dashboard.py` reads live `CircuitBreaker`/`HealthMonitor` objects; extends the existing System Health card in `pages/dashboard.py`
- [X] Add system metrics and performance monitoring interface — `theteam/ui/components/metrics_panel.py` parses the real `core/metrics.py` Prometheus exposition; rendered in the dashboard's System Metrics card
- [X] Add agent roster panel (status indicators, recent contribution feed, per-agent performance metrics) — `theteam/ui/components/agent_roster.py`; rendered at `/agents`
- [X] Implement visual state machine semantics (closed/half-open/open with icons+color+labels) — `design_tokens.py` maps the real `CircuitState` enum to icon/color/label; `open` is the *bad* state (danger) and `closed` the good one
- [X] Add progressive disclosure (expandable/collapsible detail panels) — `theteam/ui/components/disclosure.py`; shared expansion state reused by activity, health, and roster panels

### Deliverables
- `theteam/ui/components/` - UI component library (stdlib view models + optional Reflex renderers)
- `theteam/ui/components/design_tokens.py` - Design tokens: palette, severity ramp, state visuals
- `theteam/ui/components/activity_stream.py` - Real-time event visualization
- `theteam/ui/components/health_dashboard.py` - Health status interface
- `theteam/ui/components/agent_roster.py` - Agent management interface
- `theteam/ui/components/metrics_panel.py` - Metrics/performance interface
- `theteam/ui/components/disclosure.py` - Progressive disclosure
- ~~`theteam/ui/components/visibility.py`~~ - **deleted M10** (no production importer; named in docstrings only)
- ~~`theteam/ui/components/reflex_renderers.py`~~ - **deleted M10** (no production importer)

### Notes
The view models in `theteam/ui/components/` are pure stdlib and import no
Reflex, so they are unit-tested in CI (Reflex is not a declared dependency).
`reflex_renderers.py` imports Reflex lazily and raises a clear error if it is
absent, so the package stays importable without a web stack. Verified: all
component modules import with Reflex blocked, and the Reflex app compiles with
`/`, `/tasks`, `/activity`, and `/agents` registered.

### Defects found and fixed during Phase 5
- `circuit_breaker.py`: `stats.state` was assigned `CLOSED` at construction and
  never written again, so a breaker could not trip - `allow_request()` always
  returned `True`. The state machine (trip at threshold or low health score,
  half-open probe after the recovery deadline with bounded concurrency,
  recovery with capped exponential backoff) is now implemented and covered.
- `system_integration.py`: `_run_integrated_system_analysis` never returned its
  result, so the caller's `result['success']` raised `TypeError` on the success
  path; it also referenced `sys` and `PROJECT_ROOT`, neither defined in the
  module. Both fixed, with regression tests.
- `pages/activity.py` and `pages/agents.py` read a row key `detail_lines` while
  the builder emitted `detail_text`, so every disclosure panel silently
  rendered empty detail. Fixed, and `test_visibility_state.py` now
  cross-checks page keys against real builder output.
- `subskills/task_stack/core.py` (out of Phase 5 scope): `execution_time` used
  the wall clock (`time.time()`), which can return exactly `0.0` for a fast
  handler and made `test_execute_task_success` intermittently fail. Switched to
  `time.monotonic()`.

## Drift Prevention Gates

These gates prevent agents from drifting from the target architecture:

1. **Schema Validation Gate** - All state files must pass schema validation before load
2. **Contract Compliance Gate** - All components must implement required interfaces
3. **CI/CD Gate** - All changes must pass automated tests before merge
4. **Containerization Gate** - All agents must run in isolated containers
5. **Health Check Gate** - All components must report health status periodically
6. **Database Integrity Gate** - All state writes must use atomic transactions
7. **Event Rate Limiting Gate** - Event bus must enforce rate limits
## M11 — The headline command crashed

`theteam discuss` is the skill's primary command. It could not run.

`DiscussionState.start_discussion` calls `self._notify_listeners`, but that method is
defined only on `UnifiedStateManager` — never on `DiscussionState`,
`SystemAwarenessState` or `TaskState`. `run_discussion` reaches
`start_discussion` before it selects or spawns a single member, so the whole path raised:

```
AttributeError: 'DiscussionState' object has no attribute '_notify_listeners'
```

Ten call sites across three classes, none of them defined. `state_manager.py` had **no test
coverage at all**, which is how this survived nine milestones.

- [X] **Reproduce it** — `hasattr(DiscussionState, '_notify_listeners')` → `False`; `start_discussion` raises. Confirmed, not inferred.
- [X] **Fix it** — a `_Notifying` mixin gives every sub-state a `_notify_listeners` that is a no-op when nobody is listening, because an unobserved state transition is a legitimate state of the world, not an error. `UnifiedStateManager.__init__` injects its real notifier, so a listener registered with `add_listener` still fires.
- [X] **Test it** — new `theteam/tests/test_state_manager.py`, 7 tests. Two matter: one drives `start_discussion` directly (the crash), one asserts a registered listener *hears* a sub-state event — because the no-op default alone would pass the first while silently dropping every event, which is the same defect quieter.
- [X] **Type-check it** — the injected attribute is declared on the mixin, not set dynamically; Pyright had flagged it as unknown on all three classes.

Outside OMP the command refuses cleanly at `_require_provider()` before reaching the bug, so
the failure was invisible to any smoke test run outside a session. The crash was real on the
only path that matters.

### The second defect was worse than the first

The advisory that prompted this section asked whether `save_state` was reachable from a
shipped command. It is: `run_discussion` calls it at the *end* of the same function, on
line 954. It was not latent at all.

`save_state` was broken three ways at once, and the third is the one that matters:

1. It called `self.wal.log_state_change(...)`. `WriteAheadLog` has no such method; the
   real one is `append_entry(operation, data)`.
2. It called `self.checksum.add_checksum(state_data)` and **discarded the return value**.
   `ChecksumManager` exposes `add_checksum_to_state`, which returns a new dict — it does
   not mutate. So even a working call would have written an unchecksummed file.
3. `except Exception: logger.error(...)` swallowed both.

Measured, before the fix: `start_discussion` then `save_state` left **no file on disk at
all**, and returned normally. `theteam discuss` would have printed a full synthesis, named
a recommendation, written its report — and reported success having persisted zero state.
That is the §3.3 defect class in its purest form: a failure that is indistinguishable
from a success.

`load_state` had the mirror image. It called a non-existent `verify_checksum` inside the
same swallowing `try`, so every load raised, was caught, and restored nothing — a corrupt
state file and a fresh project were indistinguishable. It now raises a named
`ValueError` on checksum mismatch, and uses the same `ChecksumManager` API the writer
uses, so a file written by `save_state` verifies on load.

- [X] **Reproduce both** — `hasattr(DiscussionState, '_notify_listeners')` → `False`; `save_state` → `Error saving state: 'WriteAheadLog' object has no attribute 'log_state_change'` and no file.
- [X] **Fix at the root, not per call site** — a `_Notifying` mixin, no `try`/`except` around the ten call sites (which §3.3 forbids), and the swallowing `except` removed from both `save_state` and `load_state` rather than narrowed.
- [X] **Use the real APIs** — `append_entry`, `add_checksum_to_state`, `verify_state_data`; each verified against the class that defines it.
- [X] **Test the pair** — save then reload in a fresh manager, asserting the discussion and its completed task come back. The completed task is asserted in `task_history`, not `tasks`: `update_task` moves a task to history and deletes it on `completed`, which `run_discussion` does before saving. An empty `tasks` dict is the correct post-condition; my first assertion was wrong.
- [X] **Type-check clean** — all three pre-existing Pyright errors on this file are gone, because the call sites were corrected rather than suppressed.

### `run_discussion` had no test at all

653 tests passed while two hard defects sat in the same function. The cause is structural:
`_require_provider()` makes `theteam discuss` refuse cleanly outside OMP, so no smoke test
outside a session reaches any of this code.

- [X] **Add end-to-end coverage** — `theteam/tests/test_run_discussion_e2e.py` drives `run_discussion` with a stub `default_api` through selection, intros, synthesis, report generation and save. The fixture bootstraps through `bootstrap_flow` rather than hand-writing a config; the hand-written version failed with `KeyError: 'behavior'`, which is exactly how a fixture drifts from `theteam_config.REQUIRED_TOP_KEYS` and starts testing something the product never produces.
- [X] **Prove the tests bite** — reverting the mixin fails 7; restoring `log_state_change` fails 3. Neither regression can return silently.

---

## Diagrams

The target architecture is documented in:
- `diagrams/target-stability-architecture.json` - Core component architecture
- `diagrams/stability-workflow.json` - Loop execution workflow
- `diagrams/stability-lifecycle.json` - State lifecycle management

## Success Criteria

Status verified against the repository on 2026-09-26 (197 tests passing).

> **Re-verified 2026-10-01 after M10** (653 tests passing). Five criteria below changed
> status. The original verification counted a module as delivered if the file existed; this
> pass requires a production importer. Criteria 3, 6, 7, 8, 10 and 11 still hold and were
> re-checked against the current tree.

1. [X] Single loop implementation (no competing variants) — **still true, different module.** `unified_loop.py` is deleted; the single scheduler is `theteam/tasks/scheduler.py`. Three schedulers existed until M10.
2. [X] Unified task contract (no divergent task models) — **still true, different model.** `UnifiedTask`/`task_contract.py` are deleted; the canonical task is the YAML document in `tasks/*.yaml` read by `TaskRepository`.
3. [X] Atomic state persistence (no state corruption) — WAL + checksums + transactions
4. [ ] Event-driven communication — **reopened.** `event_bus.py` mediates nothing today: it has zero production importers, and the two modules behind it (`event_log.py`, `rate_limiting.py`) are reachable only through it. Components reference each other directly.
5. [~] Health monitoring with circuit breakers — **qualified.** `circuit_breaker.py` is live via `tasks/executor.py` and does its job. `health_monitor.py` is not wired anywhere: the dashboard reads a score it is never given.
6. [X] Containerized execution (no agent drift) — image builds, runs as non-root `app`, `HEALTHCHECK` passes; per-agent container isolation implemented (`agent_isolation.py`), wired into `SystemIntegration` execution, proven live against a real container (read-only rootfs, read-only project mount, 64m OOM kill at exit 137, network off by default)
7. [X] CI/CD pipeline with automated testing (no broken deployments) — CI now runs the full suite via bare `pytest`, plus import and entry-point checks
8. [X] Unified database with transactions and backups — SQLite + `transactions.py`; production PostgreSQL via `postgres_cluster.py` with pooled connections, read replicas, and standby failover. SQL-level streaming replication and failover promotion proven against a real primary+standby+replica cluster: data written to the primary appeared on both replicas; after killing the primary and promoting the standby, `pg_is_in_recovery()` returned false, the 2 rows survived, and the promoted node accepted writes. `FailoverManager.failover()` now invokes a real promotion callback before reassigning the primary.
9. [ ] Rate-limited event bus — **reopened.** `rate_limiting.py` exists and is imported by `event_bus.py`, which nothing imports. Same dead wire as criteria 4.
10. [X] Structured observability with correlation IDs — `correlation.py`, live via `state_manager.correlation`
11. [~] Real-time activity streams and health dashboards — **qualified.** The components exist and are imported by `ui/components/__init__.py`; `health_dashboard.py` has no health source to read, per criterion 5. — `theteam/ui/components/` provides the activity stream, health dashboard, metrics panel, agent roster, state-machine visuals, and progressive disclosure. Verified: 631 tests passing, all component modules import with Reflex blocked, and the Reflex app compiles with all four pages registered. Building the health dashboard exposed a production bug — `CircuitBreaker.stats.state` was only ever initialized to `CLOSED` and never assigned, so the breaker could not trip; the state machine (trip at threshold, half-open probe, recovery with capped exponential backoff) is now implemented and covered by 28 tests.