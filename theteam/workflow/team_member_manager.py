#!/usr/bin/env python3
"""
Team Member Manager for Automated Discovery and Management.

Provides comprehensive team member management with creation,
configuration, and management capabilities for team discussion system.
"""

import os
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union

class TeamMember:
    """Represents a team member with project-specific details."""
    def __init__(self, name: str, member_type: str = "project_member", 
                 roles: Optional[List[str]] = None, tags: Optional[List[str]] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.name = name
        self.member_type = member_type
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_seen = self.created_at
        self.discussions: List[str] = []
        self.contributions: int = 0
        self.metadata: Dict[str, Any] = metadata or {}
        self.tags: List[str] = tags or []
        self.roles: List[str] = roles or []
        self.id = str(uuid.uuid4())  # Unique identifier for each member

    def to_dict(self) -> Dict[str, Any]:
        """Convert team member to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "member_type": self.member_type,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "discussions": self.discussions,
            "contributions": self.contributions,
            "metadata": self.metadata,
            "tags": self.tags,
            "roles": self.roles
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamMember":
        """Create team member from dictionary."""
        member = cls(
            data["name"], 
            data.get("member_type", "project_member"),
            data.get("roles", []),
            data.get("tags", []),
            data.get("metadata", {})
        )
        member.id = data.get("id", str(uuid.uuid4()))
        member.created_at = data.get("created_at", member.created_at)
        member.last_seen = data.get("last_seen", member.last_seen)
        member.discussions = data.get("discussions", [])
        member.contributions = data.get("contributions", 0)
        return member

    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """Update member metadata with new values."""
        self.metadata.update(metadata)
        self.last_seen = datetime.now(timezone.utc).isoformat()

    def add_role(self, role: str) -> None:
        """Add a role to the member."""
        if role not in self.roles:
            self.roles.append(role)
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def remove_role(self, role: str) -> None:
        """Remove a role from the member."""
        if role in self.roles:
            self.roles.remove(role)
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def add_tag(self, tag: str) -> None:
        """Add a tag to the member."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the member."""
        if tag in self.tags:
            self.tags.remove(tag)
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def add_discussion(self, discussion_id: str) -> None:
        """Add a discussion to the member's history."""
        if discussion_id not in self.discussions:
            self.discussions.append(discussion_id)
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def add_contribution(self) -> None:
        """Record a contribution from this member."""
        self.contributions += 1
        self.last_seen = datetime.now(timezone.utc).isoformat()


class TeamMemberManager:
    """
    Comprehensive Team Member Manager for automated team member discovery and management.

    Features:
    - Auto-discovery from agent/ folder structure
    - Template loading from theteam/agents/ folder
    - Role and tag extraction from member definitions
    - Discussion tracking per member
    - Persistent storage and loading
    - Full CRUD operations (Create, Read, Update, Delete)
    - Member configuration and management utilities
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.members: Dict[str, TeamMember] = {}
        self.agents_dir = Path(project_root) / "agent"
        # Templates belong to the project being loaded, not to this source tree,
        # so discovery follows project_root like agents_dir and state_file do.
        self.templates_dir = Path(project_root) / "theteam" / "workflow" / "agents"
        from theteam.state import StateStore

        self.state_file = StateStore(str(project_root)).root / "state" / "team_members.json"

    def discover_and_load(self) -> Dict[str, TeamMember]:
        """
        Discover team members from project structure and load from storage.

        Order:
        1. Load persisted members from state file
        2. Discover new members from agent/ folder
        3. Load templates from theteam/agents/ folder
        4. Return complete member dictionary
        """
        # Step 1: Load persisted members
        self._load_persisted_members()

        # Step 2: Discover new members from agent/ folder
        self._discover_from_agent_folder()

        # Step 3: Load and merge templates
        self._load_templates()

        # Step 4: Post-processing - extract roles/tags
        self._extract_metadata()

        return self.members

    def _load_persisted_members(self) -> None:
        """Load previously saved team members from state file."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                for member_data in data:
                    member = TeamMember.from_dict(member_data)
                    self.members[member.name] = member
            except Exception:
                # If loading fails, start fresh
                pass

    def _discover_from_agent_folder(self) -> None:
        """Discover team members from project agent/ folder."""
        if not self.agents_dir.exists():
            return

        for agent_file in self.agents_dir.glob("*.md"):
            member_name = agent_file.stem

            # Skip if already loaded
            if member_name in self.members:
                continue

            try:
                content = agent_file.read_text()
                member = TeamMember(member_name)

                # Extract metadata from content
                member.tags = self._extract_tags(content)
                member.roles = self._extract_roles(content)
                member.metadata = self._extract_advanced_metadata(content)

                self.members[member_name] = member
            except Exception:
                continue

    def _load_templates(self) -> None:
        """Load general templates from theteam/agents/ folder."""
        if not self.templates_dir.exists():
            return

        for template_file in self.templates_dir.glob("*.md"):
            template_name = template_file.stem

            # Skip if already have a project member with this name
            if template_name in self.members:
                continue

            try:
                content = template_file.read_text()
                member = TeamMember(template_name, member_type="template")

                # Extract metadata from template
                member.tags = self._extract_tags(content)
                member.roles = self._extract_roles(content)
                member.metadata = self._extract_advanced_metadata(content)

                self.members[template_name] = member
            except Exception:
                continue

    def _extract_tags(self, content: str) -> List[str]:
        """Extract tags from member markdown content."""
        if not content:
            return []

        tags = re.findall(r'#(\w+)', content.lower())
        # Filter to reasonable tags
        valid_tags = [t for t in tags if len(t) > 0 and len(t) < 30]
        return list(set(valid_tags))

    def _extract_roles(self, content: str) -> List[str]:
        """Extract roles from member markdown content."""
        if not content:
            return []

        role_keywords = ["architect", "developer", "tester", "designer", "devops", "security", "analyst"]
        content_lower = content.lower()
        found_roles = [role for role in role_keywords if role in content_lower]
        return found_roles

    def _extract_advanced_metadata(self, content: str) -> Dict[str, Any]:
        """Extract advanced metadata from member markdown."""
        metadata = {}

        if not content:
            return metadata

        # Look for YAML-like front matter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    yaml_content = parts[1]
                    # Simple YAML parsing for common fields
                    for line in yaml_content.split("\n"):
                        line = line.strip()
                        if ":" in line:
                            key, _, value = line.partition(":")
                            key = key.strip().lower()
                            value = value.strip()
                            if key in ["role", "specialization", "focus"]:
                                metadata[key] = value
                except Exception:
                    pass

        # Look for specific patterns
        # Specializations
        spec_match = re.search(r'specialization[:\s]+(.+)', content, re.IGNORECASE)
        if spec_match:
            metadata["specialization"] = spec_match.group(1).strip()

        # Focus areas
        focus_match = re.search(r'focus[:\s]+(.+)', content, re.IGNORECASE)
        if focus_match:
            metadata["focus"] = focus_match.group(1).strip()

        return metadata

    def _extract_metadata(self) -> None:
        """Extract and normalize metadata from all members."""
        # Post-processing: extract and normalize metadata from all members
        for member in self.members.values():
            # Ensure tags and roles are normalized (lowercase, stripped)
            member.tags = [tag.lower().strip() for tag in member.tags]
            member.roles = [role.lower().strip() for role in member.roles]

            # Extract metadata from member's metadata field
            # This is where we would add more sophisticated metadata extraction
            # if needed, based on member-specific patterns or external sources

            # Update last seen timestamp for members with metadata
            if member.metadata:
                member.last_seen = datetime.now(timezone.utc).isoformat()

    # CRUD Operations

    def create_member(self, name: str, member_type: str = "project_member",
                     roles: Optional[List[str]] = None, tags: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> TeamMember:
        """
        Create a new team member.

        Args:
            name: Unique name for the team member
            member_type: Type of member (project_member, template, system)
            roles: List of roles for the member
            tags: List of tags for categorization
            metadata: Additional metadata for the member

        Returns:
            The created TeamMember

        Raises:
            ValueError: If a member with the same name already exists
        """
        if name in self.members:
            raise ValueError(f"Team member with name '{name}' already exists")

        member = TeamMember(name, member_type, roles, tags, metadata)
        self.members[name] = member
        return member

    def get_member(self, name: str) -> Optional[TeamMember]:
        """Get a team member by name."""
        return self.members.get(name)

    def get_member_by_id(self, member_id: str) -> Optional[TeamMember]:
        """Get a team member by unique ID."""
        for member in self.members.values():
            if member.id == member_id:
                return member
        return None

    def get_all_members(self) -> List[TeamMember]:
        """Get all discovered team members."""
        return list(self.members.values())

    def update_member(self, name: str, updates: Dict[str, Any]) -> Optional[TeamMember]:
        """
        Update an existing team member.

        Args:
            name: Name of the member to update
            updates: Dictionary of fields to update

        Returns:
            Updated TeamMember or None if member not found
        """
        member = self.get_member(name)
        if not member:
            return None

        # Handle specific field updates
        if "roles" in updates:
            member.roles = updates["roles"]
        if "tags" in updates:
            member.tags = updates["tags"]
        if "metadata" in updates:
            member.update_metadata(updates["metadata"])
        if "member_type" in updates:
            member.member_type = updates["member_type"]

        return member

    def delete_member(self, name: str) -> bool:
        """
        Delete a team member.

        Args:
            name: Name of the member to delete

        Returns:
            True if member was deleted, False if not found
        """
        if name in self.members:
            del self.members[name]
            return True
        return False

    def configure_member(self, name: str, config: Dict[str, Any]) -> Optional[TeamMember]:
        """
        Configure a team member with additional settings.

        Args:
            name: Name of the member to configure
            config: Configuration dictionary

        Returns:
            Configured TeamMember or None if member not found
        """
        member = self.get_member(name)
        if not member:
            return None

        # Handle configuration options
        if "roles" in config:
            for role in config["roles"]:
                member.add_role(role)

        if "tags" in config:
            for tag in config["tags"]:
                member.add_tag(tag)

        if "metadata" in config:
            member.update_metadata(config["metadata"])

        return member

    # Member Management Utilities

    def get_members_by_role(self, role: str) -> List[TeamMember]:
        """Get all members with a specific role."""
        return [m for m in self.members.values() if role in m.roles]

    def get_members_by_tag(self, tag: str) -> List[TeamMember]:
        """Get all members with a specific tag."""
        return [m for m in self.members.values() if tag in m.tags]

    def get_members_by_type(self, member_type: str) -> List[TeamMember]:
        """Get all members of a specific type."""
        return [m for m in self.members.values() if m.member_type == member_type]

    def search_members(self, query: str) -> List[TeamMember]:
        """
        Search for members by name, type, metadata, tags, or roles.

        Args:
            query: Search term (case-insensitive)

        Returns:
            List of matching TeamMember objects, in insertion order, no duplicates
        """
        query_lower = query.lower()
        results: List[TeamMember] = []

        for member in self.members.values():
            matched = query_lower in member.name.lower()

            # Member type is a searchable attribute too (e.g. "project_member").
            if not matched and query_lower in member.member_type.lower():
                matched = True

            if not matched:
                matched = any(
                    isinstance(value, str) and query_lower in value.lower()
                    for value in member.metadata.values()
                )

            if not matched:
                matched = any(query_lower in tag.lower() for tag in member.tags)

            if not matched:
                matched = any(query_lower in role.lower() for role in member.roles)

            if matched:
                results.append(member)

        return results

    def get_active_members(self, days: int = 30) -> List[TeamMember]:
        """
        Get members who have been active within the last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of active TeamMember objects
        """
        from datetime import datetime, timedelta
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        active_members = []
        for member in self.members.values():
            last_seen = datetime.fromisoformat(member.last_seen)
            if last_seen >= cutoff_date:
                active_members.append(member)

        return active_members

    def get_member_summary(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of a specific team member.

        Args:
            name: Name of the member

        Returns:
            Summary dictionary or None if member not found
        """
        member = self.get_member(name)
        if not member:
            return None

        return {
            "name": member.name,
            "id": member.id,
            "member_type": member.member_type,
            "roles": member.roles,
            "tags": member.tags,
            "contributions": member.contributions,
            "discussion_count": len(member.discussions),
            "created_at": member.created_at,
            "last_seen": member.last_seen,
            "metadata": member.metadata
        }

    # Persistence

    def save_persisted(self) -> None:
        """Persist current member state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = [member.to_dict() for member in self.members.values()]
            self.state_file.write_text(json.dumps(data, indent=2))
        except Exception:
            pass

    # Integration with other systems

    def add_to_discussion(self, member_name: str, discussion_id: str) -> bool:
        """
        Add a discussion to a member's history.

        Args:
            member_name: Name of the member
            discussion_id: ID of the discussion

        Returns:
            True if successful, False if member not found
        """
        member = self.get_member(member_name)
        if member:
            member.add_discussion(discussion_id)
            return True
        return False

    def record_contribution(self, member_name: str) -> bool:
        """
        Record a contribution from a member.

        Args:
            member_name: Name of the member

        Returns:
            True if successful, False if member not found
        """
        member = self.get_member(member_name)
        if member:
            member.add_contribution()
            return True
        return False


def initialize_team_members(project_root: str) -> Dict[str, TeamMember]:
    """
    Convenience function to initialize team members.

    Args:
        project_root: Project root directory

    Returns:
        Dictionary of member name -> TeamMember
    """
    manager = TeamMemberManager(project_root)
    return manager.discover_and_load()


def main():
    """Main entry point for team member management."""
    import sys

    project_root = sys.argv[1] if len(sys.argv) > 1 else "."

    members = initialize_team_members(project_root)

    print(f"Team Member Discovery for: {project_root}")
    print(f"=" * 60)
    print(f"Total Members: {len(members)}")
    print()

    for member in members.values():
        roles_str = ", ".join(member.roles) if member.roles else "none"
        tags_str = ", ".join(member.tags) if member.tags else "none"
        print(f"  • {member.name}")
        print(f"    Type: {member.member_type}")
        print(f"    Roles: {roles_str}")
        print(f"    Tags: {tags_str}")
        print(f"    Specializations: {metadata_to_str(member.metadata)}")
        print()

    # Save persisted state
    manager = TeamMemberManager(project_root)
    manager.members = {name: TeamMember.from_dict(data) for name, data in members.items()}
    manager.save_persisted()

    print("✓ Team members saved to persisted state")


def metadata_to_str(metadata: Dict[str, Any]) -> str:
    """Convert metadata dict to readable string."""
    if not metadata:
        return "none"
    parts = []
    for key, value in metadata.items():
        parts.append(f"{key}: {value}")
    return ", ".join(parts)


if __name__ == "__main__":
    main()