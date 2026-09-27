from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import json

class TaskScheduler:
    def __init__(self, schedule_path: str = ".mp/theteam/task-schedule.json"):
        self.path = Path(schedule_path)
        self._schedule_data = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            with open(self.path, 'r') as f:
                return json.load(f)
        return {"scheduled_tasks": {}, "last_run": {}}

    def reload(self):
        """Re-read schedule from disk, overwriting in-memory state."""
        self._schedule_data = self._load()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            json.dump(self._schedule_data, f, indent=2)

    def schedule(self, task_id: str, interval_minutes: int, start_delay_minutes: int = 0):
        next_run = datetime.now(timezone.utc) + timedelta(minutes=start_delay_minutes)
        self._schedule_data["scheduled_tasks"][task_id] = {
            "interval_minutes": interval_minutes,
            "next_run": next_run.isoformat(),
            "start_delay_minutes": start_delay_minutes
        }
        self._save()

    def get_next_run(self, task_id: str) -> Optional[str]:
        return self._schedule_data["scheduled_tasks"].get(task_id, {}).get("next_run")

    def check_due_tasks(self) -> List[str]:
        now = datetime.now(timezone.utc)
        due = []
        for task_id, info in self._schedule_data["scheduled_tasks"].items():
            next_run = datetime.fromisoformat(info["next_run"])
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
            if next_run <= now:
                due.append(task_id)
                # Advance next_run to prevent stale recurring execution
                interval = info.get("interval_minutes", 60)
                info["next_run"] = (now + timedelta(minutes=interval)).isoformat()
        if due:
            self._save()
        return due