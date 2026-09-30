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

Observed on 2026-10-01 by running each task with `theteam run --only <id>`.

| id | observed result |
|---|---|
| `project-integrity` | **failed (rc 1)** — phase 2, see Defect A |
| `system-awareness` | **failed (rc 137)** — OOM at its declared bound, see Defect B |
| `maintenance` | **ok** |
| `ground-truth-audit` | refused by name — requires an OMP session |
| `doc-harmonization` | refused by name — requires an OMP session |
| `native-feature-loop` | refused by name — requires an OMP session |

The three `llm` refusals are correct behaviour, not failures: each returns a
named error and writes no output file, rather than synthesizing a result.

Per-phase, through `TaskExecutor.execute_phase`: 10 phases, 0 problems from
`_phase_problem`. `loop_health_check` rc 0, `loop_maintenance` rc 0,
`run_pytest` rc 0, `loop_infrastructure_check` rc 1, `sa_runner self-correct`
rc 137.

**UNKNOWN** — the `llm` phases have never been observed producing output, on
this machine or any other in this repo. Their descriptions above come from
their prompt files and are claims, not measurements. They need an OMP session
with a provider bound to verify.

### Defect A — `project-integrity` phase 2 can never pass

`loop_infrastructure_check.py` requires `git` in `PATH`. The isolation image
`theteam:p4final` has no `git` (verified with
`docker run --entrypoint sh theteam:p4final -c 'command -v git'`). Every
containerised run exits 1 with
`FAIL: Required tool not found in PATH: git`, so this phase has always failed
under the executor, on every machine.

It passes standalone (rc 0) because the *host* has `git`. That asymmetry is why
the defect never surfaced outside the executor.

`git` is never used by the check beyond its presence test — it appears only in
`REQUIRED_TOOLS`. It is a decoration, not a dependency.

Two one-line fixes, deliberately not applied — both change what "project
integrity" means, which is a product decision:
- drop `git` from `REQUIRED_TOOLS`, or
- install `git` into `theteam:p4final`.

### Defect B — `system-awareness` is killed at its declared bound

`sa_runner.py self-correct` exits 137 under `memory_limit_mb: 64`. Measured
floor, by exit code under the same isolation policy:

| limit | exit |
|---|---|
| 64MB | 137 |
| 128MB | 137 |
| 256MB | 0 |
| 384MB | 0 |

Standalone the same script exits 0 in ~9s, so this only appears under the
executor. Raising the bound to 256MB would fix it, but that trades away an
isolation limit set deliberately under §5.4 — whether this task belongs in a
64MB budget is a product call, not a cleanup.

Both defects are the same shape: **a check that reports a truth nobody
verifies.** A check that can only fail is not a check, and a bound that always
kills is not a bound.

### Observing the bounds

Every phase logs the exact `docker run` it used, at INFO level:

```
INFO theteam.core.agent_isolation: isolated agent run: docker run --rm
  --network none --memory 64m --cpus 1.0 --read-only ... --mount type=bind,...
```

`--memory 64m` and the `ro` bind mount make both defects legible in plain
sight, before either check has run.