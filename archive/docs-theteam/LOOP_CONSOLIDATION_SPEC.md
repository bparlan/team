# Loop Consolidation Specification

## Overview
This document specifies the consolidation of competing loop implementations into a single stable, agent-friendly modular loop function.

## Current State Analysis
The project currently maintains TWO competing loop implementations:

### LoopManager (theteam/core/loop_manager.py, 736 lines)
- **Architecture**: Event-driven, pub/sub architecture
- **Phases**: IDLE→INITIALIZING→RUNNING→PAUSED→COMPLETING→ERROR
- **Features**: Background monitoring thread, state persistence, factory methods
- **Strengths**: Modular phase-based execution, comprehensive event handling

### LoopController (theteam/core/loop_controller.py, 562 lines)  
- **Architecture**: Simpler task scheduler
- **States**: STOPPED→STARTING→RUNNING→PAUSED→STOPPING→ERROR
- **Features**: Priority-based scheduling, retry logic, timeouts
- **Strengths**: Simpler interface, deterministic execution

## Unified Architecture Goals

### Design Principles
```
🔄 MODULARITY: Small, focused components with clear contracts
🎯 DETERMINISM: Predictable execution patterns for agents
🌉 INTEGRATION: Seamless system awareness integration
📊 VISIBILITY: Clear state and progress monitoring
⚡ PERFORMANCE: Efficient execution without overhead
```

### Core Components
1. **StateEngine**: Phase-based execution management
2. **TaskScheduler**: Time-based and event-driven scheduling
3. **ProgressTracker**: Deterministic progress reporting
4. **HealthMonitor**: System integration and monitoring
5. **EventSystem**: Unified event handling

### Agent Interface Contract
```python
class UnifiedLoop:
    """Stable, agent-friendly loop function with clear contracts."""
    
    # Lifecycle Management
    def start(self) -> bool
    def stop(self) -> bool  
    def pause(self) -> bool
    def resume(self) -> bool
    
    # Task Management
    def add_task(self, task: LoopTask) -> bool
    def remove_task(self, task_id: str) -> bool
    def get_status(self) -> Dict[str, Any]
    
    # System Integration (automatic)
    @property
    def health_metrics(self) -> Dict[str, Any]
    
    # Event Handling
    def add_event_handler(self, event_type: str, handler: Callable)
```

## Implementation Strategy

### Phase 1: Core Loop Function (Priority 1)
Create **UnifiedLoop** class that extends best of both implementations:

```python
class UnifiedLoop:
    def __init__(self, project_root: str, config: LoopConfig):
        # Consolidated initialization
        self.state_engine = StateEngine()
        self.task_scheduler = TaskScheduler()
        self.progress_tracker = ProgressTracker()
        self.health_monitor = HealthMonitor()
        self.event_system = EventSystem()
```

### Phase 2: Integration Simplification (Priority 2)
- **Consolidate** TaskManager and TaskStack into TaskRegistry
- **Standardize** StateManager across all components
- **Unify** EventBus system (eliminate sa_runner variants)
- **Streamline** configuration system

### Phase 3: Agent Experience Optimization (Priority 3)
Design for agent interaction:

```
🔍 MENTAL MODEL: "The loop is a stable, predictable execution engine"
🛠️ AGENT ACTIONS: start, stop, pause, resume, add_task, get_status
📊 VISIBILITY: Always know current state, progress, health
⚡ SIMPLICITY: One interface, not multiple competing systems
```

## Key Design Decisions

### 1. Mental Model for Agents
Agents should see **one predictable system**:
```
"I start a loop, it runs tasks, I can pause/stop it, I monitor progress"
```

### 2. Interface Simplicity
- **Clear state transitions**: Only 4 core states (STOPPED, RUNNING, PAUSED, STOPPED)
- **Deterministic behavior**: No hidden complexity in normal operations
- **Transparent progress**: Always know current status and progress

### 3. System Integration
- **Automatic health monitoring**: SystemIntegration built-in
- **Event-driven updates**: Real-time feedback to agents
- **Error recovery**: Graceful handling with clear retry logic

## UX/UI Considerations

### Visual Feedback
```
✅ START: Green "Loop Started" indicator
⏸️ PAUSE: Yellow "Paused" status
🛑 STOP: Red "Stopped" confirmation
📊 PROGRESS: Deterministic progress bar
⚠️ ERRORS: Clear error messages with suggested actions
```

### Error Handling
- **Predictable errors**: Same error handling across all operations
- **Clear recovery**: Simple steps to resolve common issues
- **Transparent state**: Always know why an operation failed

### Progress Visualization
```python
def get_status(self) -> Dict[str, Any]:
    return {
        'loop_state': 'RUNNING',           # Current state
        'progress_percentage': 45.2,       # Deterministic progress
        'tasks_completed': 7,              # Concrete metrics
        'tasks_pending': 3,
        'health_score': 0.85,              # System health
        'next_task_eta': '2026-09-24T07:00:00Z',  # Predictable timing
        'system_alerts': []                 # Current issues
    }
```

## Technical Implementation Details

### State Management
```python
class LoopState(Enum):
    STOPPED = auto()      # Initial, clean state
    STARTING = auto()     # Booting up
    RUNNING = auto()      # Active execution  
    PAUSED = auto()       # Interruptible state
    STOPPING = auto()     # Graceful shutdown
    ERROR = auto()        # With recovery capability
```

### Event Types for System Integration
```python
class LoopEventType(Enum):
    LOOP_STARTED = auto()      # New execution cycle
    LOOP_STOPPED = auto()      # Clean shutdown
    LOOP_PAUSED = auto()       # Interrupt by user/agent
    LOOP_RESUMED = auto()      # Continue after pause
    CYCLE_COMPLETED = auto()   # Full cycle finished
    TASK_STARTED = auto()      # Individual task begins
    TASK_COMPLETED = auto()    # Individual task finished
    TASK_FAILED = auto()       # With retry logic
    SYSTEM_ALERT = auto()      # Health/system issues
```

### Configuration Simplification
```python
@dataclass
class UnifiedLoopConfig:
    loop_id: str = auto-generated
    project_root: str = current directory
    
    # Execution settings
    auto_start: bool = False
    max_cycles: Optional[int] = None
    deterministic_mode: bool = True
    
    # Task settings
    default_interval: int = 60
    max_retries: int = 3
    timeout_seconds: int = 300
    
    # System integration
    enable_monitoring: bool = True
    health_check_interval: int = 30
    enable_automated_analysis: bool = True
    
    # Progress tracking
    enable_progress_reporting: bool = True
    progress_reporting_interval: int = 5
```

## Success Criteria

### Technical Requirements
- ✅ **Single Implementation**: One stable loop function (no competing systems)
- ✅ **Deterministic Behavior**: Predictable execution for agent operations
- ✅ **Proper Integration**: Seamless system integration
- ✅ **Clean Architecture**: Maintainable, documented codebase

### User Experience Requirements  
- ✅ **Simple Mental Model**: One predictable system agents can understand
- ✅ **Clear Interface**: Intuitive start/stop/pause/resume operations
- ✅ **Transparent State**: Always know current status and progress
- ✅ **Minimal Cognitive Load**: No need to understand competing implementations

### Operational Requirements
- ✅ **Working Tests**: All tests passing (fix test_bootstrap_creates_config)
- ✅ **Clean Documentation**: Single architectural guide
- ✅ **No Ledger Bloat**: Clean state management
- ✅ **Efficient Execution**: Minimal overhead, maximum predictability

## Next Steps

### Immediate Actions (Week 1)
1. **Eliminate sa_runner variants**: Keep only the most robust version
2. **Consolidate test files**: Fix test_bootstrap_creates_config and related tests
3. **Standardize documentation**: Create unified architecture documentation
4. **Extract common patterns**: Identify and extract shared logic from both loop implementations

### Medium-term Actions (Weeks 2-3)
1. **Implement UnifiedLoop**: Create the consolidated loop function
2. **Refactor integration**: Consolidate TaskManager and TaskStack
3. **Update interfaces**: Migrate existing users to new unified system
4. **Documentation updates**: Update all references to new system

### Long-term Actions (Month 1)
1. **Complete migration**: All systems using UnifiedLoop
2. **Performance optimization**: Fine-tune for production use
3. **Monitoring enhancement**: Add comprehensive observability
4. **Documentation completion**: Full user guide and API reference

## Conclusion

This consolidation creates a **simple, predictable, and trustworthy** system that agents can use reliably. By focusing on a single, well-designed implementation rather than maintaining competing solutions, we eliminate cognitive overhead and create a stable foundation for project development.

The key insight is that **agents need consistency and predictability** - not more complexity, but cleaner abstractions that make system interaction straightforward and reliable.