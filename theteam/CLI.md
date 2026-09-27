# theteam Command Reference

Complete command inventory for the theteam skill and project.

## Core Skill Commands

### `theteam/__init__.py` — Main Orchestrator
```bash
# Bootstrap (first run only)
python3 theteam/__init__.py --bootstrap

# Run team discussion on a topic
python3 theteam/__init__.py --topic "Database optimization"

# Execute a task
python3 theteam/__init__.py --task folder-monitoring --task-action execute

# List tasks
python3 theteam/__init__.py --task folder-monitoring --task-action list

# Check task status
python3 theteam/__init__.py --task folder-monitoring --task-action status
```

### `theteam/bin/theteam_config.py` — Configuration
```bash
# Validate config
python3 theteam/bin/theteam_config.py validate theteam.config --json

# List team members
python3 theteam/bin/theteam_config.py roster theteam.config --json

# Initialize from template
python3 theteam/bin/theteam_config.py init theteam/theteam-template.config /tmp/answers.json theteam.config
```

### `theteam/bin/theteam_report.py` — Report Generation
```bash
python3 theteam/bin/theteam_report.py build \
  --topic "System Analysis" \
  --notes-dir /tmp/theteam-notes-20260921 \
  --synthesis /tmp/theteam-synthesis-20260921.json \
  --out .omp/theteam/reports/20260921-system-analysis.md \
  --project "team" \
  --expected-ids architect,pragmatist,skeptic,designer,devops
```

## Task Stack Commands

### `theteam/subskills/task-stack/orchestrator.py`
```bash
# Register a task
python3 theteam/subskills/task-stack/orchestrator.py register tasks/system-awareness/folder-monitoring.yaml

# Execute a task
python3 theteam/subskills/task-stack/orchestrator.py execute folder-monitoring

# Loop a task (recurring)
python3 theteam/subskills/task-stack/orchestrator.py loop folder-monitoring 30

# Run all due tasks
python3 theteam/subskills/task-stack/orchestrator.py run-due

# Convert conversation to task
python3 theteam/subskills/task-stack/orchestrator.py convert-conversation 50

# Convert user request to task
python3 theteam/subskills/task-stack/orchestrator.py convert-request "Analyze system performance"

# List all tasks
python3 theteam/subskills/task-stack/orchestrator.py list

# Show status
python3 theteam/subskills/task-stack/orchestrator.py status
```

### `theteam/subskills/task-stack/daemon.py`
```bash
# Start daemon
python3 theteam/subskills/task-stack/daemon.py start

# Stop daemon
python3 theteam/subskills/task-stack/daemon.py stop

# Check daemon status
python3 theteam/subskills/task-stack/daemon.py status
```

## System Awareness Commands

### `scripts/sa_runner.py` — Consolidated System Awareness Runner
```bash
python3 scripts/sa_runner.py  # Run analysis with terminal visibility
python3 scripts/sa_runner.py --project-root /path/to/project

# Terminal monitoring commands
python3 scripts/sa_runner.py status       # View loop and health status
python3 scripts/sa_runner.py health-check  # Quick health with explicit exit codes
python3 scripts/sa_runner.py json         # Machine-readable status
```
### `theteam/core/folder_monitor.py`
```bash
# Monitor folder structure
python3 theteam/core/folder_monitor.py --compact
```

## UI Commands

### `theteam/ui/terminal_ui.py` — Curses TUI
```bash
# Launch terminal UI
python3 theteam/ui/terminal_ui.py

# Launch with specific project root
python3 theteam/ui/terminal_ui.py /path/to/project
```

### `theteam/core/integrated_orchestrator.py`
```bash
# Launch integrated orchestrator with all components
python3 theteam/core/integrated_orchestrator.py
```

## Loop Control Commands

### `scripts/loop_controller.py`
```bash
# Start loop
python3 scripts/loop_controller.py start

# Stop loop
python3 scripts/loop_controller.py stop

# Check status
python3 scripts/loop_controller.py status

# Reset loop
python3 scripts/loop_controller.py reset

# Run next task
python3 scripts/loop_controller.py run-next-task
```

## Workflow Commands

### `theteam/workflow/context_aggregator.py`
```bash
# Aggregate project context
python3 theteam/workflow/context_aggregator.py /path/to/project
```

## Testing Commands

### Run all tests
```bash
python3 -m pytest theteam/tests/ -v
```

### Run specific test
```bash
python3 -m pytest theteam/tests/test_theteam.py -v
```

## Quick Status Check
```bash
# Check daemon
python3 theteam/subskills/task-stack/daemon.py status

# Check orchestrator
python3 theteam/subskills/task-stack/orchestrator.py status

# Check loop
python3 scripts/loop_controller.py status