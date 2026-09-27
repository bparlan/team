#!/usr/bin/env python3
"""
Task Stack Daemon - Continuous Loop Runner

Runs the task stack loop in the background, executing due tasks
at their scheduled intervals. Writes status to a JSON file for
agents to read.

Usage:
  python3 theteam/subskills/task_stack/daemon.py start
  python3 theteam/subskills/task_stack/daemon.py stop
  python3 theteam/subskills/task_stack/daemon.py status
"""

import sys
import os
import json
import time
import signal
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
PID_FILE = PROJECT_ROOT / ".mp" / "theteam" / "task-stack.pid"
STATUS_FILE = PROJECT_ROOT / ".mp" / "theteam" / "task-stack-daemon.json"


def get_orchestrator():
    from .orchestrator import TaskStackOrchestrator
    return TaskStackOrchestrator(str(PROJECT_ROOT))


def write_status(status: dict):
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=2)


def is_running():
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError):
        return False


def start():
    if is_running():
        print("Daemon already running")
        return False

    pid = os.fork()
    if pid > 0:
        time.sleep(0.5)
        if is_running():
            print(f"Daemon started (PID: {pid})")
            return True
        else:
            print("Daemon failed to start")
            return False

    os.setsid()
    os.umask(0)

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    orchestrator = get_orchestrator()

    write_status({
        "running": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_check": None,
        "tasks_executed": 0
    })

    while True:
        try:
            orchestrator.scheduler.reload()  # re-read schedule from disk
            due_tasks = orchestrator.scheduler.check_due_tasks()

            if due_tasks:
                for task_id in due_tasks:
                    result = orchestrator.execute_task(task_id)
                    orchestrator.executor.log_execution(result)

                    info = orchestrator.scheduler._schedule_data["scheduled_tasks"][task_id]
                    interval = info["interval_minutes"]
                    next_run = datetime.now(timezone.utc) + timedelta(minutes=interval)
                    info["next_run"] = next_run.isoformat()
                    orchestrator.scheduler._save()

                status = {
                    "running": True,
                    "last_check": datetime.now(timezone.utc).isoformat(),
                    "tasks_executed": len(due_tasks),
                    "next_runs": {
                        task_id: info["next_run"]
                        for task_id, info in orchestrator.scheduler._schedule_data["scheduled_tasks"].items()
                    }
                }
                write_status(status)

            time.sleep(60)

        except Exception as e:
            write_status({
                "running": True,
                "error": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            })
            time.sleep(60)


def stop():
    if not is_running():
        print("Daemon not running")
        return False

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        write_status({"running": False, "stopped_at": datetime.now(timezone.utc).isoformat()})
        print(f"Daemon stopped (PID: {pid})")
        return True
    except Exception as e:
        print(f"Error stopping daemon: {e}")
        return False


def status():
    if not is_running():
        print("Daemon not running")
        if STATUS_FILE.exists():
            with open(STATUS_FILE, 'r') as f:
                print(json.dumps(json.load(f), indent=2))
        return False

    if STATUS_FILE.exists():
        with open(STATUS_FILE, 'r') as f:
            print(json.dumps(json.load(f), indent=2))
    else:
        print(f"Daemon running (PID: {PID_FILE.read_text().strip()})")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "status":
        status()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)