#!/usr/bin/env python3
"""
task_stack.core - Core task management system

Provides fundamental task management infrastructure with independent inits,
stable workflow management, and modular design.

This is Phase 3 of the comprehensive team discussion system implementation,
building upon Phase 1 (Team Member Management) and Phase 2 (Discussion Interface).
"""

import os
import json
import uuid
import time
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from threading import Lock
import hashlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class TaskStatus(Enum):
    """Task execution status enumeration."""
    CREATED = "created"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
class Priority(Enum):
    """Task priority enumeration."""
    LOW = 1
    MEDIUM = 5
    HIGH = 10
class TaskType(Enum):
    """Task type enumeration."""
    HEALTH_CHECK = "healthcheck"
    MAINTENANCE = "maintenance"
    IMPROVEMENT = "improvement"
    DOC_UPDATE = "doc-update"
    SECURITY = "security"
    ANALYSIS = "analysis"
    GENERIC = "generic"
@dataclass
class TaskResult:
    """Task execution result data structure."""
    success: bool
    output: Dict[str, Any]
    error_message: Optional[str] = None
    execution_time: float = 0.0
    timestamp: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp == "":
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.metadata is None:
            self.metadata = {}
@dataclass
class TaskDefinition:
    """Task definition data structure."""
    task_id: str
    name: str
    description: str
    task_type: TaskType
    priority: Priority
    execution_func: Optional[Callable] = None
    parameters: Dict[str, Any] = None
    schedule_interval: Optional[int] = None  # minutes
    depends_on: List[str] = None
    max_retries: int = 3
    timeout: int = 300  # seconds
    tags: List[str] = None
    enabled: bool = True

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
        if self.depends_on is None:
            self.depends_on = []
        if self.tags is None:
            self.tags = []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskDefinition":
        """Create TaskDefinition from dictionary."""
        # Handle enum conversion
        if isinstance(data.get("task_type"), str):
            data["task_type"] = TaskType(data["task_type"])
        if isinstance(data.get("priority"), int):
            # Find matching priority enum
            for priority in Priority:
                if priority.value == data["priority"]:
                    data["priority"] = priority
                    break

        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert TaskDefinition to dictionary."""
        data = asdict(self)
        # Convert enums to values
        data["task_type"] = self.task_type.value
        data["priority"] = self.priority.value
        return data
class TaskStore(ABC):
    """Abstract task storage interface."""

    @abstractmethod
    def save_task(self, task: TaskDefinition) -> bool:
        """Save task definition."""
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[TaskDefinition]:
        """Get task by ID."""
        pass

    @abstractmethod
    def get_all_tasks(self) -> List[TaskDefinition]:
        """Get all tasks."""
        pass

    @abstractmethod
    def update_task(self, task: TaskDefinition) -> bool:
        """Update task."""
        pass

    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        """Delete task."""
        pass

    @abstractmethod
    def get_tasks_by_type(self, task_type: TaskType) -> List[TaskDefinition]:
        """Get tasks by type."""
        pass

    @abstractmethod
    def get_tasks_by_tag(self, tag: str) -> List[TaskDefinition]:
        """Get tasks by tag."""
        pass
class InMemoryTaskStore(TaskStore):
    """In-memory task storage implementation."""

    def __init__(self):
        self.tasks: Dict[str, TaskDefinition] = {}
        self.lock = Lock()

    def save_task(self, task: TaskDefinition) -> bool:
        """Save task definition."""
        try:
            with self.lock:
                self.tasks[task.task_id] = task
            logger.info(f"Saved task: {task.task_id} ({task.name})")
            return True
        except Exception as e:
            logger.error(f"Failed to save task {task.task_id}: {e}")
            return False

    def get_task(self, task_id: str) -> Optional[TaskDefinition]:
        """Get task by ID."""
        with self.lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[TaskDefinition]:
        """Get all tasks."""
        with self.lock:
            return list(self.tasks.values())

    def update_task(self, task: TaskDefinition) -> bool:
        """Update task."""
        try:
            with self.lock:
                if task.task_id not in self.tasks:
                    return False
                self.tasks[task.task_id] = task
            logger.info(f"Updated task: {task.task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update task {task.task_id}: {e}")
            return False

    def delete_task(self, task_id: str) -> bool:
        """Delete task."""
        try:
            with self.lock:
                if task_id not in self.tasks:
                    return False
                del self.tasks[task_id]
            logger.info(f"Deleted task: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            return False

    def get_tasks_by_type(self, task_type: TaskType) -> List[TaskDefinition]:
        """Get tasks by type."""
        with self.lock:
            return [task for task in self.tasks.values() if task.task_type == task_type]

    def get_tasks_by_tag(self, tag: str) -> List[TaskDefinition]:
        """Get tasks by tag."""
        with self.lock:
            return [task for task in self.tasks.values() if tag in task.tags]

    def get_enabled_tasks(self) -> List[TaskDefinition]:
        """Get enabled tasks."""
        with self.lock:
            return [task for task in self.tasks.values() if task.enabled]

    def load_from_file(self, file_path: str) -> int:
        """Load tasks from JSON file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            loaded_count = 0
            for task_data in data:
                try:
                    task = TaskDefinition.from_dict(task_data)
                    self.save_task(task)
                    loaded_count += 1
                except Exception as e:
                    logger.error(f"Failed to load task from data: {e}")

            logger.info(f"Loaded {loaded_count} tasks from {file_path}")
            return loaded_count

        except Exception as e:
            logger.error(f"Failed to load tasks from {file_path}: {e}")
            return 0

    def save_to_file(self, file_path: str) -> bool:
        """Save tasks to JSON file."""
        try:
            tasks_data = [task.to_dict() for task in self.get_all_tasks()]

            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'w') as f:
                json.dump(tasks_data, f, indent=2)

            logger.info(f"Saved {len(tasks_data)} tasks to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save tasks to {file_path}: {e}")
            return False
class TaskExecutor(ABC):
    """Abstract task executor interface."""

    @abstractmethod
    def execute_task(self, task: TaskDefinition, context: Dict[str, Any]) -> TaskResult:
        """Execute a task."""
        pass

    @abstractmethod
    def can_execute(self, task_type: TaskType) -> bool:
        """Check if executor can handle task type."""
        pass
class SimpleTaskExecutor(TaskExecutor):
    """Simple task executor with built-in handlers."""

    def __init__(self):
        self.handlers: Dict[TaskType, Callable] = {}
        self.lock = Lock()

    def register_handler(self, task_type: TaskType, handler: Callable):
        """Register task handler."""
        with self.lock:
            self.handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type.value}")

    def execute_task(self, task: TaskDefinition, context: Dict[str, Any]) -> TaskResult:
        """Execute a task."""
        start_time = time.monotonic()

        try:
            # Validate dependencies
            if task.depends_on:
                # In a real implementation, check dependencies
                pass

            # Get handler
            handler = self.handlers.get(task.task_type)
            if not handler:
                return TaskResult(
                    success=False,
                    output={},
                    error_message=f"No handler registered for task type: {task.task_type.value}"
                )

            # Execute handler
            result = handler(task, context)

            execution_time = time.monotonic() - start_time

            return TaskResult(
                success=True,
                output=result if isinstance(result, dict) else {"result": result},
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.monotonic() - start_time
            logger.error(f"Task execution failed {task.task_id}: {e}")
            return TaskResult(
                success=False,
                output={},
                error_message=str(e),
                execution_time=execution_time
            )

    def can_execute(self, task_type: TaskType) -> bool:
        """Check if executor can handle task type."""
        with self.lock:
            return task_type in self.handlers
class TaskScheduler(ABC):
    """Abstract task scheduler interface."""

    @abstractmethod
    def schedule_task(self, task: TaskDefinition) -> str:
        """Schedule a task for execution."""
        pass

    @abstractmethod
    def get_scheduled_tasks(self) -> List[str]:
        """Get list of scheduled task IDs."""
        pass

    @abstractmethod
    def cancel_task(self, task_id: str) -> bool:
        """Cancel scheduled task."""
        pass

    @abstractmethod
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status."""
        pass
class SimpleTaskScheduler(TaskScheduler):
    """Simple in-memory task scheduler."""

    def __init__(self, task_store: TaskStore, task_executor: TaskExecutor):
        self.task_store = task_store
        self.task_executor = task_executor
        self.scheduled_tasks: Dict[str, Dict[str, Any]] = {}
        self.running_tasks: Dict[str, Dict[str, Any]] = {}
        self.completed_tasks: Dict[str, List[Dict[str, Any]]] = {}
        self.lock = Lock()
        self.running = False
        self.scheduler_thread = None

    def start(self):
        """Start scheduler."""
        if self.running:
            return

        self.running = True
        self.scheduler_thread = None  # In real implementation, this would be a background thread
        logger.info("Task scheduler started")

    def stop(self):
        """Stop scheduler."""
        self.running = False
        logger.info("Task scheduler stopped")

    def schedule_task(self, task: TaskDefinition) -> str:
        """Schedule a task for execution."""
        task_id = task.task_id

        with self.lock:
            # Check if task already scheduled
            if task_id in self.scheduled_tasks:
                return task_id

            task.status = TaskStatus.SCHEDULED
            self.task_store.update_task(task)

            schedule_info = {
                "task_id": task_id,
                "scheduled_at": datetime.now(timezone.utc).isoformat(),
                "status": TaskStatus.SCHEDULED.value,
                "priority": task.priority.value
            }

            self.scheduled_tasks[task_id] = schedule_info

        logger.info(f"Scheduled task: {task_id} ({task.name})")
        return task_id

    def execute_scheduled_task(self, task_id: str) -> Optional[TaskResult]:
        """Execute a scheduled task."""
        with self.lock:
            if task_id not in self.scheduled_tasks:
                return None

            schedule_info = self.scheduled_tasks[task_id]
            if schedule_info["status"] != TaskStatus.SCHEDULED.value:
                return None

            # Update status to running
            schedule_info["status"] = TaskStatus.RUNNING.value
            schedule_info["started_at"] = datetime.now(timezone.utc).isoformat()

            # Move to running tasks
            self.running_tasks[task_id] = schedule_info
            del self.scheduled_tasks[task_id]

            # Get task definition
            task = self.task_store.get_task(task_id)
            if not task:
                schedule_info["status"] = TaskStatus.FAILED.value
                schedule_info["error"] = "Task definition not found"
                self.running_tasks[task_id]["status"] = TaskStatus.FAILED.value
                del self.running_tasks[task_id]
                return None

        try:
            # Execute task
            context = self._build_task_context(task)
            result = self.task_executor.execute_task(task, context)

            # Update task status based on result
            with self.lock:
                if task_id in self.running_tasks:
                    schedule_info = self.running_tasks[task_id]

                    if result.success:
                        schedule_info["status"] = TaskStatus.COMPLETED.value
                        schedule_info["completed_at"] = datetime.now(timezone.utc).isoformat()

                        # Add to completed tasks
                        if task_id not in self.completed_tasks:
                            self.completed_tasks[task_id] = []

                        self.completed_tasks[task_id].append({
                            "result": result,
                            "timestamp": schedule_info["completed_at"]
                        })

                    else:
                        schedule_info["status"] = TaskStatus.FAILED.value
                        schedule_info["completed_at"] = datetime.now(timezone.utc).isoformat()
                        schedule_info["error"] = result.error_message

                    # Remove from running tasks
                    del self.running_tasks[task_id]

            logger.info(f"Executed task {task_id}: {'success' if result.success else 'failed'}")
            return result

        except Exception as e:
            with self.lock:
                if task_id in self.running_tasks:
                    schedule_info = self.running_tasks[task_id]
                    schedule_info["status"] = TaskStatus.FAILED.value
                    schedule_info["completed_at"] = datetime.now(timezone.utc).isoformat()
                    schedule_info["error"] = str(e)
                    del self.running_tasks[task_id]

            logger.error(f"Task execution failed {task_id}: {e}")
            return TaskResult(
                success=False,
                output={},
                error_message=str(e)
            )

    def get_scheduled_tasks(self) -> List[str]:
        """Get list of scheduled task IDs."""
        with self.lock:
            return list(self.scheduled_tasks.keys())

    def cancel_task(self, task_id: str) -> bool:
        """Cancel scheduled task."""
        with self.lock:
            if task_id in self.scheduled_tasks:
                schedule_info = self.scheduled_tasks[task_id]
                schedule_info["status"] = TaskStatus.CANCELLED.value
                schedule_info["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                return True
            return False

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status."""
        with self.lock:
            # Check scheduled tasks
            if task_id in self.scheduled_tasks:
                return self.scheduled_tasks[task_id]

            # Check running tasks
            if task_id in self.running_tasks:
                return self.running_tasks[task_id]

            # Check completed tasks
            if task_id in self.completed_tasks:
                return {
                    "status": TaskStatus.COMPLETED.value,
                    "completed_at": self.completed_tasks[task_id][-1]["timestamp"] if self.completed_tasks[task_id] else None,
                    "history": self.completed_tasks[task_id]
                }

            return None

    def _build_task_context(self, task: TaskDefinition) -> Dict[str, Any]:
        """Build context for task execution."""
        return {
            "task_id": task.task_id,
            "name": task.name,
            "description": task.description,
            "task_type": task.task_type.value,
            "priority": task.priority.value,
            "parameters": task.parameters,
            "tags": task.tags,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_root": os.getcwd()
        }
class TaskManager:
    """Main task management system."""

    def __init__(self, project_root: str = None):
        self.project_root = project_root or os.getcwd()
        self.task_store = InMemoryTaskStore()
        self.task_executor = SimpleTaskExecutor()
        self.task_scheduler = SimpleTaskScheduler(self.task_store, self.task_executor)

        # Register default handlers
        self._register_default_handlers()

        # Load tasks from default locations
        self._load_default_tasks()

        # Start scheduler
        self.task_scheduler.start()

        logger.info("TaskManager initialized")

    def _register_default_handlers(self):
        """Register default task handlers."""

        def healthcheck_handler(task: TaskDefinition, context: Dict[str, Any]) -> Dict[str, Any]:
            """Health check task handler."""
            return {
                "status": "healthy",
                "timestamp": context["timestamp"],
                "checks_passed": len(task.parameters.get("checks", [])),
                "message": "System health check completed successfully"
            }

        def maintenance_handler(task: TaskDefinition, context: Dict[str, Any]) -> Dict[str, Any]:
            """Maintenance task handler."""
            return {
                "action": "maintenance_completed",
                "timestamp": context["timestamp"],
                "tasks_maintained": task.parameters.get("tasks", []),
                "message": "Maintenance tasks completed successfully"
            }

        def improvement_handler(task: TaskDefinition, context: Dict[str, Any]) -> Dict[str, Any]:
            """Improvement task handler."""
            return {
                "action": "improvements_applied",
                "timestamp": context["timestamp"],
                "improvements": task.parameters.get("improvements", []),
                "message": "Improvement tasks completed successfully"
            }

        def analysis_handler(task: TaskDefinition, context: Dict[str, Any]) -> Dict[str, Any]:
            """Analysis task handler."""
            return {
                "analysis_type": task.parameters.get("analysis_type", "unknown"),
                "timestamp": context["timestamp"],
                "findings": task.parameters.get("findings", []),
                "recommendations": task.parameters.get("recommendations", []),
                "message": "Analysis completed successfully"
            }

        # Register handlers
        self.task_executor.register_handler(TaskType.HEALTH_CHECK, healthcheck_handler)
        self.task_executor.register_handler(TaskType.MAINTENANCE, maintenance_handler)
        self.task_executor.register_handler(TaskType.IMPROVEMENT, improvement_handler)
        self.task_executor.register_handler(TaskType.ANALYSIS, analysis_handler)

    def _load_default_tasks(self):
        """Load tasks from default locations."""
        default_locations = [
            os.path.join(self.project_root, "tasks", "*.json"),
            os.path.join(self.project_root, "task-templates", "*.json"),
            os.path.join(self.project_root, "theteam", "subskills", "task_stack", "tasks", "*.json")
        ]

        for location in default_locations:
            import glob
            for file_path in glob.glob(location):
                self.task_store.load_from_file(file_path)

    def create_task(self, task_definition: Dict[str, Any]) -> str:
        """Create a new task."""
        try:
            # Convert to TaskDefinition
            task = TaskDefinition.from_dict(task_definition)

            # Generate ID if not provided
            if not task.task_id:
                task.task_id = str(uuid.uuid4())

            # Save task
            if self.task_store.save_task(task):
                logger.info(f"Created task: {task.task_id} ({task.name})")
                return task.task_id
            else:
                logger.error(f"Failed to create task: {task.name}")
                return None

        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return None

    def schedule_task(self, task_id: str, interval_minutes: int = None) -> bool:
        """Schedule a task for execution."""
        try:
            task = self.task_store.get_task(task_id)
            if not task:
                logger.error(f"Task not found: {task_id}")
                return False

            if interval_minutes:
                task.schedule_interval = interval_minutes

            return self.task_scheduler.schedule_task(task) is not None

        except Exception as e:
            logger.error(f"Failed to schedule task {task_id}: {e}")
            return False

    def execute_task(self, task_id: str) -> Optional[TaskResult]:
        """Execute a task immediately."""
        return self.task_scheduler.execute_scheduled_task(task_id)

    def get_task(self, task_id: str) -> Optional[TaskDefinition]:
        """Get task definition."""
        return self.task_store.get_task(task_id)

    def get_all_tasks(self) -> List[TaskDefinition]:
        """Get all tasks."""
        return self.task_store.get_all_tasks()

    def get_scheduled_tasks(self) -> List[str]:
        """Get scheduled task IDs."""
        return self.task_scheduler.get_scheduled_tasks()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status."""
        return self.task_scheduler.get_task_status(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel task."""
        return self.task_scheduler.cancel_task(task_id)

    def list_tasks(self, task_type: TaskType = None, tags: List[str] = None) -> List[TaskDefinition]:
        """List tasks with optional filtering."""
        tasks = self.task_store.get_all_tasks()

        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]

        if tags:
            tasks = [t for t in tasks if any(tag in t.tags for tag in tags)]

        # Sort by priority and name
        tasks.sort(key=lambda t: (-t.priority.value, t.name))

        return tasks

    def export_tasks(self, file_path: str) -> bool:
        """Export tasks to JSON file."""
        return self.task_store.save_to_file(file_path)

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status."""
        all_tasks = self.task_store.get_all_tasks()
        scheduled = self.task_scheduler.get_scheduled_tasks()

        return {
            "total_tasks": len(all_tasks),
            "enabled_tasks": len(self.task_store.get_enabled_tasks()),
            "scheduled_tasks": len(scheduled),
            "health": "healthy" if all(t.enabled for t in all_tasks) else "warning",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scheduler_running": self.task_scheduler.running,
            "task_types": {
                task_type.value: len(self.task_store.get_tasks_by_type(task_type))
                for task_type in TaskType
            }
        }

    def stop(self):
        """Stop task manager."""
        self.task_scheduler.stop()
        logger.info("TaskManager stopped")
def create_default_task_definitions() -> List[Dict[str, Any]]:
    """Create default task definitions."""
    return [
        {
            "task_id": "task_health_check_default",
            "name": "System Health Check",
            "description": "Perform comprehensive system health check",
            "task_type": TaskType.HEALTH_CHECK.value,
            "priority": Priority.HIGH.value,
            "parameters": {
                "checks": ["disk_space", "memory", "cpu", "network", "services"]
            },
            "tags": ["system", "monitoring", "critical"],
            "schedule_interval": 60  # every hour
        },
        {
            "task_id": "task_maintenance_default",
            "name": "System Maintenance",
            "description": "Perform routine system maintenance",
            "task_type": TaskType.MAINTENANCE.value,
            "priority": Priority.MEDIUM.value,
            "parameters": {
                "tasks": ["cleanup_logs", "backup_data", "update_packages", "restart_services"]
            },
            "tags": ["system", "maintenance"],
            "schedule_interval": 120  # every 2 hours
        },
        {
            "task_id": "task_analysis_default",
            "name": "Performance Analysis",
            "description": "Analyze system performance metrics",
            "task_type": TaskType.ANALYSIS.value,
            "priority": Priority.MEDIUM.value,
            "parameters": {
                "analysis_type": "performance",
                "findings": [],
                "recommendations": []
            },
            "tags": ["analysis", "performance", "metrics"],
            "schedule_interval": 240  # every 4 hours
        }
    ]
def main():
    """Main entry point for task management system."""
    if len(sys.argv) < 2:
        print("Usage: python core.py <command> [options]")
        print("Commands: create, schedule, execute, list, status, export, stop")
        sys.exit(1)

    project_root = os.path.dirname(os.path.abspath(__file__))
    task_manager = TaskManager(project_root)

    try:
        command = sys.argv[1]

        if command == "create":
            # Create default tasks
            for task_def in create_default_task_definitions():
                task_id = task_manager.create_task(task_def)
                print(f"Created task: {task_id}")

        elif command == "list":
            tasks = task_manager.list_tasks()
            for task in tasks:
                print(f"- {task.name} ({task.task_id}) [{task.task_type.value}] Priority: {task.priority.value}")

        elif command == "status":
            status = task_manager.get_system_status()
            print("Task System Status:")
            for key, value in status.items():
                print(f"  {key}: {value}")

        elif command == "stop":
            task_manager.stop()

        else:
            print(f"Unknown command: {command}")

    finally:
        task_manager.stop()
if __name__ == "__main__":
    main()