# Phase 1: Consolidate Implementation - COMPREHENSIVE PLAN

## EXECUTIVE SUMMARY
The stability roadmap requires consolidating the loop architecture into a single source of truth. Currently, the team has:

- Two competing loop implementations (UnifiedLoop and LoopManager)
- Three different task classes (UnifiedTask, UnifiedTask duplicate, LoopTask)
- No save_configuration() method
- Missing state file validation integration
- Broken pause() method

## STRATEGY
Consolidate into LOOP_MANAGER as the single canonical implementation.

## IMPLEMENTATION SEQUENCE

### 1. Fix pause() method (CRITICAL - failing tests)
- Update UnifiedLoop.pause() to allow pausing in STARTING state
- Ensure get_status() returns 'paused' state

### 2. Consolidate Task Classes  
- Remove duplicate UnifiedTask from unified_loop.py
- Make LoopManager.LoopTask use task_contract.UnifiedTask
- Update all imports to use task_contract.UnifiedTask

### 3. Consolidate Loop Implementations
- Move all UnifiedLoop functionality into LoopManager
- Delete unified_loop.py (or deprecate)
- Update all imports to use LoopManager

### 4. Implement save_configuration()
- Add to LoopManager or state_manager
- Ensure it raises exceptions, doesn't swallow them

### 5. Integrate state_validator.py
- Add validation calls to state_manager.load_state()
- Add validation to save_state()

### 6. Update Roadmap Checkboxes
- Mark all Phase 1 tasks as completed

### 7. Run Tests
- Fix failing tests
- Verify no regression

## IMMEDIATE NEXT STEPS
1. Fix pause() method (highest priority)
2. Update tests to work with current state
3. Begin task class consolidation
4. Begin loop implementation consolidation

## FILES TO MODIFY
- /Users/bparlan/devcode/team/theteam/core/unified_loop.py
- /Users/bparlan/devcode/team/theteam/core/loop_manager.py  
- /Users/bparlan/devcode/team/theteam/core/task_contract.py
- /Users/bparlan/devcode/team/theteam/core/state_manager.py
- Various test files
