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
theteam --help          # twelve subcommands
theteam <command> --help
```

| Command | Summary |
|---|---|
| `bootstrap` | Generate a team for this project. |
| `status` | Roster, state directory, task counts, audit chain. |
| `discuss <topic>` | One-shot team discussion, this turn only. Deterministic member selection: at most 4 members speak, and a truncated selection is reported. |
| `serve` | Runs due tasks on an interval and serves Prometheus `/metrics` and `/health`. The only server. |
| `loop <task_id>` | Schedule one registered task on an interval. |
| `tasks` | List every task and its state. |
| `run` | Execute everything currently due. |
| `history` | Per-task success rate, last run, last failure. |
| `task create\|edit\|delete\|show` | Single-task operations. |
| `comment on\|off\|status` | Continuous in-context commentary. |
| `watch status\|tasks\|history` | The trust surface, rendered in the terminal. `--once`, `--interval`, `--monitor`, `--json`. |
| `manager` | Grow the roster from a topic. `--topic` proposes and writes nothing; `--apply` persists. `--status` states why every member is on the roster; `--reset` restores the bootstrapped team. |

Global flags: `--json` is accepted on either side of the subcommand; `--project-root` only before it
(`theteam --project-root PATH status`). Passing `--project-root` after the subcommand exits 2 with
`unrecognized arguments` — measured, not inferred.

`watch --monitor` is the change monitor: it diffs each frame against the one before it and names
the transitions worth noticing (a breaker reaching `open`, an audit chain leaving `intact`, a task
leaving the registry). It is a flag on the same payload, not a new view, and it is off by default.
Full semantics are in the root [`README.md`](../README.md) under **Watching for change** and in
`ARCHITECTURE.md` §2.

## Testing the surface yourself

`scripts/smoke_cli.py` exercises every subcommand above against a throwaway project in a temp
directory — it never touches this repo's `.omp/`. Copy the flags from `--help`, not from a doc;
the script's checks are quoted from real `--help` output.

```bash
python3 scripts/smoke_cli.py           # human-readable, 23 checks
python3 scripts/smoke_cli.py --json    # machine-readable
python3 scripts/smoke_cli.py --keep    # leave the temp project for inspection
```

Exit 0 when every command behaved. A command that exits non-zero **and names its reason** is a
pass — refusing to run without a provider, without Docker, or without a live OMP session is the
correct behaviour, not a failure (§3.3). A command that exits non-zero with no reason is the
failure this exists to catch.

The checks cover: `status`, `tasks`, `history` (including `--task` on a missing task), `manager`
(`--status`, `--topic`), `run` (`--dry-run`, `--only` on a missing task), `watch` (all three
surfaces, `--once`, `--json`, `--monitor`), `comment` (`status`/`on`/`off`), `task`
(`show`/`delete`/`create --path`/`edit --patch`), `loop` (`--interval`), `discuss`, and
`bootstrap`.

Two commands are not covered, deliberately: `serve` blocks forever and `watch` without `--once`
loops forever. Test `serve` by hand:

```bash
theteam --project-root "$T" serve --port 8080 --tick-seconds 5 &
sleep 10
curl -s localhost:8080/health     # {"status": "healthy"}
curl -s localhost:8080/metrics | head -4   # theteam_tasks_* counters
kill %1
```

## Running the tasks themselves

`smoke_cli.py` proves the commands answer. It does not prove a task *ran* — those are different
claims, and the second one needs Docker. Run these from the repo root, against this project:

```bash
# The two containerized script tasks. Both should report result "ok".
python3 -m theteam.cli --json run --only project-integrity
python3 -m theteam.cli --json run --only maintenance

# The LLM tasks. Outside an OMP session each is *skipped*, not failed.
python3 -m theteam.cli --json run --only doc-truth
python3 -m theteam.cli --json run --only native-feature-loop
python3 -m theteam.cli --json run --only root-organization
```

**`smoke_cli.py` reports which tasks can actually run on your machine.** It reads the Docker
gate directly — `AgentIsolation.available()` — and derives the spawn requirement from each task's
own phase kinds, then prints a readiness line per task. An unrunnable task is a *named refusal*
(`refused: needs Docker (no daemon answering)`), never reported as though it ran.

It used to read `hasattr(theteam, "default_api")` and report every `llm` task as `refused:
needs a bound OMP provider`. That was true of the code and useless to a reader: no environment
binds that symbol, so the column said four of six tasks were permanently unrunnable and gave no
way to learn the command that runs them. The gate now names what is actually required — a session
to spawn the member — and those tasks report runnable.

```
environment: docker=True session_spawn_required=True
task                     phases  kinds                      worst   readiness
project-integrity        2       scr,scr                    600     runnable: runnable here
maintenance              1       scr                        300     runnable: runnable here
doc-truth                2       llm,llm                    600     runnable: runnable here (llm phases need a session to spawn)
root-organization        5       llm,llm,llm,llm,llm            1500    runnable: runnable here (llm phases need a session to spawn)
native-feature-loop      4       llm,llm,scr,llm            1800    runnable: runnable here (llm phases need a session to spawn)
```

Read this first. It tells you what the rest of the table can and cannot demonstrate on your box.

Measured on this machine, Docker 28.1.1:

| task | phases | kind | worst case | bare `theteam run` |
|---|---|---|---|---|
| `project-integrity` | 2 | script ×2 | 600s | `ok` — both phases `rc=0` |
| `maintenance` | 1 | script | 300s | `ok` — cache cleaned, logs rotated |
| `doc-truth` | 2 | llm ×2 | 600s | `awaiting` — names the `audit` phase |
| `root-organization` | 4 | llm ×4 | 1200s | `awaiting` — names the `scan` phase |
| `native-feature-loop` | 4 | llm ×3 + script | 1800s | `awaiting` at `recon` |

**Two outcomes for an `llm` task, and neither is a failure.** `theteam run` does not spawn. It
resolves which phase is next and reports `awaiting` with everything the session needs. A phase is
done when its declared output exists and is not empty, so re-running the command is always safe: it
either names the next unfinished phase or reports the task complete.

```
$ theteam run --only root-organization
root-organization: awaiting (0.01s) (session must spawn the next phase)
  root-organization: awaiting a member
    spawn:  sonic (as devops)
    prompt: prompts/root-organization-scan.md
    write:  .omp/theteam/reports/root-organization-scan.md
0 ran, 0 skipped, 0 failed in 0.01s
```

`spawn:` is the **agent type** a session must spawn; the parenthetical is the
**persona** from `theteam.config`, which exists only for the prompt's framing.
They are different: `agent(prompt, agent="devops")` raises `Unknown agent`,
because the spawnable types are `advisor`, `default`, `designer`, `explore`,
`scout`, `task`, `Tester`, `vision`, `reviewer`, `security-reviewer`,
`librarian`, `sonic`. A task file declares both, `agent_type:` and `member:`.

**A stale artifact reads as done.** That is the deliberate trade for the
simplest completion signal that works: a non-empty declared output *is* the
evidence. To redo a phase, delete its output file.

**The other non-outcome, `dependency_unmet`.** A task may declare
`depends_on: [<task id>, ...]` and runs only when every dependency's last recorded result is `ok`.
Two cases refuse: the dependency has **never run** (no evidence it succeeded) or it last came back
anything but `ok` — including `skipped`, because a skipped dependency did not do its work and
whatever it would have written is not on disk. A dependency that ran and reported *findings* is
`ok`; whether the project has problems is a different question.

The refusal counts against no breaker and writes no `task_start`: a task waiting on a prerequisite
has not been attempted. `order` is unaffected — it still only sorts a listing.

```
$ theteam run --only root-organization --json
{"ran": 0, "skipped": 1, "awaiting": 0, "results": [{"id": "root-organization",
  "result": "skipped", "detail": "dependency_unmet",
  "hint": "unmet: project-integrity (last result: failed). Run the dependencies first: theteam run --only <dependency>"}]}
```

**Check `context` in every payload.** Each run reports
`context: {written: true, context_bytes: N}` — the per-run context file (§5.6). A
missing `written` means the run happened without leaving the record it is supposed
to leave, which is the failure mode this whole product is built against.

**A script task needs Docker, and says so by name.** With no daemon,
`AgentIsolation.available()` returns False and `execute_phase` refuses with
`container isolation unavailable (no Docker daemon), and an unguarded run is not
permitted` (`tasks/executor.py:209-212`). It does not fall back to running the
script on the host. Not reproducible on a Docker-equipped machine — read the
source, or run the suite, which covers it.

**`worst_case_seconds` is what the schedule guard compares against.** A task whose
interval is shorter than its worst case is refused at `theteam loop` time
(see [Schedule integrity](#24-schedule-integrity) in ARCHITECTURE.md).

## The helper scripts

Two scripts remain, in different places. `theteam_config.py` is in `theteam/bin/`
and is part of the package; `theteam_report.py` is at repo-root `bin/`, outside it.
Neither is part of the user-facing CLI. The config script imports `bin.utilities`
as a top-level package, so it needs `theteam/` on the path; the report script
imports only the standard library and needs nothing.

```bash
# Validate a project config
PYTHONPATH=theteam python3 theteam/bin/theteam_config.py validate theteam.config --json

# Build a report from member notes and a synthesis file
python3 bin/theteam_report.py build \
  --topic "..." --notes-dir /tmp/notes --synthesis /tmp/synthesis.json \
  --out /tmp/report.md --project "<name>" --expected-ids architect,pragmatist
```

Running them as `python3 theteam/bin/theteam_config.py` without `PYTHONPATH=theteam` fails with
`ModuleNotFoundError: No module named 'bin'`. That is how the skill imports them internally
(`from .bin.theteam_config import ...`), not how a user runs them.
