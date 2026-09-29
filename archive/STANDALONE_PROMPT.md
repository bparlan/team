# STANDALONE_PROMPT.md — What shipped, and what is still open

> **Archived 2026-09-29.** The questions this file answered — what the watch surface can do, and
> what the next milestone should be — are now settled in the documents that are maintained:
> `README.md` §"Watching for change" for the flag's semantics, `ARCHITECTURE.md` §2 for why the
> monitor deliberately has no API layer, and `theteam/CHANGELOG.md` for what each milestone did.
> This file is kept as a record of the decision, not as guidance. Nothing here is a source of
> truth; where it differs from those three, they are right.

> **Rewritten 2026-09-29.** The previous version of this file prescribed `theteam/alerts.py`,
> `theteam/api/monitor.py`, and a `theteam.get_monitor_status()` / `get_recent_events()` /
> `clear_alerts()` API surface. **None of that exists, and its absence is a decision, not a gap.**
> `ARCHITECTURE.md` §2 records it: those functions would read a process-local `deque` from outside
> the process, which has no caller and would be a second adapter past the payload boundary. The
> file also described `watch` as unable to monitor, which stopped being true when
> `theteam/monitor.py` landed. Both claims are gone. What follows is the state of the code.

## What exists today

`theteam watch status|tasks|history` has a monitoring mode. It is a flag on the existing renderer,
over the payloads `status`, `tasks`, and `history` already emit.

```bash
theteam watch status --monitor          # live, default 5s interval
theteam watch tasks --once --monitor    # one frame with the change block
theteam watch status --monitor --json   # the payload, not the frame
```

`theteam/monitor.py` is three pieces, all standard library:

| Symbol | Kind | What it does |
|---|---|---|
| `diff(before, after)` | pure function | Flatten two payloads to leaf paths, return the ones that moved. |
| `alerts(changed)` | pure function | Name the transitions worth reporting: a breaker reaching `open`, an audit chain leaving `intact: true`, a task leaving the registry. |
| `Monitor(view)` | value object | Holds the previous frame, a change count, and a bounded `deque` of recent transitions. One per watch loop. Its whole interface is `observe(payload)` and `recent()`. |

Both functions are pure, which is why the rules are testable without a running loop. `Monitor` is a
value, not a service: nothing to start, nothing to poll, nothing to shut down.

## The three properties that make it trustworthy

1. **An alert is a transition, not a level.** A breaker that is open has been open since the frame
   it opened. Reporting it every tick trains the reader to ignore the line exactly when it matters.
2. **A `None` never raises an alert.** A task that has never run is an observation of absence.
   Reading it as an event is the fabricated opinion `ARCHITECTURE.md` §3.3 forbids.
3. **The first frame is a baseline, not "0 changes."** There is no previous frame, so nothing has
   been compared, and a zero there would claim a stability nobody has checked.

A change count counts **frames that differed**, not fields. One frame that moved six fields is one
change.

## What it does not do, on purpose

| Not implemented | Why |
|---|---|
| An API layer (`get_monitor_status`, `get_recent_events`, `clear_alerts`) | Would read a process-local `deque` from outside the process. No caller; a second adapter past the payload boundary. `ARCHITECTURE.md` §2. |
| A separate `alerts.py` module | `alerts()` is 30 lines and shares `diff`'s change records. A second module would be a second spelling of one rule. |
| `theteam watch history --task <id>` | `history` has the filter, `watch` does not. A renderer gap, not a false claim. Unresolved — see below. |
| Scraping `theteam serve` | The CLI payloads are the source of truth. `serve` is an optional export; a monitor that depended on it would fail closed when it is down. |

## The guarantee, in its checkable form

`--monitor` is off by default and adds no data source. `theteam status|tasks|history --json` are
byte-identical with and without it, anywhere in the tree, because `watch` only ever read those
payloads. If a JSON payload changes when you add a rendering flag, the flag has become a data
path — that is a bug.

Verified against a pre-change worktree at `01413dd`, with the gate that asserts the old code
actually loads and that its `--help` lacks `--monitor`:

```
status  --json  BYTE-IDENTICAL  1cd98c745f5bcc5e4b50272258ed8311
tasks   --json  BYTE-IDENTICAL  f9c8ba5bbea0f7492c4fb9f422ca3821
history --json  BYTE-IDENTICAL  979b400064342017f8c5532cca677557
```

## Open, and worth a decision

1. **`watch history --task <id>`.** `history` filters; `watch history` renders everything. For a
   project with many tasks this is the difference between a readable frame and a scroll. It is one
   flag and one branch, and the payload function already takes the argument.
2. **Four `core/` modules with no production importer** — `state_validator`, `schema_versioning`,
   `system_integration`, `integrated_orchestrator`. `ARCHITECTURE.md` §5.2.1 assigns them no layer
   by measurement. Each needs a caller or a §5.3 removal row.
3. **No digest cache** in the advisory layer. The per-turn token cost is real and currently paid.
   `ARCHITECTURE.md` §4.6 explains why a root-directory mtime would be the wrong invalidation key.
4. **`selection_options` divergence.** `SKILL.md` describes a four-option prompt; the key is
   optional per the schema, absent from every shipped config, and `theteam/__init__.py:692`
   carries a divergent three-option fallback. Doc-corrected in M8; the code fix is undecided.

## What was rejected, and why

An earlier draft of this plan proposed a Python API over the task repository — `list_tasks()`,
`get_task_status()`, `execute_tasks()` — so a user would not have to learn eleven subcommands.

The reason it was dropped is the same reason the monitor has no API layer. `TaskRepository` is
already a clean Python object with a documented surface; the CLI is a thin Layer 0 dispatcher over
it. A module-level facade would be a second name for the same object, one more thing to keep in
sync, and no new capability. The actual friction was never "the API is hard to call" — it was
"the docs did not say which of the eleven subcommands matter." That was a documentation defect, and
it is fixed in the root `README.md` and `theteam/ONBOARDING.md`.

## Verification

```
python3 -m pytest -q                # 772 tests
bash scripts/check_invariants.sh   # 7 checks
```
