#!/usr/bin/env python3
"""
Team Member Management System for theteam skill enhancement.

This module provides comprehensive team member management capabilities with:
- Modular, token-efficient design for any project, any context
- Independent initialization and configuration
- Stable member lifecycle management
- Integration-ready with all other team components

Key Features:
- Create, configure, list, and remove team members
- Member validation and token-efficient operations
- Persistent storage with automatic cleanup
- Integration with DiscussionManager, TaskManager, and LoopManager
- Backward compatibility maintained
"""

import os
import json
import uuid
import time
import threading
import weakref
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class TeamMemberConfig:
    """Configuration for team member management system."""
    def __init__(self):
        self.members_dir = ".mp/theteam/members"
        self.member_ttl_days = 365  # Member validity period
        self.max_members = 1000  # Maximum team members
        self.enable_auto_cleanup = True
        self.token_efficient = True

class TeamMember:
    """Represents a team member with full configuration."""
    def __init__(self, member_id: str, role: str, permissions: List[str] = None):
        self.member_id = member_id
        self.role = role
        self.permissions = permissions or []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_active = datetime.now(timezone.utc).isoformat()
        self.is_active = True
        self.contexts = set()  # Projects/contexts this member can access
        self.preferences = {}

class _MemberStore:
    """Reference-counted holder for one project's member dict.

    A plain dict cannot be weakly referenced, so the shared registry maps
    project roots to this holder instead; when the last manager for a project
    is collected, the entry disappears from the weak table on its own.
    """

    def __init__(self, members: Optional[Dict[str, TeamMember]] = None):
        self.members: Dict[str, TeamMember] = members if members is not None else {}

class TeamMemberManager:
    """Modular team member management system with token-efficient operations.

    One project has one member registry. Instances for the same project_root
    share their member store, so components that each construct a manager
    (DiscussionInterface, workflow tooling) never observe divergent state.

    The shared store is a weak side table keyed by project root: a store lives
    only while some manager for that project is alive, so long-running processes
    that touch many projects do not accumulate one registry per project
    forever. Disk remains the source of truth on construction — a member file
    written by another process is always merged in, never dropped in favour of
    a stale in-memory copy.
    """
    # project_root -> store. A bare dict is not weak-referenceable, so the store
    # is held by a small refcounted holder; the weak table drops the entry once
    # the last manager for a project is gone.
    _shared_stores: "weakref.WeakValueDictionary[str, '_MemberStore']" = (
        weakref.WeakValueDictionary()
    )
    _shared_lock = threading.RLock()

    def __init__(self, project_root: str, config: Optional[TeamMemberConfig] = None):
        """
        Initialize team member manager.

        Args:
            project_root: Root directory of the project
            config: Team member configuration (uses defaults if None)
        """
        self.project_root = Path(project_root)
        self.config = config or TeamMemberConfig()
        self._setup_directories()
        self._member_lock = threading.RLock()
        self._performance_cache = {}

        # Disk is authoritative: the first manager for a project builds the store
        # from disk, and any later manager folds the current on-disk state into
        # the existing store instead of discarding what it just read.
        with TeamMemberManager._shared_lock:
            key = str(self.project_root)
            store = TeamMemberManager._shared_stores.get(key)
            if store is None:
                store = _MemberStore(self._read_members_from_disk())
                TeamMemberManager._shared_stores[key] = store
            else:
                self._merge_into(store)
            # Keep the holder alive for as long as this manager exists.
            self._store = store
            self.members = store.members

        logger.info(f"TeamMemberManager initialized for project: {project_root}")

    @classmethod
    def clear_shared_store(cls, project_root: str) -> None:
        """Drop the shared store for a project. Intended for tests."""
        with cls._shared_lock:
            cls._shared_stores.pop(str(Path(project_root)), None)
    
    def _setup_directories(self):
        """Set up required directory structure under the project root."""
        # Members live inside the project they describe, not the process CWD.
        self.config.members_dir = str(self.project_root / self.config.members_dir)
        os.makedirs(self.config.members_dir, exist_ok=True)
    
    def _read_members_from_disk(self) -> Dict[str, TeamMember]:
        """Read every persisted member from the members directory."""
        loaded: Dict[str, TeamMember] = {}
        try:
            for member_file in os.listdir(self.config.members_dir):
                if not member_file.endswith('.json'):
                    continue
                member_id = member_file[:-5]
                member_path = os.path.join(self.config.members_dir, member_file)
                with open(member_path, 'r') as f:
                    member_data = json.load(f)
                member = TeamMember(
                    member_id=member_data.get('member_id', member_id),
                    role=member_data.get('role', 'member'),
                    permissions=member_data.get('permissions', [])
                )
                # Set additional metadata
                if 'created_at' in member_data:
                    member.created_at = member_data['created_at']
                if 'last_active' in member_data:
                    member.last_active = member_data['last_active']
                if 'is_active' in member_data:
                    member.is_active = member_data['is_active']
                if 'contexts' in member_data:
                    member.contexts = set(member_data['contexts'])
                if 'preferences' in member_data:
                    member.preferences = member_data['preferences']
                loaded[member_id] = member
        except Exception as e:
            logger.error(f"Failed to load team members: {e}")
        return loaded

    def _merge_into(self, store: "_MemberStore") -> None:
        """Fold on-disk state into an existing store; disk wins per member."""
        for member_id, member in self._read_members_from_disk().items():
            store.members[member_id] = member
    
    def _save_member(self, member: TeamMember):
        """Save a team member to storage."""
        member_path = os.path.join(self.config.members_dir, f"{member.member_id}.json")
        member_data = {
            'member_id': member.member_id,
            'role': member.role,
            'permissions': member.permissions,
            'created_at': member.created_at,
            'last_active': member.last_active,
            'is_active': member.is_active,
            'contexts': list(member.contexts),
            'preferences': member.preferences
        }
        
        try:
            with open(member_path, 'w') as f:
                json.dump(member_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save member {member.member_id}: {e}")
            raise

    def create_team_member(self, role: str, permissions: List[str] = None, 
                          member_id: Optional[str] = None) -> TeamMember:
        """
        Create a new team member.
        
        Args:
            role: Role of the team member
            permissions: List of permissions for the member
            member_id: Optional member ID (auto-generated if not provided)
            
        Returns:
            Created TeamMember instance
        """
        if member_id is None:
            member_id = f"member_{uuid.uuid4().hex[:8]}"
        
        with self._member_lock:
            if member_id in self.members:
                raise ValueError(f"Member with ID '{member_id}' already exists")
            
            if len(self.members) >= self.config.max_members:
                raise ValueError(f"Maximum number of members ({self.config.max_members}) reached")
            
            member = TeamMember(member_id, role, permissions or [])
            # A member belongs to the project it was created in, so it starts
            # with access to that project root. Wider contexts are granted
            # explicitly via configure_team_member(contexts=...).
            member.contexts.add(str(self.project_root))
            self.members[member_id] = member
            self._save_member(member)
            
            logger.info(f"Created team member: {member_id} with role: {role}")
            return member

    def configure_team_member(self, member_id: str, **kwargs) -> bool:
        """
        Configure a team member with new settings.
        
        Args:
            member_id: ID of the member to configure
            **kwargs: Configuration options (role, permissions, contexts, preferences)
            
        Returns:
            True if configuration updated successfully, False otherwise
        """
        with self._member_lock:
            if member_id not in self.members:
                logger.error(f"Member not found: {member_id}")
                return False
            
            member = self.members[member_id]
            
            if 'role' in kwargs:
                member.role = kwargs['role']
            
            if 'permissions' in kwargs:
                member.permissions = kwargs['permissions']
            
            if 'contexts' in kwargs:
                if isinstance(kwargs['contexts'], (set, list)):
                    member.contexts = set(kwargs['contexts'])
                else:
                    member.contexts = {kwargs['contexts']}
            
            if 'is_active' in kwargs:
                member.is_active = bool(kwargs['is_active'])

            if 'preferences' in kwargs:
                member.preferences.update(kwargs['preferences'])
            
            member.last_active = datetime.now(timezone.utc).isoformat()
            self._save_member(member)
            
            logger.info(f"Configured team member: {member_id}")
            return True

    def list_team_members(self, role_filter: Optional[str] = None, 
                         context: Optional[str] = None, active_only: bool = True) -> List[TeamMember]:
        """
        List team members with optional filtering.
        
        Args:
            role_filter: Filter members by role
            context: Filter members by context access
            active_only: Only return active members
            
        Returns:
            List of matching TeamMember instances
        """
        with self._member_lock:
            members = list(self.members.values())
            
            # Apply filters
            if role_filter:
                members = [m for m in members if m.role == role_filter]
            
            if context:
                members = [m for m in members if context in m.contexts]
            
            if active_only:
                members = [m for m in members if m.is_active]
            
            # Sort by role, then member_id for consistent ordering
            members.sort(key=lambda m: (m.role, m.member_id))
            return members

    def remove_team_member(self, member_id: str, permanent: bool = False) -> bool:
        """
        Remove a team member.
        
        Args:
            member_id: ID of the member to remove
            permanent: If True, permanently delete; if False, mark as inactive
            
        Returns:
            True if member removed successfully, False otherwise
        """
        with self._member_lock:
            if member_id not in self.members:
                logger.error(f"Member not found: {member_id}")
                return False
            
            member = self.members[member_id]
            
            if permanent:
                # Remove from storage
                member_path = os.path.join(self.config.members_dir, f"{member_id}.json")
                try:
                    os.remove(member_path)
                except Exception as e:
                    logger.error(f"Failed to remove member file: {e}")
                    return False
                del self.members[member_id]
                logger.info(f"Permanently removed team member: {member_id}")
            else:
                # Mark as inactive
                member.is_active = False
                member.last_active = datetime.now(timezone.utc).isoformat()
                self._save_member(member)
                logger.info(f"Deactivated team member: {member_id}")
            
            return True

    def get_team_member(self, member_id: str) -> Optional[TeamMember]:
        """
        Get a team member by ID.
        
        Args:
            member_id: ID of the member to retrieve
            
        Returns:
            TeamMember instance if found, None otherwise
        """
        with self._member_lock:
            return self.members.get(member_id)

    def add_context_access(self, member_id: str, context: str) -> bool:
        """
        Add context access for a team member.
        
        Args:
            member_id: ID of the member
            context: Context/project to grant access to
            
        Returns:
            True if access added successfully, False otherwise
        """
        with self._member_lock:
            if member_id not in self.members:
                return False
            
            self.members[member_id].contexts.add(context)
            self._save_member(self.members[member_id])
            return True

    def remove_context_access(self, member_id: str, context: str) -> bool:
        """
        Remove context access for a team member.
        
        Args:
            member_id: ID of the member
            context: Context/project to revoke access from
            
        Returns:
            True if access removed successfully, False otherwise
        """
        with self._member_lock:
            if member_id not in self.members:
                return False
            
            self.members[member_id].contexts.discard(context)
            self._save_member(self.members[member_id])
            return True

    def can_access_context(self, member_id: str, context: str) -> bool:
        """
        Check if a team member can access a specific context.
        
        Args:
            member_id: ID of the member
            context: Context/project to check access for
            
        Returns:
            True if member has access, False otherwise
        """
        with self._member_lock:
            member = self.members.get(member_id)
            if not member:
                return False
            
            # Member can access if they have the context explicitly
            if context in member.contexts:
                return True
            
            # Member can access if they have 'admin' role
            if member.role == 'admin':
                return True
            
            return False

    def cleanup_inactive_members(self) -> int:
        """
        Clean up inactive team members based on TTL.
        
        Returns:
            Number of members cleaned up
        """
        if not self.config.enable_auto_cleanup:
            return 0
        
        with self._member_lock:
            current_time = datetime.now(timezone.utc)
            members_to_remove = []
            
            for member_id, member in self.members.items():
                if not member.is_active:
                    # TTL runs from the member's last activity, not its creation:
                    # an explicitly deactivated member must not survive cleanup
                    # just because it was created recently.
                    last_active = datetime.fromisoformat(member.last_active or member.created_at)
                    days_inactive = (current_time - last_active).days

                    if days_inactive >= self.config.member_ttl_days:
                        members_to_remove.append(member_id)
            
            # Remove inactive members
            cleaned_count = 0
            for member_id in members_to_remove:
                member_path = os.path.join(self.config.members_dir, f"{member_id}.json")
                try:
                    os.remove(member_path)
                    del self.members[member_id]
                    cleaned_count += 1
                except Exception as e:
                    logger.error(f"Failed to clean up member {member_id}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} inactive team members")
            
            return cleaned_count

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get system status and statistics.
        
        Returns:
            Dictionary with system status information
        """
        with self._member_lock:
            active_members = [m for m in self.members.values() if m.is_active]
            roles = {}
            for member in self.members.values():
                roles[member.role] = roles.get(member.role, 0) + 1
            
            total_contexts = set()
            for member in self.members.values():
                total_contexts.update(member.contexts)
            
            return {
                'total_members': len(self.members),
                'active_members': len(active_members),
                'inactive_members': len(self.members) - len(active_members),
                'member_roles': roles,
                'total_contexts': len(total_contexts),
                'contexts': list(total_contexts),
                'max_members': self.config.max_members,
                'members_dir': self.config.members_dir,
                'auto_cleanup_enabled': self.config.enable_auto_cleanup,
                'member_ttl_days': self.config.member_ttl_days,
                'token_efficient_mode': self.config.token_efficient
            }

    def export_members(self, export_path: Optional[str] = None) -> str:
        """
        Export all team members to a file.
        
        Args:
            export_path: Path to export file (auto-generated if None)
            
        Returns:
            Path to exported file
        """
        with self._member_lock:
            if export_path is None:
                export_path = os.path.join(self.config.members_dir, 
                                           f"team_members_export_{int(time.time())}.json")
            
            members_data = {}
            for member_id, member in self.members.items():
                members_data[member_id] = {
                    'member_id': member.member_id,
                    'role': member.role,
                    'permissions': member.permissions,
                    'created_at': member.created_at,
                    'last_active': member.last_active,
                    'is_active': member.is_active,
                    'contexts': list(member.contexts),
                    'preferences': member.preferences
                }
            
            try:
                with open(export_path, 'w') as f:
                    json.dump(members_data, f, indent=2)
                logger.info(f"Exported {len(self.members)} team members to {export_path}")
                return export_path
            except Exception as e:
                logger.error(f"Failed to export team members: {e}")
                raise

    def import_members(self, import_path: str) -> int:
        """
        Import team members from a file.
        
        Args:
            import_path: Path to import file
            
        Returns:
            Number of members imported
        """
        if not os.path.exists(import_path):
            raise FileNotFoundError(f"Import file not found: {import_path}")
        
        try:
            with open(import_path, 'r') as f:
                members_data = json.load(f)
            
            imported_count = 0
            with self._member_lock:
                for member_id, member_data in members_data.items():
                    if member_id not in self.members:
                        member = TeamMember(
                            member_id=member_data.get('member_id', member_id),
                            role=member_data.get('role', 'member'),
                            permissions=member_data.get('permissions', [])
                        )
                        member.created_at = member_data.get('created_at', member.created_at)
                        member.last_active = member_data.get('last_active', member.last_active)
                        member.is_active = member_data.get('is_active', True)
                        member.contexts = set(member_data.get('contexts', []))
                        member.preferences = member_data.get('preferences', {})
                        
                        self.members[member_id] = member
                        imported_count += 1
            
            logger.info(f"Imported {imported_count} team members from {import_path}")
            return imported_count
        except Exception as e:
            logger.error(f"Failed to import team members: {e}")
            raise

    def cleanup(self):
        """Clean up resources."""
        self._member_lock.acquire()
        try:
            self._performance_cache.clear()
            self.members.clear()
        finally:
            self._member_lock.release()