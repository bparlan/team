# Theteam Silent Failures & TUI Blind Spots Review

## Silent Failure Scenarios (≥3 concrete examples)

### 1. `theteam discuss` - Outside OMP
- **Location**: `theteam/cli.py:169-174`
- **Failure**: Returns `EXIT_ERROR` (1) but prints no error message. User sees nothing, just a failed command.
- **TUI Impact**: Would show "discussion complete" when nothing happened.
- **Evidence**: `run_discussion()` returns `False`, triggering `EXIT_ERROR` with no user feedback.

### 2. `theteam run` - Nothing Due
- **Location**: `theteam/cli.py:227-283` 
- **Failure**: Returns successful JSON payload when `not due` (line 277-278). Payload shows `"ran": 0` but this is a success state, not a measurement.
- **TUI Impact**: Shows "0 tasks executed" as if work was measured, not as "nothing was due".
- **Evidence**: Line 277: `if not due: return _emit(args, payload, "nothing due")` - successful emission despite zero work.

### 3. `theteam comment on` - Cap Enforcement
- **Location**: `theteam/cli.py:548-551`
- **Failure**: When `--max-members` exceeds cap (4), calls `_fail()` which prints only command and reason, leaving no state behind.
- **TUI Impact**: Shows "commentary on" succeeded when it never started.
- **Evidence**: Line 549-551: `return _fail(args, "comment on", f"--max-members {args.max_members} exceeds the cap of {COMMENT_MAX_MEMBERS}")`

## Honest Gap Analysis

**The missing thing is CODE STRUCTURE VISIBILITY, not a TUI**

The user says "it feels very hard for me to check how the code-structure-architecture works." The TUI solves display problems but not architecture exploration:

- **Missing**: `code-search --skeletons` - no way to discover component interfaces, dependencies, data flows
- **Missing**: `ARCHITECTURE.md` rendering - no visual system topology
- **Missing**: Component relationship graphs - cannot trace which adapters break the chain

The TUI shows rendered output but not the architecture that produces it. Users can't ask "what's the trust surface contract?" or "what interfaces exist?"

## What TUI Gets Wrong by Design

### 1. Audit Chain State Confusion
- **Bug**: `chain_line()` renders `intact: null` as "intact, 0 entries" (line 161-162)
- **Impact**: TUI shows green "audit chain intact" when nothing was measured
- **Root Cause**: `read_chain_state()` returns `"intact": None` for empty/missing files (line 123), but `chain_line()` treats `intact` as truthy

### 2. Circuit Breaker Ambiguity  
- **Bug**: `_breaker_cell(None)` returns "never run" (line 65-66)
- **Impact**: TUI cannot distinguish "never measured" from "measured as closed"
- **Root Cause**: `circuit_visual(None)` returns UNKNOWN, but `status_payload` writes `"breaker": None` when task never ran

### 3. Status Command Error Surface
- **Bug**: `status_payload()` returns `(None, error)` when not bootstrapped (line 119-120)
- **Impact**: TUI has no error display, just hangs or crashes
- **Root Cause**: CLI error handling uses `_fail()` which prints to stderr, but TUI reads `status_payload()` directly

## Edge Cases TUI Would Hide

### 1. Loop Scheduling Edge Cases
- **Interval <= 0**: `cmd_loop()` line 181-188 rejects with `_fail()` but user sees nothing in TUI
- **Task not found**: Same failure path, TUI shows "scheduled" when schedule failed

### 2. Task Delete Orphaned Schedules  
- **Bug**: `task delete --yes` leaves orphaned schedule entries (line 443-449)
- **Impact**: TUI shows "deleted" but orphaned entries persist and cause future scheduling bugs
- **Evidence**: `_delete_plan()` checks schedule["scheduled_tasks"], repo.delete() doesn't clean orphaned entries

### 3. Comment State Corruption
- **Bug**: Double "on" or "off" leaves corrupted state (lines 557-588)
- **Impact**: TUI shows "commentary on" regardless of actual state
- **Evidence**: Line 570-571 writes state with `on=True` even if already on; line 585 writes `on=False` even if already off

### 4. Run Idempotency Masking
- **Bug**: Repeated runs on same due task create identical results but TUI shows "completed" each time
- **Impact**: Users can't tell if work actually changed state or was just re-executed
- **Evidence**: `cmd_run()` line 263-283 processes same due tasks multiple times with identical outcomes

## Evidence Required for "Team Operable via TUI"

### 1. Audit Chain State Distinction
- **Test**: Verify `watch status` shows "absent" vs "empty" vs "intact" with clear visual cues
- **Evidence**: `audit chain    absent (no audit file)` vs `audit chain    empty (is empty)` vs `audit chain    intact, 5 entries`

### 2. Circuit Breaker Clarity
- **Test**: Verify TUI shows "never measured" for tasks with no runs, "closed" for healthy tasks, "open" for tripped breakers
- **Evidence**: `_breaker_cell()` returns different strings for None vs "closed" vs "open"

### 3. Comment State Accuracy
- **Test**: Verify `comment status` matches actual state after toggle operations
- **Evidence**: `on_marker.exists()` matches state["on"] and `commentary_stop.exists()`

### 4. Graceful Error Handling
- **Test**: Verify `watch` command handles permission errors, missing files, corrupted state
- **Evidence**: Error surfaces visible in TUI, not just stderr

### 5. Null vs Measured State Verification
- **Test**: Verify TUI distinguishes `intact: null` (nothing measured) from `intact: true` (verified) and `intact: false` (broken)
- **Evidence**: `chain_line()` renders all three states distinctly, not treating null as true

**Critical Missing Evidence**: Current tests pass but don't verify that TUI surfaces all these silent failures. The TUI currently treats "nothing measured" as "healthy".