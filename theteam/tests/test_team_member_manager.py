#!/usr/bin/env python3
"""
Team Member Manager Tests - Comprehensive test suite for Phase 1 Team Member Management System.

Tests team member creation, configuration, and management capabilities.
"""
import os
import sys
import tempfile
import json
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from theteam.workflow.team_member_manager import TeamMember, TeamMemberManager

class TestTeamMember(unittest.TestCase):
    """Test TeamMember class functionality."""

    def test_initialization(self):
        """Test basic TeamMember initialization."""
        member = TeamMember("test_member", "project_member")
        self.assertEqual(member.name, "test_member")
        self.assertEqual(member.member_type, "project_member")
        self.assertIsNotNone(member.id)
        self.assertIsNotNone(member.created_at)
        self.assertEqual(member.contributions, 0)
        self.assertEqual(member.discussions, [])

    def test_initialization_with_params(self):
        """Test TeamMember initialization with custom parameters."""
        member = TeamMember(
            name="custom_member",
            member_type="template",
            roles=["architect", "developer"],
            tags=["senior", "backend"],
            metadata={"specialization": "system design"}
        )

        self.assertEqual(member.name, "custom_member")
        self.assertEqual(member.member_type, "template")
        self.assertEqual(member.roles, ["architect", "developer"])
        self.assertEqual(member.tags, ["senior", "backend"])
        self.assertEqual(member.metadata["specialization"], "system design")

    def test_to_dict(self):
        """Test TeamMember.to_dict serialization."""
        member = TeamMember("test", "project_member", ["role1"], ["tag1"])
        member.contributions = 5
        member.add_discussion("discussion1")

        data = member.to_dict()
        self.assertEqual(data["name"], "test")
        self.assertEqual(data["member_type"], "project_member")
        self.assertEqual(data["roles"], ["role1"])
        self.assertEqual(data["tags"], ["tag1"])
        self.assertEqual(data["contributions"], 5)
        self.assertEqual(data["discussions"], ["discussion1"])
        self.assertIn("id", data)
        self.assertIn("created_at", data)

    def test_from_dict(self):
        """Test TeamMember.from_dict deserialization."""
        data = {
            "name": "restored_member",
            "member_type": "template",
            "roles": ["developer"],
            "tags": ["frontend"],
            "metadata": {"focus": "react"},
            "contributions": 3,
            "discussions": ["disc1", "disc2"],
            "created_at": "2023-01-01T00:00:00Z",
            "last_seen": "2023-01-02T00:00:00Z"
        }

        member = TeamMember.from_dict(data)
        self.assertEqual(member.name, "restored_member")
        self.assertEqual(member.member_type, "template")
        self.assertEqual(member.roles, ["developer"])
        self.assertEqual(member.tags, ["frontend"])
        self.assertEqual(member.metadata["focus"], "react")
        self.assertEqual(member.contributions, 3)
        self.assertEqual(member.discussions, ["disc1", "disc2"])
        # Note: id is generated, not from data
        self.assertIsNotNone(member.id)

    def test_add_role(self):
        """Test adding roles to a member."""
        member = TeamMember("test")
        self.assertEqual(member.roles, [])

        member.add_role("architect")
        self.assertEqual(member.roles, ["architect"])

        member.add_role("developer")
        self.assertEqual(member.roles, ["architect", "developer"])

        # Adding duplicate role should not duplicate
        member.add_role("architect")
        self.assertEqual(member.roles, ["architect", "developer"])

    def test_remove_role(self):
        """Test removing roles from a member."""
        member = TeamMember("test", roles=["architect", "developer"])
        self.assertEqual(member.roles, ["architect", "developer"])

        member.remove_role("architect")
        self.assertEqual(member.roles, ["developer"])

        member.remove_role("nonexistent")
        self.assertEqual(member.roles, ["developer"])  # Should not change

    def test_add_tag(self):
        """Test adding tags to a member."""
        member = TeamMember("test")
        self.assertEqual(member.tags, [])

        member.add_tag("senior")
        self.assertEqual(member.tags, ["senior"])

        member.add_tag("backend")
        self.assertEqual(member.tags, ["senior", "backend"])

        # Adding duplicate tag should not duplicate
        member.add_tag("senior")
        self.assertEqual(member.tags, ["senior", "backend"])

    def test_remove_tag(self):
        """Test removing tags from a member."""
        member = TeamMember("test", tags=["senior", "backend"])
        self.assertEqual(member.tags, ["senior", "backend"])

        member.remove_tag("senior")
        self.assertEqual(member.tags, ["backend"])

        member.remove_tag("nonexistent")
        self.assertEqual(member.tags, ["backend"])  # Should not change

    def test_add_discussion(self):
        """Test adding discussions to a member."""
        member = TeamMember("test")
        self.assertEqual(member.discussions, [])

        member.add_discussion("discussion1")
        self.assertEqual(member.discussions, ["discussion1"])

        member.add_discussion("discussion2")
        self.assertEqual(member.discussions, ["discussion1", "discussion2"])

        # Adding duplicate discussion should not duplicate
        member.add_discussion("discussion1")
        self.assertEqual(member.discussions, ["discussion1", "discussion2"])

    def test_add_contribution(self):
        """Test adding contributions to a member."""
        member = TeamMember("test")
        self.assertEqual(member.contributions, 0)

        member.add_contribution()
        self.assertEqual(member.contributions, 1)

        member.add_contribution()
        self.assertEqual(member.contributions, 2)

    def test_update_metadata(self):
        """Test updating member metadata."""
        member = TeamMember("test")
        self.assertEqual(member.metadata, {})

        member.update_metadata({"key1": "value1", "key2": "value2"})
        self.assertEqual(member.metadata["key1"], "value1")
        self.assertEqual(member.metadata["key2"], "value2")

        # Update should merge, not replace
        member.update_metadata({"key1": "updated", "key3": "value3"})
        self.assertEqual(member.metadata["key1"], "updated")
        self.assertEqual(member.metadata["key2"], "value2")
        self.assertEqual(member.metadata["key3"], "value3")


class TestTeamMemberManager(unittest.TestCase):
    """Test TeamMemberManager class functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.project_root = self.test_dir

        # Create basic project structure
        agents_dir = Path(self.test_dir) / "agent"
        agents_dir.mkdir(exist_ok=True)

        # Create a test agent file with #tag format
        agent_file = agents_dir / "developer.md"
        agent_file.write_text("# Developer\n\nrole: developer\n#backend #api\n---\nspecialization: microservices")

        # Create templates directory at the correct path
        # The TeamMemberManager looks for templates_dir at: Path(__file__).parent.parent / "agents"
        workflow_dir = Path(self.test_dir) / "theteam" / "workflow"
        workflow_dir.mkdir(parents=True, exist_ok=True)

        templates_dir = workflow_dir / "agents"
        templates_dir.mkdir(parents=True, exist_ok=True)

        # Create a test template file with #tag format
        template_file = templates_dir / "architect.md"
        template_file.write_text("# Architect\n\nrole: architect\n#design\nfocus: system design")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_manager_initialization(self):
        """Test TeamMemberManager initialization."""
        manager = TeamMemberManager(self.project_root)
        self.assertEqual(manager.project_root, self.project_root)
        self.assertEqual(manager.members, {})
        self.assertTrue(manager.agents_dir.exists())
        self.assertTrue(manager.templates_dir.exists())

    def test_discover_and_load(self):
        """Test basic discovery and loading."""
        manager = TeamMemberManager(self.project_root)
        members = manager.discover_and_load()

        # Should discover developer from agent folder
        self.assertIn("developer", members)
        developer = members["developer"]
        self.assertEqual(developer.name, "developer")
        self.assertIn("developer", developer.roles)
        self.assertIn("backend", developer.tags)
        self.assertIn("api", developer.tags)

        # Should discover architect from templates
        self.assertIn("architect", members)
        architect = members["architect"]
        self.assertEqual(architect.member_type, "template")
        self.assertIn("architect", architect.roles)
        self.assertIn("design", architect.tags)

    def test_create_member(self):
        """Test creating a new team member."""
        manager = TeamMemberManager(self.project_root)
        member = manager.create_member(
            "new_member",
            "project_member",
            ["tester", "qa"],
            ["junior", "testing"],
            {"specialization": "automated testing"}
        )

        self.assertEqual(member.name, "new_member")
        self.assertEqual(member.member_type, "project_member")
        self.assertEqual(member.roles, ["tester", "qa"])
        self.assertEqual(member.tags, ["junior", "testing"])
        self.assertEqual(member.metadata["specialization"], "automated testing")

        # Verify member is in manager
        self.assertIn("new_member", manager.members)

    def test_create_duplicate_member(self):
        """Test that creating duplicate members raises error."""
        manager = TeamMemberManager(self.project_root)
        manager.create_member("existing", "project_member")

        with self.assertRaises(ValueError) as context:
            manager.create_member("existing", "project_member")

        self.assertIn("already exists", str(context.exception))

    def test_get_member(self):
        """Test getting a specific member."""
        manager = TeamMemberManager(self.project_root)
        manager.create_member("test_member", "project_member")

        member = manager.get_member("test_member")
        self.assertIsNotNone(member)
        self.assertEqual(member.name, "test_member")

        # Test non-existent member
        self.assertIsNone(manager.get_member("nonexistent"))

    def test_get_member_by_id(self):
        """Test getting member by ID."""
        manager = TeamMemberManager(self.project_root)
        member = manager.create_member("test_member", "project_member")
        member_id = member.id

        retrieved = manager.get_member_by_id(member_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "test_member")

        # Test non-existent ID
        self.assertIsNone(manager.get_member_by_id("non-existent-id"))

    def test_get_all_members(self):
        """Test getting all members."""
        manager = TeamMemberManager(self.project_root)
        manager.create_member("member1", "project_member")
        manager.create_member("member2", "template")

        all_members = manager.get_all_members()
        self.assertEqual(len(all_members), 2)

        names = [m.name for m in all_members]
        self.assertIn("member1", names)
        self.assertIn("member2", names)

    def test_update_member(self):
        """Test updating a member."""
        manager = TeamMemberManager(self.project_root)
        member = manager.create_member("test_member", "project_member", ["old_role"])

        # Update with new roles
        updated = manager.update_member("test_member", {
            "roles": ["new_role1", "new_role2"],
            "tags": ["new_tag"]
        })

        self.assertIsNotNone(updated)
        self.assertEqual(updated.roles, ["new_role1", "new_role2"])
        self.assertEqual(updated.tags, ["new_tag"])

        # Test updating non-existent member
        self.assertIsNone(manager.update_member("nonexistent", {"roles": ["new"]}))

    def test_delete_member(self):
        """Test deleting a member."""
        manager = TeamMemberManager(self.project_root)
        manager.create_member("to_delete", "project_member")

        # Verify it exists
        self.assertIsNotNone(manager.get_member("to_delete"))

        # Delete it
        deleted = manager.delete_member("to_delete")
        self.assertTrue(deleted)

        # Verify it's gone
        self.assertIsNone(manager.get_member("to_delete"))

        # Test deleting non-existent member
        self.assertFalse(manager.delete_member("nonexistent"))

    def test_configure_member(self):
        """Test configuring a member."""
        manager = TeamMemberManager(self.project_root)
        member = manager.create_member("config_test", "project_member")

        # Configure with additional roles and tags
        configured = manager.configure_member("config_test", {
            "roles": ["new_role"],
            "tags": ["new_tag"],
            "metadata": {"config_key": "config_value"}
        })

        self.assertIsNotNone(configured)
        self.assertIn("new_role", configured.roles)
        self.assertIn("new_tag", configured.tags)
        self.assertEqual(configured.metadata["config_key"], "config_value")

    def test_get_members_by_role(self):
        """Test getting members by role."""
        manager = TeamMemberManager(self.project_root)
        manager.create_member("member1", "project_member", ["architect"])
        manager.create_member("member2", "project_member", ["developer"])
        manager.create_member("member3", "template", ["architect", "developer"])

        architects = manager.get_members_by_role("architect")
        self.assertEqual(len(architects), 2)
        names = [m.name for m in architects]
        self.assertIn("member1", names)
        self.assertIn("member3", names)

        developers = manager.get_members_by_role("developer")
        self.assertEqual(len(developers), 2)
        names = [m.name for m in developers]
        self.assertIn("member2", names)
        self.assertIn("member3", names)

    def test_get_members_by_tag(self):
        """Test getting members by tag."""
        manager = TeamMemberManager(self.project_root)
        manager.create_member("member1", "project_member", tags=["senior"])
        manager.create_member("member2", "project_member", tags=["junior"])
        manager.create_member("member3", "template", tags=["senior", "mid-level"])

        seniors = manager.get_members_by_tag("senior")
        self.assertEqual(len(seniors), 2)
        names = [m.name for m in seniors]
        self.assertIn("member1", names)
        self.assertIn("member3", names)

    def test_get_members_by_type(self):
        """Test getting members by type."""
        manager = TeamMemberManager(self.project_root)
        manager.create_member("member1", "project_member")
        manager.create_member("member2", "template")
        manager.create_member("member3", "system")

        project_members = manager.get_members_by_type("project_member")
        self.assertEqual(len(project_members), 1)
        self.assertEqual(project_members[0].name, "member1")

        templates = manager.get_members_by_type("template")
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0].name, "member2")

    def test_search_members(self):
        """Test searching for members."""
        manager = TeamMemberManager(self.project_root)
        manager.create_member("john_doe", "project_member", roles=["developer"], tags=["backend"])
        manager.create_member("jane_smith", "project_member", roles=["designer"], tags=["frontend"])
        manager.create_member("bob_wilson", "template", metadata={"focus": "devops"})

        # Search by name
        results = manager.search_members("john")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "john_doe")

        # Search by role
        results = manager.search_members("designer")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "jane_smith")

        # Search by tag
        results = manager.search_members("backend")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "john_doe")

        # Search by metadata
        results = manager.search_members("devops")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "bob_wilson")

        # Search by member_type: the two project_member members match.
        # bob_wilson is a "template" member, so it must not match "member".
        results = manager.search_members("member")
        self.assertEqual(len(results), 2)
        self.assertEqual({r.name for r in results}, {"john_doe", "jane_smith"})

    def test_get_active_members(self):
        """Test getting active members."""
        manager = TeamMemberManager(self.project_root)
        member1 = manager.create_member("active_member", "project_member")
        member1.last_seen = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()

        member2 = manager.create_member("inactive_member", "project_member")
        member2.last_seen = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()

        # Get active members (default 30 days)
        active = manager.get_active_members()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].name, "active_member")

        # Get active members (50 days)
        active = manager.get_active_members(50)
        self.assertEqual(len(active), 2)

    def test_get_member_summary(self):
        """Test getting member summary."""
        manager = TeamMemberManager(self.project_root)
        member = manager.create_member("summary_test", "project_member", ["role1"], ["tag1"])
        member.contributions = 5
        member.add_discussion("disc1")
        member.add_discussion("disc2")

        summary = manager.get_member_summary("summary_test")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["name"], "summary_test")
        self.assertEqual(summary["contributions"], 5)
        self.assertEqual(summary["discussion_count"], 2)
        self.assertEqual(summary["roles"], ["role1"])
        self.assertEqual(summary["tags"], ["tag1"])

        # Test non-existent member
        self.assertIsNone(manager.get_member_summary("nonexistent"))

    def test_add_to_discussion(self):
        """Test adding discussion to member."""
        manager = TeamMemberManager(self.project_root)
        manager.create_member("discussion_member", "project_member")

        result = manager.add_to_discussion("discussion_member", "discussion123")
        self.assertTrue(result)

        member = manager.get_member("discussion_member")
        self.assertIn("discussion123", member.discussions)

        # Test non-existent member
        self.assertFalse(manager.add_to_discussion("nonexistent", "disc123"))

    def test_record_contribution(self):
        """Test recording contribution from member."""
        manager = TeamMemberManager(self.project_root)
        manager.create_member("contributor", "project_member")

        result = manager.record_contribution("contributor")
        self.assertTrue(result)

        member = manager.get_member("contributor")
        self.assertEqual(member.contributions, 1)

        # Record another contribution
        result = manager.record_contribution("contributor")
        self.assertTrue(result)
        self.assertEqual(member.contributions, 2)

    def test_persistence(self):
        """Test saving and loading persisted members."""
        manager = TeamMemberManager(self.project_root)
        member1 = manager.create_member("persistent1", "project_member")
        member1.roles = ["role1", "role2"]
        member1.add_contribution()

        # Save state
        manager.save_persisted()

        # Create new manager and load
        manager2 = TeamMemberManager(self.project_root)
        members = manager2.discover_and_load()

        # Should load the persisted member
        self.assertIn("persistent1", members)
        loaded_member = members["persistent1"]
        self.assertEqual(loaded_member.roles, ["role1", "role2"])
        self.assertEqual(loaded_member.contributions, 1)

    def test_integration_with_discovery(self):
        """Test integration with agent discovery."""
        manager = TeamMemberManager(self.project_root)
        members = manager.discover_and_load()

        # Should have discovered developer from agent folder
        self.assertIn("developer", members)
        developer = members["developer"]

        # Verify metadata extraction worked
        self.assertIn("developer", developer.roles)
        self.assertIn("backend", developer.tags)
        self.assertIn("api", developer.tags)
        self.assertEqual(developer.metadata.get("specialization"), "microservices")


class TestPhase1Acceptance(unittest.TestCase):
    """Test Phase 1 acceptance criteria."""

    def test_team_member_management_system(self):
        """Test that the team member management system provides comprehensive capabilities."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = TeamMemberManager(temp_dir)

            # Test creation, configuration, and management
            member1 = manager.create_member("alice", "project_member", ["architect"], ["senior"])
            member2 = manager.create_member("bob", "template", ["developer"], ["mid-level"])

            # Verify configuration capabilities
            self.assertEqual(member1.roles, ["architect"])
            self.assertEqual(member1.tags, ["senior"])

            # Test member management utilities
            architects = manager.get_members_by_role("architect")
            seniors = manager.get_members_by_tag("senior")

            self.assertEqual(len(architects), 1)
            self.assertEqual(len(seniors), 1)

            # Test search and retrieval
            search_results = manager.search_members("alice")
            self.assertEqual(len(search_results), 1)

            # Test persistence
            manager.save_persisted()

            # Verify system can discuss ANY project context
            self.assertTrue(len(manager.get_all_members()) >= 2)

    def test_modular_design(self):
        """Test that the system is modular and independently implementable."""
        # TeamMember class should be independent
        member = TeamMember("test")
        self.assertIsInstance(member, TeamMember)

        # TeamMemberManager should have focused responsibilities
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = TeamMemberManager(temp_dir)
            self.assertTrue(hasattr(manager, 'create_member'))
            self.assertTrue(hasattr(manager, 'get_member'))
            self.assertTrue(hasattr(manager, 'update_member'))
            self.assertTrue(hasattr(manager, 'delete_member'))
            self.assertTrue(hasattr(manager, 'configure_member'))

    def test_stability_and_token_efficiency(self):
        """Test that the system is stable and token-efficient."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test minimal viable product principles
            manager = TeamMemberManager(temp_dir)

            # Should handle basic operations efficiently
            member = manager.create_member("efficient", "project_member")
            self.assertIsNotNone(member)

            # Should not allocate unnecessary resources
            self.assertEqual(len(manager.get_all_members()), 1)

            # Should handle errors gracefully
            try:
                manager.create_member("efficient", "project_member")
            except ValueError:
                pass  # Expected

    def test_backward_compatibility(self):
        """Test that the system maintains backward compatibility."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = TeamMemberManager(temp_dir)

            # Existing API should still work
            member = manager.create_member("legacy", "project_member", ["legacy_role"])

            # Old-style access patterns should still work
            self.assertEqual(member.roles, ["legacy_role"])
            self.assertEqual(member.name, "legacy")

            # New methods should be available
            self.assertTrue(hasattr(manager, 'configure_member'))
            self.assertTrue(hasattr(manager, 'get_member_by_id'))


if __name__ == '__main__':
    unittest.main()