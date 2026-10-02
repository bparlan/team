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
| `project-integrity` | 0 | 2 scripts | directories, configs (parsed, not just present), scripts, tools, Python version, loop-state existence and parseability |
| `maintenance` | 3 | script | cache cleaning, log rotation, temp-file cleanup |
| `doc-truth` | 5 | llm ×2 | audit: reports where a documented claim is contradicted by the code. harmonize: consumes the audit, makes the documents true |
| `root-organization` | 6 | llm ×4 | devops scan → architect classify → skeptic decide → pragmatist report. `depends_on: [project-integrity]` |
| `native-feature-loop` | 7 | llm×3 + script | skeptic recon → pragmatist implement → pytest → docs sync |

`order` is the task's own `order:` field, and the gaps are deliberate — an
order is a position, not a rank, so removing a task does not renumber the rest.
`theteam tasks` displays the *sequence position* (0-4 here) rather than the
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

**`context:` was removed from all five tasks.** It looked like a field and was
not one. The only code that ever read `task["context"]` was
`scripts/task_executor.py:85`, and that file cannot be imported
(`ModuleNotFoundError: No module named 'task_archive'`) — it is a 265-line
orphan, already recorded as one in [Orphan scripts](#orphan-scripts). The `llm`
runner builds its prompt from `prompt_file` alone (`runners/llm.py:_read_prompt`),
and each prompt file already names its own inputs. So the key was prose for a
reader of the YAML that no execution path ever consulted, which is the
schema-lies-nothing-enforces shape that retired `option_selection_required`.

A phase names **either** `script` or `runner: llm`, never both and never
neither; the executor refuses a phase that names no runner, by name.

## Usage

```bash
theteam tasks                     # list every task and its state
theteam run                       # execute everything currently due
theteam run --only <task-id>      # one task, ignoring the rest (bypasses the schedule)
theteam run --dry-run             # what would run and its worst-case time; runs nothing
theteam loop <id> --interval <m>  # schedule one task to run on an interval
theteam serve                     # run due tasks on a tick, publishing /metrics
theteam history                   # success rate, last run, last failure
```

There is no `theteam --loop start`. The scheduler is `theteam loop` for one
task and `theteam serve` to run whatever is due.

A task is `not scheduled` until you schedule it, so `theteam run` on a fresh
clone runs nothing. `--only <id>` runs a task whether or not it was ever
scheduled: naming it *is* the request.

### Routine vs on-call

| kind | tasks | how they run |
|---|---|---|
| **Routine** | `project-integrity`, `maintenance` | schedule them; `theteam serve` picks them up on a tick |
| **On-call** | `doc-truth`, `root-organization`, `native-feature-loop` | `theteam run --only <id>`, inside an OMP session |

The three on-call tasks are `runner: llm`. `theteam run` does not spawn: it
names the next phase and the agent type to spawn, and reports `awaiting` until
the declared output file exists and is non-empty. That is an **awaiting state,
not a skip or a failure** — nothing is counted against the breaker, so an
unfinished task cannot walk to a permanent trip. Previously each refusal
counted, and all three were one bad run from a trip they could never clear.

### Watch it run

Phase output is streamed as it arrives, so a long run is no longer a silent
wait:

```bash
theteam run --only system-awareness
#   system-awareness/analyse and correct: up to 600s      <- the bound, before starting
#     🔍 STARTING SYSTEM ARCHITECTURE ANALYSIS             <- live, as printed
#     Phase 1: Project Structure Analysis
#   ...
#   system-awareness: ok (362.4s)
#   1 ran, 0 skipped, 0 failed in 362.4s
```

Every result carries a measured `elapsed`. Use `--dry-run` first if you want
the worst-case time without waiting for it.

### Scheduling guard

An interval shorter than the task's own worst-case time is refused:

```bash
$ theteam loop system-awareness --interval 1
theteam loop: interval 1m is shorter than task 'system-awareness' can take
(600s worst case). Use --interval 10 or more.
```

Such a task is permanently overdue — it is still running when it comes due
again — and every sweep re-runs it. That is not a slow schedule; it is a
schedule that cannot be kept.

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
`theteam run --only doc-truth` must be run inside one.

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

| id | observed result | evidence it ran |
|---|---|---|
| `project-integrity` | **ok** | both phases reported, `rc=0` |
| `system-awareness` | **ok** — score **0.5545**, grade **D**; five reports + `.loop-state.json` written | artifacts on disk with fresh mtimes; its own `self-check` reports one output missing (below) |
| `maintenance` | **ok** | single phase, `rc=0` |
| `doc-truth` | **awaiting** — names the `audit` phase | spawn request printed, breaker not advanced |
| `native-feature-loop` | **awaiting** — names `recon` | spawn request printed, breaker not advanced |
| `root-organization` | **awaiting** → **ok** after 4 phases | phase 1 driven by a live member (`sonic`, 492 entries); phases 2–4 advanced on directly-written artifacts — **not** verified through a spawn |

Run counts and success rates are deliberately absent. They are not stable: every
rerun changes them, and a rate that has not been refreshed reads as current
when it can be wrong within the hour — worse than carrying none, because a stale
number looks like a measurement. `theteam history` reports the live figures;
rates there move as tasks re-run.

**One declared output is never written, and the task reports `ok` anyway.**
`sa_runner.py` lists five expected outputs in `EXPECTED_OUTPUTS`, one of them
`infrastructure_report`. The writer exists (`scripts/sa_runner.py:201`) and has
exactly one call site — line 574, the last statement of
`_update_state_with_improvement`. But the self-correct write path is
`_run_correction_cycle` (lines 437-443), which writes health, team summary,
architecture, documentation and optimization and simply never calls
`write_infrastructure_report`. So `EXPECTED_OUTPUTS` names an output the cycle
does not produce. The `improvement` branches are not the cause: an earlier draft
of this note blamed the `improvement == 0` branch, which is wrong —
`_evaluate_health_improvement` returns `1` for a non-empty result set, so
`_update_state_with_improvement` is reached in principle. The writer is simply
not on the path that runs.

Confirmed by running it twice: the five reports `_run_correction_cycle` does
write land with fresh mtimes, `infrastructure_report.json` is absent both times,
the phase exits 0, and the task reports `ok`. Calling
`write_infrastructure_report` directly produces the file, so the writer is not
broken — it is uncalled.

This is the §3.3 shape again, one level up: the checks *inside* the script are
more honest than the exit code the executor reads — `self-check` reports the
missing output as `"healthy": false` while the phase returns success. The
minimal fix is to add one line to `_run_correction_cycle` (or drop
`infrastructure_report` from `EXPECTED_OUTPUTS` so the self-check stops
reporting an output this path never produces). Recorded, not fixed.

What is worth recording is which failures were *real*, because a rate cannot
distinguish "this task is broken" from "this task has never been run since it
was fixed":

- `project-integrity` has failed twice, both times with
  `FAIL: Required tool not found in PATH: git` — `git` was in `REQUIRED_TOOLS`
  and is not visible inside the isolation container. Fixed in M12; every run
  since has passed.
- The `system-awareness` task, since deleted, failed five times before its
  fixes landed: five OOM-kills at the old memory bound, then the breaker
  deadlock, then the 300s timeout. All were fixed before its removal.
- The three `llm` tasks have never succeeded **and have never failed a real
  phase** — they refuse by name before doing anything, so their history records
  refusals, not results.

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

`system-awareness` was found skipping `breaker_open` on every attempt and
permanently unrunnable — five consecutive failures, breaker open, and no way for
it to close. Root cause: `TaskExecutor._breaker` reconstructs
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
| `maintenance` | **yes** | no inputs |
| `doc-truth` | **no** | needs an OMP session; `harmonize` consumes `audit`'s output, but as a *phase* of the same task, so the ordering is the executor's |
| `root-organization` | **no** | needs an OMP session; phases 2-4 consume files from earlier phases; `depends_on: [project-integrity]` |
| `native-feature-loop` | **no** | needs an OMP session; phases 2-4 consume files from earlier phases |

Ordering facts, and **which of them the executor enforces**:

1. `doc-truth`'s `audit` → `harmonize` is a *phase* boundary inside one task.
   `execute_task` runs phases in order and breaks on a failed one, so this
   ordering is code, not prose. It was not always: `ground-truth-audit` and
   `doc-harmonization` were separate tasks whose only sequence was a sentence
   in a prompt file, and the two could run in either order or concurrently.
   Merging them into one task is what moved the guarantee into code.
2. `root-organization` → anything that needs the tree intact is a
   *task* boundary, and it is declared `depends_on: [project-integrity]`.
   `TaskExecutor._dependency_refusal` holds the task until every dependency's
   last result is `ok`; a never-run dependency and a non-`ok` one both refuse,
   and the refusal counts against no breaker.
3. `native-feature-loop` recon → implement → test → docs is sequential within
   one task, and the handoff is by file. `execute_task` breaks on
   `phase_result["success"]` and nothing else, so a phase that "succeeds"
   without writing still lets the next one run. That remains a recorded gap.

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
- **Merging `system-awareness` into `doc-truth`.** SA counts files and
  headings; `doc-truth` compares claims against code. Different questions.
- **Splitting `system-awareness`.** It runs four analyses in one process, which
  is why it needs 384MB. Splitting is the right move when it outgrows that, not
  before.

**Deliberate gaps, recorded not fixed:**

- Four orphan scripts totalling 1003 lines — `security_policy.py`,
  `task_executor.py`, `loop_state.py`, `loop_reporter.py` — imported by nothing,
  one of them unable to import at all. `loop_state.py` and `loop_reporter.py`
  still resolve from `os.getcwd()` rather than `__file__`. Operator tooling,
  left in place; see *Orphan scripts*.
- `.loop-state.json` carries two `last_execution` fields, one nested and
  current, one top-level and frozen. Both stores agree on score and grade.
  Pre-existing, outside the fixes above.
- `project-integrity`'s two recorded failures are both from before the M12 fix —
  `FAIL: Required tool not found in PATH: git`, because `git` was in
  `REQUIRED_TOOLS` and is not visible inside the isolation container.
  `REQUIRED_TOOLS` is now `["python3"]`, and every run since has passed. Kept
  here rather than deleted only because `theteam history` still shows those old
  runs until they age out of the execution log.
- No command resets a tripped breaker, and `breaker_open` is the only reason
  recorded once a breaker trips — so the *original* failure is lost from the
  schedule. A single `last_run` entry per task cannot hold both. The 60s window
  itself clears on its own now, including under repeated invocation, because
  skips go through `record_skip` and do not restamp `at`; see *Skips were
  fabricating state* for what that cost before.
- `theteam history` reports a lifetime success rate per task, and nothing ages
  those old runs out. A task fixed today still reads as failing for as long as
  its pre-fix runs stay in the execution log, so the rate is evidence about the
  past, not the present — reading it requires knowing which failures were real.
  A window, or a "since <date>" filter, would fix that; neither exists.