#!/usr/bin/env python3
"""
theteam.tasks.repository - the one place a task is read from.

Two sources, one reader. YAML under `<project_root>/tasks/` is canonical; the
pre-M2 JSON registry at `.omp/theteam/task-registry.json` is still served, so
an id that lost its YAML file is not silently gone. That fallback is the whole
safety mechanism of the migration, and it is visible in the payload
(`legacy_only`, `legacy_tasks`, `orphaned_schedules`) because an empty result
from a failed read looks exactly like a project with no tasks, and means the
opposite.

Membership is decided by `tasks/TASK_ORDER`, not by whichever source has an
entry. The registry accumulated conversion leftovers with no order position;
letting it vote on membership is how the list drifts from 4 to 8.

    TASK_ORDER names an id + a YAML file has it  -> YAML content
    TASK_ORDER names an id + only the registry  -> registry content (recovery)
    only the registry has it                     -> listed under `legacy_tasks`

Order is TASK_ORDER sequence; an id absent from it sorts last, by priority
descending then id. Deterministic, so `theteam tasks` is reproducible.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import yaml

TASKS_DIRNAME = "tasks"
TASK_ORDER_FILENAME = "TASK_ORDER"
REGISTRY_FILENAME = "task-registry.json"
SCHEDULE_FILENAME = "task-schedule.json"

# A task is readable if it names an id. Everything else is optional, and a
# missing key is reported rather than defaulted, per §3.3.
REQUIRED_FIELDS = ("id",)


class TaskDefinitionError(ValueError):
    """A task file that exists but is not a task. Named, never swallowed."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise TaskDefinitionError(f"{path}: not a mapping")
    for field in REQUIRED_FIELDS:
        if not data.get(field):
            raise TaskDefinitionError(f"{path}: missing required field '{field}'")
    return data


def read_task_order(project_root: str) -> List[str]:
    """Ids in `TASK_ORDER` sequence. Empty when the file is absent."""
    path = os.path.join(project_root, TASKS_DIRNAME, TASK_ORDER_FILENAME)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    # The file is a numbered list, optionally behind a `#` comment header.
    return re.findall(r"^\s*\d+\.\s+(\S+)\s*$", text, re.MULTILINE)


def _priority(task: Dict[str, Any]) -> int:
    """Priority as a number. Non-numeric is reported as unprioritised, not 0-claimed."""
    value = task.get("priority", 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def _parse_next_run(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class TaskRepository:
    """Reads tasks from YAML, falling back to the legacy registry."""

    def __init__(self, project_root: str) -> None:
        self.project_root = os.path.abspath(project_root)
        self.tasks_dir = os.path.join(self.project_root, TASKS_DIRNAME)
        self._order = read_task_order(self.project_root)
        self._rank = {task_id: i for i, task_id in enumerate(self._order)}
        self._yaml = self._read_yaml()
        self._legacy = self._read_legacy()

    # -- sources -----------------------------------------------------------

    def _read_yaml(self) -> Dict[str, Dict[str, Any]]:
        tasks: Dict[str, Dict[str, Any]] = {}
        if not os.path.isdir(self.tasks_dir):
            return tasks
        for name in sorted(os.listdir(self.tasks_dir)):
            # `tasks/` also holds non-tasks (`SECURITY_POLICY.yaml`, and it is
            # not even parseable YAML), so globbing every `*.yaml` here dies on
            # a file that is none of this reader's business. The `task-` prefix
            # is the directory's own convention, not a new one.
            if not (name.startswith("task-") and name.endswith((".yaml", ".yml"))):
                continue
            task = _load_yaml(os.path.join(self.tasks_dir, name))
            task.setdefault("source_file", name)
            tasks[task["id"]] = task
        return tasks

    def _state_path(self, filename: str) -> str:
        # `state.py` owns this resolution; reuse it rather than repeat the env
        # var and default, so a container or a test points both at one scratch dir.
        from theteam.state import state_dir

        return str(state_dir(self.project_root) / filename)

    def _read_legacy(self) -> Dict[str, Any]:
        """Registered tasks from the pre-M2 JSON registry, or `{}`.

        Read directly rather than through `TaskRegistry`: that class is the
        loader M2 replaces, and the CLI must not depend on code it is deleting.
        """
        path = self._state_path(REGISTRY_FILENAME)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle).get("tasks", {})

    def schedule(self) -> Dict[str, Any]:
        path = self._state_path(SCHEDULE_FILENAME)
        if not os.path.exists(path):
            return {"scheduled_tasks": {}, "last_run": {}}
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("scheduled_tasks", {})
        data.setdefault("last_run", {})
        return data

    # -- membership --------------------------------------------------------

    @property
    def yaml_ids(self) -> List[str]:
        return sorted(self._yaml)

    @property
    def legacy_only(self) -> List[str]:
        """Named ids whose YAML file is gone. Empty means the switch is done."""
        return [t for t in self._order if t in self._legacy and t not in self._yaml]

    @property
    def unregistered_tasks(self) -> List[Dict[str, Any]]:
        """Registry entries with no order position. Listed, never executed."""
        extras = {t: v for t, v in self._legacy.items() if t not in self._rank}
        return sorted(extras.values(), key=lambda t: (-_priority(t), t["id"]))

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._yaml.get(task_id) or self._legacy.get(task_id)

    @property
    def missing_tasks(self) -> List[str]:
        """Ids TASK_ORDER names that no source can supply. Reported, never hidden."""
        return [t for t in self._order if self.get(t) is None]

    def all_tasks(self) -> List[Dict[str, Any]]:
        """The project's tasks, in TASK_ORDER sequence.

        Ids past the end of the file still resolve, so an unlisted task is not
        dropped; it just sorts last. An id that resolves to nothing is left out
        and named in `missing_tasks` — dropping it without saying so is the
        quiet-empty-failure this module exists to prevent.
        """
        tail = len(self._rank)
        tasks = [t for t in (self.get(i) for i in self._order) if t is not None]
        tasks += [t for t in self._yaml.values() if t["id"] not in self._rank]
        return sorted(tasks, key=lambda t: (self._rank.get(t["id"], tail),
                                           -_priority(t), t["id"]))

    def _row(self, task: Dict[str, Any], schedule: Dict[str, Any]) -> Dict[str, Any]:
        """One `theteam tasks` row. State is real or absent, never guessed."""
        entry = schedule["scheduled_tasks"].get(task["id"], {})
        last = schedule["last_run"].get(task["id"], {})
        return {
            "id": task["id"],
            "name": task.get("name", task["id"]),
            "type": task.get("type"),
            "priority": _priority(task),
            "order": self._rank.get(task["id"]),
            "next_run": entry.get("next_run"),
            "interval_minutes": entry.get("interval_minutes"),
            "last_result": last.get("result"),
            "breaker": last.get("breaker", "closed"),
        }

    def list_tasks(self) -> Dict[str, Any]:
        """
        The `theteam tasks` payload.

        `yaml_count` and `legacy_only` are the migration reporting itself, so a
        caller can tell "this project has no tasks" from "the read found none",
        which are indistinguishable from the outside and mean opposite things.
        """
        schedule = self.schedule()
        tasks = self.all_tasks()
        return {
            "tasks": [self._row(t, schedule) for t in tasks],
            "count": len(tasks),
            "yaml_count": len(self._yaml),
            "legacy_only": self.legacy_only,
            "legacy_tasks": [t["id"] for t in self.unregistered_tasks],
            "missing_tasks": self.missing_tasks,
        }

    # -- due ---------------------------------------------------------------

    def due(self, only: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Tasks whose `next_run` has passed, in TASK_ORDER sequence.

        Pure: it advances nothing. `record_run` is the only writer, so a `run`
        with nothing due touches no state and two consecutive runs are identical.
        """
        now = _now()
        due = []
        for task in self.all_tasks():
            if only and task["id"] != only:
                continue
            entry = self.schedule()["scheduled_tasks"].get(task["id"])
            if not entry:
                continue
            next_run = _parse_next_run(entry.get("next_run"))
            if next_run is not None and next_run <= now:
                due.append(task)
        return due

    def orphaned_schedules(self) -> List[str]:
        """Scheduled ids that no longer name a task. Reported, never fired."""
        return sorted(
            task_id for task_id in self.schedule()["scheduled_tasks"]
            if self.get(task_id) is None
        )

    def record_run(self, task_id: str, result: str, detail: str) -> None:
        """Advance the schedule and note the outcome. The only writer here."""
        path = self._state_path(SCHEDULE_FILENAME)
        schedule = self.schedule()
        entry = schedule["scheduled_tasks"].get(task_id, {})
        interval = entry.get("interval_minutes")
        if interval:

            entry["next_run"] = (_now() + timedelta(minutes=int(interval))).isoformat()
            schedule["scheduled_tasks"][task_id] = entry
        schedule["last_run"][task_id] = {
            "result": result,
            "detail": detail,
            "at": _now().isoformat(),
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(schedule, handle, indent=2)
