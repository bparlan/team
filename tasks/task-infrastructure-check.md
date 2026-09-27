# Task: infrastructure-check
## Type
monitoring
## Priority
8
## Description
Check project infrastructure health including file structure, scripts, and runtime configuration
## Execution
python3 scripts/loop_infrastructure_check.py
## Context
- Python version compatibility
- Required scripts and tools
- Directory layout integrity
- Loop state files
## Expected Output
Infrastructure check passed: all systems operational
## Failure Handling
retry