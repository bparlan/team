#!/usr/bin/env python3
"""
Unified state management for theteam skill enhancement.

This module provides centralized state management that integrates:
- Team discussion state
- System awareness state
- Task management state
- Real-time monitoring capabilities
"""

import os
import json
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import logging
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

# Import Phase 2 modules for robust state management
from .wal import WriteAheadLog
from .checksum import ChecksumManager
from .database import DatabaseManager
from .transactions import TransactionManager
from .correlation import CorrelationManager

class StateEventType(Enum):
    DISCUSSION_STARTED = "discussion_started"
    DISCUSSION_COMPLETED = "discussion_completed"
    SYSTEM_ANALYSIS_STARTED = "system_analysis_started"
    SYSTEM_ANALYSIS_COMPLETED = "system_analysis_completed"
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    MEMBER_JOINED = "member_joined"
    MEMBER_LEFT = "member_left"
    SYSTEM_HEALTH_UPDATE = "system_health_update"
    USER_INTERACTION = "user_interaction"
class DiscussionState:
    def __init__(self):
        self.active_discussions: Dict[str, Dict[str, Any]] = {}
        self.discussion_history: List[Dict[str, Any]] = []
        self.current_discussion_id: Optional[str] = None
        self.topic_suggestions: List[str] = []

    def start_discussion(self, topic: str, project_root: str) -> str:
        """Start a new discussion and return its ID."""
        discussion_id = f"discussion_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.active_discussions[discussion_id] = {
            'topic': topic,
            'project_root': project_root,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'status': 'active',
            'participants': [],
            'tasks': [],
            'system_analysis': None
        }
        self.current_discussion_id = discussion_id
        self._notify_listeners(StateEventType.DISCUSSION_STARTED, {
            'discussion_id': discussion_id,
            'topic': topic
        })
        logger.info(f"Started discussion {discussion_id} on topic: {topic}")
        return discussion_id

    def complete_discussion(self, discussion_id: str) -> bool:
        """Complete a discussion and move it to history."""
        if discussion_id in self.active_discussions:
            discussion = self.active_discussions[discussion_id]
            discussion['completed_at'] = datetime.now(timezone.utc).isoformat()
            discussion['status'] = 'completed'
            self.discussion_history.append(discussion)
            del self.active_discussions[discussion_id]
            self.current_discussion_id = None
            self._notify_listeners(StateEventType.DISCUSSION_COMPLETED, {
                'discussion_id': discussion_id
            })
            logger.info(f"Completed discussion {discussion_id}")
            return True
        return False

    def add_participant(self, discussion_id: str, member_id: str):
        """Add a participant to a discussion."""
        if discussion_id in self.active_discussions:
            if member_id not in self.active_discussions[discussion_id]['participants']:
                self.active_discussions[discussion_id]['participants'].append(member_id)
                self._notify_listeners(StateEventType.MEMBER_JOINED, {
                    'discussion_id': discussion_id,
                    'member_id': member_id
                })

    def add_task(self, discussion_id: str, task_info: Dict[str, Any]):
        """Add a task to a discussion."""
        if discussion_id in self.active_discussions:
            task_info['task_id'] = f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            task_info['added_at'] = datetime.now(timezone.utc).isoformat()
            self.active_discussions[discussion_id]['tasks'].append(task_info)
            self._notify_listeners(StateEventType.TASK_CREATED, {
                'discussion_id': discussion_id,
                'task': task_info
            })

    def get_discussion_state(self, discussion_id: str) -> Optional[Dict[str, Any]]:
        """Get the state of a specific discussion."""
        return self.active_discussions.get(discussion_id)

    def get_active_discussions(self) -> List[Dict[str, Any]]:
        """Get all active discussions."""
        return list(self.active_discussions.values())
class SystemAwarenessState:
    def __init__(self):
        self.active_analyses: Dict[str, Dict[str, Any]] = {}
        self.analysis_history: List[Dict[str, Any]] = []
        self.health_metrics: Dict[str, Any] = {}
        self.health_history: List[Dict[str, Any]] = []
        self.analysis_triggers: List[Dict[str, Any]] = []

    def start_analysis(self, analysis_type: str, project_root: str) -> str:
        """Start a system awareness analysis and return its ID."""
        analysis_id = f"analysis_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.active_analyses[analysis_id] = {
            'type': analysis_type,
            'project_root': project_root,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'status': 'running',
            'results': None
        }
        self._notify_listeners(StateEventType.SYSTEM_ANALYSIS_STARTED, {
            'analysis_id': analysis_id,
            'type': analysis_type
        })
        logger.info(f"Started system analysis {analysis_id} of type: {analysis_type}")
        return analysis_id

    def complete_analysis(self, analysis_id: str, results: Dict[str, Any]):
        """Complete a system analysis and store results."""
        if analysis_id in self.active_analyses:
            analysis = self.active_analyses[analysis_id]
            analysis['completed_at'] = datetime.now(timezone.utc).isoformat()
            analysis['status'] = 'completed'
            analysis['results'] = results
            self.analysis_history.append(analysis)
            del self.active_analyses[analysis_id]
            self._notify_listeners(StateEventType.SYSTEM_ANALYSIS_COMPLETED, {
                'analysis_id': analysis_id,
                'results': results
            })
            logger.info(f"Completed system analysis {analysis_id}")

    def update_health_metrics(self, metrics: Dict[str, Any]):
        """Update system health metrics."""
        self.health_metrics.update(metrics)
        metrics['timestamp'] = datetime.now(timezone.utc).isoformat()
        self.health_history.append(metrics)
        # Keep only last 1000 entries
        if len(self.health_history) > 1000:
            self.health_history = self.health_history[-1000:]
        self._notify_listeners(StateEventType.SYSTEM_HEALTH_UPDATE, metrics)

    def add_analysis_trigger(self, trigger: Dict[str, Any]):
        """Add a trigger for system analysis."""
        self.analysis_triggers.append({
            **trigger,
            'trigger_id': f"trigger_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            'created_at': datetime.now(timezone.utc).isoformat()
        })

    def get_active_analyses(self) -> List[Dict[str, Any]]:
        """Get all active analyses."""
        return list(self.active_analyses.values())

    def get_recent_health_metrics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent health metrics."""
        return self.health_history[-limit:] if self.health_history else []
class TaskState:
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_history: List[Dict[str, Any]] = []
        self.task_assignments: Dict[str, List[str]] = {}  # task_id -> list of member_ids

    def create_task(self, task_info: Dict[str, Any], discussion_id: Optional[str] = None) -> str:
        """Create a new task and return its ID."""
        task_id = f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        task_info['task_id'] = task_id
        task_info['created_at'] = datetime.now(timezone.utc).isoformat()
        task_info['discussion_id'] = discussion_id
        task_info['status'] = 'created'
        self.tasks[task_id] = task_info
        if discussion_id:
            self._notify_listeners(StateEventType.TASK_CREATED, {
                'task_id': task_id,
                'discussion_id': discussion_id,
                'task_info': task_info
            })
        logger.info(f"Created task {task_id}: {task_info.get('title', 'Untitled')}")
        return task_id

    def update_task(self, task_id: str, updates: Dict[str, Any]):
        """Update a task's state."""
        if task_id in self.tasks:
            self.tasks[task_id].update(updates)
            self.tasks[task_id]['last_updated'] = datetime.now(timezone.utc).isoformat()
            if updates.get('status') == 'completed':
                self.task_history.append(self.tasks[task_id].copy())
                del self.tasks[task_id]
            else:
                self._notify_listeners(StateEventType.TASK_UPDATED, {
                    'task_id': task_id,
                    'updates': updates
                })

    def assign_task(self, task_id: str, member_ids: List[str]):
        """Assign a task to members."""
        if task_id in self.tasks:
            self.task_assignments[task_id] = member_ids
            self._notify_listeners(StateEventType.TASK_UPDATED, {
                'task_id': task_id,
                'assignments': member_ids
            })

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task details."""
        return self.tasks.get(task_id)

    def get_tasks_by_discussion(self, discussion_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a discussion."""
        return [task for task in self.tasks.values() if task.get('discussion_id') == discussion_id]

    def get_tasks_by_member(self, member_id: str) -> List[Dict[str, Any]]:
        """Get all tasks assigned to a member."""
        assigned_task_ids = self.task_assignments.get(member_id, [])
        return [task for task_id, task in self.tasks.items() if task_id in assigned_task_ids]
class UnifiedStateManager:
    def __init__(self, state_file: Optional[str] = None):
        # Initialize Phase 2 modules
        self.wal = WriteAheadLog()
        self.checksum = ChecksumManager()
        self.db = DatabaseManager()
        self.tx = TransactionManager()
        self.correlation = CorrelationManager()
        
        self.discussion_state = DiscussionState()
        self.system_awareness_state = SystemAwarenessState()
        self.task_state = TaskState()
        self.state_file = state_file
        self.listeners: List[Callable[[StateEventType, Dict[str, Any]], None]] = []
        self.lock = threading.Lock()

    def add_listener(self, listener: Callable[[StateEventType, Dict[str, Any]], None]):
        """Add a listener for state changes."""
        self.listeners.append(listener)

    def _notify_listeners(self, event_type: StateEventType, data: Dict[str, Any]):
        """Notify all listeners of a state change."""
        for listener in self.listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                logger.error(f"Error in state listener: {e}")

    def save_state(self):
        """Save state to file."""
        if self.state_file:
            try:
                state_data = {
                    'discussion_state': {
                        'active_discussions': self.discussion_state.active_discussions,
                        'discussion_history': self.discussion_state.discussion_history,
                        'current_discussion_id': self.discussion_state.current_discussion_id
                    },
                    'system_awareness_state': {
                        'active_analyses': self.system_awareness_state.active_analyses,
                        'analysis_history': self.system_awareness_state.analysis_history,
                        'health_metrics': self.system_awareness_state.health_metrics,
                        'health_history': self.system_awareness_state.health_history
                    },
                    'task_state': {
                        'tasks': self.task_state.tasks,
                        'task_history': self.task_state.task_history,
                        'task_assignments': self.task_state.task_assignments
                    }
                }
                
                # Log to WAL before writing
                self.wal.log_state_change('save', state_data)
                
                # Add checksum for integrity
                self.checksum.add_checksum(state_data)
                
                with open(self.state_file, 'w') as f:
                    json.dump(state_data, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving state: {e}")

    def save_configuration(self):
        """Save configuration without swallowing exceptions."""
        if not self.state_file:
            raise ValueError("No state file configured for saving")
        
        try:
            # Create configuration data
            config_data = {
                'state_file': self.state_file,
                'version': '1.0',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Save configuration - let exceptions propagate
            with open(self.state_file, 'w') as f:
                json.dump(config_data, f, indent=2)
                
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Configuration file not found: {e}")
        except PermissionError as e:
            raise PermissionError(f"Permission denied writing configuration: {e}")
        except OSError as e:
            raise OSError(f"OS error writing configuration: {e}")
        except Exception as e:
            # Re-raise any other unexpected exceptions
            raise RuntimeError(f"Unexpected error saving configuration: {e}")



    def load_state(self):
        """Load state from file."""
        if self.state_file and os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)
                
                # Verify checksum
                if not self.checksum.verify_checksum(state_data):
                    raise ValueError("State file checksum verification failed")
                
                # Replay WAL entries for recovery
                self.wal.replay_entries()
                
                self.discussion_state.active_discussions = state_data.get('discussion_state', {}).get('active_discussions', {})
                self.discussion_state.discussion_history = state_data.get('discussion_state', {}).get('discussion_history', [])
                self.discussion_state.current_discussion_id = state_data.get('discussion_state', {}).get('current_discussion_id')

                self.system_awareness_state.active_analyses = state_data.get('system_awareness_state', {}).get('active_analyses', {})
                self.system_awareness_state.analysis_history = state_data.get('system_awareness_state', {}).get('analysis_history', [])
                self.system_awareness_state.health_metrics = state_data.get('system_awareness_state', {}).get('health_metrics', {})
                self.system_awareness_state.health_history = state_data.get('system_awareness_state', {}).get('health_history', [])

                self.task_state.tasks = state_data.get('task_state', {}).get('tasks', {})
                self.task_state.task_history = state_data.get('task_state', {}).get('task_history', [])
                self.task_state.task_assignments = state_data.get('task_state', {}).get('task_assignments', {})
            except Exception as e:
                logger.error(f"Error loading state: {e}")

    def start_monitoring(self, interval: int = 60):
        """Start background monitoring for state persistence."""
        def monitor():
            while True:
                time.sleep(interval)
                self.save_state()

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        logger.info(f"Started state monitoring with {interval}s interval")

    def get_unified_dashboard(self) -> Dict[str, Any]:
        """Get a unified dashboard view of all state."""
        with self.lock:
            return {
                'active_discussions': self.discussion_state.get_active_discussions(),
                'active_analyses': self.system_awareness_state.get_active_analyses(),
                'recent_health_metrics': self.system_awareness_state.get_recent_health_metrics(5),
                'pending_tasks': list(self.task_state.tasks.values()),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
# Global state manager instance
_state_manager = None

def get_state_manager(state_file: Optional[str] = None) -> UnifiedStateManager:
    """Get or create the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = UnifiedStateManager(state_file)
        # Load existing state if available
        _state_manager.load_state()
        # Start background monitoring
        _state_manager.start_monitoring()
    return _state_manager

if __name__ == "__main__":
    # Example usage
    state_manager = get_state_manager("/tmp/theteam_state.json")

    # Simulate starting a discussion
    discussion_id = state_manager.discussion_state.start_discussion(
        "Optimize database queries", os.getcwd()
    )
    state_manager.discussion_state.add_participant(discussion_id, "architect")
    state_manager.discussion_state.add_task(discussion_id, {
        'title': 'Analyze slow queries',
        'priority': 'high',
        'assignee': 'architect'
    })

    # Simulate system analysis
    analysis_id = state_manager.system_awareness_state.start_analysis(
        "infrastructure_assessment", os.getcwd()
    )

    # Simulate health metrics
    state_manager.system_awareness_state.update_health_metrics({
        'cpu_usage': 45.2,
        'memory_usage': 62.8,
        'disk_usage': 78.3,
        'network_io': 1024.5
    })

    # Simulate task creation
    task_id = state_manager.task_state.create_task({
        'title': 'Review database indexes',
        'priority': 'medium',
        'assignee': 'pragmatist'
    }, discussion_id)

    # Get dashboard
    dashboard = state_manager.get_unified_dashboard()
    print("Unified Dashboard:")
    print(json.dumps(dashboard, indent=2))

    # Save state
    state_manager.save_state()
    print("\nState saved to file")