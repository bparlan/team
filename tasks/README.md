# Task Archive

This directory contains looping tasks for the `theteam` skill.

## Task Format

Each task is a markdown file with this structure:

```markdown
# Task: <task-name>

## Type
healthcheck | maintenance | improvement | doc-update | security | analysis

## Priority
1-10 (10 = highest)

## Description
What this task does.

## Execution
```bash
# Commands to run
python3 scripts/health-check.py
```

## Context
- Required files to read before execution
- Required context to pass to subagent

## Expected Output
What constitutes success.

## Failure Handling
ask | skip | retry | stop
```

## Task Order

Tasks are executed in priority order (highest first) as defined in `TASK_ORDER`.

## Usage

```bash
# Start loop mode
theteam --loop start

# Check loop status
theteam --loop status

# Stop loop mode
theteam --loop stop
```