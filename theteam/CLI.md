# theteam CLI reference

**This file is a pointer, not a second reference.** The complete, verified command surface —
every command, flag, default, cap, exit code, and JSON shape — lives in the root
[`README.md`](../README.md) and in [`ARCHITECTURE.md`](../ARCHITECTURE.md) Part 2. Read those.

The previous version of this file documented `python3 theteam/__init__.py --bootstrap`,
`subskills/task-stack/orchestrator.py`, `scripts/loop_controller.py`, and
`theteam/ui/terminal_ui.py`. None of those exist any more: `__main__.py` and
`subskills/task_stack/` were deleted in M1–M2, `scripts/loop_controller.py` was never in the
tree, and `terminal_ui.py` was replaced by `theteam/ui/terminal.py`. A second CLI document is
exactly the kind of thing that drifts, so it does not live here.

## The surface, in one place

```bash
theteam --help          # eleven subcommands
theteam <command> --help
```

| Command | Summary |
|---|---|
| `bootstrap` | Generate a team for this project. |
| `status` | Roster, state directory, task counts, audit chain. |
| `discuss <topic>` | One-shot team discussion, this turn only. Deterministic member selection: at most 4 members speak, and a truncated selection is reported. |
| `serve` | Prometheus metrics endpoint. The only server. |
| `loop <task_id>` | Schedule one registered task on an interval. |
| `tasks` | List every task and its state. |
| `run` | Execute everything currently due. |
| `history` | Per-task success rate, last run, last failure. |
| `task create\|edit\|delete\|show` | Single-task operations. |
| `comment on\|off\|status` | Continuous in-context commentary. |
| `watch status\|tasks\|history` | The trust surface, rendered in the terminal. `--once`, `--interval`, `--monitor`, `--json`. |

Global flags: `--project-root PATH` and `--json`, both accepted on either side of the subcommand.

`watch --monitor` is the change monitor: it diffs each frame against the one before it and names
the transitions worth noticing (a breaker reaching `open`, an audit chain leaving `intact`, a task
leaving the registry). It is a flag on the same payload, not a new view, and it is off by default.
Full semantics are in the root [`README.md`](../README.md) under **Watching for change** and in
`ARCHITECTURE.md` §2.

## The helper scripts in `theteam/bin/`

Two scripts remain. They are helpers for the skill's config and report generation, not part of
the user-facing CLI. Note the invocation form: they import `bin.utilities` as a top-level
package, so they need `theteam/` on the path.

```bash
# Validate a project config
PYTHONPATH=theteam python3 theteam/bin/theteam_config.py validate theteam.config --json

# Build a report from member notes and a synthesis file
PYTHONPATH=theteam python3 theteam/bin/theteam_report.py build \
  --topic "..." --notes-dir /tmp/notes --synthesis /tmp/synthesis.json \
  --out /tmp/report.md --project "<name>" --expected-ids architect,pragmatist
```

Running them as `python3 theteam/bin/theteam_config.py` without `PYTHONPATH=theteam` fails with
`ModuleNotFoundError: No module named 'bin'`. That is how the skill imports them internally
(`from .bin.theteam_config import ...`), not how a user runs them.
