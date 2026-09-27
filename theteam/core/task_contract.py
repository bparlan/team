#!/usr/bin/env python3
"""
task_contract.py - Unified Task Contract

This file implements the single, canonical Task data structure required by the
Stability Architecture Roadmap Phase 1.

Previously theteam had 3 divergent task management systems with incompatible
Task definitions. This unified contract provides:
- Single canonical Task dataclass with status, priority, scheduling
- Backward compatibility through adapter patterns where needed
- Clear contract interface for all loop implementations

Core tasks:
1. Delete LoopController (562 lines) - COMPLETED
2. Make UnifiedLoop the single loop implementation - IN PROGRESS
3. Define unified Task contract - COMPLETED
4. Add state file validation on load - IN PROGRESS
5. Consolidate TaskManager/TaskStack into unified contracts - PENDING

This is a Phase 1 deliverable from STABILITY_ROADMAP.md
"""

import uuid
import time
import json
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod

class TaskStatus(Enum):
    """Unified task status enumeration - single source of truth."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

    @classmethod
    def is_terminal(cls, status: 'TaskStatus') -> bool:
        """Check if task status is terminal (cannot transition)."""
        return status in [cls.COMPLETED, cls.FAILED, cls.TIMEOUT, cls.CANCELLED]

    @classmethod
    def is_active(cls, status: 'TaskStatus') -> bool:
        """Check if task is actively running."""
        return status == cls.RUNNING

class TaskPriority(Enum):
    """Standard priority levels for unified task scheduling."""
    CRITICAL = 100
    HIGH = 50
    NORMAL = 0
    LOW = -50
    BACKGROUND = -100

    @classmethod
    def from_str(cls, priority_str: str) -> 'TaskPriority':
        """Convert string to priority enum."""
        priority_map = {
            'critical': cls.CRITICAL,
            'high': cls.HIGH,
            'normal': cls.NORMAL,
            'low': cls.LOW,
            'background': cls.BACKGROUND,
        }
        return priority_map.get(priority_str.lower(), cls.NORMAL)

class UnifiedTask:
    """
    Canonical Task definition - single source of truth for all task systems.
    
    Previously LoopController, LoopManager, and TaskManager each had different
    Task classes with different fields and behaviors. This unified contract
    consolidates them while maintaining backward compatibility.
    """
    
    def __init__(
        self,
        task_id: Optional[str] = None,
        name: Optional[str] = None,
        handler: Optional[Callable] = None,
        status: TaskStatus = TaskStatus.PENDING,
        priority: TaskPriority = TaskPriority.NORMAL,
        schedule: Optional[Dict[str, Any]] = None,
        interval: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        timeout: Optional[timedelta] = None,
        retry_count: int = 0,
        max_retries: int = 3,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.name = name or "Unnamed Task"
        self.handler = handler
        self.status = status
        self.priority = priority
        # `interval` is shorthand for the recurring-schedule cadence; the
        # schedule dict stays the single representation.
        self.schedule = dict(schedule or {})
        if interval is not None:
            self.schedule.setdefault('interval', interval)
        self.parameters = parameters or {}
        self.dependencies = dependencies or []
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now(timezone.utc)
        self.started_at = started_at
        self.completed_at = completed_at
        self.timeout = timeout
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.result = result
        self.error = error
        
        # Validate task structure
        self._validate()
    
    def _validate(self) -> None:
        """Validate task contract integrity."""
        if not self.task_id:
            raise ValueError("Task must have a task_id")
        
        if not self.name:
            raise ValueError("Task must have a name")
        
        if not isinstance(self.status, TaskStatus):
            raise ValueError(f"Task status must be TaskStatus, got {type(self.status)}")
        
        if not isinstance(self.priority, TaskPriority):
            raise ValueError(f"Task priority must be TaskPriority, got {type(self.priority)}")
        
        if self.metadata is None:
            self.metadata = {}
        
        if self.parameters is None:
            self.parameters = {}
        
        if self.dependencies is None:
            self.dependencies = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'name': self.name,
            'status': self.status.value,
            'priority': self.priority.value,
            'schedule': self.schedule,
            'parameters': self.parameters,
            'dependencies': self.dependencies,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'timeout': self.timeout.total_seconds() if self.timeout else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'result': self.result,
            'error': self.error,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedTask':
        """Create task from dictionary (for deserialization)."""
        task = cls()
        
        # Set basic attributes
        task.task_id = data.get('task_id')
        task.name = data.get('name')
        task.status = TaskStatus(data.get('status', 'pending'))
        task.priority = TaskPriority(data.get('priority', 0))
        task.schedule = data.get('schedule', {})
        task.parameters = data.get('parameters', {})
        task.dependencies = data.get('dependencies', [])
        task.metadata = data.get('metadata', {})
        task.retry_count = data.get('retry_count', 0)
        task.max_retries = data.get('max_retries', 3)
        task.result = data.get('result')
        task.error = data.get('error')
        
        # Parse datetime fields
        for field_name, attr_name in [
            ('created_at', 'created_at'),
            ('started_at', 'started_at'),
            ('completed_at', 'completed_at'),
        ]:
            if field_name in data and data[field_name]:
                setattr(task, attr_name, datetime.fromisoformat(data[field_name]))
        
        # Parse timeout
        if 'timeout' in data and data['timeout'] is not None:
            task.timeout = timedelta(seconds=data['timeout'])
        
        return task
    
    def can_start(self) -> bool:
        """Check if task can start execution."""
        return self.status == TaskStatus.PENDING and not self.is_cancelled()
    
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return (
            self.status == TaskStatus.FAILED and
            self.retry_count < self.max_retries
        )
    
    def is_cancelled(self) -> bool:
        """Check if task has been cancelled."""
        return self.status == TaskStatus.CANCELLED
    
    def is_terminal(self) -> bool:
        """Check if task has reached a terminal state."""
        return self.status.is_terminal()
    
    def is_active(self) -> bool:
        """Check if task is currently running."""
        return self.status.is_active()
    
    def set_running(self) -> None:
        """Mark task as running."""
        if self.can_start():
            self.status = TaskStatus.RUNNING
            self.started_at = datetime.now(timezone.utc)
        else:
            raise ValueError(f"Cannot start task with status: {self.status}")
    
    def complete(self, result: Any = None) -> None:
        """Mark task as completed with result."""
        if self.is_active():
            self.status = TaskStatus.COMPLETED
            self.result = result
            self.completed_at = datetime.now(timezone.utc)
        else:
            raise ValueError(f"Cannot complete task with status: {self.status}")
    
    def fail(self, error: Optional[str] = None) -> None:
        """Mark task as failed with error."""
        if self.is_active():
            self.status = TaskStatus.FAILED
            self.error = error
            self.completed_at = datetime.now(timezone.utc)
        else:
            raise ValueError(f"Cannot fail task with status: {self.status}")
    
    def timeout(self) -> None:
        """Mark task as timed out."""
        if self.is_active() or self.status == TaskStatus.PENDING:
            self.status = TaskStatus.TIMEOUT
            self.completed_at = datetime.now(timezone.utc)
        else:
            raise ValueError(f"Cannot timeout task with status: {self.status}")
    
    def cancel(self) -> None:
        """Cancel the task."""
        if not self.is_terminal():
            self.status = TaskStatus.CANCELLED
            self.completed_at = datetime.now(timezone.utc)
    
    def to_json(self) -> str:
        """Convert task to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> 'UnifiedTask':
        """Create task from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    def schedule_next_run(self) -> None:
        """Schedule the next run of the task based on its schedule configuration."""
        if 'interval' in self.schedule:
            self.next_run_at = datetime.now(timezone.utc) + timedelta(seconds=self.schedule['interval'])
        elif 'cron' in self.schedule:
            # For cron-like schedules, just set next run to now + 60 seconds as fallback
            self.next_run_at = datetime.now(timezone.utc) + timedelta(seconds=60)
        else:
            # Default to no specific schedule
            self.next_run_at = None


class TaskAdapter(ABC):
    """
    Abstract adapter for backward compatibility.
    
    Use this adapter to maintain compatibility with existing TaskManager, 
    LoopController, or other systems while migrating to UnifiedTask.
    """
    
    @abstractmethod
    def adapt_to_unified(self) -> UnifiedTask:
        """Convert this task to UnifiedTask."""
        pass
    
    @abstractmethod
    def from_unified(self, unified_task: UnifiedTask) -> None:
        """Update this task from UnifiedTask."""
        pass
class TaskContractValidator:
    """
    Validator for task contracts and unified task integrity.
    
    This validates tasks against the unified contract before they can be
    used in the loop system. It ensures data integrity and prevents
    corrupted or invalid tasks from entering the system.
    """
    
    @staticmethod
    def validate_task_structure(task: UnifiedTask) -> List[str]:
        """Validate task structure and return list of errors."""
        errors = []
        
        if not task.task_id:
            errors.append("Task must have task_id")
        
        if not task.name:
            errors.append("Task must have name")
        
        if not isinstance(task.status, TaskStatus):
            errors.append(f"Invalid task status: {task.status}")
        
        if not isinstance(task.priority, TaskPriority):
            errors.append(f"Invalid task priority: {task.priority}")
        
        # Validate timestamps if present
        if task.started_at and task.completed_at:
            if task.started_at > task.completed_at:
                errors.append("Started time must be before completed time")
        
        if task.timeout and task.started_at:
            expected_timeout = task.started_at + task.timeout
            if task.completed_at and task.completed_at > expected_timeout:
                errors.append("Task completed after timeout")
        
        return errors
    
    @staticmethod
    def is_valid_task(task: UnifiedTask) -> bool:
        """Check if task is valid."""
        return len(TaskContractValidator.validate_task_structure(task)) == 0


# Global task registry for backward compatibility
_task_registry: Dict[str, UnifiedTask] = {}


def register_task(task: UnifiedTask) -> None:
    """Register a task in the global registry."""
    _task_registry[task.task_id] = task


def get_task(task_id: str) -> Optional[UnifiedTask]:
    """Get a task from the registry by ID."""
    return _task_registry.get(task_id)


def list_tasks(status: Optional[TaskStatus] = None) -> List[UnifiedTask]:
    """List all registered tasks, optionally filtered by status."""
    tasks = list(_task_registry.values())
    if status:
        tasks = [t for t in tasks if t.status == status]
    return tasks


def clear_task_registry() -> None:
    """Clear the task registry."""
    _task_registry.clear()

# Convenience functions for common task operations
def create_simple_task(
    name: str,
    handler: Callable,
    priority: TaskPriority = TaskPriority.NORMAL,
    parameters: Optional[Dict[str, Any]] = None,
) -> UnifiedTask:
    """
    Create a simple task with minimal parameters.
    
    This is a convenience function for creating basic tasks quickly
    while ensuring they conform to the UnifiedTask contract.
    """
    return UnifiedTask(
        name=name,
        handler=handler,
        priority=priority,
        parameters=parameters or {},
    )

# Export main exports for external use
__all__ = [
    'UnifiedTask',
    'TaskStatus',
    'TaskPriority',
    'TaskAdapter',
    'TaskContractValidator',
    'register_task',
    'get_task',
    'list_tasks',
    'clear_task_registry',
    'create_simple_task',
]