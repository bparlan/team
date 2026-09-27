# Usage Patterns - Refactored Team Discussion System

## Overview

This document provides comprehensive examples and patterns for using the refactored team discussion system in the Oh My Pi harness. It covers both legacy usage (for backward compatibility) and new lightweight usage patterns.

## Table of Contents

1. [Introduction](#introduction)
2. [Legacy Usage Patterns](#legacy-usage-patterns)
3. [Lightweight Usage Patterns](#lightweight-usage-patterns)
4. [Integration Patterns](#integration-patterns)
5. [Performance Optimization Patterns](#performance-optimization-patterns)
6. [Error Handling Patterns](#error-handling-patterns)
7. [Migration Patterns](#migration-patterns)
8. [Advanced Usage Patterns](#advanced-usage-patterns)
9. [Common Anti-Patterns](#common-anti-patterns)
10. [Troubleshooting Guide](#troubleshooting-guide)

## Introduction

The refactored team discussion system offers two main usage patterns:

- **Legacy Pattern**: Full backward compatibility with original DiscussionManager
- **Lightweight Pattern**: New, optimized interface for modern usage

Choose the pattern based on your requirements:
- **Legacy Pattern**: When maintaining existing integrations or requiring full API compatibility
- **Lightweight Pattern**: When building new features or optimizing performance

## Legacy Usage Patterns

### 1. Basic Discussion Management

#### Import and Initialize

```python
# Import original DiscussionManager (legacy pattern)
from theteam.workflow.discussion_manager import DiscussionManager

# Initialize with project root
project_root = "/path/to/project"
manager = DiscussionManager(project_root)
```

#### Create and Manage Discussions

```python
# Create a new discussion
discussion = manager.create_discussion(
    "Architecture Review",
    ["architect", "devops", "security"]
)
print(f"Created discussion: {discussion['discussion_id']}")

# Add participants
manager.add_participant(discussion['discussion_id'], "backend")
manager.add_participant(discussion['discussion_id'], "frontend")

# Add notes
manager.add_note(
    discussion['discussion_id'],
    "architect",
    {
        "content": "Need to review system integration patterns",
        "type": "architecture",
        "priority": "high"
    }
)

# Add and complete tasks
task_id = manager.add_task(
    discussion['discussion_id'],
    {
        "title": "Update system integration",
        "description": "Refactor TUI and system awareness",
        "assignee": "backend",
        "priority": "high"
    }
)

result = manager.complete_task(
    discussion['discussion_id'],
    task_id,
    {
        "status": "completed",
        "reviewer": "architect",
        "completion_notes": "Successfully refactored system integration"
    }
)

# Get discussion
retrieved = manager.get_discussion(discussion['discussion_id'])
print(f"Retrieved discussion with {len(retrieved['notes'])} notes")

# Get system status
status = manager.get_system_status()
print(f"System health: {status['system_health']}")
```

### 2. Advanced Legacy Patterns

#### Using Discussion Analytics

```python
# Get analytics for a discussion
analytics = manager.get_discussion_analytics(discussion['discussion_id'])
print(f"Task completion rate: {analytics['completed_tasks']}/{analytics['total_tasks']}")
print(f"Discussion age: {analytics['discussion_age']:.1f} seconds")
print(f"Participant count: {analytics['participants']}")
```

#### Search and Filter Discussions

```python
# Search discussions by topic
results = manager.search_discussions("architecture", ["topic"])
for discussion in results:
    print(f"Found: {discussion['topic']}")

# Get discussions by member
member_discussions = manager.get_discussions_by_member("architect")
for discussion in member_discussions:
    print(f"Architect participates in: {discussion['topic']}")

# Get discussions by status
active_discussions = manager.get_discussions_by_status("active")
completed_discussions = manager.get_discussions_by_status("completed")
```

#### Export and Import Discussion Data

```python
# Export discussion data
exported_data = manager.export_discussion_data(discussion['discussion_id'])
with open("discussion_backup.json", "w") as f:
    import json
    json.dump(exported_data, f, indent=2)

# Import discussion data
with open("discussion_backup.json", "r") as f:
    import_data = json.load(f)

import_result = manager.import_discussion_data(import_data)
print(f"Import successful: {import_result}")
```

#### Generate Topic Suggestions

```python
# Generate topic suggestions based on project context
project_context = {
    "project_type": "web_application",
    "team_size": 10,
    "current_focus": "performance_optimization",
    "recent_activities": ["database_optimization", "frontend_refactor"]
}

suggestions = manager.generate_topic_suggestions(project_context)
print("Suggested topics:")
for i, suggestion in enumerate(suggestions, 1):
    print(f"  {i}. {suggestion}")
```

#### Complete Discussion Lifecycle

```python
# Complete a discussion
complete_result = manager.complete_discussion(discussion['discussion_id'])
print(f"Discussion completed: {complete_result}")

# Get discussion history
history = manager.get_discussion_history(limit=5)
for i, disc in enumerate(history):
    print(f"{i+1}. {disc['topic']} - {disc['created_at']}")
```

### 3. System Monitoring (Legacy)

```python
# Start system monitoring
manager.start_monitoring(interval=300)  # 5 minutes

# Monitor system status continuously
import time
while True:
    status = manager.get_system_status()
    print(f"Status: {status['system_health']} - "
          f"{status['total_active_discussions']} discussions")
    time.sleep(60)  # Check every minute

# Stop monitoring
manager.stop_monitoring()
```

## Lightweight Usage Patterns

### 1. Basic Operations

#### Import and Initialize

```python
# Import lightweight interface
from theteam.workflow.discussion_interface import DiscussionInterface

# Initialize with project root
project_root = "/path/to/project"
interface = DiscussionInterface(project_root)
```

#### Simple Discussion Management

```python
# Create a discussion
discussion = interface.create_discussion(
    "Performance Optimization",
    ["performance", "devops"]
)
print(f"Created discussion: {discussion['discussion_id']}")

# Add a note
interface.add_note(
    discussion['discussion_id'],
    "performance",
    {
        "content": "Identify performance bottlenecks",
        "type": "performance_issue"
    }
)

# Add a task
task_id = interface.add_task(
    discussion['discussion_id'],
    {
        "title": "Profile application",
        "description": "Run performance profiling tools"
    }
)

# Complete the task
interface.complete_task(
    discussion['discussion_id'],
    task_id,
    {
        "status": "completed",
        "profile_results": "Found 3 bottlenecks"
    }
)

# Get system status
status = interface.get_system_status()
print(f"Active discussions: {status['total_active_discussions']}")
print(f"Total tasks: {status['total_tasks']}")
print(f"Completed tasks: {status['completed_tasks']}")
```

### 2. Module-Level Functions (Simplest Usage)

#### Using Module-Level Functions

```python
# Import module-level functions
from theteam.workflow.discussion_interface import (
    create_discussion,
    get_discussion,
    add_participant,
    get_system_status
)

# Simple discussion creation (no manager instance needed)
discussion = create_discussion(
    "/path/to/project",
    "Database Optimization",
    ["database", "backend"]
)
print(f"Created discussion: {discussion['discussion_id']}")

# Simple participant addition
add_participant(
    "/path/to/project",
    discussion['discussion_id'],
    "cache_admin"
)

# Get discussion status
discussion_status = get_discussion(
    "/path/to/project",
    discussion['discussion_id']
)

# Get system status
system_status = get_system_status("/path/to/project")
print(f"System health: {system_status['system_health']}")
```

### 3. Advanced Lightweight Patterns

#### Multiple Discussion Management

```python
# Manage multiple discussions efficiently
interface = DiscussionInterface("/path/to/project")

discussions = []
for topic, members in [
    ("Frontend Performance", ["frontend", "performance"]),
    ("Backend Optimization", ["backend", "performance"]),
    ("Database Tuning", ["database", "backend"])
]:
    discussion = interface.create_discussion(topic, members)
    discussions.append(discussion)
    print(f"Created: {discussion['discussion_id']} - {topic}")

# Get all active discussions
all_discussions = interface.get_active_discussions()
print(f"Total discussions: {len(all_discussions)}")

# Perform operations on all discussions
for discussion in all_discussions:
    task_id = interface.add_task(
        discussion['discussion_id'],
        {"title": f"Review {discussion['topic']}"}
    )
    interface.complete_task(
        discussion['discussion_id'],
        task_id,
        {"status": "completed"}
    )
```

#### Batch Operations

```python
# Perform batch operations for efficiency
interface = DiscussionInterface("/path/to/project")

# Create multiple discussions in batch
def create_batch_discussions(topics, members_list):
    created = []
    for topic, members in zip(topics, members_list):
        discussion = interface.create_discussion(topic, members)
        created.append(discussion)
    return created

batch = create_batch_discussions(
    ["Topic A", "Topic B", "Topic C"],
    [["user1"], ["user2"], ["user3"]]
)

# Batch status check
status = interface.get_system_status()
print(f"Batch operation completed: {len(batch)} discussions created")
print(f"New total: {status['total_active_discussions']} discussions")

# Batch cleanup
interface.cleanup_inactive_discussions(max_hours_inactive=24)
print("Cleanup completed")
```

#### Monitoring and Maintenance

```python
# Start monitoring for production use
interface.start_monitoring(interval=300)  # 5 minutes

# Check system status periodically
import time
for i in range(5):
    status = interface.get_system_status()
    print(f"Check {i+1}: {status['system_health']} "
          f"({status['total_active_discussions']} discussions)")
    time.sleep(30)

# Stop monitoring when done
interface.stop_monitoring()

# Cleanup old discussions
interface.cleanup_inactive_discussions(max_hours_inactive=48)
print("Cleanup completed")
```

## Integration Patterns

### 1. System Integration Layer

#### Integration with System Integration

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager
from theteam.core.system_integration import SystemIntegration

# Create discussion manager (legacy for compatibility)
discussion_manager = create_discussion_manager(
    "/path/to/project",
    use_legacy=True
)

# Initialize system integration with discussion manager
integration = SystemIntegration(
    "/path/to/project",
    discussion_manager=discussion_manager
)

# System integration will automatically use the discussion manager
# for discussion-related operations and monitoring
```

#### TUI Integration

```python
from theteam.ui.terminal_ui import TerminalUI

# Create discussion manager
discussion_manager = create_discussion_manager(
    "/path/to/project",
    use_legacy=True
)

# Initialize TUI with discussion manager
ui = TerminalUI(
    "/path/to/project",
    discussion_manager=discussion_manager
)

# TUI will use the discussion manager for:
# - Displaying discussion lists
# - Creating new discussions
# - Managing tasks and notes
# - Updating system status
```

### 2. Configuration Integration

#### Update System Configuration

```python
# Update system-awareness-config.json
import json

config_path = "/path/to/project/system-awareness-config.json"
with open(config_path, "r") as f:
    config = json.load(f)

# Configure for new discussion system
config["team_discussion"]["manager_type"] = "lightweight"
config["team_discussion"]["discussion_manager_class"] = "theteam.workflow.discussion_manager_refactored"

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print("Configuration updated for new discussion system")
```

#### Environment Configuration

```python
# Environment-based configuration
import os

class DiscussionConfig:
    def __init__(self):
        self.project_root = os.getenv("PROJECT_ROOT", "/default/project")
        self.discussion_type = os.getenv("DISCUSSION_TYPE", "lightweight")
        self.monitoring_interval = int(os.getenv("MONITORING_INTERVAL", "300"))
        self.cleanup_hours = int(os.getenv("CLEANUP_HOURS", "24"))
        
    def get_discussion_manager(self):
        if self.discussion_type == "legacy":
            from theteam.workflow.discussion_manager_refactored import create_discussion_manager
            return create_discussion_manager(self.project_root, use_legacy=True)
        else:
            from theteam.workflow.discussion_interface import DiscussionInterface
            return DiscussionInterface(self.project_root)

# Usage
config = DiscussionConfig()
manager = config.get_discussion_manager()
```

## Performance Optimization Patterns

### 1. Connection Pooling Pattern

```python
# Reuse discussion managers for better performance
from theteam.workflow.discussion_manager_refactored import create_discussion_manager

class DiscussionManagerPool:
    def __init__(self, project_root, pool_size=5):
        self.project_root = project_root
        self.pool_size = pool_size
        self.manager_pool = []
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize manager pool"""
        for _ in range(self.pool_size):
            manager = create_discussion_manager(self.project_root, use_legacy=True)
            self.manager_pool.append(manager)
    
    def get_manager(self):
        """Get a manager from the pool"""
        return self.manager_pool.pop() if self.manager_pool else None
    
    def return_manager(self, manager):
        """Return manager to the pool"""
        self.manager_pool.append(manager)
    
    def execute_batch(self, operation, data):
        """Execute batch operations efficiently"""
        results = []
        for item in data:
            manager = self.get_manager()
            if manager:
                result = operation(manager, item)
                results.append(result)
                self.return_manager(manager)
        return results

# Usage example
pool = DiscussionManagerPool("/path/to/project", pool_size=10)

def create_discussion_operation(manager, topic_members):
    topic, members = topic_members
    return manager.create_discussion(topic, members)

batch_topics = [("Topic A", ["user1"]), ("Topic B", ["user2"])]
results = pool.execute_batch(create_discussion_operation, batch_topics)
print(f"Batch created {len(results)} discussions")
```

### 2. Caching Pattern

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager
import time

class DiscussionCache:
    def __init__(self, project_root, cache_ttl=300):
        self.project_root = project_root
        self.cache_ttl = cache_ttl
        self.cache = {}
        self.manager = create_discussion_manager(project_root, use_legacy=True)
    
    def get_discussion_cached(self, discussion_id):
        """Get discussion with caching"""
        current_time = time.time()
        
        if discussion_id in self.cache:
            cached_data, timestamp = self.cache[discussion_id]
            if current_time - timestamp < self.cache_ttl:
                return cached_data
            else:
                del self.cache[discussion_id]
        
        # Fetch from manager if not in cache or expired
        discussion = self.manager.get_discussion(discussion_id)
        if discussion:
            self.cache[discussion_id] = (discussion, current_time)
        
        return discussion
    
    def get_system_status_cached(self):
        """Get system status with caching"""
        cache_key = "system_status"
        current_time = time.time()
        
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if current_time - timestamp < self.cache_ttl:
                return cached_data
        
        status = self.manager.get_system_status()
        self.cache[cache_key] = (status, current_time)
        return status

# Usage
cache = DiscussionCache("/path/to/project", cache_ttl=60)

# This will use cache for frequently accessed data
discussion = cache.get_discussion_cached("discussion_123")
status = cache.get_system_status_cached()
```

### 3. Lazy Loading Pattern

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager

class LazyDiscussionManager:
    def __init__(self, project_root):
        self.project_root = project_root
        self._manager = None
        self._discussion_cache = {}
        self._system_status_cache = None
    
    def _ensure_manager_loaded(self):
        """Lazy load the discussion manager"""
        if self._manager is None:
            from theteam.workflow.discussion_manager_refactored import create_discussion_manager
            self._manager = create_discussion_manager(self.project_root, use_legacy=True)
    
    def create_discussion(self, topic, member_ids):
        """Create discussion (lazy load)"""
        self._ensure_manager_loaded()
        return self._manager.create_discussion(topic, member_ids)
    
    def get_discussion(self, discussion_id):
        """Get discussion (lazy load with caching)"""
        if discussion_id not in self._discussion_cache:
            self._ensure_manager_loaded()
            discussion = self._manager.get_discussion(discussion_id)
            self._discussion_cache[discussion_id] = discussion
        
        return self._discussion_cache[discussion_id]
    
    def get_system_status(self):
        """Get system status (lazy load with caching)"""
        if self._system_status_cache is None:
            self._ensure_manager_loaded()
            self._system_status_cache = self._manager.get_system_status()
        
        return self._system_status_cache

# Usage - manager loads on first use
lazy_manager = LazyDiscussionManager("/path/to/project")

# Manager loads automatically here
discussion = lazy_manager.create_discussion("Lazy Topic", ["user1"])
print("Manager loaded automatically")

# Subsequent calls use cached data
status = lazy_manager.get_system_status()
```

## Error Handling Patterns

### 1. Graceful Degradation Pattern

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager
import logging

class ResilientDiscussionManager:
    def __init__(self, project_root):
        self.project_root = project_root
        self.logger = logging.getLogger(__name__)
        self._primary_manager = None
        self._fallback_manager = None
    
    def _initialize_managers(self):
        """Initialize primary and fallback managers"""
        try:
            # Try to initialize primary manager
            self._primary_manager = create_discussion_manager(
                self.project_root, use_legacy=True
            )
            self.logger.info("Primary discussion manager initialized")
        except Exception as e:
            self.logger.error(f"Primary manager initialization failed: {e}")
            self._primary_manager = None
        
        try:
            # Initialize fallback manager (lightweight)
            from theteam.workflow.discussion_interface import DiscussionInterface
            self._fallback_manager = DiscussionInterface(self.project_root)
            self.logger.info("Fallback discussion manager initialized")
        except Exception as e:
            self.logger.error(f"Fallback manager initialization failed: {e}")
            self._fallback_manager = None
    
    def create_discussion(self, topic, member_ids):
        """Create discussion with graceful fallback"""
        # Try primary manager first
        if self._primary_manager:
            try:
                return self._primary_manager.create_discussion(topic, member_ids)
            except Exception as e:
                self.logger.warning(f"Primary manager failed: {e}")
        
        # Fallback to lightweight manager
        if self._fallback_manager:
            try:
                return self._fallback_manager.create_discussion(topic, member_ids)
            except Exception as e:
                self.logger.error(f"Fallback manager also failed: {e}")
        
        # All managers failed
        raise Exception("All discussion managers failed to create discussion")
    
    def get_system_status(self):
        """Get system status with graceful degradation"""
        # Try primary manager first
        if self._primary_manager:
            try:
                return self._primary_manager.get_system_status()
            except Exception as e:
                self.logger.warning(f"Primary manager status failed: {e}")
        
        # Fallback to lightweight manager
        if self._fallback_manager:
            try:
                return self._fallback_manager.get_system_status()
            except Exception as e:
                self.logger.error(f"Fallback manager status also failed: {e}")
        
        # Return minimal status if all managers fail
        return {
            "total_active_discussions": 0,
            "system_health": "degraded",
            "error": "All discussion managers unavailable",
            "timestamp": time.time()
        }

# Usage with resilient error handling
resilient_manager = ResilientDiscussionManager("/path/to/project")

# This will automatically handle failures gracefully
status = resilient_manager.get_system_status()
print(f"Status even during partial failures: {status}")
```

### 2. Circuit Breaker Pattern

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager
import time

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                self.logger.info("Circuit breaker moving to HALF_OPEN state")
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.logger.warning("Circuit breaker moved to OPEN state")

class ProtectedDiscussionManager:
    def __init__(self, project_root):
        self.project_root = project_root
        self.circuit_breaker = CircuitBreaker()
        self.manager = create_discussion_manager(project_root, use_legacy=True)
    
    def create_discussion(self, topic, member_ids):
        """Create discussion with circuit breaker protection"""
        return self.circuit_breaker.call(
            self.manager.create_discussion, topic, member_ids
        )
    
    def get_system_status(self):
        """Get system status with circuit breaker protection"""
        return self.circuit_breaker.call(self.manager.get_system_status)

# Usage with circuit breaker protection
protected_manager = ProtectedDiscussionManager("/path/to/project")

# Calls are protected by circuit breaker
status = protected_manager.get_system_status()
```

## Migration Patterns

### 1. Phased Migration

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager

class MigrationManager:
    def __init__(self, project_root):
        self.project_root = project_root
        self.migration_phase = "ANALYSIS"  # ANALYSIS, DEPLOYMENT, VALIDATION, COMPLETE
        self.original_manager = None
        self.new_manager = None
    
    def migrate_to_new_system(self):
        """Migrate to new discussion system in phases"""
        print("Starting migration to new discussion system...")
        
        # Phase 1: Analysis and setup
        self._phase1_analysis()
        
        # Phase 2: Gradual deployment
        self._phase2_deployment()
        
        # Phase 3: Validation
        self._phase3_validation()
        
        # Phase 4: Complete migration
        self._phase4_complete()
    
    def _phase1_analysis(self):
        """Phase 1: Analysis and preparation"""
        print("Phase 1: Analysis and preparation")
        
        # Backup current system
        self._backup_current_system()
        
        # Analyze usage patterns
        self._analyze_usage_patterns()
        
        # Plan migration strategy
        self._plan_migration_strategy()
        
        # Set migration phase
        self.migration_phase = "DEPLOYMENT"
    
    def _phase2_deployment(self):
        """Phase 2: Gradual deployment"""
        print("Phase 2: Gradual deployment")
        
        # Create new manager
        self.new_manager = create_discussion_manager(
            self.project_root, use_legacy=True
        )
        
        # Deploy to non-critical services first
        self._deploy_to_non_critical_services()
        
        # Monitor for issues
        self._monitor_migration()
        
        # If successful, switch critical services
        if self._check_migration_success():
            self._switch_critical_services()
            self.migration_phase = "VALIDATION"
    
    def _phase3_validation(self):
        """Phase 3: Validation"""
        print("Phase 3: Validation")
        
        # Compare systems
        self._compare_systems()
        
        # Validate all functionality
        self._validate_all_functionality()
        
        # Get user feedback
        self._get_user_feedback()
        
        if self._validation_passed():
            self.migration_phase = "COMPLETE"
    
    def _phase4_complete(self):
        """Phase 4: Complete migration"""
        print("Phase 4: Complete migration")
        
        # Decommission old system
        self._decommission_old_system()
        
        # Update documentation
        self._update_documentation()
        
        # Final verification
        self._final_verification()
    
    def _backup_current_system(self):
        """Backup current discussion system"""
        # Implementation for backing up current system
        print("Backing up current discussion system...")
    
    def _deploy_to_non_critical_services(self):
        """Deploy new system to non-critical services"""
        print("Deploying to non-critical services...")
    
    def _monitor_migration(self):
        """Monitor migration for issues"""
        print("Monitoring migration...")
    
    def _check_migration_success(self):
        """Check if migration was successful"""
        return True  # Simplified for example
    
    def _switch_critical_services(self):
        """Switch critical services to new system"""
        print("Switching critical services to new system...")
        
        # Replace old manager with new manager
        self.original_manager = None
    
    def _compare_systems(self):
        """Compare old and new systems"""
        print("Comparing old and new systems...")
    
    def _validate_all_functionality(self):
        """Validate all functionality"""
        print("Validating all functionality...")
    
    def _get_user_feedback(self):
        """Get user feedback"""
        print("Getting user feedback...")
    
    def _validation_passed(self):
        """Check if validation passed"""
        return True  # Simplified for example
    
    def _decommission_old_system(self):
        """Decommission old discussion system"""
        print("Decommissioning old discussion system...")
    
    def _update_documentation(self):
        """Update documentation"""
        print("Updating documentation...")
    
    def _final_verification(self):
        """Perform final verification"""
        print("Performing final verification...")

# Usage
migration_manager = MigrationManager("/path/to/project")
migration_manager.migrate_to_new_system()
```

### 2. Hybrid Mode

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager

class HybridDiscussionSystem:
    """Hybrid system supporting both old and new functionality"""
    
    def __init__(self, project_root):
        self.project_root = project_root
        self.legacy_manager = create_discussion_manager(
            project_root, use_legacy=True
        )
        self.lightweight_manager = create_discussion_manager(
            project_root, use_legacy=False
        )
        self.manager_mode = "HYBRID"  # LEGACY, LIGHTWEIGHT, HYBRID
    
    def set_manager_mode(self, mode):
        """Set manager mode"""
        if mode in ["LEGACY", "LIGHTWEIGHT", "HYBRID"]:
            self.manager_mode = mode
        else:
            raise ValueError(f"Invalid manager mode: {mode}")
    
    def create_discussion(self, topic, member_ids, **kwargs):
        """Create discussion based on current manager mode"""
        if self.manager_mode == "LEGACY":
            return self.legacy_manager.create_discussion(topic, member_ids)
        elif self.manager_mode == "LIGHTWEIGHT":
            return self.lightweight_manager.create_discussion(topic, member_ids)
        else:  # HYBRID
            # Use legacy manager for legacy methods
            # Use lightweight manager for new methods
            return self.legacy_manager.create_discussion(topic, member_ids)
    
    def get_system_status(self, **kwargs):
        """Get system status based on current manager mode"""
        if self.manager_mode == "LEGACY":
            return self.legacy_manager.get_system_status()
        elif self.manager_mode == "LIGHTWEIGHT":
            return self.lightweight_manager.get_system_status()
        else:  # HYBRID
            # Combine status from both managers
            legacy_status = self.legacy_manager.get_system_status()
            lightweight_status = self.lightweight_manager.get_system_status()
            
            return {
                "legacy_system": legacy_status,
                "lightweight_system": lightweight_status,
                "combined_total_discussions": (
                    legacy_status["total_active_discussions"] +
                    lightweight_status["total_active_discussions"]
                ),
                "system_health": "healthy" if self.manager_mode == "HYBRID" else "unknown"
            }

# Usage with hybrid mode
hybrid_system = HybridDiscussionSystem("/path/to/project")

# Start with hybrid mode
hybrid_system.set_manager_mode("HYBRID")
discussion = hybrid_system.create_discussion("Hybrid Topic", ["user1"])

# Switch to lightweight mode for performance
hybrid_system.set_manager_mode("LIGHTWEIGHT")
status = hybrid_system.get_system_status()
print(f"Switched to lightweight mode: {status}")

# Switch back to legacy mode for compatibility
hybrid_system.set_manager_mode("LEGACY")
```

## Advanced Usage Patterns

### 1. Event-Driven Pattern

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager
import time

class EventDrivenDiscussionSystem:
    """Event-driven discussion system"""
    
    def __init__(self, project_root):
        self.project_root = project_root
        self.manager = create_discussion_manager(project_root, use_legacy=True)
        self.event_handlers = {}
        self.event_bus = EventBus()
    
    def register_event_handler(self, event_type, handler):
        """Register event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def handle_event(self, event_type, event_data):
        """Handle event and notify registered handlers"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(event_data)
                except Exception as e:
                    print(f"Error in event handler: {e}")
    
    def create_discussion_with_events(self, topic, member_ids):
        """Create discussion and trigger events"""
        discussion = self.manager.create_discussion(topic, member_ids)
        
        # Trigger discussion created event
        self.handle_event("discussion_created", {
            "discussion_id": discussion["discussion_id"],
            "topic": discussion["topic"],
            "member_ids": discussion["member_ids"],
            "timestamp": time.time()
        })
        
        return discussion
    
    def complete_task_with_events(self, discussion_id, task_id, result):
        """Complete task and trigger events"""
        success = self.manager.complete_task(discussion_id, task_id, result)
        
        if success:
            # Trigger task completed event
            self.handle_event("task_completed", {
                "discussion_id": discussion_id,
                "task_id": task_id,
                "result": result,
                "timestamp": time.time()
            })
        
        return success

# Usage with event-driven patterns
class DiscussionEventHandler:
    def __init__(self, system):
        self.system = system
    
    def on_discussion_created(self, event_data):
        print(f"📝 Discussion created: {event_data['topic']} "
              f"(ID: {event_data['discussion_id']})")
    
    def on_task_completed(self, event_data):
        print(f"✅ Task completed in discussion {event_data['discussion_id']} "
              f"with result: {event_data['result']['status']}")

# Create event-driven system
event_system = EventDrivenDiscussionSystem("/path/to/project")
handler = DiscussionEventHandler(event_system)
event_system.register_event_handler("discussion_created", handler.on_discussion_created)
event_system.register_event_handler("task_completed", handler.on_task_completed)

# Use event-driven system
discussion = event_system.create_discussion_with_events(
    "Event-Driven Topic", ["user1", "user2"]
)
```

### 2. Actor Model Pattern

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager
import threading
import time

class DiscussionActor:
    """Actor model for discussion management"""
    
    def __init__(self, actor_id, project_root):
        self.actor_id = actor_id
        self.project_root = project_root
        self.manager = create_discussion_manager(project_root, use_legacy=True)
        self.message_queue = []
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def send_message(self, message_type, data):
        """Send message to actor"""
        message = {
            "type": message_type,
            "data": data,
            "sender": self.actor_id,
            "timestamp": time.time()
        }
        self.message_queue.append(message)
    
    def receive_message(self):
        """Receive and process messages"""
        if self.message_queue:
            return self.message_queue.pop(0)
        return None
    
    def _run(self):
        """Actor main loop"""
        while self.is_running:
            message = self.receive_message()
            if message:
                self._process_message(message)
            time.sleep(0.1)  # Small delay to prevent busy waiting
    
    def _process_message(self, message):
        """Process incoming message"""
        message_type = message["type"]
        data = message["data"]
        
        if message_type == "CREATE_DISCUSSION":
            self._handle_create_discussion(data)
        elif message_type == "GET_DISCUSSION":
            self._handle_get_discussion(data)
        elif message_type == "ADD_NOTE":
            self._handle_add_note(data)
        elif message_type == "ADD_TASK":
            self._handle_add_task(data)
        elif message_type == "COMPLETE_TASK":
            self._handle_complete_task(data)
    
    def _handle_create_discussion(self, data):
        """Handle create discussion message"""
        discussion = self.manager.create_discussion(data["topic"], data["member_ids"])
        self.send_message("DISCUSSION_CREATED", {
            "discussion_id": discussion["discussion_id"],
            "topic": discussion["topic"]
        })
    
    def _handle_get_discussion(self, data):
        """Handle get discussion message"""
        discussion = self.manager.get_discussion(data["discussion_id"])
        self.send_message("DISCUSSION_RETRIEVED", {
            "discussion_id": data["discussion_id"],
            "discussion": discussion
        })
    
    def _handle_add_note(self, data):
        """Handle add note message"""
        success = self.manager.add_note(
            data["discussion_id"],
            data["member_id"],
            data["note_data"]
        )
        self.send_message("NOTE_ADDED", {
            "discussion_id": data["discussion_id"],
            "success": success
        })
    
    def _handle_add_task(self, data):
        """Handle add task message"""
        task_id = self.manager.add_task(
            data["discussion_id"],
            data["task_info"]
        )
        self.send_message("TASK_ADDED", {
            "discussion_id": data["discussion_id"],
            "task_id": task_id
        })
    
    def _handle_complete_task(self, data):
        """Handle complete task message"""
        success = self.manager.complete_task(
            data["discussion_id"],
            data["task_id"],
            data["result"]
        )
        self.send_message("TASK_COMPLETED", {
            "discussion_id": data["discussion_id"],
            "task_id": data["task_id"],
            "success": success
        })

# Usage with actor model
actors = [
    DiscussionActor("actor1", "/path/to/project"),
    DiscussionActor("actor2", "/path/to/project"),
    DiscussionActor("actor3", "/path/to/project")
]

# Actors work concurrently
actors[0].send_message("CREATE_DISCUSSION", {
    "topic": "Actor Model Topic",
    "member_ids": ["actor1", "actor2"]
})

# Let actors process messages
time.sleep(1)

# Multiple actors can process different operations concurrently
for actor in actors:
    actor.send_message("CREATE_DISCUSSION", {
        "topic": f"Topic from {actor.actor_id}",
        "member_ids": [actor.actor_id]
    })
```

## Common Anti-Patterns

### 1. Mixing Manager Instances

```python
# ❌ ANTI-PATTERN: Mixing different manager instances
manager1 = create_discussion_manager(".", use_legacy=True)
manager2 = create_discussion_manager(".", use_legacy=False)

# This can lead to inconsistent state
discussion1 = manager1.create_discussion("Topic 1", ["user1"])
discussion2 = manager2.create_discussion("Topic 2", ["user1"])

# User1 appears in both systems but discussions are not shared
print(f"Manager1 discussions: {len(manager1.get_active_discussions())}")
print(f"Manager2 discussions: {len(manager2.get_active_discussions())}")

# ✅ BETTER: Use consistent manager instance
consistent_manager = create_discussion_manager(".", use_legacy=True)
discussion = consistent_manager.create_discussion("Topic", ["user1"])
print(f"Consistent system: {len(consistent_manager.get_active_discussions())} discussions")
```

### 2. Ignoring Error Handling

```python
# ❌ ANTI-PATTERN: Ignoring error handling
from theteam.workflow.discussion_manager_refactored import create_discussion_manager

manager = create_discussion_manager(".", use_legacy=True)

# This can fail silently or with cryptic errors
discussion = manager.create_discussion(None, None)  # Invalid data
print(f"Created discussion: {discussion}")  # Might print None or crash

# ✅ BETTER: Proper error handling
manager = create_discussion_manager(".", use_legacy=True)

try:
    discussion = manager.create_discussion("Valid Topic", ["valid_user"])
    print(f"Created discussion: {discussion['discussion_id']}")
except Exception as e:
    print(f"Error creating discussion: {e}")
    # Handle error appropriately
```

### 3. Over-Reliance on Caching

```python
# ❌ ANTI-PATTERN: Over-relying on caching
from theteam.workflow.discussion_manager_refactored import create_discussion_manager

manager = create_discussion_manager(".", use_legacy=True)
status = manager.get_system_status()
print(f"Cached status: {status}")

# Data is stale or cached
import time
time.sleep(300)  # Wait 5 minutes
status = manager.get_system_status()  # Still uses old cache
print(f"Stale status: {status}")

# ✅ BETTER: Balance cache and freshness
manager = create_discussion_manager(".", use_legacy=True)

# Get fresh status when needed
status = manager.get_system_status()
print(f"Fresh status: {status}")

# Cache for performance in bulk operations
statuses = []
for i in range(10):
    status = manager.get_system_status()  # May use cache
    statuses.append(status)
```

### 4. Inconsistent Manager Modes

```python
# ❌ ANTI-PATTERN: Inconsistent manager modes in same application
from theteam.workflow.discussion_manager_refactored import create_discussion_manager

# Different parts of the application use different modes
legacy_manager = create_discussion_manager(".", use_legacy=True)
lightweight_manager = create_discussion_manager(".", use_legacy=False)

# Create discussions with different managers
discussion1 = legacy_manager.create_discussion("Legacy Topic", ["user1"])
discussion2 = lightweight_manager.create_discussion("Lightweight Topic", ["user1"])

# Inconsistent state
print(f"Legacy discussions: {len(legacy_manager.get_active_discussions())}")
print(f"Lightweight discussions: {len(lightweight_manager.get_active_discussions())}")

# ✅ BETTER: Consistent manager usage
consistent_manager = create_discussion_manager(".", use_legacy=True)

# All operations use the same manager
discussion1 = consistent_manager.create_discussion("Topic 1", ["user1"])
discussion2 = consistent_manager.create_discussion("Topic 2", ["user2"])

print(f"Consistent discussions: {len(consistent_manager.get_active_discussions())}")
```

## Troubleshooting Guide

### 1. Discussion Not Found

#### Symptoms
- Attempting to retrieve a discussion that doesn't exist
- Discussion appears to be missing or deleted

#### Solutions

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager

manager = create_discussion_manager(".", use_legacy=True)

# Solution 1: Check if discussion exists first
discussion_id = "non_existent_id"
discussion = manager.get_discussion(discussion_id)
if discussion is None:
    print("Discussion not found or has been cleaned up")
    # Create new discussion instead
    discussion = manager.create_discussion("New Topic", ["user1"])

# Solution 2: Use legacy analytics to debug
analytics = manager.get_discussion_analytics(discussion_id)
print(f"Debug info: {analytics}")
```

### 2. Performance Issues

#### Symptoms
- Discussion operations are slow
- System status takes a long time
- Multiple slow operations in sequence

#### Solutions

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager

manager = create_discussion_manager(".", use_legacy=True)

# Solution 1: Check system status for bottlenecks
status = manager.get_system_status()
print(f"Active discussions: {status['total_active_discussions']}")
print(f"Total tasks: {status['total_tasks']}")

if status['total_active_discussions'] > 1000:
    print("⚠️  High number of discussions may cause performance issues")
    # Consider cleanup
    manager.cleanup_inactive_discussions(max_hours_inactive=24)

# Solution 2: Use lightweight manager for better performance
lightweight_manager = create_discussion_manager(".", use_legacy=False)

# Lightweight operations are faster
start_time = time.time()
discussion = lightweight_manager.create_discussion("Fast Topic", ["user1"])
end_time = time.time()
print(f"Lightweight creation took: {end_time - start_time:.2f}s")
```

### 3. Legacy Compatibility Issues

#### Symptoms
- Original DiscussionManager methods not working
- Integration with existing code fails
- API calls are not being processed correctly

#### Solutions

```python
# Solution 1: Ensure correct import
from theteam.workflow.discussion_manager import DiscussionManager

# Solution 2: Use legacy mode in factory function
from theteam.workflow.discussion_manager_refactored import create_discussion_manager

manager = create_discussion_manager(".", use_legacy=True)

# Solution 3: Check for namespace conflicts
import sys
print("Python path:", sys.path)

# Solution 4: Verify module structure
import theteam.workflow.discussion_manager_refactored as dm
print("Module contents:", dir(dm))
```

### 4. Error Handling and Recovery

#### Symptoms
- Operations failing with cryptic errors
- No clear error messages
- System in inconsistent state

#### Solutions

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager
import logging

# Setup proper logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

manager = create_discussion_manager(".", use_legacy=True)

# Solution 1: Comprehensive error handling
try:
    discussion = manager.create_discussion("Test Topic", ["user1"])
    print(f"Success: {discussion['discussion_id']}")
except Exception as e:
    logger.error(f"Failed to create discussion: {e}")
    # Attempt recovery
    try:
        # Fallback operation
        discussion = manager.create_discussion("Fallback Topic", ["user1"])
        print(f"Recovered: {discussion['discussion_id']}")
    except Exception as fallback_error:
        logger.critical(f"Recovery failed: {fallback_error}")

# Solution 2: Retry mechanism
import time

for attempt in range(3):
    try:
        discussion = manager.create_discussion(f"Retry Topic {attempt}", ["user1"])
        print(f"Success on attempt {attempt + 1}: {discussion['discussion_id']}")
        break
    except Exception as e:
        logger.warning(f"Attempt {attempt + 1} failed: {e}")
        if attempt < 2:  # Not last attempt
            time.sleep(1)  # Wait before retry
        else:
            logger.error("All attempts failed")
```

### 5. Memory Issues

#### Symptoms
- High memory usage
- Memory leaks
- System becoming unresponsive

#### Solutions

```python
from theteam.workflow.discussion_manager_refactored import create_discussion_manager
import psutil
import os

manager = create_discussion_manager(".", use_legacy=True)

# Solution 1: Monitor memory usage
process = psutil.Process(os.getpid())

while True:
    memory_info = process.memory_info()
    print(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")
    
    if memory_info.rss > 100 * 1024 * 1024:  # 100 MB threshold
        print("⚠️  High memory usage detected")
        # Perform cleanup
        cleaned = manager.cleanup_inactive_discussions()
        print(f"Cleaned up {cleaned} discussions")
    
    time.sleep(30)  # Check every 30 seconds

# Solution 2: Use lightweight manager (lower memory)
lightweight_manager = create_discussion_manager(".", use_legacy=False)

# Lightweight manager uses less memory
print("Switched to lightweight manager for better memory efficiency")
```

## Conclusion

The refactored team discussion system offers a rich set of usage patterns to suit different scenarios:

- **Legacy Patterns**: For maintaining backward compatibility
- **Lightweight Patterns**: For performance and simplicity
- **Integration Patterns**: For system integration and coordination
- **Performance Patterns**: For optimization and scaling
- **Error Handling Patterns**: For robust and resilient operations
- **Migration Patterns**: For smooth transition between versions
- **Advanced Patterns**: For complex and specialized use cases

Choose the pattern that best fits your requirements:

1. **Legacy Compatibility**: Use Legacy DiscussionManager or factory with `use_legacy=True`
2. **Performance Optimization**: Use Lightweight DiscussionManager or factory with `use_legacy=False`
3. **System Integration**: Use the new lightweight interface with system integration
4. **Error Resilience**: Implement error handling and recovery patterns
5. **Migration**: Use phased migration with hybrid mode for gradual transition

The key to successful usage is:

- **Consistent Manager Usage**: Use the same manager instance throughout your application
- **Proper Error Handling**: Implement comprehensive error handling and recovery
- **Performance Monitoring**: Monitor system performance and optimize as needed
- **Regular Maintenance**: Perform regular cleanup and maintenance operations
- **Testing**: Thoroughly test all functionality before production deployment

These patterns provide a solid foundation for building robust, performant, and maintainable discussion systems in the Oh My Pi harness.