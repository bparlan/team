# Task: maintenance
## Type
maintenance
## Priority
5
## Description
Perform routine maintenance including cache cleaning, log rotation, and temporary file cleanup
## Execution
python3 scripts/loop_maintenance.py
## Context
- Temporary files
- Log directories
- Cache directories
## Expected Output
Routine maintenance complete: cache cleaned, logs rotated
## Failure Handling
retry