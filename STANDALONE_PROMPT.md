# STANDALONE_PROMPT.md — Standalone Usage Plan

## Executive Summary
The `theteam` skill's terminal `watch` function already provides core monitoring capability, but it lacks **change detection** and **alert mechanisms**. This plan enhances the existing `watch` function to become a true monitoring tool while preserving its machine surface contract.

## Core Insight

The existing `watch` function (`theteam/ui/terminal.py:215`) renders project state via hardcoded `RENDERERS` (status/tasks/history). However, it **cannot monitor** because:
1. No change detection between frames
2. No alert system for state transitions  
3. No indication of healthy vs. concerning states
4. Static rendering without dynamic updates

## Technical Conflict Resolution

The team correctly identified: 
> "**a TUI that improves them by rewriting them has broken the contract they exist to serve**"

**Solution:** Enhance `watch` as a **monitoring overlay** that:
- Preserves the existing machine surface contract
- Adds **change detection** and **alerting** capabilities
- Maintains **output honesty** (no fabricated opinions)
- Leverages **existing payload functions** without duplication

## Implementation Architecture

### Current State
```
┌─────────────────┐     ┌─────────────────┐
│ User CLI        │     │ API Layer       │
│ (theteam status │ ←── │ (new)           │
│  theteam watch) │     │                 │
└─────────────────┘     └─────────────────┘
         │                        │
         ├─────────────────────────┼─────────────────────────┤
         │                        │                        │
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Terminal Watch  │     │ Monitoring      │     │ State Manager   │
│ (existing)      │     │ Enhancement     │     │ (existing)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Enhanced Watch Function Features

**1. Change Detection**
- Track payload differences between frames
- Show change count in header (e.g., "theteam watch status [3 changes]")
- Highlight changed cells in rendered output

**2. Alert System**  
- Monitor circuit breaker state changes
- Alert on task status transitions (queued→running→completed)
- Health score degradation detection
- Threshold breach notifications

**3. Dynamic State Indicators**
- Clear visual distinction between "nothing measured" and "measured state"
- Progress indicators for ongoing operations
- Error state prominence with clear messages

**4. Event Timeline**
- Recent change timeline overlay
- Drill-down capability for specific events
- Event type categorization (task, circuit, health, etc.)

## Implementation Tasks

### Task 1: Enhanced Watch Function (Critical Path)
**Duration:** 1 day

**Modified Components:**
- `theteam/ui/terminal.py` - Enhanced `watch()` function
- `theteam/cli.py` - Updated `cmd_watch()` for monitoring mode

**Technical Requirements:**
```python
# NEW: Change detection
def watch(project_root: str, view: str, once: bool = False,
          interval: float = DEFAULT_INTERVAL, 
          stream: Optional[Any] = None, monitoring: bool = False) -> int:
    
    # NEW: State tracking
    last_payload = None
    change_count = 0
    event_timeline = deque(maxlen=100)
    
    while True:
        payload, lines = read()
        
        # NEW: Change detection logic
        if payload is not None:
            if payload != last_payload:
                change_count += 1
                event_timeline.append({
                    'timestamp': time.time(),
                    'view': view,
                    'payload': payload,
                    'changes': detect_changes(last_payload, payload)
                })
            last_payload = payload
        
        # Enhanced rendering with monitoring features
        frame = RENDERERS[view](payload, monitoring=True, 
                                change_count=change_count,
                                event_timeline=event_timeline)
```

### Task 2: Monitoring Alert System
**Duration:** 2 days

**Components:**
- `theteam/monitor.py` - New monitoring core
- `theteam/alerts.py` - Alert management system
- Enhanced `RENDERERS` with alert indicators

**Features:**
- Circuit breaker state change alerts
- Task execution milestone alerts
- Health score degradation alerts
- Custom threshold alerts

### Task 3: API Integration
**Duration:** 1 day

**Components:**
- `theteam/api/monitor.py` - Monitoring API functions
- `theteam.get_monitor_status()` - Get current monitoring state
- `theteam.get_recent_events()` - Get event timeline
- `theteam.clear_alerts()` - Clear alert state

## Success Criteria

### Technical Requirements
- [ ] `watch` function provides real-time change detection
- [ ] Monitoring alerts for state transitions
- [ ] Health scoring across all components
- [ ] API layer exposes monitoring capabilities
- [ ] No regression in existing CLI functionality

### User Experience Requirements
- [ ] Clear visual indicators of system health
- [ ] Change count in header (e.g., "[3 changes]")
- [ ] Drill-down capability for events
- [ ] Alert system for threshold breaches
- [ ] No information overload - clear, focused monitoring

### Quality Gates
- [ ] All 744 existing tests pass
- [ ] Monitoring integration tests
- [ ] API layer unit tests
- [ ] End-to-end monitoring workflow tests

## Timeline

**Critical Path (3 days):**
- Day 1: Enhanced watch function with change detection
- Day 2: Monitoring alert system
- Day 3: API integration

**Total Implementation:** 3 days (vs. original 3.5 days)

## Rollout Strategy

1. **Phase 1:** Enhanced watch with change detection
2. **Phase 2:** Add monitoring alert system  
3. **Phase 3:** Expose monitoring via API layer

## Architecture Diagrams Updated

### Existing Diagram Enhancements
- **`diagrams/active-usage-architecture.json`**: Add monitoring layer
- **`diagrams/active-usage-milestones.html`**: Reference enhanced watch

### New Diagrams
- **`diagrams/theteam-monitoring-architecture.json`**: Document monitoring layer
- **`diagrams/theteam-watch-enhancement.json`**: Show watch function improvements

## Technical Debt Resolution

**Problem Resolved:** The watch function was static and couldn't provide monitoring value.

**Solution:** Enhanced the existing watch function as a monitoring overlay that:
- Preserves all existing contracts
- Adds change detection and alerting
- Provides real-time monitoring without breaking the machine surface
- Integrates with the existing state management system

This approach solves the user's need for a monitoring tool while respecting the architectural constraints and avoiding the team's recommendation against a new TUI layer.

## Validation

**File Status:** STANDALONE_PROMPT.md needs to be created
**Key Changes:** Enhanced watch function with monitoring capabilities, new monitoring layer, API integration
**Timeline:** 3 days critical path
**Risk:** Low - leverages existing, well-tested codebase

This revised plan makes the `theteam` skill genuinely usable as a monitoring tool while preserving all existing functionality and respecting the team's architectural guidance.