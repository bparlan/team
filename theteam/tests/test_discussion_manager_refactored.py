#!/usr/bin/env python3
"""
Unit tests for the refactored discussion manager.
"""

import os
import sys
import tempfile
import unittest
import json
import time
from datetime import datetime, timezone

# Project root is provided by the test runner/pytest rootdir; do NOT mutate
# sys.path at module scope — that leaks across test sessions and breaks isolation.

from theteam.workflow.discussion_manager_refactored import (
    create_discussion_manager,
    LightweightDiscussionManager,
    LegacyDiscussionManager
)
class TestLightweightDiscussionManager(unittest.TestCase):
    """Tests for the lightweight discussion manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = self.temp_dir
        self.manager = create_discussion_manager(self.project_root, use_legacy=False)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_discussion(self):
        """Test discussion creation."""
        discussion = self.manager.create_discussion(
            "Test Topic",
            ["member1", "member2"]
        )

        self.assertIsNotNone(discussion)
        self.assertIn("discussion_id", discussion)
        self.assertEqual(discussion["topic"], "Test Topic")

    def test_get_discussion(self):
        """Test getting discussion by ID."""
        discussion = self.manager.create_discussion(
            "Get Topic",
            ["member1"]
        )

        retrieved = self.manager.get_discussion(discussion["discussion_id"])
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["discussion_id"], discussion["discussion_id"])

    def test_get_discussion_not_found(self):
        """Test getting non-existent discussion."""
        discussion = self.manager.get_discussion("non_existent")
        self.assertIsNone(discussion)

    def test_add_participant(self):
        """Test adding participant to discussion."""
        discussion = self.manager.create_discussion(
            "Topic",
            ["member1"]
        )

        result = self.manager.add_participant(discussion["discussion_id"], "member2")
        self.assertTrue(result)

        retrieved = self.manager.get_discussion(discussion["discussion_id"])
        self.assertIn("member2", retrieved["member_ids"])

    def test_add_participant_duplicate(self):
        """Test adding duplicate participant."""
        discussion = self.manager.create_discussion(
            "Topic",
            ["member1"]
        )

        result = self.manager.add_participant(discussion["discussion_id"], "member2")
        self.assertTrue(result)

        result = self.manager.add_participant(discussion["discussion_id"], "member2")
        self.assertFalse(result)

        retrieved = self.manager.get_discussion(discussion["discussion_id"])
        self.assertEqual(retrieved["member_ids"].count("member2"), 1)

    def test_add_note(self):
        """Test adding note to discussion."""
        discussion = self.manager.create_discussion(
            "Topic",
            ["member1"]
        )

        note = self.manager.add_note(
            discussion["discussion_id"],
            "member1",
            {"content": "Test note"}
        )

        self.assertTrue(note)
        self.assertIn("discussion_id", discussion)
        retrieved = self.manager.get_discussion(discussion["discussion_id"])
        self.assertIn("notes", retrieved)
        note_id = f"note_"  # Note IDs are UUID based, we'll find the one we just added
        for note_key in retrieved["notes"]:
            if note_key.startswith("note_"):
                self.assertEqual(retrieved["notes"][note_key]["member_id"], "member1")
                self.assertEqual(retrieved["notes"][note_key]["content"], "Test note")
                break

    def test_add_task(self):
        """Test adding task to discussion."""
        discussion = self.manager.create_discussion(
            "Topic",
            ["member1"]
        )

        task = self.manager.add_task(
            discussion["discussion_id"],
            "member1",
            "Test task",
            """# Test Task

                    Implement test functionality."""
        )

        retrieved = self.manager.get_discussion(discussion["discussion_id"])
        self.assertIn("tasks", retrieved)
        task_id = f"task_"  # Task IDs are UUID based
        for task_key in retrieved["tasks"]:
            if task_key.startswith("task_"):
                self.assertEqual(retrieved["tasks"][task_key]["member_id"], "member1")
                self.assertEqual(retrieved["tasks"][task_key]["task_description"], "Test task")
                self.assertEqual(retrieved["tasks"][task_key]["status"], "pending")
                break

    def test_complete_task(self):
        """Test completing task."""
        discussion = self.manager.create_discussion(
            "Topic",
            ["member1"]
        )

        task = self.manager.add_task(
            discussion["discussion_id"],
            "member1",
            "Test task",
            """# Test Task

                    Implement test functionality."""
        )

        completed_result = self.manager.complete_task(
            discussion["discussion_id"],
            task["task_id"],
            "member1",
            "Task completed successfully"
        )

        self.assertTrue(completed_result)

        retrieved = self.manager.get_discussion(discussion["discussion_id"])
        tasks = retrieved["tasks"]
        completed_task = next(t for t in tasks.values() if t.get("status") == "completed")
        self.assertEqual(completed_task["result"], "Task completed successfully")

    def test_get_system_status(self):
        """Test getting system status."""
        status = self.manager.get_system_status()
        self.assertIsNotNone(status)
        self.assertIn("total_active_discussions", status)
        self.assertIn("pending_tasks", status)
        self.assertIn("last_updated", status)

    def test_system_status_with_data(self):
        """Test system status with data."""
        self.manager.create_discussion(
            "Topic1",
            ["member1"]
        )

        discussion = self.manager.create_discussion(
            "Topic2",
            ["member2"]
        )

        self.manager.add_task(
            discussion["discussion_id"],
            "member2",
            "Another task",
            """# Another Task

                    Another task."""
        )

        status = self.manager.get_system_status()
        self.assertEqual(status["total_active_discussions"], 2)
        self.assertEqual(status["pending_tasks"], 1)

    def test_cleanup_inactive_discussions(self):
        """Test cleanup of inactive discussions."""
        discussion = self.manager.create_discussion(
            "Active Topic",
            ["member1"]
        )

        result = self.manager.complete_discussion(discussion["discussion_id"])
        self.assertTrue(result)

        self.manager.cleanup_inactive_discussions()

        retrieved = self.manager.get_discussion(discussion["discussion_id"])
        self.assertIsNone(retrieved)

    def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring."""
        self.assertFalse(self.manager.monitoring_active)

        self.manager.start_monitoring()
        self.assertTrue(self.manager.monitoring_active)

        self.manager.stop_monitoring()
        self.assertFalse(self.manager.monitoring_active)

    def test_get_active_discussions(self):
        """Test getting active discussions."""
        discussion = self.manager.create_discussion(
            "Active Topic",
            ["member1"]
        )

        active = self.manager.get_active_discussions()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["discussion_id"], discussion["discussion_id"])

    def test_multiple_discussions(self):
        """Test handling multiple discussions."""
        discussions = []
        for i in range(5):
            discussion = self.manager.create_discussion(
                f"Topic {i}",
                [f"member{i}"]
            )
            discussions.append(discussion)

        status = self.manager.get_system_status()
        self.assertEqual(status["total_active_discussions"], 5)

        for i, discussion in enumerate(discussions):
            retrieved = self.manager.get_discussion(discussion["discussion_id"])
            self.assertEqual(retrieved["topic"], f"Topic {i}")
class TestLegacyDiscussionManager(unittest.TestCase):
    """Tests for the legacy discussion manager."""

    def setUp(self):
        """Set up test fixtures."""
        import shutil
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = self.temp_dir
        self.legacy_manager = create_discussion_manager(self.project_root, use_legacy=True)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_create_discussion(self):
        """Test legacy discussion creation."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Topic",
            ["member1"]
        )

        self.assertIsNotNone(discussion)
        self.assertIn("discussion_id", discussion)
        self.assertEqual(discussion["topic"], "Legacy Topic")

    def test_legacy_get_discussion(self):
        """Test legacy getting discussion by ID."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Get Topic",
            ["member1"]
        )

        retrieved = self.legacy_manager.get_discussion(discussion["discussion_id"])
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["discussion_id"], discussion["discussion_id"])

    def test_legacy_get_discussion_not_found(self):
        """Test legacy getting non-existent discussion."""
        discussion = self.legacy_manager.get_discussion("non_existent")
        self.assertIsNone(discussion)

    def test_legacy_add_participant(self):
        """Test legacy adding participant to discussion."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Topic",
            ["member1"]
        )

        result = self.legacy_manager.add_participant(discussion["discussion_id"], "member2")
        self.assertTrue(result)

        retrieved = self.legacy_manager.get_discussion(discussion["discussion_id"])
        self.assertIn("member2", retrieved["member_ids"])

    def test_legacy_add_participant_duplicate(self):
        """Test legacy adding duplicate participant."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Topic",
            ["member1"]
        )

        result = self.legacy_manager.add_participant(discussion["discussion_id"], "member2")
        self.assertTrue(result)

        result = self.legacy_manager.add_participant(discussion["discussion_id"], "member2")
        self.assertFalse(result)

        retrieved = self.legacy_manager.get_discussion(discussion["discussion_id"])
        self.assertEqual(retrieved["member_ids"].count("member2"), 1)

    def test_legacy_add_note(self):
        """Test legacy adding note to discussion."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Topic",
            ["member1"]
        )

        note = self.legacy_manager.add_note(
            discussion["discussion_id"],
            "member1",
            {"content": "Legacy test note"}
        )

        self.assertTrue(note)
        self.assertIn("discussion_id", discussion)
        retrieved = self.legacy_manager.get_discussion(discussion["discussion_id"])
        self.assertIn("notes", retrieved)
        note_id = f"note_"
        for note_key in retrieved["notes"]:
            if note_key.startswith("note_"):
                self.assertEqual(retrieved["notes"][note_key]["member_id"], "member1")
                self.assertEqual(retrieved["notes"][note_key]["content"], "Legacy test note")
                break

    def test_legacy_add_task(self):
        """Test legacy adding task to discussion."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Topic",
            ["member1"]
        )

        task = self.legacy_manager.add_task(
            discussion["discussion_id"],
            "member1",
            "Legacy test task",
            """# Legacy Test Task

                    Legacy test task."""
        )

        retrieved = self.legacy_manager.get_discussion(discussion["discussion_id"])
        self.assertIn("tasks", retrieved)
        task_id = f"task_"
        for task_key in retrieved["tasks"]:
            if task_key.startswith("task_"):
                self.assertEqual(retrieved["tasks"][task_key]["member_id"], "member1")
                self.assertEqual(retrieved["tasks"][task_key]["task_description"], "Legacy test task")
                self.assertEqual(retrieved["tasks"][task_key]["status"], "pending")
                break

    def test_legacy_complete_task(self):
        """Test legacy completing task."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Topic",
            ["member1"]
        )

        task = self.legacy_manager.add_task(
            discussion["discussion_id"],
            "member1",
            "Legacy test task",
            """# Legacy Test Task

                    Legacy test task."""
        )

        completed_result = self.legacy_manager.complete_task(
            discussion["discussion_id"],
            task["task_id"],
            "member1",
            "Legacy task completed"
        )

        self.assertTrue(completed_result)

        retrieved = self.legacy_manager.get_discussion(discussion["discussion_id"])
        tasks = retrieved["tasks"]
        completed_task = next(t for t in tasks.values() if t.get("status") == "completed")
        self.assertEqual(completed_task["result"], "Legacy task completed")

    def test_legacy_get_discussion_analytics(self):
        """Test legacy getting discussion analytics."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Analytics Topic",
            ["member1"]
        )

        analytics = self.legacy_manager.get_discussion_analytics(discussion["discussion_id"])
        self.assertIsNotNone(analytics)
        self.assertIn("discussion_id", analytics)
        self.assertIn("topic", analytics)
        self.assertIn("member_count", analytics)
        self.assertIn("note_count", analytics)
        self.assertIn("task_count", analytics)
        self.assertIn("created_at", analytics)
        self.assertIn("last_updated", analytics)

        self.assertEqual(analytics["discussion_id"], discussion["discussion_id"])
        self.assertEqual(analytics["topic"], "Legacy Analytics Topic")
        self.assertEqual(analytics["member_count"], 1)

    def test_legacy_complete_discussion(self):
        """Test legacy complete discussion."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Complete Topic",
            ["member1"]
        )

        result = self.legacy_manager.complete_discussion(discussion["discussion_id"])
        self.assertTrue(result)

        retrieved = self.legacy_manager.get_discussion(discussion["discussion_id"])
        self.assertEqual(retrieved["status"], "completed")

    def test_legacy_export_import(self):
        """Test legacy export and import."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Export Topic",
            ["member1"]
        )

        self.legacy_manager.add_participant(discussion["discussion_id"], "member2")
        self.legacy_manager.add_note(
            discussion["discussion_id"],
            "member1",
            {"content": "Export note"}
        )

        export_data = self.legacy_manager.export_discussion(discussion["discussion_id"])
        self.assertIsNotNone(export_data)
        self.assertIn("discussion_id", export_data)
        self.assertEqual(export_data["discussion_id"], discussion["discussion_id"])

        imported = self.legacy_manager.import_discussion(export_data, self.temp_dir)
        self.assertIsNotNone(imported)
        self.assertEqual(imported["topic"], "Legacy Export Topic")

    def test_legacy_get_discussions_by_member(self):
        """Test legacy get discussions by member."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Member Topic",
            ["member1"]
        )

        discussions = self.legacy_manager.get_discussions_by_member("member1")
        self.assertEqual(len(discussions), 1)
        self.assertEqual(discussions[0]["discussion_id"], discussion["discussion_id"])

        discussions = self.legacy_manager.get_discussions_by_member("member2")
        self.assertEqual(len(discussions), 0)

    def test_legacy_get_discussions_by_status(self):
        """Test legacy get discussions by status."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy Status Topic",
            ["member1"]
        )

        discussions = self.legacy_manager.get_discussions_by_status("active")
        self.assertEqual(len(discussions), 1)
        self.assertEqual(discussions[0]["discussion_id"], discussion["discussion_id"])

        completed_discussions = self.legacy_manager.get_discussions_by_status("completed")
        self.assertEqual(len(completed_discussions), 0)

    def test_legacy_search_discussions(self):
        """Test legacy search discussions."""
        discussion1 = self.legacy_manager.create_discussion(
            "Legacy Search Topic 1",
            ["member1"]
        )

        discussion2 = self.legacy_manager.create_discussion(
            "Legacy Search Topic 2",
            ["member2"]
        )

        results = self.legacy_manager.search_discussions("Legacy Search Topic")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["topic"], "Legacy Search Topic 2")  # Most recent first

    def test_legacy_generate_topic_suggestions(self):
        """Test legacy topic suggestions."""
        discussion1 = self.legacy_manager.create_discussion(
            "Legacy Architecture Topic",
            ["member1"]
        )

        discussion2 = self.legacy_manager.create_discussion(
            "Legacy Performance Tuning Topic",
            ["member2"]
        )

        suggestions = self.legacy_manager.generate_topic_suggestions("Legacy")
        self.assertIn("System architecture review", suggestions)

    def test_legacy_get_discussion_history(self):
        """Test legacy discussion history."""
        discussion = self.legacy_manager.create_discussion(
            "Legacy History Topic",
            ["member1"]
        )

        history = self.legacy_manager.get_discussion_history(discussion["discussion_id"])
        self.assertIsNotNone(history)
        self.assertIn("discussion_id", history)
        self.assertIn("topic", history)

        self.assertEqual(history["discussion_id"], discussion["discussion_id"])
        self.assertEqual(history["topic"], "Legacy History Topic")
        self.assertEqual(history["activity_count"], 1)
        self.assertEqual(history["participant_count"], 1)
        self.assertEqual(history["note_count"], 0)
        self.assertEqual(history["task_count"], 0)

        # Add some activity
        self.legacy_manager.add_note(
            discussion["discussion_id"],
            "member1",
            {"content": "Note 1"}
        )

        history = self.legacy_manager.get_discussion_history(discussion["discussion_id"])
        self.assertEqual(history["activity_count"], 2)
        self.assertEqual(history["note_count"], 1)

        # Add another discussion
        discussion2 = self.legacy_manager.create_discussion(
            "History Topic 2",
            ["member1"]
        )

        history = self.legacy_manager.get_discussion_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["topic"], "History Topic 2")  # Most recent first

class TestFactoryFunction(unittest.TestCase):
    """Tests for the factory function."""

    def test_factory_creates_lightweight(self):
        """Test factory creates lightweight discussion manager."""
        manager = create_discussion_manager("/tmp", use_legacy=False)
        self.assertIsInstance(manager, LightweightDiscussionManager)

    def test_factory_creates_legacy(self):
        """Test factory creates legacy discussion manager."""
        manager = create_discussion_manager("/tmp", use_legacy=True)
        self.assertIsInstance(manager, LegacyDiscussionManager)

if __name__ == "__main__":
    unittest.main()
