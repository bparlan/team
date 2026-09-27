# theteam Onboarding Guide

How agents and users adopt the theteam skill.

## Quick Start

### For Agents

1. **Read the config**:
   ```bash
   python3 theteam/bin/theteam_config.py validate theteam.config --json
   ```

2. **Check team members**:
   ```bash
   python3 theteam/bin/theteam_config.py roster theteam.config --json
   ```

3. **Run a discussion**:
   ```bash
   python3 theteam/__init__.py --topic "Your topic here"
   ```

4. **Execute a task**:
   ```bash
   python3 theteam/__init__.py --task folder-monitoring --task-action execute
   ```

### For Users

1. **Bootstrap** (first run only):
   ```bash
   python3 theteam/__init__.py --bootstrap
   ```

2. **Start the daemon**:
   ```bash
   python3 theteam/subskills/task-stack/daemon.py start
   ```

3. **Launch the TUI**:
   ```bash
   python3 theteam/ui/terminal_ui.py
   ```

   ```bash
   python3 scripts/sa_runner.py
   ```
   
   # Terminal monitoring commands
   ```bash
   python3 scripts/sa_runner.py status       # View loop and health status
   python3 scripts/sa_runner.py health-check  # Quick health with explicit exit codes
   python3 scripts/sa_runner.py json         # Machine-readable status
   ```
## Project Structure

```
theteam/
├── __init__.py              # Main orchestrator
├── bin/
│   ├── theteam_config.py    # Configuration management
│   └── theteam_report.py    # Report generation
├── core/
│   ├── state_manager.py     # Unified state management
│   ├── system_integration.py # System awareness integration
│   ├── integrated_orchestrator.py # Event-driven orchestrator
│   ├── event_bus.py         # Event system
│   └── folder_monitor.py    # Folder structure monitoring
├── workflow/
│   ├── discussion_manager.py # Discussion lifecycle
│   └── context_aggregator.py # Project context
├── ui/
│   ├── terminal_ui.py       # Curses TUI
│   └── task_stack_adapter.py # TUI-TaskStack bridge
├── subskills/
│   └── task-stack/
│       ├── orchestrator.py  # Task stack CLI
│       ├── daemon.py        # Background daemon
│       ├── scheduler.py     # Task scheduling
│       ├── registry.py      # Task registry
│       ├── executor.py      # Task execution
│       └── converter.py     # Conversation converter
├── tests/
│   └── test_theteam.py      # Test suite
└── CLI.md                   # Command reference
```

## Permitted Skills

The theteam skill can invoke these skills via `task` or `hub`:
- `ponytail` — Code audit and refactoring
- `evolve-skills` — Skill evolution and improvement
- `code-search` — Repository search and analysis

## Configuration

The `theteam.config` file controls behavior:
- `behavior.*` — Skill behavior settings
- `team.*` — Team member definitions
- `permitted_skills` — Allowed subagent skills
- `output.*` — Output directory settings

## Monitoring

### Check daemon status
```bash
python3 theteam/subskills/task-stack/daemon.py status
```

### Check orchestrator status
```bash
python3 theteam/subskills/task-stack/orchestrator.py status
```

### Check loop status
```bash
python3 scripts/loop_controller.py status
```

### View system awareness results
```bash
cat .mp/theteam/health-score.json
cat .mp/theteam/system-awareness-summary.json
```

## Troubleshooting

### Daemon not starting
```bash
# Check if already running
python3 theteam/subskills/task-stack/daemon.py status

# Stop and restart
python3 theteam/subskills/task-stack/daemon.py stop
python3 theteam/subskills/task-stack/daemon.py start
```

### TUI not launching
```bash
# Check terminal supports curses
python3 -c "import curses; print('curses OK')"

# Try with explicit project root
python3 theteam/ui/terminal_ui.py /path/to/project
```

### Tasks not executing
```bash
# Check scheduler
python3 theteam/subskills/task-stack/orchestrator.py status

# Run due tasks manually
python3 theteam/subskills/task-stack/orchestrator.py run-due
```