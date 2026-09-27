import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import reflex as rx

from theteam.state import StateStore

_STORE = StateStore(os.environ.get("THETEAM_PROJECT_ROOT") or os.getcwd())
MP_DIR = _STORE.root


def read_json(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def read_log(path: Path, lines: int = 20) -> List[Dict]:
    if not path.exists():
        return []
    result = []
    with open(path) as f:
        for line in f:
            try:
                result.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                pass
    return result[-lines:]


def flatten_tasks(tasks: List[Dict]) -> List[Dict]:
    """Add schedule_text and short_id to each task for Reflex-safe rendering."""
    out = []
    for t in tasks:
        s = t.get("schedule", {})
        interval = s.get("interval_minutes")
        if interval:
            st = f"Every {interval}m"
        else:
            st = s.get("mode", "once")
        out.append({
            "id": t.get("id", "")[:20],
            "name": t.get("name", ""),
            "type": t.get("type", "unknown"),
            "priority": t.get("priority", "medium"),
            "schedule_text": st,
        })
    return out


class DashboardState(rx.State):
    """Central Reflex state that bridges task-stack data to the web UI."""

    # --- Reactive display fields (all pre-processed, no slicing in templates) ---
    tasks: List[Dict] = []
    scheduled_tasks_list: List[Dict] = []
    execution_log: List[Dict] = []

    task_count: int = 0
    scheduled_count: int = 0
    daemon_running_text: str = ""
    daemon_last_check_text: str = ""
    daemon_display: Dict = {}
    root_clutter: int = 0
    critical_folders_ok: bool = True
    connection_ok: bool = True
    loading: bool = False
    error_message: str = ""
    last_refresh: str = ""

    async def load_all(self):
        self.loading = True
        self.error_message = ""
        try:
            tasks_data = read_json(MP_DIR / "task-registry.json").get("tasks", [])
            self.tasks = flatten_tasks(tasks_data)
            self.task_count = len(self.tasks)

            sched = read_json(MP_DIR / "task-schedule.json").get("scheduled_tasks", {})
            self.scheduled_count = len(sched)
            self.scheduled_tasks_list = [
                {"id": tid[:20], "interval": f"Every {info.get('interval_minutes', '?')}m",
                 "next_run": str(info.get("next_run", ""))[:19]}
                for tid, info in sched.items()
            ]

            ds = read_json(MP_DIR / "task-stack-daemon.json")
            self.daemon_running_text = "Running" if ds.get("running") else "Stopped"
            lc = ds.get("last_check", "")
            self.daemon_last_check_text = lc[:19] if lc else "never"
            self.daemon_display = {
                "started": ds.get("started_at", "")[:19],
                "executed": ds.get("tasks_executed", 0),
            }

            ss = read_json(MP_DIR / "structure-summary.json")
            fh = ss.get("folder_health", {})
            self.root_clutter = fh.get("root_clutter", 0)
            self.critical_folders_ok = fh.get("critical_folders_ok", True)

            raw_log = read_log(MP_DIR / "task-execution.log")
            self.execution_log = [
                {**e, "timestamp_short": e.get("timestamp", "")[:19]}
                for e in raw_log
            ]

            self.last_refresh = datetime.now().strftime("%H:%M:%S")
            self.connection_ok = bool(ds) or bool(tasks_data)
        except Exception as e:
            self.error_message = str(e)
            self.connection_ok = False
        finally:
            self.loading = False