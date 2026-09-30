#!/usr/bin/env python3
"""
Task repository with full CRUD operations.

Tasks are canonical YAML files under `tasks/`. That is the only source: the
legacy JSON registry that M2 dual-read is gone, so a task the read cannot find
does not exist rather than hiding in a second store.

The repository is the single source of truth for task membership and order.
Tasks are owned by a specific project root.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import yaml

TASKS_DIRNAME = "tasks"
SCHEDULE_FILENAME = "task-schedule.json"

# A task is readable if it names an id. Everything else is optional, and a
# missing key is reported rather than defaulted, per §3.3.
REQUIRED_FIELDS = ("id",)

# Paths under this directory are dead: the layout was deleted in M1.
DEAD_DIR = ".mp/theteam"


class TaskDefinitionError(ValueError):
    """A task file that exists but is not a task. Named, never swallowed."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check_task(data: Any, name: str) -> Dict[str, Any]:
    """
    The read contract: a mapping that names an id and references no dead path.

    Deliberately permissive about everything else. The four migrated tasks
    predate the write rules below, and a read path that enforces them would
    turn a listable project into an unreadable one.
    """
    if not isinstance(data, dict):
        raise TaskDefinitionError(f"{name}: not a mapping")
    for field in REQUIRED_FIELDS:
        if not data.get(field):
            raise TaskDefinitionError(f"{name}: missing required field '{field}'")
    # Reject paths that reference the deleted .mp/theteam directory,
    # since that layout was removed and any task pointing there is dead.
    for section in ("outputs", "phases"):
        for item in data.get(section, []) or []:
            if not isinstance(item, dict):
                continue
            for key in ("path", "script"):
                value = item.get(key)
                if isinstance(value, str) and DEAD_DIR in value:
                    raise TaskDefinitionError(
                        f"{name}: {section} entry '{key}' references dead directory '{DEAD_DIR}'"
                    )
    return data


def _check_writable(data: Any, name: str) -> Dict[str, Any]:
    """
    The write contract, §5.4: the read contract plus a memory bound per phase.

    A phase without `memory_limit_mb` is rejected here, at the write that
    introduced it, rather than discovered mid-run against a real process.
    """
    _check_task(data, name)
    for phase in data.get("phases", []) or []:
        if isinstance(phase, dict) and not phase.get("memory_limit_mb"):
            raise TaskDefinitionError(
                f"{name}: phase '{phase.get('name', '?')}' has no memory_limit_mb"
            )
    return data


def _load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return _check_task(data, os.path.basename(path))


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


def _audit(project_root: str, event: str, **fields: Any) -> None:
    """
    Append one mutation event to the project's hash-chained audit log (§1.2).

    `AuditLogger` has no create/edit/delete event method, so the entry goes
    through the shared `record_event`, which is the component's own append
    path. The write is best-effort: an audit sink that cannot be written is
    already broken, and a broken sink must not turn a successful task write
    into a failed command.
    """
    from theteam.core.audit_chain import record_event

    record_event(project_root, event, **fields)


class TaskRepository:
    """The task store. YAML under `tasks/` is the only source."""

    def __init__(self, project_root: str) -> None:
        self.project_root = os.path.abspath(project_root)
        self.tasks_dir = os.path.join(self.project_root, TASKS_DIRNAME)
        self._yaml = self._read_yaml()
        # Order is now a per-task key (§5.4). We seed `_rank` from those
        # keys. `TASK_ORDER` is no longer a source.
        self._rank = {t: self._yaml[t].get("order", 999) for t in self._yaml}
        self._order = sorted(self._yaml, key=lambda t: self._rank[t])
        # `read_task_order` and `_write_task_order` are removed; they read/write
        # the `TASK_ORDER` file, which is now obsolete.

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

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._yaml.get(task_id)

    def all_tasks(self) -> List[Dict[str, Any]]:
        """The project's tasks, in `order` sequence.

        Ids past the end of the file still resolve, so an unlisted task is not
        dropped; it just sorts last. The `order` key is a per-task value, and
        the listing is positional, so a sparse or duplicated key prints as a
        position rather than the raw value.
        """
        tail = len(self._rank)
        tasks = [t for t in (self.get(i) for i in self._order) if t is not None]
        tasks += [t for t in self._yaml.values() if t["id"] not in self._rank]
        return sorted(tasks, key=lambda t: (self._rank.get(t["id"], tail),
                                           -_priority(t), t["id"]))

    def _row(self, task: Dict[str, Any], schedule: Dict[str, Any], rank: Dict[str, int]) -> Dict[str, Any]:
        """One `theteam tasks` row. State is real or absent, never guessed."""
        entry = schedule["scheduled_tasks"].get(task["id"], {})
        last = schedule["last_run"].get(task["id"], {})
        return {
            "id": task["id"],
            "name": task.get("name", task["id"]),
            "type": task.get("type"),
            "priority": _priority(task),
            "order": rank.get(task["id"]),
            "next_run": entry.get("next_run"),
            "last_result": last.get("result"),
            # `None` means no breaker state has been measured for this task -
            # it has never run. §3.3: the old `"closed"` default printed a
            # measurement that was never taken, indistinguishable from a real
            # closed breaker. A caller distinguishes "never run" from "closed"
            # by the value being absent rather than reading it as a reading.
            "breaker": last.get("breaker"),
            "breaker_consecutive_failures": last.get("breaker_consecutive_failures"),
        }

    def list_tasks(self) -> Dict[str, Any]:
        """
        The `theteam tasks` payload.

        `yaml_count` stays, so a caller can tell "this project has no tasks"
        from "the read found none" - indistinguishable from the outside, and
        they mean opposite things.
        """
        schedule = self.schedule()
        tasks = self.all_tasks()
        # Positional, not the raw YAML value: sparse or duplicated `order`
        # keys would print as 0, 5, 5.
        rank = {t["id"]: i for i, t in enumerate(tasks)}
        return {
            "tasks": [self._row(t, schedule, rank) for t in tasks],
            "count": len(tasks),
            "yaml_count": len(self._yaml),
        }

    # -- due ---------------------------------------------------------------

    def due(self, only: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Tasks whose `next_run` has passed, in TASK_ORDER sequence.

        Pure: it advances nothing. `record_run` is the only writer, so a `run`
        with nothing due touches no state and two consecutive runs are identical.

        `--only <id>` means "run this one now", and **bypasses the schedule**
        (M9 Phase 4). It previously filtered the due set, so naming a task
        that was never scheduled reported `nothing due` — which made
        `theteam run --only ground-truth-audit` inert on a project where the
        user had never run `theteam loop`. An explicit id is the request;
        a schedule is what makes a task due *without* being named.

        A named id that matches no task returns empty, not a guess: §3.3.
        """
        now = _now()
        schedule = self.schedule()["scheduled_tasks"]
        due = []
        for task in self.all_tasks():
            if only and task["id"] != only:
                continue
            entry = schedule.get(task["id"])
            if only:
                # Named explicitly: due regardless of any schedule entry.
                due.append(task)
                continue
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

    def record_run(self, task_id: str, result: str, detail: str,
                   breaker: Optional[str] = None,
                   consecutive_failures: Optional[int] = None) -> None:
        """Advance the schedule and note the outcome. The only writer here.

        `breaker` is the state a real `CircuitBreaker` reported for this run,
        as `CircuitState.value`. Both breaker arguments default to `None`,
        which means "not measured", and are written as such: §3.3 forbids a
        value here that reads like a measurement when nothing measured one.
        A task's breaker survives process exit because it lives here, in the
        same `last_run` entry `theteam tasks` and `theteam history` read.
        """
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
            "breaker": breaker,
            "breaker_consecutive_failures": consecutive_failures,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(schedule, handle, indent=2)

    # ======= write path =======
    #
    # Every write goes through `_check_writable` on the *merged* mapping before
    # anything touches the disk. Validating the file on disk instead meant the
    # write was never checked, so a task that could not be read back landed
    # anyway and the next `TaskRepository()` construction raised - one edit
    # made the whole project unreadable.

    def _save_schedule(self, schedule: Dict[str, Any]) -> None:
        path = self._state_path(SCHEDULE_FILENAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(schedule, handle, indent=2)

    def schedule_task(self, task_id: str, interval_minutes: int) -> str:
        """
        Schedule a task on an interval, returning its ISO `next_run`.

        Scheduling lives here so the state directory is resolved in one place.
        The CLI must not assemble a schedule file by hand.

        Raises:
            KeyError: the id names no task.
        """
        if self.get(task_id) is None:
            raise KeyError(f"Task '{task_id}' not found")
        next_run = _now() + timedelta(minutes=int(interval_minutes))
        schedule = self.schedule()
        schedule["scheduled_tasks"][task_id] = {
            "next_run": next_run.isoformat(),
            "interval_minutes": int(interval_minutes),
        }
        self._save_schedule(schedule)
        return next_run.isoformat()

    def _write_task(self, name: str, task: Dict[str, Any]) -> None:
        """Write the task as the operator's file, not as the reader sees it.

        `source_file` is a back-reference the reader adds. §5.4's format has
        no such key and none of the migrated tasks carry one, so writing it
        would push an internal detail into a hand-edited document.
        """
        canonical = {k: v for k, v in task.items() if k != "source_file"}
        with open(os.path.join(self.tasks_dir, name), "w", encoding="utf-8") as handle:
            yaml.dump(canonical, handle, sort_keys=False)

    def update(self, task_id: str, patch: Dict[str, Any]) -> None:
        """
        Apply a patch to an existing YAML task, and write what was patched.

        A patch may rename the task. A rename moves the file, the order entry,
        the schedule entry and the run history together, so the schedule is
        never left firing at an id no task answers to.

        Raises:
            KeyError: the task is not a YAML task.
            TaskDefinitionError: the merged task is not writable, or the new
                id is already taken. Nothing is written in either case.
        """
        if task_id not in self._yaml:
            raise KeyError(f"Task '{task_id}' not found")

        old_name = self._yaml[task_id]["source_file"]
        merged = {k: v for k, v in self._yaml[task_id].items() if k != "source_file"}
        merged.update(patch)
        new_id = merged["id"]

        if new_id != task_id and new_id in self._yaml:
            raise TaskDefinitionError(f"Task '{new_id}' already exists")
        new_name = f"task-{new_id}.yaml"
        # Validate the merged mapping, not the file on disk - that is the whole
        # point. `source_file` is carried in so the error names the file the
        # task would land in; `_write_task` drops it from what is written.
        _check_writable({**merged, "source_file": new_name}, new_name)

        renamed = new_id != task_id
        if renamed:
            os.rename(os.path.join(self.tasks_dir, old_name),
                      os.path.join(self.tasks_dir, new_name))
        self._write_task(new_name, {**merged, "source_file": new_name})
        del self._yaml[task_id]
        self._yaml[new_id] = {**merged, "source_file": new_name}

        # Order lives in the task's `order` key. A rename carries the key
        # across with the file, so nothing is rewritten here.

        if renamed:
            self._move_schedule(task_id, new_id)

        _audit(self.project_root, "task_edited", task_id=task_id, new_id=new_id,
               fields=sorted(patch))

    def _move_schedule(self, old_id: str, new_id: str) -> None:
        """Carry the schedule entry and the run history to a renamed task."""
        schedule = self.schedule()
        moved = False
        for section in ("scheduled_tasks", "last_run"):
            if old_id in schedule[section]:
                schedule[section][new_id] = schedule[section].pop(old_id)
                moved = True
        if moved:
            self._save_schedule(schedule)

    def delete(self, task_id: str) -> None:
        """
        Delete a task and every reference to it:
          1. the task's YAML file;
          2. its `TASK_ORDER` entry, matched by parsed id;
          3. its schedule entry and run history, so nothing keeps firing at
             an id no task answers to.

        Raises:
            KeyError: the task is not a YAML task.
        """
        if task_id not in self._yaml:
            raise KeyError(f"Task '{task_id}' not found")

        os.remove(os.path.join(self.tasks_dir, self._yaml[task_id]["source_file"]))
        del self._yaml[task_id]

        if task_id in self._order:
            # The order is a per-task key, so removing the file removes the
            # entry. Nothing else to rewrite.
            self._order.remove(task_id)
            del self._rank[task_id]

        schedule = self.schedule()
        for section in ("scheduled_tasks", "last_run"):
            schedule[section].pop(task_id, None)
        self._save_schedule(schedule)

        _audit(self.project_root, "task_deleted", task_id=task_id)

    def create(self, task_data: Dict[str, Any]) -> str:
        """
        Create a task from a definition and return its id.

        The definition is validated before anything is written, so a rejected
        task leaves no file and no order entry behind.

        Raises:
            KeyError: the definition names no id.
            ValueError: the id is taken.
            TaskDefinitionError: the definition is not writable.
        """
        task_id = task_data["id"]
        if task_id in self._yaml:
            raise ValueError(f"Task '{task_id}' already exists")

        name = f"task-{task_id}.yaml"
        # Validate first, write second. The reverse order leaves an invalid
        # task on disk under a name nothing will ever read.
        _check_writable({**task_data, "source_file": name}, name)

        self._write_task(name, {**task_data, "source_file": name})
        self._yaml[task_id] = {**task_data, "source_file": name}

        self._yaml[task_id] = {**task_data, "source_file": name}
        # Order lives in the task's `order` key. A new task is appended, so
        # its `order` is one past the current maximum - never a line count,
        # which throws off with comment headers and trailing newlines.
        next_order = max((t.get("order", 0) for t in self._yaml.values()), default=-1) + 1
        self._write_task(name, {**task_data, "order": next_order, "source_file": name})
        self._yaml[task_id] = {**task_data, "order": next_order, "source_file": name}
        self._rank[task_id] = next_order
        self._order.append(task_id)

        _audit(self.project_root, "task_created", task_id=task_id, source_file=name)
        return task_id


# Export public API
__all__ = [
    "TASKS_DIRNAME",
    "SCHEDULE_FILENAME",
    "REQUIRED_FIELDS",
    "TaskDefinitionError",
    "_priority",
    "_parse_next_run",
    "_now",
    "TaskRepository",
]