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

Observed 2026-10-01 by running each task with `theteam run --only <id>`. The
run count is the final measured sweep, not the history at the time of writing —
`theteam history` moves as tasks are re-run.

| id | observed result | runs | rate |
|---|---|---|---|
| `project-integrity` | **ok** | 10 | 80.0% |
| `system-awareness` | **ok** — score **0.5545**, grade **D**, six reports + `.loop-state.json` written | 7 | 14.3% |
| `maintenance` | **ok** | 7 | 100.0% |
| `ground-truth-audit` | refused by name — requires an OMP session | 2 | 0.0% |
| `doc-harmonization` | refused by name — requires an OMP session | 2 | 0.0% |
| `native-feature-loop` | refused by name — requires an OMP session | 2 | 0.0% |

**The rates are historical, not current.** `project-integrity`'s two failures
are both from before the M12 fix and neither has recurred in eight consecutive
passes since. `system-awareness`'s five failures are the breaker deadlock and
the 300s timeout documented below, both fixed; its current state is one
consecutive failure and a closed breaker. The three `llm` tasks are 0.0% because
they have never had the session they require, not because they fail when run.

The three `llm` refusals are correct behaviour: each returns a named error and
writes no output file, rather than synthesizing a result.

**UNKNOWN** — no `llm` phase has ever been observed producing output, on this
machine or any other in this repo. Their behaviour comes from their prompt
files and is a claim, not a measurement. They need an OMP session with a
provider bound to verify.

**Exit code is not evidence on its own.** One defect below shipped green: a
phase reported `ok` while writing nothing. Acceptance for a writing phase is
*artifact on disk*, checked after the run.

### The circuit breaker, and a bug it was hiding

Each task has a breaker that opens after **5 consecutive failures**. While open,
the task is skipped with the literal `breaker_open` and is **not** counted
against itself — so the trip persists until something actually runs green.
State lives in `.omp/theteam/task-schedule.json` and outlives the process.

`system-awareness` was found at 0.0% over 5 runs, skipping `breaker_open` every
time — permanently unrunnable. Root cause: `TaskExecutor._breaker` reconstructs
the breaker per process and replays `record_failure()` N times, and replaying
re-stamps `recovery_deadline = now + 60s`. The window was therefore measured
from **process start**, not from the original failure. A CLI invocation lives
milliseconds and `serve` rebuilds the executor every tick, so neither could ever
hold the window open. Proved by measurement: a 140-second
`serve --tick-seconds 20` logged `closed -> open` on every tick and ran the task
zero times.

Fixed by restoring the deadline from `last_run[task_id].at` — already persisted
— rather than recomputing it. Defended by `test_breaker_recovery_window.py`.

**What the breaker had been hiding:** with it admitting the task again,
`system-awareness` still failed — `timed out after 300s`. The remembered
failures were OOM-kills from before the 384MB bound landed, but under them was a
second defect: the analysis takes **117s bare on the host and ~360s inside the
executor container** (single CPU, pid limit, read-only rootfs). `timeout_seconds`
is now 600, measured. The bare-host number is the trap — it says nothing about
where the phase actually runs.

### Skips were fabricating state

The same investigation found that both skip paths in `run_due_tasks` called
`record_run`, which writes `at = now` and writes `breaker`/`consecutive_failures`
even when the caller never measured them. Two consequences, both reproduced:

1. **The recovery window could be re-anchored forever.** Because the window is
   anchored to `at`, any retry faster than 60s moved it forward again. Measured
   before the fix: three consecutive skips each pushed the deadline a further
   60s out. A `while ! ok; do theteam run --only <id>; done` loop, or a
   `serve --tick-seconds 30`, could never have recovered.
2. **A real breaker reading was erased.** The config-problem skip passes no
   breaker arguments, so `breaker: null` overwrote a genuine `open` with five
   consecutive failures. Reproduced: a task seeded open ten minutes earlier came
   back `breaker: null` after one skipped run.

`record_skip` now owns both skip paths. It preserves `at` and preserves the
breaker fields when they were not measured, so a skip records only that nothing
ran and why. Defended by `test_record_skip_preserves_at.py`.

## Project portability, measured

Two questions, answered by grep and by running the code rather than by reading
the table above.

### Hardcoded developer paths

Five scripts carried `~/devcode/team/...`. `check_invariants.sh` check 3 scanned
`theteam/` only, so none of them tripped it — the guard existed and pointed at
the wrong tree.

| site | was | now |
|---|---|---|
| `sa_runner.py:236` | `"~/devcode/team/tasks"` default state value | `"tasks"` |
| `security_policy.py:26,164` | `os.path.expanduser("~/devcode/team/tasks")` | `os.path.join(PROJECT_ROOT, "tasks")` |
| `task_executor.py:31` | `os.path.expanduser(...)` | `os.path.join(project_root, "tasks")` |
| `loop_state.py:45` | `"~/devcode/team/tasks"` default state value | `"tasks"` |

The two default-state values were a different defect from the two resolution
sites. A resolution site *uses* the path, so on any other machine it pointed at
a developer's home directory. A default state value is only written when
`.loop-state.json` is absent, and nothing reads the field — so it was a latent
wrong value rather than a live one. Both are recorded as project-relative now.

Check 3 now scans `theteam/` **and** `scripts/`. Verified by mutation: adding
one hardcoded path to `scripts/loop_health_check.py` turns the gate red.

**Scope of that fix, stated honestly.** Every script that a *task actually runs*
now resolves its own root from `__file__`. Two of the four fixed sites are in
`security_policy.py` and `task_executor.py`, which nothing imports — so those
two were unreachable rather than live, and correcting them changed no
execution path. `loop_state.py` and `loop_reporter.py` still use
`os.getcwd()` and are still orphans. The gate now covers `scripts/`, so a new
hardcoded path fails the build; it does not prove the orphan scripts are
reachable, and they are not.

### Orphan scripts

1003 lines across four scripts that no task invokes and nothing in `theteam/`
imports:

| script | lines | real importers | state |
|---|---|---|---|
| `sa_runner.py` | — | 2, both **tests** | live — a task runs it |
| `security_policy.py` | 187 | 0 | orphan |
| `task_executor.py` | 265 | 0 | orphan, **and broken** |
| `loop_state.py` | 401 | 0 | orphan |
| `loop_reporter.py` | 150 | 0 | orphan |

`task_executor.py` cannot even be imported: it does `from task_archive import
TaskArchive`, and `task_archive.py` was deleted in M0. Confirmed by stashing my
edit — it failed identically before it.

`CHANGELOG.md:971` recorded `loop_reporter.py` and `task_executor.py` as
imported-by-nothing. **That still holds** — and the check it records was
correct. What the entry did not know is that `loop_state.py` and
`security_policy.py` are in the same state: 588 more lines, also imported by
nothing.

Left in place. They are operator tooling, and the one protection worth keeping
was already ported out of the deleted variant. But the honest count is four
orphans, not two.

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
- Four orphan scripts totalling 1003 lines — `security_policy.py`,
  `task_executor.py`, `loop_state.py`, `loop_reporter.py` — imported by nothing,
  one of them unable to import at all. `loop_state.py` and `loop_reporter.py`
  still resolve from `os.getcwd()` rather than `__file__`. Operator tooling,
  left in place; see *Orphan scripts*.
- `.loop-state.json` carries two `last_execution` fields, one nested and
  current, one top-level and frozen. Both stores agree on score and grade.
  Pre-existing, outside the fixes above.
- `project-integrity`'s two failures are both from before the M12 fix, and
  neither has recurred in eight consecutive passes since. Cause read from the
  execution log, not guessed: phase 2 returned `FAIL: Required tool not found in
  PATH: git`, because `git` was in `REQUIRED_TOOLS` and is not visible inside
  the isolation container. `REQUIRED_TOOLS` is now `["python3"]`. This is
  resolved, and it is kept here rather than deleted because the historical rate
  in `theteam history` still shows it until the old runs age out.
- No command resets a tripped breaker, and `breaker_open` is the only reason
  recorded once a breaker trips — so the *original* failure is lost from the
  schedule. A single `last_run` entry per task cannot hold both. The 60s window
  itself clears on its own now, including under repeated invocation, because
  skips go through `record_skip` and do not restamp `at`; see *Skips were
  fabricating state* for what that cost before.