# Implementation Plan: Theteam Robustness Fixes

## Overview
This document outlines the minimal, reliable implementation plan to address robustness issues in the Oh My Pi team skill orchestrator.

## Critical Issues Identified

### 1. Missing Context Aggregator & Tool Manifest
**Issue**: SKILL.md requires `theteam/workflow/context_aggregator.py` and `.omp/theteam/tool-manifest.json`, but neither exists.

**Impact**: Steps 4-5 cannot execute - no actual project context or tool inventory for team members.

**Status**: ✅ **FIXED**
- Created `/Users/bparlan/devcode/team/theteam/workflow/context_aggregator.py` with comprehensive project context aggregation
- Created `/Users/bparlan/devcode/team/theteam/.omp/theteam/tool-manifest.json` with complete tool inventory

### 2. Missing Personality Fields in Config
**Issue**: Current `theteam.config` lacks `personality` fields present in template.

**Impact**: Chatroom-style member intros cannot display proper member personas.

**Status**: ✅ **FIXED**
- Updated `/Users/bparlan/devcode/team/theteam.config` with complete personality fields:
  - `closing`: Member closing remarks
  - `color`: UI color theme
  - `emoji`: Chatroom display emoji
  - `greeting`: Member greeting message
  - `interaction_frequency`: Communication style
  - `speech_pattern`: Communication rhythm
  - `style`: Expression approach

### 3. Non-Deterministic Task Spawning
**Issue**: `__init__.py` simulates member spawning instead of actually using the `task` tool.

**Expected**: Each enabled member should be spawned via `task(task_name=member_id, ...)` with proper JSON output.

**Impact**: Members are not actually running, just printing what would happen.

**Remaining Work**: 
- Replace simulation in `run_discussion()` with actual `task` calls
- Each member needs proper system prompt construction
- Task output should be written to note files

### 4. Missing Member Reporting Verification
**Issue**: No actual enforcement that all enabled members report via their expected notes.

**Expected**: SKILL.md requires verification that every enabled member actually files notes before synthesis.

**Remaining Work**:
- Implement file existence checks after all tasks complete
- Verify JSON schema compliance (`{id, role, verdict, note}`)
- Fail fast if any enabled member missing or failed

### 5. Configuration Loading Issues
**Issue**: `load_config()` expects `.json` but actual config is `.config` format.

**Status**: ✅ **FIXED**
- Updated `load_config()` to handle `.config` extension by trying YAML first, then JSON
- Fixed config path resolution

## Implementation Roadmap

### Phase 1: Fix Task Spawning (Priority 1)
**Task**: Replace simulation with actual `task` calls in `run_discussion()`

**Changes**:
1. Import `task` tool from available tools
2. For each enabled member:
   - Construct system prompt from `role`, `expertise`, `voice`, topic
   - Include project context and tool inventory
   - Set `outputSchema` to require `{id, role, verdict, note}`
   - Write result to `/tmp/theteam-notes-<timestamp>/<id>.json`

**Acceptance Criteria**:
- All enabled members actually spawn as tasks
- Each task returns valid JSON with required fields
- Note files are written correctly
- Process fails if any member doesn't report

### Phase 2: Add Member Reporting Verification (Priority 2)
**Task**: Implement robustness checks for member notes

**Changes**:
1. After all tasks complete, read expected member IDs from config
2. Verify corresponding note files exist
3. Validate JSON schema of each note file
4. Fail with clear error if any member missing/failed
5. Log successful verification

**Acceptance Criteria**:
- All expected members have note files
- All note files are valid JSON
- System fails fast on missing members
- Success is clearly logged

### Phase 3: Complete Discussion Workflow (Priority 3)
**Task**: Implement full deterministic discussion flow

**Changes**:
1. Replace hardcoded user choice with actual user input
2. Implement proper state machine for 4 selection options:
   - `proceed`: Continue with normal synthesis
   - `alternative`: Follow alternative path
   - `more_details`: Request additional member details
   - `user_input`: Accept custom user input
3. Ensure guardrails against edits without approved plan
4. Implement pre-analysis research when enabled

**Acceptance Criteria**:
- User can actually make meaningful choices
- Each choice triggers appropriate workflow
- Guards prevent unauthorized edits
- All workflow steps are deterministic

### Phase 4: Error Handling & Edge Cases (Priority 4)
**Task**: Add robustness for failure scenarios

**Changes**:
1. Graceful handling of missing context_aggregator/tool-manifest
2. Validation of config schema completeness
3. Retry logic for task failures
4. Clear error messages for users
5. Proper exit codes matching `theteam_report.py`

**Acceptance Criteria**:
- All error scenarios handled gracefully
- Clear user-facing error messages
- Proper exit codes (0, 1, 2, 3)
- No silent failures

## Testing Strategy

### Unit Tests (Not Required for Initial Fix)
- Skip per project policy
- Tools will be tested through integration

### Integration Verification
1. **Manual Testing**: Run theteam with various configurations
2. **Context Test**: Verify context_aggregator produces valid output
3. **Config Test**: Test with modified configs (missing fields, invalid data)
4. **Member Test**: Verify all enabled members can spawn and report
5. **Edge Case Test**: Test failure scenarios and error handling

### Acceptance Criteria
- All enabled members successfully report notes
- Synthesis can be performed with actual member input
- Reports are generated with correct expected-ids
- No regressions in existing functionality

## Dependencies

### Required
- Python 3.6+
- PyYAML (`pip install PyYAML`)

### Optional (for full functionality)
- `ponytail`: Code quality analysis
- `evolve-skills`: Repository evidence analysis  
- `code-search`: Pattern discovery
- `archify`: Architecture validation

## Timeline
- **Phase 1** (Task Spawning): 2-3 hours
- **Phase 2** (Verification): 1-2 hours
- **Phase 3** (Discussion): 2-3 hours
- **Phase 4** (Error Handling): 1-2 hours

**Total Estimated Time**: 6-10 hours

## Risk Assessment

### High Risk: Task Spawning
**Impact**: Core functionality broken
**Mitigation**: Test with simple mock tasks first
**Fallback**: Maintain simulation mode during development

### Medium Risk: Member Verification
**Impact**: Silent failures possible
**Mitigation**: Fail-fast approach with clear error messages
**Fallback**: Log warnings but proceed (less robust)

### Low Risk: Discussion Workflow
**Impact**: User experience degraded
**Mitigation**: Implement step-by-step with testing
**Fallback**: Keep simple simulation mode

## Conclusion

This plan addresses all identified robustness issues with minimal, focused changes. The implementation maintains backward compatibility while adding the required functionality for deterministic multi-agent discussions.

**Key Principles**:
1. **Fix first**: Address critical missing infrastructure (context, tool manifest)
2. **Prioritize**: Focus on actual task spawning over simulation
3. **Verify**: Ensure all members report before synthesis
4. **Fail**: Fail fast with clear error messages
5. **Minimal**: Make smallest changes necessary to fix issues

**Ready to Start**: All prerequisites have been addressed (context aggregator created, tool manifest available, config updated with personality fields).