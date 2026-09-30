# Tasks

Registered tasks for the `theteam` skill. One YAML file per task, named
`task-<id>.yaml` — the `task-` prefix is what `TaskRepository` looks for, so a
task file without it is invisible to the runner.

## Current tasks

| id | order | what it does |
|---|---|---|
| `project-integrity` | 0 | directories, configs, scripts, tools, Python version, loop-state freshness |
| `system-awareness` | 2 | 4-phase analysis (structure, documentation, architecture, infrastructure) with health scoring |
| `maintenance` | 3 | cache cleaning, log rotation, temp-file cleanup |
| `ground-truth-audit` | 5 | reports where a documented claim is contradicted by the code |
| `doc-harmonization` | 6 | consumes the audit, makes the documents true |
| `native-feature-loop` | 7 | skeptic recon → pragmatist implement → pytest → docs sync |

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
order: <n>              # execution position; lower runs first
```

`order` is the only ordering source. `TASK_ORDER` was removed when ordering
moved onto each task — nothing reads it, and nothing writes it.

A phase names **either** `script` or `runner: llm`, never both and never
neither; the executor refuses a phase that names no runner, by name.

## Usage

```bash
theteam tasks              # list every task and its state
theteam loop <id> --interval <s>   # schedule one task to run on an interval
theteam run                # execute everything currently due
theteam serve              # run due tasks on a tick, publishing /metrics
theteam history            # success rate, last run, last failure
```

There is no `theteam --loop start`. The scheduler is `theteam loop` for one
task and `theteam serve` to run whatever is due.