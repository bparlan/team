# Task: health-check
## Type
monitoring
## Priority
10
## Description
Run project health checks and system diagnostics
## Execution
python3 scripts/loop_health_check.py
## Context
- Project root structure
- Runtime configuration
- Required files and directories
## Expected Output
Health check passed: /path/to/root
## Failure Handling
retry