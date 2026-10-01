#!/usr/bin/env python3
"""
Loop state manager for theteam skill.

Manages persistent state for task loop execution including
active tasks, completed tasks, failed tasks, and execution history.
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class LoopState:
    """Manages loop execution state."""
    
    def __init__(self, state_file=None):
        if state_file is None:
            project_root = os.getcwd()
            state_file = os.path.join(project_root, ".loop-state.json")
        self.state_file = state_file
        self.state = self._load_state()
    
    def _load_state(self):
        """Load state from file or create default."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return self._default_state()
    
    def _default_state(self):
        """Create default state."""
        return {
            "version": 1,
            "project": "team-skill",
            "loop_active": False,
            "current_task_index": 0,
            "completed_tasks": [],
            "failed_tasks": [],
            "blocked_tasks": [],
            "last_execution": None,
            "task_archive": "tasks",
            "total_tasks": 0,
            "next_activation": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            # Phase 2: Persistent circuit breaker state
            "circuit_breaker": {
                "state": "closed",  # closed, open, half_open
                "failure_count": 0,
                "failure_threshold": 3,
                "timeout_seconds": 300,
                "last_failure_time": None,
                "last_success_time": None
            },
            # Phase 2: Health score persistence
            "health_score": {
                "overall_score": 0.0,
                "grade": "F",
                "timestamp": None,
                "last_run_success": False,
                "consecutive_failures": 0
            },
            # Phase 2: Monotonic progress tracking
            "progress": {
                "total_iterations": 0,
                "last_iteration_time": None,
                "stalled_since": None,
                "recovery_count": 0
            }
        }
    
    def save(self):
        """Persist state to file."""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def is_active(self):
        """Check if loop is active."""
        return self.state.get("loop_active", False)
    
    def activate(self):
        """Activate the loop."""
        self.state["loop_active"] = True
        self.state["next_activation"] = None
        self.save()
    
    def deactivate(self):
        """Deactivate the loop."""
        self.state["loop_active"] = False
        self.save()
    
    def reset(self):
        """Reset loop state."""
        self.state = self._default_state()
        self.save()
    
    def get_current_task_index(self):
        """Get current task index."""
        return self.state.get("current_task_index", 0)
    
    def set_current_task_index(self, index):
        """Set current task index."""
        self.state["current_task_index"] = index
        self.save()
    
    def add_completed_task(self, task_name, result, output=""):
        """Add a completed task."""
        self.state["completed_tasks"].append({
            "task": task_name,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
            "output": output
        })
        self.state["current_task_index"] += 1
        self.state["last_execution"] = datetime.now(timezone.utc).isoformat()
        self.save()
    
    def add_failed_task(self, task_name, error, output=""):
        """Add a failed task."""
        self.state["failed_tasks"].append({
            "task": task_name,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "error": error,
            "output": output
        })
        self.state["last_execution"] = datetime.now(timezone.utc).isoformat()
        self.save()
    
    def add_blocked_task(self, task_name, reason):
        """Add a blocked task."""
        self.state["blocked_tasks"].append({
            "task": task_name,
            "blocked_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason
        })
        self.save()
    
    def to_dict(self):
        """Get state as dictionary."""
        return self.state.copy()
    
    # Phase 2: Circuit Breaker Management
    def get_circuit_breaker_state(self):
        """Get current circuit breaker state."""
        return self.state.get("circuit_breaker", {})
    
    def update_circuit_breaker(self, state=None, failure_count=None, last_failure_time=None, last_success_time=None):
        """Update circuit breaker state."""
        cb = self.state.get("circuit_breaker", {})
        if state is not None:
            cb["state"] = state
        if failure_count is not None:
            cb["failure_count"] = failure_count
        if last_failure_time is not None:
            cb["last_failure_time"] = last_failure_time
        if last_success_time is not None:
            cb["last_success_time"] = last_success_time
        self.state["circuit_breaker"] = cb
        self.save()
    
    # Phase 2: Health Score Management
    def get_health_score(self):
        """Get stored health score."""
        return self.state.get("health_score", {})
    
    def update_health_score(self, score, grade, timestamp, success):
        """Update stored health score."""
        hs = self.state.get("health_score", {})
        hs["overall_score"] = score
        hs["grade"] = grade
        hs["timestamp"] = timestamp
        hs["last_run_success"] = success
        if success:
            hs["consecutive_failures"] = 0
    def get_summary(self):
        """Get state summary with health freshness and circuit breaker information."""
        summary = {
            "loop_active": self.state.get("loop_active", False),
            "current_task_index": self.state.get("current_task_index", 0),
            "completed_tasks": len(self.state.get("completed_tasks", [])),
            "failed_tasks": len(self.state.get("failed_tasks", [])),
            "blocked_tasks": len(self.state.get("blocked_tasks", [])),
            "total_tasks": self.state.get("total_tasks", 0),
            "last_execution": self.state.get("last_execution")
        }
        
        # Phase 2: Add circuit breaker state
        cb = self.state.get("circuit_breaker", {})
        summary["circuit_breaker"] = {
            "state": cb.get("state", "closed"),
            "failure_count": cb.get("failure_count", 0),
            "last_failure_time": cb.get("last_failure_time")
        }
        
        # Phase 2: Add health score persistence
        hs = self.state.get("health_score", {})
        summary["health_score"] = {
            "overall_score": hs.get("overall_score", 0.0),
            "grade": hs.get("grade", "F"),
            "timestamp": hs.get("timestamp"),
            "last_run_success": hs.get("last_run_success", False),
            "consecutive_failures": hs.get("consecutive_failures", 0)
        }
        
        # Phase 2: Add progress tracking
        progress = self.state.get("progress", {})
        summary["progress"] = {
            "total_iterations": progress.get("total_iterations", 0),
            "last_iteration_time": progress.get("last_iteration_time"),
            "stalled_since": progress.get("stalled_since"),
            "recovery_count": progress.get("recovery_count", 0)
        }
        
        # Add health score freshness check
        health_file = os.path.join(
            os.path.dirname(self.state_file), ".mp", "theteam", "health-score.json"
        )
        if os.path.exists(health_file):
            try:
                with open(health_file, 'r') as f:
                    health = json.load(f)
                    summary["health_score"]["overall_score"] = health.get("overall_score", 0.0)
                    summary["health_score"]["grade"] = health.get("grade", "F")
                    summary["health_score"]["timestamp"] = health.get("timestamp")
                    
                    # Calculate freshness
                    health_time = datetime.fromisoformat(health.get("timestamp", ""))
                    age_hours = (datetime.now(timezone.utc) - health_time.replace(tzinfo=timezone.utc)).total_seconds() / 3600
                    summary["health_score"]["age_hours"] = round(age_hours, 2)
                    summary["health_score"]["fresh"] = age_hours < 24
            except (json.JSONDecodeError, IOError, ValueError):
                pass
        
        return summary
        self.state["health_score"] = hs
        self.save()
    
    # Phase 2: Progress Tracking
    def get_progress(self):
        """Get progress tracking information."""
        return self.state.get("progress", {})
    
    def update_progress(self, iteration_completed=False, stalled=False):
        """Update progress tracking."""
        progress = self.state.get("progress", {})
        if iteration_completed:
            progress["total_iterations"] = progress.get("total_iterations", 0) + 1
            progress["last_iteration_time"] = datetime.now(timezone.utc).isoformat()
            progress["stalled_since"] = None
        if stalled:
            progress["stalled_since"] = datetime.now(timezone.utc).isoformat()
        self.state["progress"] = progress
        self.save()
    
    def record_recovery(self):
        """Record a recovery event."""
        progress = self.state.get("progress", {})
        progress["recovery_count"] = progress.get("recovery_count", 0) + 1
        self.state["progress"] = progress
        self.save()
    
    def get_completed_count(self):
        """Get count of completed tasks."""
        return len(self.state.get("completed_tasks", []))
    
    def get_failed_count(self):
        """Get count of failed tasks."""
        return len(self.state.get("failed_tasks", []))
    
    def get_total_tasks(self):
        """Get total task count."""
        return self.state.get("total_tasks", 0)
    
    def set_total_tasks(self, count):
        """Set total task count."""
        self.state["total_tasks"] = count
        self.save()
    
    def to_dict(self):
        """Get state as dictionary."""
        return self.state.copy()
    
    def get_summary(self):
        """Get state summary with health freshness information."""
        summary = {
            "loop_active": self.state.get("loop_active", False),
            "current_task_index": self.state.get("current_task_index", 0),
            "completed_tasks": len(self.state.get("completed_tasks", [])),
            "failed_tasks": len(self.state.get("failed_tasks", [])),
            "blocked_tasks": len(self.state.get("blocked_tasks", [])),
            "total_tasks": self.state.get("total_tasks", 0),
            "last_execution": self.state.get("last_execution")
        }
        
        # Add health score freshness check
        health_file = os.path.join(
            os.path.dirname(self.state_file), ".mp", "theteam", "health-score.json"
        )
        if os.path.exists(health_file):
            try:
                with open(health_file, 'r') as f:
                    health = json.load(f)
                    summary["health_score"] = health.get("overall_score", 0.0)
                    summary["health_grade"] = health.get("grade", "F")
                    summary["health_timestamp"] = health.get("timestamp")
                    
                    # Calculate freshness
                    health_time = datetime.fromisoformat(health.get("timestamp", ""))
                    age_hours = (datetime.now(timezone.utc) - health_time.replace(tzinfo=timezone.utc)).total_seconds() / 3600
                    summary["health_age_hours"] = round(age_hours, 2)
                    summary["health_fresh"] = age_hours < 24
            except (json.JSONDecodeError, IOError, ValueError):
                pass
        
        return summary

    # Phase 3: Team Integration
    def add_team_member(self, member_id, name, role):
        """Add a team member to the loop state."""
        if "team_members" not in self.state:
            self.state["team_members"] = {}
        self.state["team_members"][member_id] = {
            "name": name,
            "role": role,
            "last_active": datetime.now(timezone.utc).isoformat(),
            "contributions": 0
        }
        self.save()

    def get_team_members(self):
        """Get all team members."""
        return self.state.get("team_members", {})

    def update_team_member_activity(self, member_id, contribution_type=None):
        """Update team member activity."""
        members = self.state.get("team_members", {})
        if member_id in members:
            members[member_id]["last_active"] = datetime.now(timezone.utc).isoformat()
            if contribution_type:
                members[member_id]["contributions"] += 1
            self.save()

    def add_team_contribution(self, member_id, task_name, result, output=""):
        """Add a team member contribution."""
        if "team_contributions" not in self.state:
            self.state["team_contributions"] = []
        self.state["team_contributions"].append({
            "member_id": member_id,
            "task": task_name,
            "result": result,
            "output": output,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self.update_team_member_activity(member_id, contribution_type=task_name)
        self.save()

    def get_team_collaboration_score(self):
        """Compute team collaboration score based on member activity."""
        members = self.state.get("team_members", {})
        if not members:
            return 0.0
        total_contributions = sum(m["contributions"] for m in members.values())
        active_members = sum(1 for m in members.values()
                           if (datetime.now(timezone.utc) - datetime.fromisoformat(m["last_active"])).total_seconds() < 86400)
        collaboration_score = (active_members / len(members)) * 0.5 + (min(total_contributions / len(members), 1.0) * 0.5)
        return round(collaboration_score, 2)

def main():
    """Main entry point for loop state management."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: loop_state.py <command> [args]")
        print("Commands: status, activate, deactivate, reset")
        sys.exit(1)
    
    command = sys.argv[1]
    state = LoopState()
    
    if command == "status":
        summary = state.get_summary()
        print(json.dumps(summary, indent=2))
    elif command == "activate":
        state.activate()
        print("Loop activated")
    elif command == "deactivate":
        state.deactivate()
        print("Loop deactivated")
    elif command == "reset":
        state.reset()
        print("Loop state reset")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
