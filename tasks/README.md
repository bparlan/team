# Tasks

Registered tasks for the `theteam` skill. One YAML file per task, named
`task-<id>.yaml` — the `task-` prefix is what `TaskRepository` looks for, so a
task file without it is invisible to the runner.

## Current tasks

Every row was produced by running the task, not by reading its YAML — see
[Verified behaviour](#verified-behaviour) for the evidence and the two defects
that behaviour exposes.

| id | order | kind | what it does |
|---|---|---|---|
| `project-integrity` | 0 | 2 scripts | directories, configs (parsed, not just present), scripts, tools, Python version, loop-state freshness |
| `system-awareness` | 2 | script | 4-phase analysis (structure, documentation, architecture, infrastructure) with health scoring |
| `maintenance` | 3 | script | cache cleaning, log rotation, temp-file cleanup |
| `ground-truth-audit` | 5 | llm | reports where a documented claim is contradicted by the code |
| `doc-harmonization` | 6 | llm | consumes the audit, makes the documents true |
| `native-feature-loop` | 7 | llm×3 + script | skeptic recon → pragmatist implement → pytest → docs sync |

`order` is the task's own `order:` field, and the gaps are deliberate — an
order is a position, not a rank, so removing a task does not renumber the rest.
`theteam tasks` displays the *sequence position* (0-5 here) rather than the
field, which is why the two differ.

## Task format

```yaml
id: <task-name>
name: <display name>
type: analysis | monitoring | maintenance
priority: 1-10          # 10 = highest
description: >-
  What this task does, and what it does not.
failure_handling: retry | skip | stop
context:
- Input the task needs
expected_output: 'What constitutes success'
phases:
  - name: <phase name>
    # exactly one runner per phase:
    script: scripts/<runner>.py     # a script phase
    # runner: llm                   # ...or a model phase
    # member: architect
    # prompt_file: prompts/<file>.md
    args: []
    timeout_seconds: 300
    memory_limit_mb: 64
    writable_project: false        # true only if the phase writes into the repo
order: <n>              # execution position; lower runs first
```

`order` is the only ordering source. `TASK_ORDER` was removed when ordering
moved onto each task — nothing reads it, and nothing writes it.

A phase names **either** `script` or `runner: llm`, never both and never
neither; the executor refuses a phase that names no runner, by name.

## Usage

```bash
theteam tasks                     # list every task and its state
theteam run                       # execute everything currently due
theteam run --only <task-id>      # one task, ignoring the rest (bypasses the schedule)
theteam loop <id> --interval <s>  # schedule one task to run on an interval
theteam serve                     # run due tasks on a tick, publishing /metrics
theteam history                   # success rate, last run, last failure
```

There is no `theteam --loop start`. The scheduler is `theteam loop` for one
task and `theteam serve` to run whatever is due.

A task is `not scheduled` until you schedule it, so `theteam run` on a fresh
clone runs nothing:

```bash
theteam loop project-integrity --interval 3600
```

### Running a phase's script directly

Bypasses the executor and its isolation — useful for debugging, but you lose
the memory bound, the network bound, and user isolation:

```bash
python3 scripts/loop_health_check.py
python3 scripts/loop_infrastructure_check.py
python3 scripts/loop_maintenance.py
python3 scripts/sa_runner.py self-correct   # runs the 4-phase analysis
python3 scripts/sa_runner.py health-check   # reads state, analyses nothing
python3 scripts/run_pytest.py
```

`llm` phases have no direct equivalent — they need an OMP session, so
`theteam run --only ground-truth-audit` must be run inside one.

## Phase kinds

| in YAML | runs | bound | isolation |
|---|---|---|---|
| `script:` | a Python file | `memory_limit_mb`, `timeout_seconds` | Docker, project mounted read-only unless `writable_project: true` |
| `runner: llm` | a team member reading `prompt_file` | none — there is no process | none needed |

`script:` is for anything deterministic. `runner: llm` is for judgement.
`native-feature-loop` keeps its test phase a `script:` on purpose: a test suite
is deterministic and must not be judged by a model.

## Verified behaviour

Observed on 2026-10-01 by running each task with `theteam run --only <id>`,
after the two fixes recorded below.

| id | observed result |
|---|---|
| `project-integrity` | **ok** |
| `system-awareness` | **ok** — 40 reports on disk, `.loop-state.json` fresh, grade D |
| `maintenance` | **ok** |
| `ground-truth-audit` | refused by name — requires an OMP session |
| `doc-harmonization` | refused by name — requires an OMP session |
| `native-feature-loop` | refused by name — requires an OMP session |

The three `llm` refusals are correct behaviour, not failures: each returns a
named error and writes no output file, rather than synthesizing a result.

Per-phase, through `TaskExecutor.execute_phase`: 10 phases, 0 problems from
`_phase_problem`. `loop_health_check` rc 0, `loop_maintenance` rc 0,
`run_pytest` rc 0, `loop_infrastructure_check` rc 0, `sa_runner self-correct`
rc 0.

**UNKNOWN** — the `llm` phases have never been observed producing output, on
this machine or any other in this repo. Their descriptions above come from
their prompt files and are claims, not measurements. They need an OMP session
with a provider bound to verify.

**Exit code is not evidence on its own.** One of the defects below shipped
green: a phase reported `ok` while writing nothing. Acceptance for any writing
phase is *artifact on disk*, checked after the run.

### Fixed A — `git` was required and never used

`loop_infrastructure_check.py` required `git` in `PATH`, but the isolation
image `theteam:p4final` has no `git`, so phase 2 exited 1 on every
containerised run, on every machine. It passed standalone only because the
*host* has `git` — that asymmetry is why it never surfaced outside the
executor.

`git` appeared nowhere except its own presence test. It has been removed, so
`REQUIRED_TOOLS` is now `["python3"]`. Verified: `project-integrity: ok`
through the executor.

If the image should carry `git` instead, that is a Dockerfile change rather
than a task change — and the entry belongs back in `REQUIRED_TOOLS` with it,
because an infrastructure check that cannot see the VCS it is meant to verify
is checking a fiction.

### Fixed B — `system-awareness` was killed, then shipped a hollow success

Two defects, found in that order.

**The bound.** The phase declared `memory_limit_mb: 64` and was OOM-killed at
exit 137 on every run. Measured floor *through the executor*:

| limit | exit |
|---|---|
| 64MB | 137 |
| 256MB | 137 |
| 320MB | 0 |
| 384MB | 0 |

320 is the lowest bound measured to survive the executor, and the executor is
what runs the task. A bare `docker run --memory=256m` succeeds where the
executor is killed at 256, so this floor has to be measured through the
executor — a direct invocation understates it.

**The hollow success the memory fix was hiding.** With the bound fixed, the
phase still reported `ok` while writing **nothing**: zero reports, and
`.loop-state.json` untouched. It has 7 write sites and never declared
`writable_project: true`, so the container's writes failed while the script
still exited 0. `writable_project: true` is now declared, as in
`maintenance`.

A task reporting success having done nothing is the defect class this repo
exists to prevent, and it survived one layer above the `print_help` no-op
found earlier. It is why the acceptance check is the artifact, not rc 0.

Both defects are the same shape: **a check that reports a truth nobody
verifies.** A check that can only fail is not a check, and a bound that always
kills is not a bound.

### Observing the bounds

Every phase logs the exact `docker run` it used, at INFO level:

```
INFO theteam.core.agent_isolation: isolated agent run: docker run --rm
  --network none --memory 320m --cpus 1.0 ... --mount type=bind,...
```

`--memory 320m` and the mount mode make both defects legible in plain sight,
before either check has run.

### Known issue, not fixed

`.loop-state.json` carries two `last_execution` fields — a nested one, fresh
and correct, and a top-level one frozen at `2026-09-30T22:35`. Both stores
agree on score `0.5551` and grade `D`. Pre-existing, outside the two fixes
above.