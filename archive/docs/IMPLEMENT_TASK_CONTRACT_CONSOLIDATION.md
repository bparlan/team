# Task Contract Consolidation Implementation

## Summary
We need to consolidate three different task classes into one canonical UnifiedTask from task_contract.UnifiedTask.

## Current State
1. task_contract.UnifiedTask: 14 methods, canonical
2. unified_loop.UnifiedTask: 6 methods, duplicate (same name, different implementation)
3. loop_manager.LoopTask: 6 methods, different interface

## Implementation Plan

### Phase 1: Update unified_loop.py
- Remove the duplicate UnifiedTask class from unified_loop.py
- Change all references to use task_contract.UnifiedTask
- Update imports

### Phase 2: Update loop_manager.py  
- Replace LoopTask with task_contract.UnifiedTask
- Update all task-related code to use the canonical task contract
- Remove LoopTask class

### Phase 3: Update all other files
- Update imports across the codebase
- Update test files
- Update documentation

## Priority
1. Fix unified_loop.py (easier)
2. Fix loop_manager.py (more complex)
3. Update other files
4. Run tests
