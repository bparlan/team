#!/usr/bin/env python3
"""
Failure handling system for theteam skill.

Classifies failures, prompts users for clarification (HITL),
and handles user actions for stuck tasks.
"""

import os
import sys
import json
from datetime import datetime, timezone

class FailureHandler:
    """Handles task failures with HITL (Human-In-The-Loop) prompts."""
    
    def __init__(self, project_root=None):
        if project_root is None:
            project_root = os.getcwd()
        self.project_root = project_root
        self.failure_log = os.path.join(project_root, ".loop-log", "failures.json")
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        """Ensure failure log directory exists."""
        os.makedirs(os.path.dirname(self.failure_log), exist_ok=True)
    
    def classify_failure(self, error, task=None):
        """Classify a failure into a category."""
        error_lower = str(error).lower()
        
        if "timeout" in error_lower or "time" in error_lower:
            return "timeout"
        elif "permission" in error_lower or "access" in error_lower:
            return "permission"
        elif "not found" in error_lower or "missing" in error_lower:
            return "missing_dependency"
        elif "network" in error_lower or "connection" in error_lower:
            return "network"
        elif "syntax" in error_lower or "parse" in error_lower:
            return "syntax_error"
        elif "validation" in error_lower or "invalid" in error_lower:
            return "validation"
        else:
            return "unknown"
    
    def prompt_user(self, task, error, failure_type):
        """Prompt user for action on a failed task (HITL)."""
        print("\n" + "="*60)
        print("TASK FAILURE - Human Intervention Required")
        print("="*60)
        print(f"Task: {task.get('name', 'unknown')}")
        print(f"Type: {task.get('type', 'unknown')}")
        print(f"Priority: {task.get('priority', 'unknown')}")
        print(f"Failure Type: {failure_type}")
        print(f"Error: {error}")
        print("-"*60)
        print("Options:")
        print("  1. Retry - Retry the task")
        print("  2. Skip - Skip this task and continue")
        print("  3. Stop - Stop the loop entirely")
        print("  4. Fix - User fixes the issue, then retry")
        print("="*60)
        
        # In production, this would use the ask tool
        # For now, return default action
        return self._get_user_choice()
    
    def _get_user_choice(self):
        """Get user choice (simulated for now)."""
        # In production, this would use the ask tool
        # For now, default to skip
        return "skip"
    
    def handle_failure(self, task, error, failure_type=None):
        """Handle a task failure with appropriate action."""
        if failure_type is None:
            failure_type = self.classify_failure(error, task)
        
        # Log the failure
        self._log_failure(task, error, failure_type)
        
        # Determine action based on task's failure handling setting
        failure_handling = task.get("failure_handling", "ask")
        
        if failure_handling == "skip":
            action = "skip"
        elif failure_handling == "retry":
            action = "retry"
        elif failure_handling == "stop":
            action = "stop"
        else:  # ask
            action = self.prompt_user(task, error, failure_type)
        
        return action
    
    def _log_failure(self, task, error, failure_type):
        """Log a failure to the failure log."""
        failure_entry = {
            "task": task.get("name", "unknown"),
            "error": str(error),
            "failure_type": failure_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "pending"
        }
        
        # Load existing failures
        failures = []
        if os.path.exists(self.failure_log):
            try:
                with open(self.failure_log, 'r') as f:
                    failures = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        # Add new failure
        failures.append(failure_entry)
        
        # Save failures
        with open(self.failure_log, 'w') as f:
            json.dump(failures, f, indent=2)
    
    def update_failure_action(self, task_name, action):
        """Update the action for a logged failure."""
        if not os.path.exists(self.failure_log):
            return
        
        try:
            with open(self.failure_log, 'r') as f:
                failures = json.load(f)
            
            for failure in failures:
                if failure["task"] == task_name and failure["action"] == "pending":
                    failure["action"] = action
                    failure["resolved_at"] = datetime.now(timezone.utc).isoformat()
            
            with open(self.failure_log, 'w') as f:
                json.dump(failures, f, indent=2)
        except (json.JSONDecodeError, IOError):
            pass
    
    def get_failure_stats(self):
        """Get failure statistics."""
        if not os.path.exists(self.failure_log):
            return {"total": 0, "by_type": {}}
        
        try:
            with open(self.failure_log, 'r') as f:
                failures = json.load(f)
            
            stats = {
                "total": len(failures),
                "by_type": {},
                "by_action": {}
            }
            
            for failure in failures:
                ftype = failure.get("failure_type", "unknown")
                action = failure.get("action", "pending")
                
                stats["by_type"][ftype] = stats["by_type"].get(ftype, 0) + 1
                stats["by_action"][action] = stats["by_action"].get(action, 0) + 1
            
            return stats
        except (json.JSONDecodeError, IOError):
            return {"total": 0, "by_type": {}}

def main():
    """Main entry point for failure handler."""
    handler = FailureHandler()
    
    if len(sys.argv) < 2:
        print("Usage: failure_handler.py <command> [args]")
        print("Commands: classify, stats, log")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "classify":
        if len(sys.argv) < 3:
            print("Usage: failure_handler.py classify <error>")
            sys.exit(1)
        error = sys.argv[2]
        ftype = handler.classify_failure(error)
        print(ftype)
    elif command == "stats":
        stats = handler.get_failure_stats()
        print(json.dumps(stats, indent=2))
    elif command == "log":
        if len(sys.argv) < 4:
            print("Usage: failure_handler.py log <task> <error>")
            sys.exit(1)
        task_name = sys.argv[2]
        error = sys.argv[3]
        task = {"name": task_name}
        action = handler.handle_failure(task, error)
        print(f"Action: {action}")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()