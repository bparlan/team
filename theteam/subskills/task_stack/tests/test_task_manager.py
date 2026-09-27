#!/usr/bin/env python3
"""
test_task_manager.py - Tests for the Task Management System

Validates the Phase 3 Task Management System implementation with comprehensive
test coverage for task lifecycle management, scheduling, and execution.
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import threading
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from theteam.subskills.task_stack.core import (
    TaskManager,
    TaskDefinition,
    TaskType,
    Priority,
    TaskStatus,
    InMemoryTaskStore,
    SimpleTaskExecutor,
    SimpleTaskScheduler
)
class TestTaskDefinition(unittest.TestCase):
    """Test TaskDefinition data structure."""

    def test_task_definition_creation(self):
        """Test creating a TaskDefinition from dictionary."""
        task_def = {
            "task_id": "test_task_1",
            "name": "Test Task",
            "description": "A test task",
            "task_type": TaskType.HEALTH_CHECK.value,
            "priority": Priority.HIGH.value,
            "parameters": {"checks": ["disk"]},
            "tags": ["test", "health"]
        }

        task = TaskDefinition.from_dict(task_def)

        self.assertEqual(task.task_id, "test_task_1")
        self.assertEqual(task.name, "Test Task")
        self.assertEqual(task.task_type, TaskType.HEALTH_CHECK)
        self.assertEqual(task.priority, Priority.HIGH)
        self.assertEqual(task.parameters["checks"], ["disk"])
        self.assertEqual(task.tags, ["test", "health"])

    def test_task_definition_to_dict(self):
        """Test converting TaskDefinition to dictionary."""
        task = TaskDefinition(
            task_id="test_task_1",
            name="Test Task",
            description="A test task",
            task_type=TaskType.ANALYSIS,
            priority=Priority.MEDIUM
        )

        data = task.to_dict()

        self.assertEqual(data["task_id"], "test_task_1")
        self.assertEqual(data["task_type"], TaskType.ANALYSIS.value)
        self.assertEqual(data["priority"], Priority.MEDIUM.value)

    def test_task_definition_post_init(self):
        """Test TaskDefinition __post_init__ methods."""
        task = TaskDefinition(
            task_id="test_task_1",
            name="Test Task",
            description="A test task",
            task_type=TaskType.HEALTH_CHECK,
            priority=Priority.LOW
        )

        # Check default values were set
        self.assertEqual(task.parameters, {})
        self.assertEqual(task.depends_on, [])
        self.assertEqual(task.tags, [])
class TestInMemoryTaskStore(unittest.TestCase):
    """Test InMemoryTaskStore storage implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.store = InMemoryTaskStore()

    def test_save_and_get_task(self):
        """Test saving and retrieving a task."""
        task = TaskDefinition(
            task_id="test_task_1",
            name="Test Task",
            description="A test task",
            task_type=TaskType.HEALTH_CHECK,
            priority=Priority.HIGH
        )

        # Save task
        result = self.store.save_task(task)
        self.assertTrue(result)

        # Get task
        retrieved = self.store.get_task("test_task_1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.task_id, "test_task_1")
        self.assertEqual(retrieved.name, "Test Task")

    def test_get_all_tasks(self):
        """Test retrieving all tasks."""
        # Create multiple tasks
        task1 = TaskDefinition(
            task_id="task_1",
            name="Task 1",
            description="First task",
            task_type=TaskType.HEALTH_CHECK,
            priority=Priority.HIGH
        )

        task2 = TaskDefinition(
            task_id="task_2",
            name="Task 2",
            description="Second task",
            task_type=TaskType.ANALYSIS,
            priority=Priority.MEDIUM
        )

        self.store.save_task(task1)
        self.store.save_task(task2)

        all_tasks = self.store.get_all_tasks()
        self.assertEqual(len(all_tasks), 2)

    def test_update_task(self):
        """Test updating a task."""
        task = TaskDefinition(
            task_id="task_1",
            name="Task 1",
            description="First task",
            task_type=TaskType.HEALTH_CHECK,
            priority=Priority.HIGH
        )

        self.store.save_task(task)

        # Update task
        updated = TaskDefinition(
            task_id="task_1",
            name="Updated Task 1",
            description="Updated first task",
            task_type=TaskType.MAINTENANCE,
            priority=Priority.HIGH
        )

        result = self.store.update_task(updated)
        self.assertTrue(result)

        # Verify update
        retrieved = self.store.get_task("task_1")
        self.assertEqual(retrieved.name, "Updated Task 1")
        self.assertEqual(retrieved.task_type, TaskType.MAINTENANCE)

    def test_delete_task(self):
        """Test deleting a task."""
        task = TaskDefinition(
            task_id="task_1",
            name="Task 1",
            description="First task",
            task_type=TaskType.HEALTH_CHECK,
            priority=Priority.HIGH
        )

        self.store.save_task(task)
        result = self.store.delete_task("task_1")
        self.assertTrue(result)

        retrieved = self.store.get_task("task_1")
        self.assertIsNone(retrieved)

    def test_get_tasks_by_type(self):
        """Test retrieving tasks by type."""
        health_task = TaskDefinition(
            task_id="health_1",
            name="Health Check",
            description="Health check task",
            task_type=TaskType.HEALTH_CHECK,
            priority=Priority.HIGH
        )

        analysis_task = TaskDefinition(
            task_id="analysis_1",
            name="Performance Analysis",
            description="Analysis task",
            task_type=TaskType.ANALYSIS,
            priority=Priority.MEDIUM
        )

        self.store.save_task(health_task)
        self.store.save_task(analysis_task)

        health_tasks = self.store.get_tasks_by_type(TaskType.HEALTH_CHECK)
        analysis_tasks = self.store.get_tasks_by_type(TaskType.ANALYSIS)

        self.assertEqual(len(health_tasks), 1)
        self.assertEqual(len(analysis_tasks), 1)
        self.assertEqual(health_tasks[0].name, "Health Check")

    def test_get_tasks_by_tag(self):
        """Test retrieving tasks by tag."""
        task1 = TaskDefinition(
            task_id="task_1",
            name="Task 1",
            description="First task",
            task_type=TaskType.HEALTH_CHECK,
            priority=Priority.HIGH,
            tags=["test", "health"]
        )

        task2 = TaskDefinition(
            task_id="task_2",
            name="Task 2",
            description="Second task",
            task_type=TaskType.ANALYSIS,
            priority=Priority.MEDIUM,
            tags=["analysis", "performance"]
        )

        self.store.save_task(task1)
        self.store.save_task(task2)

        test_tasks = self.store.get_tasks_by_tag("test")
        health_tasks = self.store.get_tasks_by_tag("health")
        analysis_tasks = self.store.get_tasks_by_tag("analysis")

        self.assertEqual(len(test_tasks), 1)
        self.assertEqual(len(health_tasks), 1)
        self.assertEqual(len(analysis_tasks), 1)

    def test_get_enabled_tasks(self):
        """Test retrieving only enabled tasks."""
        enabled_task = TaskDefinition(
            task_id="enabled_1",
            name="Enabled Task",
            description="Enabled task",
            task_type=TaskType.HEALTH_CHECK,
            priority=Priority.HIGH,
            enabled=True
        )

        disabled_task = TaskDefinition(
            task_id="disabled_1",
            name="Disabled Task",
            description="Disabled task",
            task_type=TaskType.ANALYSIS,
            priority=Priority.MEDIUM,
            enabled=False
        )

        self.store.save_task(enabled_task)
        self.store.save_task(disabled_task)

        enabled_tasks = self.store.get_enabled_tasks()
        self.assertEqual(len(enabled_tasks), 1)
        self.assertEqual(enabled_tasks[0].task_id, "enabled_1")

    def test_load_from_json(self):
        """Test loading tasks from JSON file."""
        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            task_data = [
                {
                    "task_id": "json_task_1",
                    "name": "JSON Task 1",
                    "description": "Task loaded from JSON",
                    "task_type": TaskType.HEALTH_CHECK.value,
                    "priority": Priority.HIGH.value
                }
            ]
            json.dump(task_data, f)
            json_path = f.name

        try:
            loaded_count = self.store.load_from_file(json_path)
            self.assertEqual(loaded_count, 1)

            task = self.store.get_task("json_task_1")
            self.assertIsNotNone(task)
            self.assertEqual(task.name, "JSON Task 1")
        finally:
            os.unlink(json_path)

    def test_save_to_json(self):
        """Test saving tasks to JSON file."""
        task = TaskDefinition(
            task_id="json_save_task",
            name="JSON Save Task",
            description="Task to save",
            task_type=TaskType.MAINTENANCE,
            priority=Priority.MEDIUM
        )

        self.store.save_task(task)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_path = f.name

        try:
            result = self.store.save_to_file(json_path)
            self.assertTrue(result)

            # Load and verify
            with open(json_path, 'r') as f:
                saved_data = json.load(f)

            self.assertEqual(len(saved_data), 1)
            self.assertEqual(saved_data[0]["task_id"], "json_save_task")
        finally:
            os.unlink(json_path)
class TestSimpleTaskExecutor(unittest.TestCase):
    """Test SimpleTaskExecutor implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.executor = SimpleTaskExecutor()

        # Register mock handlers
        self.healthcheck_result = {"status": "healthy", "checks_passed": 3}
        self.maintenance_result = {"action": "maintenance_completed", "tasks": ["cleanup"]}

        def healthcheck_handler(task, context):
            return self.healthcheck_result

        def maintenance_handler(task, context):
            return self.maintenance_result

        self.executor.register_handler(TaskType.HEALTH_CHECK, healthcheck_handler)
        self.executor.register_handler(TaskType.MAINTENANCE, maintenance_handler)

    def test_can_execute(self):
        """Test checking if executor can handle task types."""
        self.assertTrue(self.executor.can_execute(TaskType.HEALTH_CHECK))
        self.assertTrue(self.executor.can_execute(TaskType.MAINTENANCE))
        self.assertFalse(self.executor.can_execute(TaskType.ANALYSIS))

    def test_execute_task_success(self):
        """Test successful task execution."""
        task = TaskDefinition(
            task_id="test_task",
            name="Test Task",
            description="A test task",
            task_type=TaskType.HEALTH_CHECK,
            priority=Priority.HIGH,
            parameters={"checks": ["disk", "memory", "cpu"]}
        )

        context = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": task.task_id
        }

        result = self.executor.execute_task(task, context)

        self.assertTrue(result.success)
        self.assertEqual(result.output, self.healthcheck_result)
        self.assertIsNone(result.error_message)
        self.assertGreater(result.execution_time, 0)

    def test_execute_task_no_handler(self):
        """Test task execution with no registered handler."""
        task = TaskDefinition(
            task_id="test_task",
            name="Test Task",
            description="A test task",
            task_type=TaskType.ANALYSIS,  # No handler registered
            priority=Priority.HIGH
        )

        context = {"timestamp": datetime.now(timezone.utc).isoformat()}
        result = self.executor.execute_task(task, context)

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "No handler registered for task type: analysis")

    def test_execute_task_exception(self):
        """Test task execution that raises exception."""
        def failing_handler(task, context):
            raise ValueError("Handler failed!")

        self.executor.register_handler(TaskType.ANALYSIS, failing_handler)

        task = TaskDefinition(
            task_id="test_task",
            name="Test Task",
            description="A test task",
            task_type=TaskType.ANALYSIS,
            priority=Priority.HIGH
        )

        context = {"timestamp": datetime.now(timezone.utc).isoformat()}
        result = self.executor.execute_task(task, context)

        self.assertFalse(result.success)
        self.assertIn("Handler failed!", result.error_message)
class TestSimpleTaskScheduler(unittest.TestCase):
    """Test SimpleTaskScheduler implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.store = InMemoryTaskStore()
        self.executor = SimpleTaskExecutor()
        self.scheduler = SimpleTaskScheduler(self.store, self.executor)

        # Register a simple handler
        def simple_handler(task, context):
            return {"result": "success", "task_id": task.task_id}

        self.executor.register_handler(TaskType.GENERIC, simple_handler)

    def test_schedule_task(self):
        """Test scheduling a task."""
        task = TaskDefinition(
            task_id="test_task",
            name="Test Task",
            description="A test task",
            task_type=TaskType.GENERIC,
            priority=Priority.HIGH
        )

        self.store.save_task(task)
        task_id = self.scheduler.schedule_task(task)

        self.assertEqual(task_id, "test_task")
        self.assertEqual(len(self.scheduler.get_scheduled_tasks()), 1)

        # Check task status
        status = self.scheduler.get_task_status("test_task")
        self.assertEqual(status["status"], TaskStatus.SCHEDULED.value)

    def test_execute_scheduled_task(self):
        """Test executing a scheduled task."""
        task = TaskDefinition(
            task_id="test_task",
            name="Test Task",
            description="A test task",
            task_type=TaskType.GENERIC,
            priority=Priority.HIGH
        )

        self.store.save_task(task)
        self.scheduler.schedule_task(task)

        # Execute task
        result = self.scheduler.execute_scheduled_task("test_task")
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertEqual(result.output["result"], "success")

        # Check task status is completed
        status = self.scheduler.get_task_status("test_task")
        self.assertEqual(status["status"], TaskStatus.COMPLETED.value)

    def test_cancel_task(self):
        """Test canceling a scheduled task."""
        task = TaskDefinition(
            task_id="test_task",
            name="Test Task",
            description="A test task",
            task_type=TaskType.GENERIC,
            priority=Priority.HIGH
        )

        self.store.save_task(task)
        self.scheduler.schedule_task(task)

        # Cancel task
        result = self.scheduler.cancel_task("test_task")
        self.assertTrue(result)

        # Check task status is cancelled
        status = self.scheduler.get_task_status("test_task")
        self.assertEqual(status["status"], TaskStatus.CANCELLED.value)

    def test_get_task_status(self):
        """Test getting task status at different stages."""
        task = TaskDefinition(
            task_id="test_task",
            name="Test Task",
            description="A test task",
            task_type=TaskType.GENERIC,
            priority=Priority.HIGH
        )

        # Initially no status
        status = self.scheduler.get_task_status("test_task")
        self.assertIsNone(status)

        # Schedule task
        self.store.save_task(task)
        self.scheduler.schedule_task(task)

        # Check scheduled status
        status = self.scheduler.get_task_status("test_task")
        self.assertIsNotNone(status)
        self.assertEqual(status["status"], TaskStatus.SCHEDULED.value)
    def test_build_task_context(self):
        """Test building task execution context."""
        task = TaskDefinition(
            task_id="test_task",
            name="Test Task",
            description="A test task",
            task_type=TaskType.HEALTH_CHECK,
            priority=Priority.HIGH,
            parameters={"checks": ["disk"]},
            tags=["health", "system"]
        )

        context = self.scheduler._build_task_context(task)

        self.assertEqual(context["task_id"], "test_task")
        self.assertEqual(context["name"], "Test Task")
        self.assertEqual(context["description"], "A test task")
        self.assertEqual(context["task_type"], TaskType.HEALTH_CHECK.value)
        self.assertEqual(context["priority"], Priority.HIGH.value)
        self.assertEqual(context["parameters"], {"checks": ["disk"]})
        self.assertEqual(context["tags"], ["health", "system"])
        self.assertIsNotNone(context["timestamp"])
class TestTaskManager(unittest.TestCase):
    """Test TaskManager integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = tempfile.mkdtemp()
        self.task_manager = TaskManager(self.project_root)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.project_root, ignore_errors=True)

    def test_create_task(self):
        """Test creating a task."""
        task_def = {
            "task_id": "create_test_task",
            "name": "Create Test Task",
            "description": "A task to test creation",
            "task_type": TaskType.HEALTH_CHECK.value,
            "priority": Priority.HIGH.value,
            "tags": ["test"]
        }

        task_id = self.task_manager.create_task(task_def)
        self.assertIsNotNone(task_id)
        self.assertEqual(task_id, "create_test_task")

        # Verify task exists
        task = self.task_manager.get_task("create_test_task")
        self.assertIsNotNone(task)
        self.assertEqual(task.name, "Create Test Task")

    def test_schedule_task(self):
        """Test scheduling a task."""
        # Create task
        task_def = {
            "task_id": "schedule_test_task",
            "name": "Schedule Test Task",
            "description": "A task to test scheduling",
            "task_type": TaskType.HEALTH_CHECK.value,
            "priority": Priority.HIGH.value
        }

        task_id = self.task_manager.create_task(task_def)
        self.assertIsNotNone(task_id)

        # Schedule task
        result = self.task_manager.schedule_task(task_id, 30)  # 30 minutes
        self.assertTrue(result)

        # Check scheduled
        scheduled = self.task_manager.get_scheduled_tasks()
        self.assertIn(task_id, scheduled)

    def test_execute_task(self):
        """Test executing a task."""
        # Register handler for our test
        def test_handler(task, context):
            return {"test_result": "passed"}

        self.task_manager.task_executor.register_handler(TaskType.HEALTH_CHECK, test_handler)

        # Create and schedule task
        task_def = {
            "task_id": "execute_test_task",
            "name": "Execute Test Task",
            "description": "A task to test execution",
            "task_type": TaskType.HEALTH_CHECK.value,
            "priority": Priority.HIGH.value
        }

        task_id = self.task_manager.create_task(task_def)
        self.task_manager.schedule_task(task_id)

        # Execute task
        result = self.task_manager.execute_task(task_id)
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertEqual(result.output["test_result"], "passed")

    def test_list_tasks(self):
        """Test listing tasks with filtering."""
        # Create tasks of different types
        health_task_def = {
            "task_id": "health_task",
            "name": "Health Check Task",
            "description": "Health check task",
            "task_type": TaskType.HEALTH_CHECK.value,
            "priority": Priority.HIGH.value,
            "tags": ["system", "health"]
        }

        analysis_task_def = {
            "task_id": "analysis_task",
            "name": "Analysis Task",
            "description": "Analysis task",
            "task_type": TaskType.ANALYSIS.value,
            "priority": Priority.MEDIUM.value,
            "tags": ["performance", "analysis"]
        }

        self.task_manager.create_task(health_task_def)
        self.task_manager.create_task(analysis_task_def)

        # List all tasks
        all_tasks = self.task_manager.list_tasks()
        self.assertEqual(len(all_tasks), 2)

        # List by type
        health_tasks = self.task_manager.list_tasks(TaskType.HEALTH_CHECK)
        analysis_tasks = self.task_manager.list_tasks(TaskType.ANALYSIS)

        self.assertEqual(len(health_tasks), 1)
        self.assertEqual(len(analysis_tasks), 1)
        self.assertEqual(health_tasks[0].task_id, "health_task")

        # List by tag
        system_tasks = self.task_manager.list_tasks(tags=["system"])
        self.assertEqual(len(system_tasks), 1)
        self.assertEqual(system_tasks[0].task_id, "health_task")

    def test_cancel_task(self):
        """Test canceling a task."""
        # Create and schedule task
        task_def = {
            "task_id": "cancel_test_task",
            "name": "Cancel Test Task",
            "description": "A task to test cancellation",
            "task_type": TaskType.GENERIC.value,
            "priority": Priority.HIGH.value
        }

        task_id = self.task_manager.create_task(task_def)
        self.task_manager.schedule_task(task_id)

        # Cancel task
        result = self.task_manager.cancel_task(task_id)
        self.assertTrue(result)

        # Verify cancellation
        status = self.task_manager.get_task_status(task_id)
        self.assertEqual(status["status"], TaskStatus.CANCELLED.value)

    def test_get_system_status(self):
        """Test getting system status."""
        # Create some tasks
        task_def1 = {
            "task_id": "status_task_1",
            "name": "Status Task 1",
            "description": "First status task",
            "task_type": TaskType.HEALTH_CHECK.value,
            "priority": Priority.HIGH.value,
            "enabled": True
        }

        task_def2 = {
            "task_id": "status_task_2",
            "name": "Status Task 2",
            "description": "Second status task",
            "task_type": TaskType.ANALYSIS.value,
            "priority": Priority.MEDIUM.value,
            "enabled": False
        }

        self.task_manager.create_task(task_def1)
        self.task_manager.create_task(task_def2)

        # Schedule one task
        self.task_manager.schedule_task("status_task_1")

        # Get status
        status = self.task_manager.get_system_status()

        self.assertEqual(status["total_tasks"], 2)
        self.assertEqual(status["enabled_tasks"], 1)  # Only one is enabled
        self.assertEqual(status["scheduled_tasks"], 1)
        self.assertEqual(status["health"], "warning")  # Not all enabled
        self.assertEqual(status["scheduler_running"], True)
        self.assertIn("task_types", status)

    def test_export_tasks(self):
        """Test exporting tasks to JSON."""
        # Create task
        task_def = {
            "task_id": "export_test_task",
            "name": "Export Test Task",
            "description": "A task to test export",
            "task_type": TaskType.MAINTENANCE.value,
            "priority": Priority.MEDIUM.value
        }

        self.task_manager.create_task(task_def)

        # Export to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_path = f.name

        try:
            result = self.task_manager.export_tasks(json_path)
            self.assertTrue(result)

            # Load and verify exported data
            with open(json_path, 'r') as f:
                exported_data = json.load(f)

            self.assertEqual(len(exported_data), 1)
            self.assertEqual(exported_data[0]["task_id"], "export_test_task")
        finally:
            os.unlink(json_path)
class TestTaskManagerIntegration(unittest.TestCase):
    """Integration tests for TaskManager with real files."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        # TaskManager auto-loads from <project_root>/tasks/*.json
        self.tasks_dir = os.path.join(self.test_dir, "tasks")
        os.makedirs(self.tasks_dir, exist_ok=True)
        self.task_file = os.path.join(self.tasks_dir, "test_tasks.json")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_integration_with_json_file(self):
        """Test integration with JSON task file."""
        # Create JSON task file
        task_data = [
            {
                "task_id": "integration_task_1",
                "name": "Integration Task 1",
                "description": "First integration task",
                "task_type": TaskType.HEALTH_CHECK.value,
                "priority": Priority.HIGH.value
            },
            {
                "task_id": "integration_task_2",
                "name": "Integration Task 2",
                "description": "Second integration task",
                "task_type": TaskType.ANALYSIS.value,
                "priority": Priority.MEDIUM.value
            }
        ]

        with open(self.task_file, 'w') as f:
            json.dump(task_data, f)

        # Create task manager with JSON file
        task_manager = TaskManager(self.test_dir)

        # Check tasks were loaded
        all_tasks = task_manager.get_all_tasks()
        self.assertEqual(len(all_tasks), 2)

        # Verify tasks
        task_ids = {task.task_id for task in all_tasks}
        self.assertEqual(task_ids, {"integration_task_1", "integration_task_2"})

        # Test scheduling one task
        result = task_manager.schedule_task("integration_task_1")
        self.assertTrue(result)

        scheduled = task_manager.get_scheduled_tasks()
        self.assertIn("integration_task_1", scheduled)

        # Stop scheduler
        task_manager.stop()
if __name__ == '__main__':
    unittest.main()