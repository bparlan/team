#!/usr/bin/env python3
"""
Unit tests for the Phase 2 lightweight DiscussionInterface.

Tests the token-efficient discussion interface for any project, any context
with backward compatibility.
"""

import os
import sys
import tempfile
import unittest
import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add theteam to path for imports
sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "..", "..")))

from theteam.workflow.discussion_interface import DiscussionInterface, create_discussion, add_participant, get_discussion, get_system_status
class TestDiscussionInterface(unittest.TestCase):
    """Tests for the lightweight DiscussionInterface."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.interface = DiscussionInterface(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_discussion(self):
        """Test discussion creation with minimal overhead."""
        discussion = self.interface.create_discussion("Test Topic", ["member1", "member2"])
        
        self.assertIn("discussion_id", discussion)
        self.assertEqual(discussion["topic"], "Test Topic")
        self.assertEqual(discussion["member_ids"], ["member1", "member2"])
        self.assertEqual(discussion["participants"], ["member1", "member2"])
        self.assertEqual(discussion["status"], "active")
        self.assertIsInstance(discussion["analytics"], dict)

    def test_get_discussion_existing(self):
        """Test getting an existing discussion."""
        discussion = self.interface.create_discussion("Test Topic", ["member1"])
        discussion_id = discussion["discussion_id"]
        
        retrieved = self.interface.get_discussion(discussion_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["discussion_id"], discussion_id)
        self.assertEqual(retrieved["topic"], "Test Topic")

    def test_get_discussion_not_found(self):
        """Test getting a non-existent discussion."""
        discussion = self.interface.get_discussion("non_existent")
        self.assertIsNone(discussion)

    def test_add_participant_new(self):
        """Test adding a new participant to discussion."""
        discussion = self.interface.create_discussion("Test Topic", ["member1"])
        discussion_id = discussion["discussion_id"]
        
        result = self.interface.add_participant(discussion_id, "member2")
        self.assertTrue(result)
        
        # Verify participant was added
        updated_discussion = self.interface.get_discussion(discussion_id)
        self.assertIn("member2", updated_discussion["participants"])
        self.assertIn("member2", updated_discussion["member_ids"])

    def test_add_participant_duplicate(self):
        """Test adding duplicate participant - should be idempotent."""
        discussion = self.interface.create_discussion("Test Topic", ["member1", "member2"])
        discussion_id = discussion["discussion_id"]
        
        result = self.interface.add_participant(discussion_id, "member2")
        self.assertTrue(result)  # Should still return True for backward compatibility
        
        # Verify no duplicates were added
        updated_discussion = self.interface.get_discussion(discussion_id)
        self.assertEqual(updated_discussion["participants"].count("member2"), 1)
        self.assertEqual(updated_discussion["member_ids"].count("member2"), 1)

    def test_add_participant_nonexistent_discussion(self):
        """Test adding participant to non-existent discussion."""
        result = self.interface.add_participant("non_existent", "member1")
        self.assertFalse(result)

    def test_add_note(self):
        """Test adding a note to discussion."""
        discussion = self.interface.create_discussion("Test Topic", ["member1"])
        discussion_id = discussion["discussion_id"]
        
        note_data = {"content": "Important point", "tags": ["priority", "urgent"]}
        result = self.interface.add_note(discussion_id, "member1", note_data)
        self.assertTrue(result)
        
        # Verify note was added
        updated_discussion = self.interface.get_discussion(discussion_id)
        self.assertIn("notes", updated_discussion)
        note_ids = list(updated_discussion["notes"].keys())
        self.assertEqual(len(note_ids), 1)
        
        note = updated_discussion["notes"][note_ids[0]]
        self.assertEqual(note["content"], "Important point")
        self.assertEqual(note["tags"], ["priority", "urgent"])
        self.assertEqual(note["member_id"], "member1")
        self.assertIn("note_id", note)
        self.assertIn("created_at", note)

    def test_add_note_nonexistent_discussion(self):
        """Test adding note to non-existent discussion."""
        note_data = {"content": "Test note"}
        result = self.interface.add_note("non_existent", "member1", note_data)
        self.assertFalse(result)

    def test_add_task(self):
        """Test adding a task to discussion."""
        discussion = self.interface.create_discussion("Test Topic", ["member1"])
        discussion_id = discussion["discussion_id"]
        
        task_info = {"title": "Complete review", "description": "Review the documentation"}
        task_id = self.interface.add_task(discussion_id, task_info)
        
        self.assertIsNotNone(task_id)
        self.assertTrue(task_id.startswith("task_"))
        
        # Verify task was added
        updated_discussion = self.interface.get_discussion(discussion_id)
        self.assertIn("tasks", updated_discussion)
        self.assertIn(task_id, updated_discussion["tasks"])
        
        task = updated_discussion["tasks"][task_id]
        self.assertEqual(task["title"], "Complete review")
        self.assertEqual(task["description"], "Review the documentation")
        self.assertEqual(task["status"], "pending")
        self.assertIn("task_id", task)
        self.assertIn("created_at", task)

    def test_add_task_nonexistent_discussion(self):
        """Test adding task to non-existent discussion."""
        task_info = {"title": "Test task"}
        task_id = self.interface.add_task("non_existent", task_info)
        self.assertEqual(task_id, "")  # Should return empty string

    def test_complete_task(self):
        """Test completing a task."""
        discussion = self.interface.create_discussion("Test Topic", ["member1"])
        discussion_id = discussion["discussion_id"]
        
        task_info = {"title": "Complete review"}
        task_id = self.interface.add_task(discussion_id, task_info)
        
        result = self.interface.complete_task(discussion_id, task_id, {"outcome": "completed successfully"})
        self.assertTrue(result)
        
        # Verify task was completed
        updated_discussion = self.interface.get_discussion(discussion_id)
        task = updated_discussion["tasks"][task_id]
        self.assertEqual(task["status"], "completed")
        self.assertIn("completed_at", task)
        self.assertEqual(task["result"], {"outcome": "completed successfully"})

    def test_complete_task_not_found(self):
        """Test completing non-existent task."""
        discussion = self.interface.create_discussion("Test Topic", ["member1"])
        discussion_id = discussion["discussion_id"]
        
        result = self.interface.complete_task(discussion_id, "non_existent_task", {"result": "done"})
        self.assertFalse(result)

    def test_get_system_status(self):
        """Test getting system status."""
        status = self.interface.get_system_status()
        
        self.assertIn("total_active_discussions", status)
        self.assertIn("total_participants", status)
        self.assertIn("total_tasks", status)
        self.assertIn("completed_tasks", status)
        self.assertIn("pending_tasks", status)
        self.assertIn("system_health", status)
        self.assertIn("timestamp", status)
        
        # Initial state should be idle
        self.assertEqual(status["total_active_discussions"], 0)
        self.assertEqual(status["system_health"], "idle")

    def test_system_status_with_data(self):
        """Test system status with discussion data."""
        # Create a discussion with tasks
        discussion = self.interface.create_discussion("Test Topic", ["member1", "member2"])
        discussion_id = discussion["discussion_id"]
        
        # Add some tasks
        task_id1 = self.interface.add_task(discussion_id, {"title": "Task 1"})
        task_id2 = self.interface.add_task(discussion_id, {"title": "Task 2"})
        
        # Complete one task
        self.interface.complete_task(discussion_id, task_id1, {"outcome": "done"})
        
        # Check system status
        status = self.interface.get_system_status()
        
        self.assertEqual(status["total_active_discussions"], 1)
        self.assertEqual(status["total_participants"], 2)
        self.assertEqual(status["total_tasks"], 2)
        self.assertEqual(status["completed_tasks"], 1)
        self.assertEqual(status["pending_tasks"], 1)
        self.assertEqual(status["system_health"], "healthy")

    def test_cleanup_inactive_discussions(self):
        """Test cleanup of inactive discussions."""
        # Create a discussion
        discussion = self.interface.create_discussion("Test Topic", ["member1"])
        discussion_id = discussion["discussion_id"]
        
        # Set its creation time to be old (simulate inactivity)
        discussion["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        self.interface._save_discussion(discussion_id, discussion)
        
        # Load it to update active_discussions
        loaded = self.interface.get_discussion(discussion_id)
        self.assertIsNotNone(loaded)
        
        # Run cleanup (should clean up old discussions)
        cleaned = self.interface.cleanup_inactive_discussions(max_hours_inactive=24)
        self.assertEqual(cleaned, 1)
        
        # Verify discussion is gone
        retrieved = self.interface.get_discussion(discussion_id)
        self.assertIsNone(retrieved)

    def test_get_active_discussions(self):
        """Test getting active discussions."""
        # Initially should be empty
        active = self.interface.get_active_discussions()
        self.assertEqual(len(active), 0)
        
        # Create some discussions
        discussion1 = self.interface.create_discussion("Topic 1", ["member1"])
        discussion2 = self.interface.create_discussion("Topic 2", ["member2"])
        
        # Get active discussions
        active = self.interface.get_active_discussions()
        self.assertEqual(len(active), 2)
        
        discussion_ids = [d["discussion_id"] for d in active]
        self.assertIn(discussion1["discussion_id"], discussion_ids)
        self.assertIn(discussion2["discussion_id"], discussion_ids)

    def test_module_level_functions(self):
        """Test module-level convenience functions."""
        # Test create_discussion function
        discussion = create_discussion(self.temp_dir, "Module Test", ["member1", "member2"])
        self.assertIn("discussion_id", discussion)
        self.assertEqual(discussion["topic"], "Module Test")
        
        # Test get_discussion function
        retrieved = get_discussion(self.temp_dir, discussion["discussion_id"])
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["discussion_id"], discussion["discussion_id"])
        
        # Test add_participant function
        result = add_participant(self.temp_dir, discussion["discussion_id"], "member3")
        self.assertTrue(result)
        
        # Test get_system_status function
        status = get_system_status(self.temp_dir)
        self.assertIn("system_health", status)
        
        # Test add_note with module function
        # Note: module functions don't expose add_note directly
        # But we can test through interface
        interface = DiscussionInterface(self.temp_dir)
        result = interface.add_note(discussion["discussion_id"], "member1", {"content": "Test"})
        self.assertTrue(result)

    def test_token_efficiency(self):
        """Test that implementation is token-efficient (no unnecessary code)."""
        # Count lines in DiscussionInterface class
        interface_lines = len(Path(__file__).resolve().parent.parent.joinpath(
            "workflow", "discussion_interface.py").read_text().splitlines())
        
        # Should be significantly reduced compared to original discussion_manager.py
        self.assertLess(interface_lines, 500, "DiscussionInterface should be token-efficient (< 500 lines)")
        # Check for unnecessary complexity
        content = Path(__file__).resolve().parent.parent.joinpath(
            "workflow", "discussion_interface.py").read_text()
        
        # Should not have overly complex patterns
        self.assertNotIn("class DiscussionManager:", content, "Should not include DiscussionManager")
        self.assertNotIn("import.*threading.*threading", content, "Should not have excessive threading")
        
        # Should focus on core functionality
        core_methods = ["create_discussion", "get_discussion", "add_participant", 
                       "add_note", "add_task", "complete_task", "get_system_status"]
        for method in core_methods:
            self.assertIn(f"def {method}(", content, f"Should include essential method: {method}")

    def test_context_independence(self):
        """Test that interface works with any project context."""
        # Test with different project root paths
        temp_dir1 = tempfile.mkdtemp()
        temp_dir2 = tempfile.mkdtemp()
        
        try:
            interface1 = DiscussionInterface(temp_dir1)
            interface2 = DiscussionInterface(temp_dir2)
            
            # Both should work independently
            discussion1 = interface1.create_discussion("Project 1", ["member1"])
            discussion2 = interface2.create_discussion("Project 2", ["member1"])
            
            self.assertEqual(discussion1["topic"], "Project 1")
            self.assertEqual(discussion2["topic"], "Project 2")
            
            # Each should only see its own discussions
            status1 = interface1.get_system_status()
            status2 = interface2.get_system_status()
            
            self.assertEqual(status1["total_active_discussions"], 1)
            self.assertEqual(status2["total_active_discussions"], 1)
            
        finally:
            import shutil
            shutil.rmtree(temp_dir1, ignore_errors=True)
            shutil.rmtree(temp_dir2, ignore_errors=True)

    def test_backward_compatibility(self):
        """Test backward compatibility with existing DiscussionManager patterns."""
        # Test that interface can be used similarly to old DiscussionManager
        interface = DiscussionInterface(self.temp_dir)
        
        # Should support the same basic operations as old DiscussionManager
        discussion = interface.create_discussion("Test", ["user1", "user2"])
        
        # Member management
        self.assertIn("participants", discussion)
        self.assertIn("member_ids", discussion)
        
        # Task tracking
        task_id = interface.add_task(discussion["discussion_id"], {"title": "Test task"})
        self.assertIsNotNone(task_id)
        
        # Completion workflow
        result = interface.complete_task(discussion["discussion_id"], task_id, {"status": "completed"})
        self.assertTrue(result)
        
        # Notes and analytics
        interface.add_note(discussion["discussion_id"], "user1", {"content": "Test note"})
        
        # System status
        status = interface.get_system_status()
        self.assertIn("total_tasks", status)
        self.assertIn("completed_tasks", status)
        
        # Monitoring (basic start/stop)
        interface.start_monitoring()
        time.sleep(0.1)  # Give thread time to start
        interface.stop_monitoring()

    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        interface = DiscussionInterface(self.temp_dir)
        
        # Operations on non-existent discussions should handle gracefully
        self.assertIsNone(interface.get_discussion("non_existent"))
        self.assertFalse(interface.add_participant("non_existent", "user1"))
        self.assertFalse(interface.add_note("non_existent", "user1", {"content": "test"}))
        self.assertEqual(interface.add_task("non_existent", {"title": "test"}), "")
        self.assertFalse(interface.complete_task("non_existent", "task1", {"result": "done"}))
        
        # Should not crash
        interface.start_monitoring()
        interface.stop_monitoring()

    def test_disk_persistence(self):
        """Test that discussions are properly persisted to disk."""
        interface = DiscussionInterface(self.temp_dir)
        
        # Create a discussion
        discussion = interface.create_discussion("Test Topic", ["member1"])
        discussion_id = discussion["discussion_id"]
        
        # Verify file was created
        discussion_path = os.path.join(self.temp_dir, ".omp", "theteam", "discussions", f"{discussion_id}.json")
        self.assertTrue(os.path.exists(discussion_path))
        
        # Verify file content
        with open(discussion_path, 'r') as f:
            file_content = json.load(f)
        self.assertEqual(file_content["discussion_id"], discussion_id)
        self.assertEqual(file_content["topic"], "Test Topic")
        
        # Create another interface with same project root
        interface2 = DiscussionInterface(self.temp_dir)
        discussion2 = interface2.get_discussion(discussion_id)
        
        # Should load from disk
        self.assertIsNotNone(discussion2)
        self.assertEqual(discussion2["discussion_id"], discussion_id)
if __name__ == "__main__":
    unittest.main()