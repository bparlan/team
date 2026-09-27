# Team Skill Deployment Guide

Standardized environment and deployment configurations for the theteam skill.

## Environment Configuration

The skill uses a `.env` file (or system environment variables) for runtime configuration.

### Template (`.env.template`)

```bash
# State directory override. Defaults to <project-root>/.omp/theteam.
THETEAM_STATE_DIR="$HOME/.omp/theteam"

# Task Stack Daemon Settings
TASK_STACK_MONITORING_INTERVAL=60
LOG_LEVEL="INFO"

# Terminal UI Settings
TUI_REFRESH_INTERVAL=5

# Reflex Dashboard Settings (if used)
REFLEX_FRONTEND_PORT=3000
REFLEX_BACKEND_PORT=8000
```

## Deployment Options

### 1. Daemon Mode (Recommended for development)

Run the task-stack daemon to handle scheduled tasks (like folder-monitoring).

```bash
# Start daemon
python3 theteam/subskills/task-stack/daemon.py start

# Check status
python3 theteam/subskills/task-stack/daemon.py status

# Stop daemon
python3 theteam/subskills/task-stack/daemon.py stop
```

### 2. Manual Execution

Run individual components as needed.

python3 scripts/sa_runner.py  # Consolidated system awareness runner
python3 scripts/sa_runner.py --project-root PROJECT_ROOT

### 3. TUI Monitoring

Keep the TUI open for real-time state and task monitoring.

```bash
python3 theteam/ui/terminal_ui.py
```

## Maintenance

### Logs
Logs are stored in `.omp/theteam/logs/`.
- `daemon.log`: Background task execution
- `orchestrator.log`: Task management actions
- `theteam.log`: Skill activity

### Cleanup
To reset the task stack state (caution: clears history):
```bash
rm .omp/theteam/task-schedule.json
rm .omp/theteam/task-stack.json
```
