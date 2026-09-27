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

### Tasks
- [X] Map existing stability architecture (analyze LoopManager, LoopController, task_manager, state_manager) — analysis task, no code deliverable
- [X] Define target architecture contract (formalize Task Contract and UnifiedLoop interface) — `task_contract.py`, `unified_loop.py`
- [X] Delete LoopController (562 lines) — removed; also removed `loop_manager.py` (UnifiedLoop is the sole loop)
- [X] Make UnifiedLoop the single loop implementation — `unified_loop.py` is the only loop module
- [X] Define unified Task contract (canonical Task data structure) — `UnifiedTask`; `LoopPriority` now aliases `TaskPriority`
- [X] Add state file validation on load — `state_manager.load_state` verifies checksums; `state_validator.py` wired into the package
- [X] Fix save_configuration() - stop swallowing exceptions — re-raises
- [X] Add basic file locking for concurrent access — `threading.Lock` guards state writes

### Deliverables
- `theteam/core/unified_loop.py` - Single loop implementation
- `theteam/core/task_contract.py` - Unified task definition
- State validation module

## Phase 2: Harden State (Weeks 3-4)

**Objective:** Implement robust state management and event handling.

### Tasks
- [X] Implement Write-Ahead Logging (WAL) — `wal.py`, invoked before state writes
- [X] Implement Event Sourcing (store all state changes as events) — `event_log.py`, `EventSourcingManager`
- [X] Add schema versioning for state files and events — `schema_versioning.py`
- [X] Add checksums for state files — `checksum.py`, verified on load
- [X] Set up database with migrations and connection pooling — `database.py` (SQLite; Postgres is Phase 4)
- [X] Implement atomic transactions for state updates — `transactions.py`
- [X] Add correlation IDs for structured observability — `correlation.py`
- [X] Add event rate limiting (prevent event storms) — `rate_limiting.py`, wired via `event_bus.py`

### Deliverables
- `theteam/core/state_manager.py` - Atomic state persistence (roadmap named `state_store.py`; the implementation lives in `state_manager.py`)
- `theteam/core/event_log.py` - Event sourcing implementation
- Schema versioning module
- Database configuration and migration scripts

## Phase 3: Add Safety Nets (Weeks 5-6)

**Objective:** Introduce resilience mechanisms and proactive monitoring.

### Tasks
- [X] Implement Health Monitoring (HealthMonitor component) — `health_monitor.py`, surfaced in `UnifiedLoop.get_status()['health']`
- [X] Implement Circuit Breakers (protect against cascading failures) — `circuit_breaker.py`, gated via `allow_request()`
- [X] Implement Resource Limiter (prevent runaway resource consumption) — `resource_limiter.py`
- [X] Add CI/CD pipeline (automate validation and deployment) — `.github/workflows/ci.yml` runs the full test suite via bare `pytest` across Python 3.9–3.12, plus import and entry-point checks
- [X] Add dead-letter queues for failed events — `UnifiedLoop` DLQ with retry and retention
- [X] Implement proper error handling (eliminate silent failures) — save paths re-raise; `health_monitor` corruption block removed
- [X] Add bounded growth policies (retention for metrics, logs, ledger) — alert retention + DLQ cleanup

### Deliverables
- `theteam/core/health_monitor.py` - Health monitoring
- `theteam/core/circuit_breaker.py` - Circuit breaker implementation
- `theteam/core/resource_limiter.py` - Resource limits
- CI/CD configuration files
- Rate limiting and observability modules

## Phase 4: Productionize (Weeks 7-8)

**Objective:** Prepare the system for reliable production deployment.

### Tasks
- [X] Containerize with Docker (isolate agents and dependencies) — multi-stage `Dockerfile` (non-root `app` user, `HEALTHCHECK`); image builds and reports `healthy`; `requirements.txt`, `pyproject.toml`, `theteam/__main__.py` added so the build and `CMD` work
- [X] Add Prometheus/Grafana monitoring (observability) — `theteam/core/metrics.py` (stdlib exposition, `/metrics` + `/health`); `prometheus.yml`, Grafana datasource/dashboard provisioning, `theteam Production` dashboard; verified scraping live
- [X] Implement backup and restore (state safety) — `theteam/core/backup.py` with real sha256 manifest, verify-before-restore, and `prune()` retention; `scripts/backup.py` and `UnifiedLoop` now delegate to it (was triplicated, with `"checksum": "TODO"`)
- [X] Add audit logging (track all state changes and agent actions) — `theteam/core/audit.py` (hash-chained, `verify_chain()`, `max_entries` retention), wired into `UnifiedLoop.add_task`
- [X] Set up production database (PostgreSQL with failover) — `theteam/core/postgres_cluster.py`: `FailoverManager` promotes standby on primary loss; `DatabaseManager` gains `pg_config`, pooled `connection_pool`, `get_failover_status()`
- [X] Add read replicas for scaling — `ReadReplicaRouter` round-robins reads across healthy replicas, falls back to primary, never reads from the standby
- [X] Separate production and development environments — `docker-compose.prod.yml` (primary + standby + 2 replicas) and `docker-compose.dev.yml` (SQLite, source-mounted, relaxed limits); both validate with `docker compose config`
- [X] Add resource bounds and retention policies — `ResourceLimiter.from_env()` honours `THETEAM_LIMIT_*`; alerts and history are now bounded deques; wired into `UnifiedLoop` and the compose env

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
- `theteam/ui/components/visibility.py` - Pure builders feeding the Reflex state
- `theteam/ui/components/reflex_renderers.py` - Optional Reflex renderers

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
## Diagrams

The target architecture is documented in:
- `diagrams/target-stability-architecture.json` - Core component architecture
- `diagrams/stability-workflow.json` - Loop execution workflow
- `diagrams/stability-lifecycle.json` - State lifecycle management

## Success Criteria

Status verified against the repository on 2026-09-26 (197 tests passing):

1. [X] Single loop implementation (no competing variants) — `unified_loop.py` only
2. [X] Unified task contract (no divergent task models) — `UnifiedTask`; `LoopPriority` aliases `TaskPriority`
3. [X] Atomic state persistence (no state corruption) — WAL + checksums + transactions
4. [X] Event-driven communication (no direct component references) — `event_bus.py` mediates
5. [X] Health monitoring with circuit breakers (no cascading failures) — both wired into the loop
6. [X] Containerized execution (no agent drift) — image builds, runs as non-root `app`, `HEALTHCHECK` passes; per-agent container isolation implemented (`agent_isolation.py`), wired into `SystemIntegration` execution, proven live against a real container (read-only rootfs, read-only project mount, 64m OOM kill at exit 137, network off by default)
7. [X] CI/CD pipeline with automated testing (no broken deployments) — CI now runs the full suite via bare `pytest`, plus import and entry-point checks
8. [X] Unified database with transactions and backups — SQLite + `transactions.py`; production PostgreSQL via `postgres_cluster.py` with pooled connections, read replicas, and standby failover. SQL-level streaming replication and failover promotion proven against a real primary+standby+replica cluster: data written to the primary appeared on both replicas; after killing the primary and promoting the standby, `pg_is_in_recovery()` returned false, the 2 rows survived, and the promoted node accepted writes. `FailoverManager.failover()` now invokes a real promotion callback before reassigning the primary.
9. [X] Rate-limited event bus (no event storms) — `rate_limiting.py`
10. [X] Structured observability with correlation IDs — `correlation.py`
11. [X] Real-time activity streams and health dashboards — `theteam/ui/components/` provides the activity stream, health dashboard, metrics panel, agent roster, state-machine visuals, and progressive disclosure. Verified: 631 tests passing, all component modules import with Reflex blocked, and the Reflex app compiles with all four pages registered. Building the health dashboard exposed a production bug — `CircuitBreaker.stats.state` was only ever initialized to `CLOSED` and never assigned, so the breaker could not trip; the state machine (trip at threshold, half-open probe, recovery with capped exponential backoff) is now implemented and covered by 28 tests.