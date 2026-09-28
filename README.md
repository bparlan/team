# theteam

A small panel of expert reviewers that reads your real working session, plus a runner for the
scheduled project tasks you keep in plain YAML. `theteam` is one CLI and one state directory.
It has two hard rules: it never invents an opinion it did not get from a real provider, and it
never prints a value that looks like a measurement when it has nothing measured. Everything
below is verified against the code at this commit.

## Requirements

Python 3.9 or newer. `PyYAML` is the only hard dependency. `rich` is **not** required and must
not be imported: it is present in some developers' environments transitively, so a renderer that
imports it passes locally and fails on a clean CI runner.

## Install

```bash
pip install -e .
```

That installs the `theteam` console script. The two working entry points are:

```bash
theteam --help
python -m theteam.cli --help
```

`python -m theteam` does **not** work. `__main__.py` was removed in M1, so it fails with
`No module named theteam.__main__`. The CI step that runs `python -m theteam --help || true`
hides that failure behind `|| true`; it is a decorative step, not a working invocation.

## Quickstart

```bash
cd /your/project
theteam bootstrap          # write a theteam.config for this project
theteam status             # the trust surface: roster, tasks, audit chain
theteam watch status --once  # the same thing, rendered as one frame
theteam run                # execute everything currently due
```

## The four capabilities

| Capability | Command | Milestone |
|---|---|---|
| Bootstrap into any project | `theteam bootstrap` | M1 |
| In-context team commentary | `theteam comment on\|off\|status` | M5 |
| Create, edit, delete tasks | `theteam task create\|edit\|delete\|show` | M3 |
| Run and manage tasks on a loop | `theteam run`, `theteam tasks`, `theteam loop` | M2, M4 |

## Command reference

Eleven subcommands. `--json` works on **either side** of the subcommand for every one of them.

| Command | Arguments and flags | What you get back |
|---|---|---|
| `theteam bootstrap [path]` | `--interactive`, `--json` | `{ok, config, state_dir}`. Non-interactive unless asked. |
| `theteam status` | `--json` | Roster, state directory, task counts, breaker trips, audit-chain state. |
| `theteam discuss <topic>` | `--json` | The team's verdict, or a named error if you are outside OMP. |
| `theteam serve` | `--port N` (default `$THETEAM_METRICS_PORT`, else `8000`), `--json` | Prometheus endpoint. The only command that starts a server. |
| `theteam loop <task_id>` | `--interval N` minutes (default 60), `--json` | `{task_id, interval_minutes, next_run}`. |
| `theteam tasks` | `--json` | One row per task: `id`, `order`, `next_run`, `last_result`, `breaker`. |
| `theteam run` | `--only <id>`, `--json` | `{ran, skipped, failures, results}`. Idempotent. |
| `theteam history` | `--task <id>`, `--json` | `runs`, `successes`, `failures`, `success_rate`, `last_run`, `last_failure`, `breaker`. |
| `theteam task create` | `--path <file.yaml>` (required), `--json` | The created task, as stored. |
| `theteam task edit <task_id>` | `--patch <file>` (required), `--json` | The new task state. |
| `theteam task delete <task_id>` | `--yes`, `--json` | The deletion plan, or what was removed with `--yes`. |
| `theteam task show <task_id>` | `--json` | The task exactly as stored. |
| `theteam comment on` | `--max-members N` (default 3, hard cap 4), `--json` | `{ok, on, max_members, marker}`. |
| `theteam comment off` | `--json` | `{ok, on, sentinel}`. Takes effect on the next tick. |
| `theteam comment status` | `--json` | `{on, marker, max_members, last_digest, last_opinion, tick_count}`. |
| `theteam watch <status\|tasks\|history>` | `--once`, `--interval SECONDS` (default 5), `--json` | A rendered frame, or the payload the frame draws with `--json`. |

Global: `--project-root PATH` (default `$THETEAM_PROJECT_ROOT`, else `$PWD`).

`status`, `tasks`, and `history` are the **machine surface** — their output is a contract with
agentic consumers. `watch` is a renderer over the same payloads and does not restate them.

### Worked example: reading the machine surface

```bash
$ theteam --json status
{
  "project_root": "/your/project",
  "state_dir": "/your/project/.omp/theteam",
  "roster": { "active": 5, "members": ["architect", "pragmatist", "skeptic", "designer", "devops"] },
  "tasks": { "registered": 4, "scheduled": 0, "breaker_trips": [] },
  "breakers": {},
  "audit_chain": { "exists": false, "entries": 0, "state": "absent", "intact": null, "reason": "no audit file at ..." }
}
```

Note `intact: null` and `state: "absent"`. Nothing has been measured, and the output says so.

## Output honesty

This is the part that changes how you read everything above, so it is stated as a contract
rather than a caveat. **No code path returns a synthesized opinion, a default standing in for
a real one, or a placeholder that reads like a result.** Concretely, when you parse this output:

| You see | It means | It does **not** mean |
|---|---|---|
| `null` | nothing was measured | that the value is zero |
| `never run` | the task has never executed | that it failed |
| `-` | the cell was not measured | `0` |
| `absent` | there is no audit file yet | that the chain is `intact` |
| `success_rate: null` | zero runs, so there is no rate | `0.0%`, which would look like a real failure rate |
| `breaker: null` | the task never ran, so no breaker state exists | `closed` |

If you see a value that looks like a healthy measurement where nothing was measured, that is a
bug. Report it. The audit row is rendered by one function (`audit_chain.chain_line`) precisely so
a fourth spelling cannot grow, and every `None` is gated before it reaches the visual tokens.

## Exit codes and failure shapes

| Code | Meaning |
|---|---|
| `0` | Success. |
| `1` | The command ran and failed. JSON mode: `{"ok": false, "error": ...}`. Text mode: `theteam <command>: <reason>` on stderr. Never a traceback. |
| `2` | A usage error argparse rejected before the command ran. |

**One deliberate exception:** a bare `theteam comment` exits **1**, not 2. Its subparsers are
`required=False` specifically so the call reaches the command, which prints its own usage error
and returns the 1 that the table names for a usage mistake. This is intentional; the next agent
to read `cli.py` should not "fix" it back to 2.

`KeyboardInterrupt` returns 1, except in `watch`, where Ctrl-C is how a watch loop is meant to
end and returns 0.

## Environment variables

| Variable | Effect |
|---|---|
| `THETEAM_PROJECT_ROOT` | Default for `--project-root`. Falls back to `$PWD`. |
| `THETEAM_METRICS_PORT` | Default for `serve --port`. Falls back to `8000`. |
| `THETEAM_STATE_DIR` | Overrides the whole state directory. The test suite and containers use it to point at a scratch tree. |

## State directory

State lives in `<project_root>/.omp/theteam`, resolved in exactly one place (`theteam/state.py`).
Tasks are plain YAML under `.omp/theteam/tasks/`, and they are yours: read them, edit them,
delete them. `theteam run` holds no state you cannot delete.

There is no database requirement. `psycopg2` is an optional extra for PostgreSQL deployments and
nothing in the default path needs it.

## Architecture and delivery order

[`ARCHITECTURE.md`](ARCHITECTURE.md) is the source of truth: what the product promises, the full
command surface, the trust surface and its failure modes, the code layers, and the milestone
order. Two rendered diagrams sit beside it:

| Diagram | Renders | File |
|---|---|---|
| System architecture | package layout, layers, entry points | [`diagrams/active-usage-architecture.html`](diagrams/active-usage-architecture.html) |
| Delivery order | M0–M6 and their gates | [`diagrams/active-usage-milestones.html`](diagrams/active-usage-milestones.html) |

Both diagrams are generated from the JSON next to them. **The JSON is authoritative; the HTML is
the rendered view.** Edit the JSON, then regenerate.

## Development

```bash
python -m pytest -q                  # 744 tests
bash scripts/check_invariants.sh     # the engineering invariant gate, 6 checks
```

CI (`.github/workflows/ci.yml`) installs from `pyproject.toml` on Python 3.9–3.12 and runs the
same three things: the suite, an import check, and the invariant gate.

## Milestone history

| Milestone | What it established |
|---|---|
| **M0** — the team cannot lie | Removed `MockAPI` and the code paths that could return a plausible-looking value on a failure. Every later milestone assumes this. |
| **M1** — reach it from a shell | `cli.py` as the single entry point, one state-directory resolver, `bootstrap`. Deleted `__main__.py`. |
| **M2** — tasks are YAML | One task store, in your repo. Deleted the legacy loader and the `subskills/task_stack` tree. |
| **M3** — create, edit, delete | The single-task write surface, validated at write time. |
| **M4** — the loop is safe | Wired `CircuitBreaker`, `ResourceLimiter`, `AgentIsolation`, and the audit chain into execution. `theteam history`. |
| **M5** — the team comments | `advisory/` reads a real OMP session and speaks when there is something to say, or reports why it did not. |
| **M6** — the terminal shows the truth | The terminal renderer, stdlib only, over the unchanged machine surface. |
| **M7** — the documentation tells the truth | This file and the command surface. Brought every document current against the code, corrected the diagrams, and fixed the `watch --json` inconsistency. |

M7 is a documentation milestone, not a product milestone. It is deliberately not in Part 6 of
`ARCHITECTURE.md`, which tracks delivered product milestones.

## What this project is not

There is no web dashboard, no multi-tenancy, no Kubernetes deployment, no ML-based scheduling,
and no Grafana integration. None of those are planned, none are in the tree, and none are in
`ARCHITECTURE.md`. An earlier version of this file promised all of them; that section was
removed rather than carried forward, because a roadmap a project does not have is a lie a reader
acts on.

## Plan evaluation (M7)

The milestone brief asked whether the plan, the diagrams, and the code still agreed. They did
not. This is the audit, so a reader can check it without re-running the work.

| Artifact | What it claimed | What was actually true |
|---|---|---|
| `ARCHITECTURE.md` Part 6 | M0–M6, seven milestones | Correct. M6 was added in its own milestone. |
| `diagrams/active-usage-milestones.json` | "Six milestones", nodes `m0`–`m5` | **M6 was absent.** The diagram stopped one milestone behind the plan. |
| `diagrams/active-usage-architecture.json` | Grounded in `theteam/subskills/task_stack` | **The directory was deleted in M2**, and the `components` array still listed `TaskStore` and `TaskManager`, which are not modules in the tree. |

Conflict order, per `ARCHITECTURE.md:12`: the document defines intent, the diagrams define
rendered shape, the running code defines fact. Where a document and the code disagree, the code
is the defect. So:

- **Changed the milestones diagram**, not the plan. Part 6 was right; the diagram was stale.
  Added node `m6` and the edge `m5 → m6`, added a `Terminal` lane so M6 has its own row, and
  updated `meta.subtitle` from "Six milestones" to "Seven". The `focus` list of the "Full
  pipeline" view now includes `m6` as well.
- **Changed the architecture diagram**, because its ground truth was a deleted directory. Every
  component was re-derived from the actual `theteam/` import graph and every component now cites
  the file it came from. `TaskStore` and `TaskManager` are gone because they never existed as
  modules; `TaskRepository` (`theteam/tasks/repository.py`) and `StateStore`
  (`theteam/state.py`) replaced them. Arrows are real imports, verified against the source.

Two things a reader should know about the diagrams:

1. The architecture diagram is rendered at the `standard` quality profile, not `showcase`. Its
   12 components and 14 edges are factually correct and every source path is verified against
   git, but eight *composition* diagnostics remain at `showcase` (relationship crossings and
   label clearance, not factual errors). Fixing those is a geometry exercise in the renderer's
   domain, and shipping a diagram that draws a subsystem that does not import is the worse
   failure.
2. The workflow schema caps columns at `0..5`, so seven milestones cannot each own a column. M6
   shares column 5 with M5 and gets its own lane, which is how the renderer distinguishes it.

