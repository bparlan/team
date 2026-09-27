# Integration Plan: TeamMemberManager with DiscussionInterface

## Problem Statement
The current DiscussionInterface accepts member_ids as simple strings, but needs to integrate with TeamMemberManager for:
1. Context-aware discussions (members have contexts/projects they can access)
2. Rich member metadata (roles, permissions, contexts)
3. Backward compatibility with existing code
4. Token-efficient operations

## Integration Strategy

### 1. Integration Points

**In DiscussionInterface class:**
- Add TeamMemberManager integration for context-aware participant validation
- Use TeamMemberManager.can_access_context() for permission checks
- Provide both simple member_id strings and rich member objects

**Module-level functions:**
- Maintain backward compatibility
- Support both string IDs and TeamMember objects
- Fallback to simple validation when TeamMemberManager unavailable

### 2. Key Changes to discussion_interface.py

**Import section:**
```python
from theteam.core.team_member_manager import TeamMemberManager, TeamMemberConfig
```

**In DiscussionInterface.__init__:**
- Optional TeamMemberManager integration
- Lazy initialization to maintain token efficiency

**In create_discussion:**
- Validate members using TeamMemberManager if available
- Support both simple member_ids and rich member objects
- Maintain backward compatibility with string-only member_ids

**In add_participant:**
- Context-aware access validation
- Support both TeamMember objects and member_ids

### 3. Implementation Details

**Context-aware validation:**
```python
def _validate_member_access(self, member_id, context):
    # Use TeamMemberManager.can_access_context() if available
    # Fallback to simple membership check
    pass
```

**Rich member support:**
- Accept TeamMember objects for enhanced functionality
- Extract member_id from objects when needed
- Store both member_id and member object reference

### 4. Backward Compatibility

**String member_ids (existing):**
- Continue to work as before
- Optional context validation

**Rich member objects (new):**
- Automatically converted to member_id
- Full context and permission validation
- Enhanced discussion metadata

### 5. Token Efficiency

**Lazy initialization:**
- TeamMemberManager only loaded when needed
- Caching of manager instances
- Minimal overhead for simple use cases

**Optimized operations:**
- Batch validation where possible
- Reduced filesystem operations
- Efficient caching strategies

### 6. Testing Strategy

**Unit tests:**
- String member_ids (backward compatibility)
- TeamMember objects (new functionality)
- Context-aware validation
- Error handling for invalid members

**Integration tests:**
- Full TeamMemberManager integration
- Performance under load
- Memory usage validation

## Files Modified

- `/Users/bparlan/devcode/team/theteam/workflow/discussion_interface.py`
  - Main integration implementation

## Verification

Run existing tests to ensure:
1. All existing functionality preserved
2. New features work correctly
3. Performance targets met
4. Backward compatibility maintained