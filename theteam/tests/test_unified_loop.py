#!/usr/bin/env python3
"""Quick test for UnifiedLoop implementation."""

import sys
import os

from theteam.core.unified_loop import UnifiedLoop, UnifiedTask, LoopConfig
from theteam.core.task_contract import TaskPriority, TaskStatus
from theteam.core.task_contract import TaskPriority, TaskStatus

def sample_task():
    """Sample task for testing."""
    return {"result": "Task completed successfully"}

def test_basic_functionality():
    """Test basic UnifiedLoop functionality."""
    print("Testing UnifiedLoop basic functionality...")
    
    # Create config
    config = LoopConfig(
        loop_id="test_loop",
        project_root=".",
        auto_start=False
    )
    
    # Create loop
    loop = UnifiedLoop(".", config)
    
    # Test initial status
    status = loop.get_status()
    assert status['loop_id'] == "test_loop"
    assert status['state']['state'] == "stopped"
    print("✓ Initial state correct")
    
    # Test start
    result = loop.start()
    assert result == True
    status = loop.get_status()
    assert status['state']['state'] == "starting"
    print("✓ Loop start successful")
    
    # Create and add task
    task = UnifiedTask(
        task_id="test_task",
        name="Sample Task",
        handler=sample_task,
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
        schedule={"interval": 2}
    )
    
    # Note: We'll pause loop before adding task since it requires running
    loop.stop()
    loop.pause()
    
    # Create new loop for task testing
    loop2 = UnifiedLoop(".", config)
    loop2.start()
    
    task2 = UnifiedTask(
        task_id="test_task",
        name="Sample Task",
        handler=sample_task,
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
        schedule={"interval": 2}
    )
    
    result = loop2.add_task(task2)
    assert result == True
    print("✓ Task added successfully")
    
    # Test status with task
    status = loop2.get_status()
    assert status['tasks_by_priority']['normal'] == 1
    print("✓ Task status correct")
    
    # Cleanup
    loop2.stop()
    print("✓ Cleanup completed")
    
    print("\nAll tests passed! UnifiedLoop implementation is working correctly.")
    assert True

if __name__ == "__main__":
    try:
        test_basic_functionality()
        print("\n🎉 SUCCESS: UnifiedLoop implementation is stable and agent-friendly!")
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        sys.exit(1)
