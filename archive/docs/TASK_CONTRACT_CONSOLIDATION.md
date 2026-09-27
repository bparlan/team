# Task Contract Consolidation Plan

## Problem
Three different task classes exist:
- task_contract.UnifiedTask (14 methods, canonical)
- unified_loop.UnifiedTask (6 methods, duplicate)
- loop_manager.LoopTask (6 methods, different)

## Solution
Consolidate all task functionality into task_contract.UnifiedTask as the single canonical task contract.

## Implementation Steps

### Step 1: Update LoopManager to use task_contract.UnifiedTask
- Modify loop_manager.py to use task_contract.UnifiedTask instead of loop_manager.LoopTask
- Remove LoopTask class from loop_manager.py
- Update all references to use task_contract.UnifiedTask

### Step 2: Update UnifiedLoop to use task_contract.UnifiedTask
- Modify unified_loop.py to use task_contract.UnifiedTask instead of unified_loop.UnifiedTask
- Remove the duplicate UnifiedTask class from unified_loop.py
- Update all references to use task_contract.UnifiedTask

### Step 3: Ensure Import Consistency
- Update all imports across the codebase to use: from theteam.core.task_contract import UnifiedTask
- Update __init__.py files if needed

### Step 4: Update Documentation and Tests
- Update any documentation referencing task classes
- Update tests to use task_contract.UnifiedTask

## Files to Modify
- /Users/bparlan/devcode/team/theteam/core/loop_manager.py
- /Users/bparlan/devcode/team/theteam/core/unified_loop.py
- /Users/bparlan/devcode/team/theteam/core/__init__.py (if needed)
- Various test files and documentation

## Priority
1. Fix UnifiedLoop task contract consistency
2. Fix LoopManager task contract consistency  
3. Update all imports and references
4. Run tests to verify no regression
