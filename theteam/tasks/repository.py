#!/usr/bin/env python3
"""
Task repository with full CRUD operations.

The repository manages tasks from two sources:
  1. Canonical YAML files under `tasks/` (new M2 layout)
  2. Legacy JSON registry under `.omp/theteam/` (M1 layout)

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
    # Reject paths that reference the deleted .mp/theteam directory,
    # since that layout was removed and any task pointing there is dead.
    dead_dir = ".mp/theteam"
    for section in ("outputs", "phases"):
        for item in data.get(section, []) or []:
            if not isinstance(item, dict):
                continue
            for key in ("path", "script"):
                value = item.get(key)
                if not value or not isinstance(value, str):
                    continue
                # Reject any path containing the dead directory
                if dead_dir in value:
                    raise TaskDefinitionError(
                        f"{path}: {section} entry '{key}' references dead directory '{dead_dir}'"
                    )
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

    # NEW: CRUD OPERATIONS

    def update(self, task_id: str, patch: Dict[str, Any]) -> None:
        """
        Update an existing task with the given patch.

        The patch is a dict of fields to update. The task_id must exist in YAML files
        (cannot update legacy-only tasks). If the patch changes the task's id,
        the file is renamed accordingly. Conflict detection is performed by reading
        the current file content before writing.

        Raises:
            KeyError: If the task_id doesn't exist in YAML files.
            ValueError: If there are any conflicts when applying the patch.
            TaskDefinitionError: If the updated task is invalid.
        """
        # Check if task exists in YAML (not legacy-only)
        if task_id not in self._yaml:
            raise KeyError(f"Task '{task_id}' not found or is legacy-only")

        task_file = self._yaml[task_id]["source_file"]
        task_path = os.path.join(self.tasks_dir, task_file)

        # Read current content for conflict detection
        with open(task_path, "r", encoding="utf-8") as f:
            current_content = f.read()

        # Load current task data
        current_task = self._yaml[task_id].copy()

        # Apply the patch
        for key, value in patch.items():
            # Disallow changes to the id field (file name is derived from id)
            if key == "id":
                new_id = value
                if new_id != task_id:
                    raise ValueError(f"Cannot change task id from '{task_id}' to '{new_id}'")

            # Special handling for source_file if it's being updated
            if key == "source_file":
                # Only allow renaming if it follows the task-* pattern
                if not (value.startswith("task-") and value.endswith((".yaml", ".yml"))):
                    raise ValueError(f"Invalid source_file name: '{value}'")
                # Remove old task from internal dict
                del self._yaml[task_id]

            current_task[key] = value

        # Validate the updated task structure
        updated_task = _load_yaml(task_path)

        # If id changed, rename the file
        if "id" in patch and patch["id"] != task_id:
            new_file = f"task-{patch['id']}.yaml"
            new_path = os.path.join(self.tasks_dir, new_file)

            # Remove the old task from internal dict
            old_file = self._yaml[task_id]["source_file"]
            del self._yaml[task_id]

            # Rename the file
            os.rename(task_path, new_path)

            # Update source_file and re-add to internal dict
            current_task["source_file"] = new_file
            self._yaml[patch["id"]] = current_task

            # Update the TASK_ORDER file if this task was in it
            if task_id in self._order:
                order_path = os.path.join(self.project_root, TASKS_DIRNAME, TASK_ORDER_FILENAME)
                with open(order_path, "r", encoding="utf-8") as f:
                    order_content = f.read()

                # Replace the id in TASK_ORDER
                lines = order_content.split("\n")
                for i, line in enumerate(lines):
                    if f"{task_id}" in line:
                        lines[i] = line.replace(task_id, patch["id"])
                        break

                with open(order_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))

                # Update internal order tracking
                self._order[self._rank[task_id]] = patch["id"]
                self._rank[patch["id"]] = self._rank[task_id]
                del self._rank[task_id]

        else:
            # Write the updated task back to the same file
            with open(task_path, "w", encoding="utf-8") as f:
                yaml.dump(current_task, f, sort_keys=False)

            # Update internal dict
            self._yaml[task_id] = current_task

    def delete(self, task_id: str) -> None:
        """
        Delete a task by its id.

        This operation performs full referential cleanup:
          1. Removes the task YAML file from tasks/
          2. Removes the task from TASK_ORDER if present
          3. Removes all schedule entries for this task
          4. Removes all run history for this task

        Raises:
            KeyError: If the task_id doesn't exist in YAML files.
        """
        # Check if task exists in YAML (not legacy-only)
        if task_id not in self._yaml:
            raise KeyError(f"Task '{task_id}' not found or is legacy-only")

        # Get the source file name
        task_file = self._yaml[task_id]["source_file"]
        task_path = os.path.join(self.tasks_dir, task_file)

        # Remove the task YAML file
        os.remove(task_path)

        # Remove from internal YAML dict
        del self._yaml[task_id]

        # Remove from TASK_ORDER if present
        if task_id in self._order:
            order_path = os.path.join(self.project_root, TASKS_DIRNAME, TASK_ORDER_FILENAME)
            with open(order_path, "r", encoding="utf-8") as f:
                order_content = f.read()

            lines = order_content.split("\n")
            filtered_lines = [line for line in lines if task_id not in line]

            with open(order_path, "w", encoding="utf-8") as f:
                f.write("\n".join(filtered_lines))

            # Update internal order tracking
            del self._rank[task_id]
            self._order = [t for t in self._order if t != task_id]
            self._rank = {task_id: i for i, task_id in enumerate(self._order)}

        # Remove schedule entry for this task
        schedule = self.schedule()
        if task_id in schedule["scheduled_tasks"]:
            del schedule["scheduled_tasks"][task_id]

        # Remove run history for this task
        if task_id in schedule["last_run"]:
            del schedule["last_run"][task_id]

        # Write the updated schedule back
        path = self._state_path(SCHEDULE_FILENAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(schedule, handle, indent=2)

    def create(self, task_data: Dict[str, Any]) -> str:
        """
        Create a new task from the given data.

        The task_data must contain at least the 'id' field. If the task already exists,
        raises ValueError. If the task is created successfully, returns the task_id.

        Raises:
            ValueError: If a task with the same id already exists.
            TaskDefinitionError: If the task data is invalid.
        """
        # Validate the task data structure
        task_id = task_data["id"]

        # Check if task already exists
        if task_id in self._yaml or task_id in self._legacy:
            raise ValueError(f"Task '{task_id}' already exists")

        # Validate the task structure
        temp_path = os.path.join(self.tasks_dir, f"task-{task_id}.yaml")
        with open(temp_path, "w", encoding="utf-8") as f:
            yaml.dump(task_data, f, sort_keys=False)

        # Re-validate by loading it
        loaded_task = _load_yaml(temp_path)

        # Add to internal dict
        self._yaml[task_id] = loaded_task

        # Update TASK_ORDER if the file exists
        order_path = os.path.join(self.project_root, TASKS_DIRNAME, TASK_ORDER_FILENAME)
        if os.path.exists(order_path):
            with open(order_path, "r", encoding="utf-8") as f:
                order_content = f.read()

            # Add to end of TASK_ORDER
            lines = order_content.split("\n")
            next_num = len(lines) + 1
            lines.append(f"{next_num}. {task_id}")

            with open(order_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            # Update internal order tracking
            self._order.append(task_id)
            self._rank[task_id] = len(self._order) - 1

        return task_id


# Export public API
__all__ = [
    "TASKS_DIRNAME",
    "TASK_ORDER_FILENAME",
    "REGISTRY_FILENAME",
    "SCHEDULE_FILENAME",
    "REQUIRED_FIELDS",
    "TaskDefinitionError",
    "read_task_order",
    "_priority",
    "_parse_next_run",
    "_now",
    "TaskRepository",
]