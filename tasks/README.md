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

Observed 2026-10-01 by running each task with `theteam run --only <id>`.

| id | observed result |
|---|---|
| `project-integrity` | **ok** |
| `system-awareness` | **ok** — reports written, `.loop-state.json` fresh, grade computed |
| `maintenance` | **ok** |
| `ground-truth-audit` | refused by name — requires an OMP session |
| `doc-harmonization` | refused by name — requires an OMP session |
| `native-feature-loop` | refused by name — requires an OMP session |

The three `llm` refusals are correct behaviour, not failures: each returns a
named error and writes no output file, rather than synthesizing a result.

**UNKNOWN** — no `llm` phase has ever been observed producing output, on this
machine or any other in this repo. Their behaviour comes from their prompt
files and is a claim, not a measurement. They need an OMP session with a
provider bound to verify.

**Exit code is not evidence on its own.** One defect below shipped green: a
phase reported `ok` while writing nothing. Acceptance for a writing phase is
*artifact on disk*, checked after the run.

## Is each task project agnostic?

No. Measured, not assumed:

| task | project agnostic? | why |
|---|---|---|
| `project-integrity` | **partly** | `REQUIRED_DIRS`/`SCRIPTS`/`CONFIGS` name *this* repo's layout. Portable only to a repo shaped like this one. |
| `system-awareness` | **yes, after this change** | detected `theteam/core` by name, and wrote into `<root>/theteam/reports`, which existed only here. Both fixed and tested. |
| `maintenance` | **yes** | operates on `__pycache__`, `*.pyc`, `.loop-log` — conventions, not this project. |
| `ground-truth-audit` | **no** | its prompt names `README.md`, `ARCHITECTURE.md`, `theteam/*.md`, `scripts/check_invariants.sh` explicitly. |
| `doc-harmonization` | **yes** | consumes the audit's output path only. |
| `native-feature-loop` | **yes** | the prompt asks what exists and names no path of this project's. |

Every script resolves `PROJECT_ROOT` from `Path(__file__).resolve().parent.parent`,
so no absolute path is baked in. The coupling is in *what they check*, not *where they run*.

## Are they self-sufficient?

| task | self-sufficient | note |
|---|---|---|
| `project-integrity` | **yes** | needs only the project tree |
| `system-awareness` | **yes** | writes its own reports; needs 384MB |
| `maintenance` | **yes** | no inputs |
| `ground-truth-audit` | **no** | needs an OMP session |
| `doc-harmonization` | **no** | needs an OMP session **and** the audit's output |
| `native-feature-loop` | **no** | needs an OMP session; phases 2-4 consume files from earlier phases |

Two ordering facts that are **not enforced by the executor**:

1. `doc-harmonization` reads `ground-truth-audit`'s output. Its prompt says to
   stop if the file is missing — that is a prompt-level guard, not a code one.
2. `native-feature-loop` recon → implement → test → docs is sequential, and the
   handoff is by file. `execute_task` breaks on `phase_result["success"]` and
   nothing else, so a phase that "succeeds" without writing still lets the next
   one run.

Both are recorded, not fixed — see *Deliberate gaps* below.

## Optimisation and modularisation

**Done — three fixes, each with a measured before/after:**

1. `format_consistency` was the literal `0.8` on every project, worth 0.24 of
   the documentation component. It is now derived from per-file format analysis.
   Measured on this repo: **0.8 → 0.0055** (1 of 181 markdown files has both a
   TOC and consistent headings).
2. `analyze_architecture` detected `theteam/core` and `theteam/security` by
   name. Every other project scored zero on architecture for not being this
   repo. Now detects any conventional source root and any `security`/`auth`
   module.
3. `report_dir` was assumed to exist. The analyzer died with `FileNotFoundError`
   on its first write against any other project. Now created.

**Not needed:**

- **Merging `project-integrity`'s two phases.** Their `REQUIRED_DIRS` overlap,
  but only phase 1 JSON-parses the configs — merging would silently drop config
  validation. Kept separate, with the reason in the task file.
- **Merging `system-awareness` into `ground-truth-audit`.** SA counts files and
  headings; GTA compares claims against code. Different questions.
- **Splitting `system-awareness`.** It runs four analyses in one process, which
  is why it needs 384MB. Splitting is the right move when it outgrows that, not
  before.

**Deliberate gaps, recorded not fixed:**

- No `depends_on:` field. Exactly one handoff exists between `llm` phases; a
  general mechanism for one case is the abstraction this repo keeps rejecting.
- `scripts/loop_reporter.py` and `scripts/loop_state.py` have zero task
  importers and use `os.getcwd()` rather than `__file__`. Operator tooling, not
  tasks — left in place.
- `.loop-state.json` carries two `last_execution` fields, one nested and
  current, one top-level and frozen. Both stores agree on score and grade.
  Pre-existing, outside the fixes above.