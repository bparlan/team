# theteam onboarding

How to adopt theteam. The full command reference is the root [`README.md`](../README.md); the
design is [`ARCHITECTURE.md`](../ARCHITECTURE.md).

> The previous version of this file documented a `subskills/task-stack/` daemon, a curses
> `ui/terminal_ui.py`, `scripts/loop_controller.py`, and a `ui/task_stack_adapter.py`. All four
> were deleted — the task stack became `theteam/tasks/` (YAML only), the TUI became
> `theteam/ui/terminal.py` driven by `theteam watch`, and the adapter was removed in M2 as a
> second source of truth. Nothing below refers to them.

## For users

```bash
pip install -e .                  # installs the `theteam` console script
cd /your/project
theteam bootstrap                 # once per project: writes theteam.config
theteam status                    # roster, task counts, audit chain
theteam watch status --once       # the same, rendered as one frame
theteam run                       # execute everything due
```

There is no daemon to start. `theteam run` executes due tasks once, and
`theteam serve` is the only command that opens a port — it runs the same due
tasks on an interval and publishes `/metrics`.

## For agents

```bash
# Validate the project config (needs theteam/ on the path — the script
# imports `bin.utilities` as a top-level package)
PYTHONPATH=theteam python3 theteam/bin/theteam_config.py validate "$(pwd)/theteam.config" --json

# Read the project context
python3 theteam/workflow/context_aggregator.py "$(pwd)"
```

The full discussion protocol — member spawning, the synthesis pass, report rendering, and the
permitted-skills boundary — is in [`SKILL.md`](SKILL.md). Do not follow a paraphrase of it; a
drifting second copy of the protocol is what this file used to be.

## Package layout, as it is now

```
theteam/
├── cli.py                    # the only entry point; `theteam` console script
├── state.py                  # the single state-directory resolver
├── __init__.py               # skill entry: bootstrap, discussion, context analysis
├── monitor.py                # `--monitor`: what changed between two frames
├── tasks/                    # the task surface
│   ├── repository.py         # YAML store — the ONE store
│   ├── executor.py           # runs one phase, under the safety layer
│   ├── scheduler.py          # `serve`'s clock — sweeps due tasks on an interval
│   └── runners/llm.py        # the second phase kind, beside `script`
├── core/                     # safety, telemetry, persistence
│   ├── circuit_breaker.py    # safety
│   ├── resource_limiter.py   # safety
│   ├── agent_isolation.py    # safety
│   ├── audit.py              # safety
│   ├── audit_chain.py        # hash-chained audit, read by `status`
│   ├── metrics.py            # `/metrics` and `/health`
│   ├── backup.py             # reached by scripts/backup.py
│   ├── health_monitor.py
│   ├── event_bus.py, event_log.py, rate_limiting.py
│   └── state_manager.py, checksum.py, database.py, wal.py,
│       transactions.py, correlation.py, member.py, postgres_cluster.py
├── advisory/                 # commentary layer
│   ├── session_reader.py, selector.py, commentary.py, roster.py,
│   │   context_slice.py, manager.py
├── workflow/
│   └── context_aggregator.py
├── ui/
│   ├── terminal.py           # the trust surface, rendered; `theteam watch`
│   └── components/           # design tokens and panel widgets
├── security/                 # path validation, audit, secrets
├── bin/                      # config helpers (see CLI.md)
└── tests/                    # 656 tests
```

M10 removed the other two schedulers. `core/unified_loop.py` and
`core/task_contract.py` are gone, and `workflow/` now holds only the context
aggregator. `tasks/scheduler.py` is the single scheduler — see
`ARCHITECTURE.md` §2.3 for why, and for the two modules that lost their importer
when the loop went and were deliberately kept.

`theteam/subskills/` no longer exists. The task stack that lived in `subskills/task_stack/` moved
to `theteam/tasks/` in M2; the directory itself was deleted during the M7 review, when the four
design files it held were archived verbatim to
`archive/docs-theteam/pre-m0-reports/`. An earlier version of this file still told readers the
directory was present.

## Configuration

`theteam.config` lives in the project root and is committed to the project's own repo:

| Key | Meaning |
|---|---|
| `behavior.*` | Skill behavior: `block_edits_without_plan`, `pre_analysis_search`, `enable_persona_comments`. `option_selection_required` is retired, read by nothing, and kept only so old configs still validate. |
| `team.*` | Member roster: id, role, expertise, voice |
| `permitted_skills` | Hard boundary on what members may invoke (default `ponytail`, `evolve-skills`, `code-search`) |
| `output.*` | `report_dir` (default `.omp/theteam/reports`), `keep_last` |

Regenerate it with `PYTHONPATH=theteam python3 theteam/bin/theteam_config.py init ...`, never by
hand-editing, so validation runs before anything reaches disk.

## State

Everything theteam writes goes under `<project_root>/.omp/theteam`, resolved in one place
(`theteam/state.py`). Set `THETEAM_STATE_DIR` to point that whole tree elsewhere — the test
suite does exactly this.

## Troubleshooting

**`theteam status` reports no roster.** The project is not bootstrapped. Run `theteam bootstrap`.

**`theteam discuss` fails with an OMP error.** Correct behavior. `discuss` refuses to run
outside an OMP-hosted session rather than inventing an opinion. Run it from inside OMP.

**`theteam watch` shows `absent` and `never run`.** Also correct: nothing has been measured yet.
See the output-honesty table in the root README.

**A helper script fails with `No module named 'bin'`.** It needs `PYTHONPATH=theteam` in front
of the command. See [`CLI.md`](CLI.md).
