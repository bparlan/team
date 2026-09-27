#!/usr/bin/env python3
"""
Task Stack Orchestrator

Unified entry point for task stack operations.
"""

import sys
import os
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional


from .registry import TaskRegistry
from .scheduler import TaskScheduler
from .stack_manager import TaskStackManager
from .executor import TaskExecutor
from .converter import ConversationConverter


class TaskStackOrchestrator:
    def __init__(self, project_root: str = None):
        if project_root is None:
            project_root = os.getcwd()
        from theteam.state import StateStore

        self.project_root = Path(project_root)
        state = StateStore(str(self.project_root))
        self.registry = TaskRegistry(str(state.task_registry))
        self.scheduler = TaskScheduler(str(state.task_schedule))
        self.stack = TaskStackManager(str(state.task_stack))
        self.executor = TaskExecutor(str(self.project_root))
        self.converter = ConversationConverter(str(self.project_root))

    def register_task(self, task_path: str) -> bool:
        with open(task_path, 'r') as f:
            task_def = yaml.safe_load(f)
        return self.registry.register(task_def)

    def execute_task(self, task_id: str) -> Dict:
        task = self.registry.get(task_id)
        if not task:
            return {"success": False, "error": f"Task not found: {task_id}"}
        result = self.executor.execute_task(task)
        self.executor.log_execution(result)
        return result

    def loop_task(self, task_id: str, interval_minutes: int) -> Dict:
        task = self.registry.get(task_id)
        if not task:
            return {"success": False, "error": f"Task not found: {task_id}"}
        self.scheduler.schedule(task_id, interval_minutes)
        self.stack.push(task_id)
        return {
            "success": True,
            "task_id": task_id,
            "interval_minutes": interval_minutes,
            "next_run": self.scheduler.get_next_run(task_id)
        }

    def run_due_tasks(self) -> List[Dict]:
        due_task_ids = self.scheduler.check_due_tasks()
        results = []
        for task_id in due_task_ids:
            result = self.execute_task(task_id)
            results.append(result)
            info = self.scheduler._schedule_data["scheduled_tasks"][task_id]
            interval = info["interval_minutes"]
            next_run = datetime.now(timezone.utc) + timedelta(minutes=interval)
            info["next_run"] = next_run.isoformat()
            self.scheduler._save()
        return results

    def convert_conversation(self, lines: int = 50) -> Dict:
        task = self.converter.convert_recent_chat(lines)
        self.registry.register(task)
        return task

    def convert_request(self, request: str) -> Dict:
        task = self.converter.convert_user_request(request)
        self.registry.register(task)
        return task

    def list_tasks(self) -> List[Dict]:
        return self.registry.list_all()

    def get_scheduled_tasks(self) -> Dict:
        return self.scheduler._schedule_data["scheduled_tasks"]

    def get_status(self) -> Dict:
        return {
            "registered_tasks": len(self.registry.list_all()),
            "scheduled_tasks": len(self.scheduler._schedule_data["scheduled_tasks"]),
            "stack_size": len(self.stack.get_stack()),
            "next_runs": {
                task_id: info["next_run"]
                for task_id, info in self.scheduler._schedule_data["scheduled_tasks"].items()
            }
        }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    orchestrator = TaskStackOrchestrator()
    cmd = sys.argv[1]

    if cmd == "register":
        if len(sys.argv) < 3:
            print("Usage: register <task.yaml>")
            sys.exit(1)
        success = orchestrator.register_task(sys.argv[2])
        print(json.dumps({"success": success}, indent=2))

    elif cmd == "execute":
        if len(sys.argv) < 3:
            print("Usage: execute <task_id>")
            sys.exit(1)
        result = orchestrator.execute_task(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "loop":
        if len(sys.argv) < 4:
            print("Usage: loop <task_id> <interval_minutes>")
            sys.exit(1)
        interval = int(sys.argv[3])
        result = orchestrator.loop_task(sys.argv[2], interval)
        print(json.dumps(result, indent=2))

    elif cmd == "run-due":
        results = orchestrator.run_due_tasks()
        print(json.dumps({"ran_tasks": len(results), "results": results}, indent=2))

    elif cmd == "convert-conversation":
        lines = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        task = orchestrator.convert_conversation(lines)
        print(json.dumps(task, indent=2))

    elif cmd == "convert-request":
        if len(sys.argv) < 3:
            print("Usage: convert-request '<request>'")
            sys.exit(1)
        request = " ".join(sys.argv[2:])
        task = orchestrator.convert_request(request)
        print(json.dumps(task, indent=2))

    elif cmd == "list":
        tasks = orchestrator.list_tasks()
        print(json.dumps({"tasks": tasks}, indent=2))

    elif cmd == "status":
        status = orchestrator.get_status()
        print(json.dumps(status, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()