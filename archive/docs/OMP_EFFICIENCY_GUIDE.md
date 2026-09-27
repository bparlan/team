# OMP Efficiency Guide — Stability Roadmap Execution

## 1. Skill Selection per Phase

| Phase | Primary Skill | Secondary | Why |
|-------|--------------|-----------|-----|
| 1. Consolidate | `ponytail` | `code-search` | Delete dead code, find duplicates |
| 2. Harden State | `code-search` | `ponytail` | Research WAL/event-sourcing patterns, simplify |
| 3. Safety Nets | `theteam` | `code-search` | Independent review of circuit breakers |
| 4. Productionize | `theteam` | `ponytail` | Review Docker/monitoring, simplify configs |
| 5. UI & Visibility | `theteam` | `designer` | Review activity streams, dashboards |

**ponytail** is for code deletion/simplification. **theteam** is for independent review. Use `code-search` for research. Never use `theteam` for implementation — only for review.

## 2. Context Management

### Root Cause of Drift
Long conversations accumulate irrelevant context. The model starts answering from stale context instead of current files.

### Solution: Single-Focus Turns

Each turn has ONE goal. Before yielding, verify:
- All affected files re-read
- All affected tests run
- No stale assumptions

### Context Reset Protocol
1. Start each phase with a fresh `read` of the roadmap
2. Re-read only the files you will modify
3. Use `todo` to track phase progress
4. After each phase, summarize in 3 lines max, then yield

### Drift Prevention Commands
```bash
# Before starting a phase, reset context
python3 ~/.omp/agent/skills/theteam/bin/theteam_config.py validate "$(pwd)/theteam.config" --json

# Check what's been done
cat STABILITY_ROADMAP.md | grep -c "\[ \]"  # Count remaining tasks
cat STABILITY_ROADMAP.md | grep -c "\[X\]"  # Count completed tasks
```

## 3. Phase-by-Phase Command Prompts

### Phase 1: Consolidate
```
"Implement Phase 1 of STABILITY_ROADMAP.md: Consolidate. 
1. Read the roadmap
2. Use ponytail to identify dead code in LoopController
3. Delete LoopController (562 lines)
4. Make LoopManager the single loop implementation
5. Define unified Task contract
6. Add state file validation on load
7. Fix save_configuration() to not swallow exceptions
8. Run existing tests to verify no regression
Update the roadmap checkboxes when done."
```

### Phase 2: Harden State
```
"Implement Phase 2 of STABILITY_ROADMAP.md: Harden State.
1. Read the roadmap
2. Implement Write-Ahead Logging
3. Implement Event Sourcing
4. Add schema versioning and checksums
5. Set up database with migrations
6. Add correlation IDs and event rate limiting
7. Run tests to verify
Update the roadmap checkboxes when done."
```

### Phase 3: Safety Nets
```
"Implement Phase 3 of STABILITY_ROADMAP.md: Add Safety Nets.
1. Read the roadmap
2. Use theteam skill to review the plan
3. Implement Health Monitoring
4. Implement Circuit Breakers
5. Implement Resource Limiter
6. Add CI/CD pipeline
7. Add dead-letter queues and bounded growth
8. Run tests to verify
Update the roadmap checkboxes when done."
```

### Phase 4: Productionize
```
"Implement Phase 4 of STABILITY_ROADMAP.md: Productionize.
1. Read the roadmap
2. Use theteam skill to review the plan
3. Containerize with Docker
4. Add Prometheus/Grafana monitoring
5. Implement backup and restore
6. Add audit logging
7. Set up production database
8. Run tests to verify
Update the roadmap checkboxes when done."
```

### Phase 5: UI & Visibility
```
"Implement Phase 5 of STABILITY_ROADMAP.md: UI & Visibility Layer.
1. Read the roadmap
2. Use theteam skill to review the plan
3. Add real-time ActivityStream component
4. Add health status dashboard
5. Add agent roster panel
6. Implement visual state machine semantics
7. Add progressive disclosure
8. Run tests to verify
Update the roadmap checkboxes when done."
```

## 4. OMP Tool Usage Rules

### `todo` — Track progress
- Init at phase start with all tasks
- Mark `done` after each sub-task
- Never leave a task `in_progress` when yielding

### `hub` — Coordinate subagents
- Use `hub wait` to wait for subagent results
- Use `hub jobs` to check status
- Never poll repeatedly — wait once, then check

### `task` — Spawn isolated workers
- One task per component
- Each task gets full context
- Tasks never see each other's output

### `read` — Ground in current state
- Re-read files before editing
- Use offset/limit for large files
- Never edit from memory

### `write` — Create/overwrite files
- Use for new files
- Use `edit` for modifications

## 5. Anti-Drift Checklist

Before yielding, verify:
- [ ] All file reads are current (re-read after any edit)
- [ ] All tests pass
- [ ] Roadmap checkboxes updated
- [ ] No stale assumptions in the response
- [ ] Next phase is clearly defined

## 6. The Team Skill Usage

The `theteam` skill provides independent review. Use it when:
- Starting a new phase
- After completing a phase
- When you suspect drift

The skill spawns 5 independent reviewers (architect, pragmatist, skeptic, designer, devops) who each file a note without seeing each other's work. The orchestrator then does a synthesis pass.

## 7. Critical Rules

1. **Never implement without a plan** — the roadmap IS the plan
2. **Never skip tests** — run existing tests after every change
3. **Never modify files outside scope** — stick to the phase
4. **Never fabricate** — if you don't know, say so
5. **Always verify** — tool results are verification, not assumptions