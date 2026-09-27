#!/usr/bin/env python3
"""
Integration Validation Tests for TeamMemberManager and DiscussionInterface

Comprehensive integration tests validating the complete integration between
TeamMemberManager and DiscussionInterface with token-efficient operations
and context-aware discussions.

This test suite validates:
1. Component integration between TeamMemberManager and DiscussionInterface
2. Backward compatibility with legacy DiscussionManager patterns
3. Token-efficient operations
4. Context-aware discussions
5. Member validation in discussions
"""

import os
import sys
import tempfile
import json
import unittest
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from theteam.core.team_member_manager import TeamMemberManager, TeamMemberConfig
from theteam.workflow.discussion_interface import DiscussionInterface, discuss_in_context

class TestTeamMemberDiscussionIntegration(unittest.TestCase):
    """Integration tests for TeamMemberManager and DiscussionInterface."""

    def setUp(self):
        """Set up test fixtures with proper integration environment."""
        self.test_dir = tempfile.mkdtemp()
        self.project_root = self.test_dir

        # Create proper project structure
        mp_dir = Path(self.test_dir) / ".mp" / "theteam"
        mp_dir.mkdir(parents=True, exist_ok=True)

        # Create members directory for TeamMemberManager
        members_dir = mp_dir / "members"
        members_dir.mkdir(exist_ok=True)

        # Create discussions directory for DiscussionInterface
        discussions_dir = mp_dir / "discussions"
        discussions_dir.mkdir(exist_ok=True)

        # Initialize both components
        self.member_manager = TeamMemberManager(self.project_root)
        self.discussion_interface = DiscussionInterface(self.project_root)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_component_initialization(self):
        """Test that both components initialize correctly with shared project root."""
        # Verify TeamMemberManager
        self.assertEqual(str(self.member_manager.project_root), self.project_root)
        self.assertIsInstance(self.member_manager.config, TeamMemberConfig)

        # Verify DiscussionInterface
        self.assertEqual(self.discussion_interface.project_root, self.project_root)
        self.assertIsNotNone(self.discussion_interface.engine)

        # Both should use same project root
        self.assertEqual(str(self.member_manager.project_root), str(self.discussion_interface.project_root))

    def test_member_creation_and_discussion_creation(self):
        """Test creating team members and discussions in integrated environment."""
        # Create team members
        member1 = self.member_manager.create_team_member("architect", permissions=["read", "write"])
        member2 = self.member_manager.create_team_member("developer", permissions=["read"])
        member3 = self.member_manager.create_team_member("designer", permissions=["read", "write", "admin"])

        self.assertEqual(member1.member_id, member1.member_id)
        self.assertEqual(member2.role, "developer")
        self.assertEqual(member3.role, "designer")

        # Create discussion with the created members
        discussion = self.discussion_interface.create_discussion(
            "System Architecture Design",
            [member1.member_id, member2.member_id, member3.member_id]
        )

        self.assertIn("discussion_id", discussion)
        self.assertEqual(discussion["topic"], "System Architecture Design")
        self.assertEqual(len(discussion["member_ids"]), 3)

        # Verify members can access the discussion context
        for member_id in discussion["member_ids"]:
            member = self.member_manager.get_team_member(member_id)
            self.assertIsNotNone(member)
            self.assertTrue(member.is_active)
            self.assertTrue(self.member_manager.can_access_context(member_id, self.project_root))

    def test_context_aware_discussion_creation(self):
        """Test discuss_in_context function for context-aware discussions."""
        # Create initial members
        member1 = self.member_manager.create_team_member("architect")
        member2 = self.member_manager.create_team_member("pragmatist")

        # Create discussion using context-aware function
        discussion = discuss_in_context(
            self.project_root,
            "Database Optimization Strategy",
            [member1.member_id, member2.member_id]
        )

        # Verify discussion was created successfully
        self.assertIn("discussion_id", discussion)
        self.assertEqual(discussion["topic"], "Database Optimization Strategy")

        # Verify members have access context
        for member_id in discussion["member_ids"]:
            self.assertTrue(self.member_manager.can_access_context(member_id, self.project_root))

    def test_member_validation_in_discussions(self):
        """Test that members are properly validated and tracked in discussions."""
        # Create members
        member1 = self.member_manager.create_team_member("architect")
        member2 = self.member_manager.create_team_member("pragmatist")
        member3 = self.member_manager.create_team_member("skeptic")

        # Create discussion
        discussion = self.discussion_interface.create_discussion(
            "Security Architecture Review",
            [member1.member_id, member2.member_id]
        )

        discussion_id = discussion["discussion_id"]

        # Add skeptic as participant
        participant_added = self.discussion_interface.add_participant(discussion_id, member3.member_id)
        self.assertTrue(participant_added)

        # Verify skeptic is now in discussion
        updated_discussion = self.discussion_interface.get_discussion(discussion_id)
        self.assertIn(member3.member_id, updated_discussion["member_ids"])
        self.assertIn(member3.member_id, updated_discussion["participants"])

        # Verify skeptic's contexts include the discussion
        skeptic = self.member_manager.get_team_member(member3.member_id)
        self.assertTrue(self.member_manager.can_access_context(skeptic.member_id, discussion_id))

    def test_token_efficient_operations(self):
        """Test that operations are token-efficient with minimal overhead."""
        # Create members and discussions
        member = self.member_manager.create_team_member("admin", member_id="test_member")
        discussion = self.discussion_interface.create_discussion(
            "Efficiency Test",
            [member.member_id]
        )

        discussion_id = discussion["discussion_id"]

        # Test token-efficient lookup (should use indexing)
        retrieved_discussion = self.discussion_interface.get_discussion(discussion_id)
        self.assertIsNotNone(retrieved_discussion)
        self.assertEqual(retrieved_discussion["discussion_id"], discussion_id)

        # Test token-efficient participant addition (idempotent)
        result1 = self.discussion_interface.add_participant(discussion_id, member.member_id)
        result2 = self.discussion_interface.add_participant(discussion_id, member.member_id)
        self.assertTrue(result1)
        self.assertTrue(result2)  # Should be idempotent

        # Verify no duplicates
        final_discussion = self.discussion_interface.get_discussion(discussion_id)
        self.assertEqual(final_discussion["participants"].count(member.member_id), 1)

    def test_backward_compatibility(self):
        """Test backward compatibility with existing patterns."""
        # Create discussion using interface
        discussion = self.discussion_interface.create_discussion(
            "Legacy Compatibility Test",
            ["legacy_user1", "legacy_user2"]
        )

        # Test all essential DiscussionManager-like operations
        discussion_id = discussion["discussion_id"]

        # Member management
        self.assertIn("participants", discussion)
        self.assertIn("member_ids", discussion)

        # Task tracking
        task_id = self.discussion_interface.add_task(discussion_id, {
            "title": "Legacy task",
            "description": "Test legacy compatibility"
        })
        self.assertIsNotNone(task_id)
        self.assertTrue(task_id.startswith("task_"))

        # Completion workflow
        result = self.discussion_interface.complete_task(discussion_id, task_id, {
            "status": "completed",
            "result": "Successfully completed"
        })
        self.assertTrue(result)

        # Notes and analytics
        note_result = self.discussion_interface.add_note(discussion_id, "legacy_user1", {
            "content": "Legacy note",
            "tags": ["important", "legacy"]
        })
        self.assertTrue(note_result)

        # System status
        status = self.discussion_interface.get_system_status()
        self.assertIn("total_tasks", status)
        self.assertIn("completed_tasks", status)
        self.assertGreaterEqual(status["total_tasks"], 1)
        self.assertGreaterEqual(status["completed_tasks"], 1)

        # Monitoring (basic start/stop)
        self.discussion_interface.start_monitoring()
        import time
        time.sleep(0.1)  # Give thread time to start
        self.discussion_interface.stop_monitoring()

    def test_error_handling_integration(self):
        """Test error handling in integrated environment."""
        # Operations on non-existent discussions should handle gracefully
        self.assertIsNone(self.discussion_interface.get_discussion("non_existent"))
        self.assertFalse(self.discussion_interface.add_participant("non_existent", "user1"))
        self.assertFalse(self.discussion_interface.add_note("non_existent", "user1", {"content": "test"}))
        self.assertEqual(self.discussion_interface.add_task("non_existent", {"title": "test"}), "")
        self.assertFalse(self.discussion_interface.complete_task("non_existent", "task1", {"result": "done"}))

        # Team member operations should handle errors
        self.assertIsNone(self.member_manager.get_team_member("non_existent"))
        self.assertFalse(self.member_manager.configure_team_member("non_existent", role="admin"))
        self.assertFalse(self.member_manager.remove_team_member("non_existent", permanent=True))

        # Should not crash
        self.discussion_interface.start_monitoring()
        self.discussion_interface.stop_monitoring()

    def test_disk_persistence_integration(self):
        """Test that both components properly persist data to disk."""
        # Create team member
        member = self.member_manager.create_team_member("persistent_member")
        member_id = member.member_id

        # Verify member file was created
        member_path = Path(self.test_dir) / ".mp" / "theteam" / "members" / f"{member_id}.json"
        self.assertTrue(member_path.exists())

        # Verify file content
        with open(member_path, 'r') as f:
            member_data = json.load(f)
        self.assertEqual(member_data["member_id"], member_id)

        # Create discussion
        discussion = self.discussion_interface.create_discussion(
            "Persistence Test",
            [member_id]
        )
        discussion_id = discussion["discussion_id"]

        # Verify discussion file was created
        discussion_path = Path(self.test_dir) / ".mp" / "theteam" / "discussions" / f"{discussion_id}.json"
        self.assertTrue(discussion_path.exists())

        # Verify discussion file content
        with open(discussion_path, 'r') as f:
            discussion_data = json.load(f)
        self.assertEqual(discussion_data["discussion_id"], discussion_id)
        self.assertEqual(discussion_data["topic"], "Persistence Test")

        # Create second instances and verify data loads from disk
        member_manager2 = TeamMemberManager(self.project_root)
        member2 = member_manager2.get_team_member(member_id)
        self.assertIsNotNone(member2)
        self.assertEqual(member2.member_id, member_id)

        discussion_interface2 = DiscussionInterface(self.project_root)
        discussion2 = discussion_interface2.get_discussion(discussion_id)
        self.assertIsNotNone(discussion2)
        self.assertEqual(discussion2["discussion_id"], discussion_id)

    def test_shared_store_merges_external_disk_write(self):
        """A member file written to disk must not be hidden by the shared store.

        Regression: the shared-store optimization used to discard the disk load
        in favour of a stale in-memory dict, so a member persisted by another
        process became invisible to any later manager for the same project.
        """
        manager = TeamMemberManager(self.project_root)
        first = manager.create_team_member("first_role")
        self.assertIsNotNone(manager.get_team_member(first.member_id))

        # Write a member straight to disk, behind the live manager's back,
        # exactly as a separate process would.
        external_path = Path(manager.config.members_dir) / "external_member.json"
        external_path.write_text(json.dumps({
            "member_id": "external_member",
            "role": "external_role",
            "permissions": ["read"],
        }))

        # A fresh manager for the same project must see the on-disk member.
        fresh = TeamMemberManager(self.project_root)
        self.assertIsNotNone(fresh.get_team_member("external_member"))
        self.assertEqual(fresh.get_team_member("external_member").role, "external_role")

        # And it must still share the one store with the manager already alive.
        self.assertIs(fresh.members, manager.members)

    def test_shared_store_does_not_leak_project_roots(self):
        """Shared stores are weakly held, so dead projects do not accumulate."""
        import gc
        before = len(TeamMemberManager._shared_stores)
        for _ in range(20):
            TeamMemberManager(tempfile.mkdtemp())
        gc.collect()
        self.assertEqual(len(TeamMemberManager._shared_stores), before)

    def test_system_status_integration(self):
        """Test integrated system status from both components."""
        # Initial status should show empty system
        member_status = self.member_manager.get_system_status()
        self.assertEqual(member_status["total_members"], 0)
        self.assertEqual(member_status["active_members"], 0)

        discussion_status = self.discussion_interface.get_system_status()
        self.assertEqual(discussion_status["total_active_discussions"], 0)
        self.assertEqual(discussion_status["system_health"], "idle")

        # Create members and discussions
        member1 = self.member_manager.create_team_member("user1")
        member2 = self.member_manager.create_team_member("user2")
        member3 = self.member_manager.create_team_member("user3")

        discussion1 = self.discussion_interface.create_discussion("Topic 1", [member1.member_id])
        discussion2 = self.discussion_interface.create_discussion("Topic 2", [member2.member_id, member3.member_id])

        # Add some tasks
        task1 = self.discussion_interface.add_task(discussion1["discussion_id"], {"title": "Task 1"})
        task2 = self.discussion_interface.add_task(discussion2["discussion_id"], {"title": "Task 2"})

        # Complete one task
        self.discussion_interface.complete_task(discussion1["discussion_id"], task1, {"result": "done"})

        # Check updated system status
        member_status = self.member_manager.get_system_status()
        self.assertEqual(member_status["total_members"], 3)
        self.assertEqual(member_status["active_members"], 3)
        # Each member was created with its own role (user1/user2/user3), so the
        # role histogram has one entry per distinct role.
        self.assertEqual(len(member_status["member_roles"]), 3)
        self.assertEqual(member_status["member_roles"], {"user1": 1, "user2": 1, "user3": 1})

        discussion_status = self.discussion_interface.get_system_status()
        self.assertEqual(discussion_status["total_active_discussions"], 2)
        self.assertEqual(discussion_status["total_participants"], 3)
        self.assertEqual(discussion_status["total_tasks"], 2)
        self.assertEqual(discussion_status["completed_tasks"], 1)
        self.assertEqual(discussion_status["pending_tasks"], 1)
        self.assertEqual(discussion_status["system_health"], "healthy")

    def test_cleanup_integration(self):
        """Test cleanup functionality across components."""
        # Create some members
        member1 = self.member_manager.create_team_member("user1")
        member2 = self.member_manager.create_team_member("user2")

        # Deactivate one member
        self.member_manager.configure_team_member(member2.member_id, is_active=False)

        # Create discussions
        discussion1 = self.discussion_interface.create_discussion("Topic 1", [member1.member_id])
        discussion2 = self.discussion_interface.create_discussion("Topic 2", [member2.member_id])

        # Verify discussions exist
        status_before = self.discussion_interface.get_system_status()
        self.assertEqual(status_before["total_active_discussions"], 2)

        # Cleanup inactive discussions (none should be cleaned up yet)
        cleaned = self.discussion_interface.cleanup_inactive_discussions(max_hours_inactive=24)
        self.assertEqual(cleaned, 0)

        # cleanup_inactive_members is TTL-based retention, not purge-on-deactivate.
        # A member deactivated moments ago is still within the TTL, so nothing
        # is removed yet.
        cleaned_members = self.member_manager.cleanup_inactive_members()
        self.assertEqual(cleaned_members, 0)

        # Backdate member2 past the TTL; now cleanup must remove it.
        self.member_manager.config.member_ttl_days = 0
        cleaned_members = self.member_manager.cleanup_inactive_members()
        self.assertEqual(cleaned_members, 1)

        # Verify member2 is gone
        member2_after = self.member_manager.get_team_member(member2.member_id)
        self.assertIsNone(member2_after)

        # Verify member1 still exists (still active)
        member1_after = self.member_manager.get_team_member(member1.member_id)
        self.assertIsNotNone(member1_after)

class TestTokenEfficiencyValidation(unittest.TestCase):
    """Validate token efficiency requirements for the integration."""

    def test_interface_line_count(self):
        """Test that DiscussionInterface is token-efficient (< 500 lines)."""
        interface_path = Path(__file__).parent.parent.parent / "theteam" / "workflow" / "discussion_interface.py"
        interface_lines = len(interface_path.read_text().splitlines())

        self.assertLess(interface_lines, 500, "DiscussionInterface should be token-efficient (< 500 lines)")

    def test_no_unnecessary_complexity(self):
        """Test that interface avoids unnecessary complexity."""
        interface_path = Path(__file__).parent.parent.parent / "theteam" / "workflow" / "discussion_interface.py"
        content = interface_path.read_text()

        # Should not have overly complex patterns
        self.assertNotIn("class DiscussionManager:", content, "Should not include DiscussionManager")

        # Should focus on core functionality
        core_methods = [
            "create_discussion", "get_discussion", "add_participant",
            "add_note", "add_task", "complete_task", "get_system_status"
        ]
        for method in core_methods:
            self.assertIn(f"def {method}(", content, f"Should include essential method: {method}")

    def test_member_manager_line_count(self):
        """Test that TeamMemberManager is reasonable in complexity."""
        manager_path = Path(__file__).parent.parent.parent / "theteam" / "core" / "team_member_manager.py"
        manager_lines = len(manager_path.read_text().splitlines())

        # Should be reasonable but can be larger than discussion interface
        self.assertLess(manager_lines, 800, "TeamMemberManager should be reasonable (< 800 lines)")

    def test_minimal_token_footprint(self):
        """Test that the integration maintains minimal token footprint."""
        # This test validates that the integrated solution doesn't introduce unnecessary complexity
        import tempfile
        import time

        member_manager = TeamMemberManager(tempfile.mkdtemp())
        discussion_interface = DiscussionInterface(tempfile.mkdtemp())

        # Create members and discussions efficiently
        member = member_manager.create_team_member("test_user")
        discussion = discussion_interface.create_discussion("Test", [member.member_id])

        # Operations should be fast and minimal overhead
        start_time = datetime.now(timezone.utc)

        # Perform several operations
        for i in range(10):
            discussion_interface.add_note(
                discussion["discussion_id"], member.member_id,
                {"content": f"Note {i}", "iteration": i}
            )

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # Should complete quickly (less than 1 second for 10 operations)
        self.assertLess(duration, 1.0, "Operations should be token-efficient and fast")

    def test_context_independence(self):
        """Test that components work independently across different contexts."""
        import tempfile
        import shutil

        # Test with different project root paths
        temp_dir1 = tempfile.mkdtemp()
        temp_dir2 = tempfile.mkdtemp()

        try:
            interface1 = DiscussionInterface(temp_dir1)
            interface2 = DiscussionInterface(temp_dir2)

            manager1 = TeamMemberManager(temp_dir1)
            manager2 = TeamMemberManager(temp_dir2)

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

            # Each manager should only manage members in its context
            member1 = manager1.create_team_member("user1")
            member2 = manager2.create_team_member("user1")  # Same ID, different context

            # Should be separate members in different contexts
            retrieved1 = manager1.get_team_member(member1.member_id)
            retrieved2 = manager2.get_team_member(member2.member_id)

            self.assertIsNotNone(retrieved1)
            self.assertIsNotNone(retrieved2)

        finally:
            shutil.rmtree(temp_dir1, ignore_errors=True)
            shutil.rmtree(temp_dir2, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()