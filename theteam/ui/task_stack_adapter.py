#!/usr/bin/env python3
"""
TaskStackAdapter - Bridge between TerminalUI and Task Stack System.

Provides UI-compatible data structures while preserving Task Stack integrity.
Single source of truth for task data synchronization.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional


class TaskStackAdapter:
    """Adapter between TerminalUI and TaskStackOrchestrator."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self._orchestrator = None
        self._cache = {}
        self._cache_ttl = 2  # seconds
        self._last_refresh = 0

    @property
    def orchestrator(self):
        """Lazy-load the orchestrator."""
        if self._orchestrator is None:
            from theteam.subskills.task_stack.orchestrator import TaskStackOrchestrator
            self._orchestrator = TaskStackOrchestrator(str(self.project_root))
        return self._orchestrator

    def _refresh_if_needed(self):
        """Refresh cache if TTL expired."""
        now = time.time()
        if now - self._last_refresh > self._cache_ttl:
            self.refresh_immediately()

    def refresh_immediately(self):
        """Force immediate refresh of cached data."""
        try:
            self._cache = {
                "task_stack_status": self._get_task_stack_status(),
                "registered_tasks": self._get_registered_tasks(),
                "scheduled_tasks": self._get_scheduled_tasks(),
                "stack_tasks": self._get_stack_tasks(),
                "daemon_status": self._get_daemon_status(),
            }
            self._last_refresh = time.time()
        except Exception as e:
            # Graceful degradation - return last known state or empty
            if not self._cache:
                self._cache = {
                    "task_stack_status": {"error": str(e)},
                    "registered_tasks": [],
                    "scheduled_tasks": {},
                    "stack_tasks": [],
                    "daemon_status": {"error": str(e)},
                }

    def _get_task_stack_status(self) -> Dict[str, Any]:
        """Get task stack status from orchestrator."""
        try:
            return self.orchestrator.get_status()
        except Exception as e:
            return {"error": str(e), "stack_health": "unknown"}

    def _get_registered_tasks(self) -> List[Dict]:
        """Get list of registered tasks."""
        try:
            return self.orchestrator.list_tasks()
        except Exception as e:
            return [{"error": str(e)}]

    def _get_scheduled_tasks(self) -> Dict:
        """Get scheduled tasks."""
        try:
            return self.orchestrator.get_scheduled_tasks()
        except Exception as e:
            return {"error": str(e)}

    def _get_stack_tasks(self) -> List[Dict]:
        """Get tasks in the stack."""
        try:
            return self.orchestrator.stack.get_stack()
        except Exception as e:
            return [{"error": str(e)}]

    def _get_daemon_status(self) -> Dict[str, Any]:
        """Get daemon status with process validation (deterministic)."""
        from theteam.state import StateStore

        state = StateStore(str(self.project_root))
        daemon_file = state.task_daemon_status
        if daemon_file.exists():
            try:
                with open(daemon_file, 'r') as f:
                    status = json.load(f)
                # Validate PID against a live process using existing infra
                pid_file = state.task_daemon_pid
                if pid_file.exists():
                    try:
                        pid = int(pid_file.read_text().strip())
                        os.kill(pid, 0)
                        status["pid_valid"] = True
                        status["daemon_running"] = True
                    except (ProcessLookupError, ValueError, PermissionError, OSError):
                        status["pid_valid"] = False
                        status["daemon_running"] = False
                else:
                    status["pid_valid"] = False
                    status["daemon_running"] = False
                return status
            except Exception as e:
                return {"error": str(e), "running": False, "daemon_running": False}
        return {"running": False, "daemon_running": False, "error": "daemon status file not found"}

    def get_unified_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data for UI."""
        self._refresh_if_needed()
        return self._cache

    def get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed task information."""
        try:
            task = self.orchestrator.registry.get(task_id)
            if task:
                return {
                    "task_id": task_id,
                    "name": task.get("name", "Unknown"),
                    "type": task.get("type", "unknown"),
                    "priority": task.get("priority", "medium"),
                    "phases": task.get("phases", []),
                    "status": task.get("status", "unknown"),
                }
            return None
        except Exception as e:
            return {"error": str(e)}

    def trigger_task_action(self, action: str, task_id: str, **kwargs) -> Dict[str, Any]:
        """Bridge UI actions to Task Stack operations."""
        try:
            if action == "execute":
                result = self.orchestrator.execute_task(task_id)
                self.refresh_immediately()
                return result
            elif action == "loop":
                interval = kwargs.get("interval_minutes", 30)
                result = self.orchestrator.loop_task(task_id, interval)
                self.refresh_immediately()
                return result
            elif action == "run-due":
                results = self.orchestrator.run_due_tasks()
                self.refresh_immediately()
                return {"ran_tasks": len(results), "results": results}
            elif action == "list":
                return {"tasks": self.orchestrator.list_tasks()}
            elif action == "status":
                return self.orchestrator.get_status()
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_refresh_interval(self, seconds: int):
        """Update cache refresh interval."""
        self._cache_ttl = seconds


if __name__ == "__main__":
    # Quick test
    adapter = TaskStackAdapter(".")
    data = adapter.get_unified_dashboard_data()
    print(json.dumps(data, indent=2))