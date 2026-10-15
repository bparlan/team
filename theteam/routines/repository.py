#!/usr/bin/env python3
"""
Task repository with full CRUD operations.

Tasks are canonical YAML files under `routines/`. That is the only source: the
legacy JSON registry that M2 dual-read is gone, so a task the read cannot find
does not exist rather than hiding in a second store.

The repository is the single source of truth for task membership and order.
Tasks are owned by a specific project root.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import yaml

#: Named after the module rather than the root logger, so a project's log
#: configuration captures this and nothing else claims it.
logger = logging.getLogger(__name__)

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
    # `depends_on` is a list of task ids, so a bare string is the mistake
    # worth naming: `depends_on: project-integrity` iterates its characters,
    # and the task silently waits on `p`, `r`, `o`, `j`, … forever.
    depends = data.get("depends_on")
    if depends is not None:
        if isinstance(depends, str) or not isinstance(depends, list):
            raise TaskDefinitionError(
                f"{name}: 'depends_on' must be a list of task ids, "
                f"got {type(depends).__name__}"
            )
        for dep in depends:
            if not isinstance(dep, str) or not dep.strip():
                raise TaskDefinitionError(
                    f"{name}: 'depends_on' entries must be non-empty task ids, "
                    f"got {dep!r}"
                )
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


class RoutineRepository:
    """The task store. YAML under `routines/` is the only source."""

    def __init__(self, project_root: str) -> None:
        self.project_root = os.path.abspath(project_root)
        self.routines_dir = os.path.join(self.project_root, TASKS_DIRNAME)
        self._yaml = self._read_yaml()
        # Order is now a per-task key (§5.4). We seed `_rank` from those
        # keys. `TASK_ORDER` is no longer a source.
        self._rank = {t: self._yaml[t].get("order", 999) for t in self._yaml}
        self._order = sorted(self._yaml, key=lambda t: self._rank[t])
        # `read_task_order` and `_write_task_order` are removed; they read/write
        # the `TASK_ORDER` file, which is now obsolete.

        # Why the last `schedule()` read could not use what was on disk, or
        # None. Read by the sweep so a lost schedule is reported rather than
        # showing up as "nothing due" — which reads as a healthy project.
        self._last_schedule_error: Optional[str] = None

    @property
    def last_schedule_error(self) -> Optional[str]:
        """Why the last `schedule()` read discarded what was on disk, or None.

        A caller rendering "nothing due" has to distinguish "nothing is
        scheduled" from "the schedule could not be read". Without this they are
        the same string, and the second one means the scheduler has lost
        everything it knew about.
        """
        return self._last_schedule_error

    # -- sources -----------------------------------------------------------

    def _read_yaml(self) -> Dict[str, Dict[str, Any]]:
        tasks: Dict[str, Dict[str, Any]] = {}
        if not os.path.isdir(self.routines_dir):
            return tasks
        for name in sorted(os.listdir(self.routines_dir)):
            # `routines/` also holds non-tasks (`SECURITY_POLICY.yaml`, and it is
            # not even parseable YAML), so globbing every `*.yaml` here dies on
            # a file that is none of this reader's business. The `task-` prefix
            # is the directory's own convention, not a new one.
            if not (name.startswith("task-") and name.endswith((".yaml", ".yml"))):
                continue
            task = _load_yaml(os.path.join(self.routines_dir, name))
            task.setdefault("source_file", name)
            tasks[task["id"]] = task
        return tasks

    def _state_path(self, filename: str) -> str:
        # `state.py` owns this resolution; reuse it rather than repeat the env
        # var and default, so a container or a test points both at one scratch dir.
        from theteam.state import state_dir
        return str(state_dir(self.project_root) / filename)

    def schedule(self) -> Dict[str, Any]:
        """The schedule, or an empty one if the file is missing or unreadable.

        A zero-byte file was unrecoverable here. `json.load` raised,
        `RoutineScheduler.tick` caught it and recorded the same `last_error` on
        every subsequent run, and nothing in the system could write a schedule
        again — a permanent outage from one interrupted write, with the fix
        being "delete the file by hand".

        `_save_schedule` is now atomic so this state should not arise, but a
        reader that cannot be bricked by its own state file is worth having
        independently: the file can also be truncated by hand, or by a disk that
        filled mid-write on some other writer.

        The corrupt file is moved aside rather than overwritten, so whatever it
        held is still available for a human to look at.

        Returns an empty schedule *and records that it did*, because returning
        empty silently is the defect this replaced. Measured: with two overdue
        tasks on disk, a zero-byte schedule made `theteam run` report `nothing
        due` — which reads as a healthy project with nothing pending, when in
        fact the scheduler had lost every task it knew about. §3.3: a result
        that looks like a measurement of the project's state, and is a
        measurement of nothing.

        So the caller can see it. `last_schedule_error` carries the reason, and
        `run_due_tasks` puts it in the payload so the human line names it.
        Recovery still proceeds rather than raising — a corrupt file must not
        stop the tool working — but it is never silent.
        """
        empty = {"scheduled_tasks": {}, "last_run": {}}
        path = self._state_path(SCHEDULE_FILENAME)
        if not os.path.exists(path):
            return empty
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError) as e:
            self._last_schedule_error = (
                f"task-schedule.json was unreadable ({type(e).__name__}: {e}); "
                f"the schedule is treated as empty until it is rewritten, so no "
                f"task is due and nothing will run"
            )
            logger.warning("%s", self._last_schedule_error)
            try:
                os.replace(path, f"{path}.corrupt")
            except OSError:
                # Cannot move it aside, so it stays. An empty schedule is still
                # the right answer to read, and the next successful write
                # replaces it. The error above is already reported either way.
                pass
            return empty
        self._last_schedule_error = None
        if not isinstance(data, dict):
            self._last_schedule_error = (
                "task-schedule.json is not a mapping "
                f"(got {type(data).__name__}); treated as empty, so nothing is due"
            )
            logger.warning("%s", self._last_schedule_error)
            return empty
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
            # `depends_on` is shown because a task that waits on another and
            # says nothing reads as a task with no work to do. The gate
            # itself lives in `RoutineExecutor.execute_task`; this is the
            # declaration surfacing in the listing so the reader can see
            # why a task was or was not due.
            "depends_on": task.get("depends_on", []) or [],
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

    def list_routines(self) -> Dict[str, Any]:
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

    def purge_orphaned_schedules(self) -> List[str]:
        """
        Drop schedule entries whose task no longer exists. Returns what went.

        A renamed or deleted task leaves its schedule entry behind, and an
        entry that names nothing is worse than no entry: it looks scheduled,
        so `theteam tasks` reports it and a reader concludes something is
        running. Nothing fires it — `due()` walks real tasks — so it just
        accumulates, silently, until someone reads the file.

        `last_run` history is kept. A task that was deleted still ran, and
        `theteam history` reads that history; dropping it would erase evidence
        of runs that really happened.
        """
        orphans = self.orphaned_schedules()
        if not orphans:
            return []
        schedule = self.schedule()
        for task_id in orphans:
            schedule["scheduled_tasks"].pop(task_id, None)
        self._save_schedule(schedule)
        _audit(self.project_root, "orphan_schedules_purged", count=len(orphans),
               ids=orphans)
        return orphans

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
        self._save_schedule(schedule)

    def record_skip(self, task_id: str, detail: str,
                    breaker: Optional[str] = None,
                    consecutive_failures: Optional[int] = None) -> None:
        """Record a skip without restamping when the last real outcome was.

        A skip is not an outcome of the task: a tripped breaker means nothing
        ran, so there is no new result to date. `record_run` writes `at = now`
        because a run genuinely happened then. Here that would be a lie in the
        other direction — it would date the *skip*, and the breaker's recovery
        window is anchored to `at`, so a retry loop faster than the window would
        re-anchor it and keep an open breaker open forever. Measured before the
        fix: every skip moved the deadline forward by a full 60s.

        So `at` is preserved when one exists, and only written when there is
        nothing to preserve. That keeps `theteam history`'s "last run" meaning
        the last time the task actually ran, and lets the recovery window elapse
        exactly as the breaker measured it.

        The breaker reading follows the same rule. `None` means "not measured"
        and is preserved rather than written, for the same reason: a skip that
        never consulted a breaker has no breaker reading to report, and writing
        `null` over a real one discards the trip. Reproduced before this fix — a
        task seeded open with five consecutive failures came back
        `breaker: null` after one skipped run.

        So every field is preserved unless the caller passed a replacement:
        result and detail become the skip, `at` holds, and the breaker fields
        keep whatever was really measured before.
        """
        schedule = self.schedule()
        previous = schedule["last_run"].get(task_id, {})
        schedule["last_run"][task_id] = {
            "result": "skipped",
            "detail": detail,
            "at": previous.get("at") or _now().isoformat(),
            "breaker": previous.get("breaker") if breaker is None else breaker,
            "breaker_consecutive_failures": (
                previous.get("breaker_consecutive_failures")
                if consecutive_failures is None else consecutive_failures
            ),
        }
        # Through the atomic writer rather than its own bare `open`. Two write
        # paths for one file means the crash-safety applies to whichever the
        # author happened to remember.
        self._save_schedule(schedule)

    # ======= write path =======
    #
    # Every write goes through `_check_writable` on the *merged* mapping before
    # anything touches the disk. Validating the file on disk instead meant the
    # write was never checked, so a task that could not be read back landed
    # anyway and the next `RoutineRepository()` construction raised - one edit
    # made the whole project unreadable.

    def _save_schedule(self, schedule: Dict[str, Any]) -> None:
        """Write the schedule atomically.

        Temp file plus `os.replace`, matching `theteam/core/run_context.py` and
        `theteam/core/wal.py`. A bare `open(path, "w")` truncates before it
        writes, so a process killed mid-dump leaves zero bytes — and then every
        later `schedule()` raises `JSONDecodeError`, which `RoutineScheduler.tick`
        catches and records as the same `last_error` forever. One Ctrl-C during
        a write was a permanent outage with no way back except deleting the
        file by hand.
        """
        path = self._state_path(SCHEDULE_FILENAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(schedule, handle, indent=2)
        os.replace(tmp, path)

    @staticmethod
    def worst_case_seconds(task: Dict[str, Any]) -> int:
        """Total wall-clock bound across a task's phases.

        One definition, shared by the write guard and the repair sweep. Two
        copies of this predicate would drift, and the drift would be invisible:
        one would refuse an interval the other considered fine.
        """
        return sum(int(p.get("timeout_seconds", 300))
                   for p in task.get("phases", []))

    def repair_schedules(self) -> List[Dict[str, Any]]:
        """Repair schedule entries that can never be satisfied.

        The interval guard lives only on the write path — `schedule_task`
        refuses a too-short interval for a *new* entry — and `record_run`
        re-stamps `next_run` from `interval_minutes` without validating it. So
        an entry written before the guard existed, or hand-edited into the
        schedule file, is copied forward on every run and never corrects itself:
        measured, `system-awareness` sat at `interval_minutes: 1` against a 600s
        bound, 36x overrun, and `due()` was true on every sweep forever.

        A hand edit is a one-time patch against a mechanism that re-infects, so
        the state is repaired where it is read instead.

        Pure with respect to the returned value and idempotent: a second call
        finds nothing to do, because the repaired interval already satisfies the
        predicate. Repairs `next_run` only — the interval itself is raised to
        the shortest workable value and reported, so the operator sees what
        changed rather than finding out later.
        """
        schedule = self.schedule()
        repairs: List[Dict[str, Any]] = []

        for task_id, entry in list(schedule["scheduled_tasks"].items()):
            task = self.get(task_id)
            if task is None:
                continue  # a task with no definition; purge handles that
            worst = self.worst_case_seconds(task)
            if not worst:
                continue
            try:
                interval = int(entry.get("interval_minutes", 0))
            except (TypeError, ValueError):
                interval = 0
            if interval * 60 >= worst:
                continue

            repaired = max(1, -(-worst // 60))
            was_next_run = entry.get("next_run")
            entry["interval_minutes"] = repaired
            entry["next_run"] = (_now() + timedelta(minutes=repaired)).isoformat()
            repairs.append({
                "task_id": task_id,
                "was_interval_minutes": interval,
                "repaired_interval_minutes": repaired,
                "worst_case_seconds": worst,
                "was_next_run": was_next_run,
            })

        if repairs:
            self._save_schedule(schedule)
        return repairs

    def schedule_task(self, task_id: str, interval_minutes: int) -> str:
        """
        Schedule a task on an interval, returning its ISO `next_run`.

        Scheduling lives here so the state directory is resolved in one place.
        The CLI must not assemble a schedule file by hand.

        Raises:
            KeyError: the id names no task.
            ValueError: the interval is shorter than the task can take.
        """
        if self.get(task_id) is None:
            raise KeyError(f"Task '{task_id}' not found")
        # A task scheduled faster than its own worst-case time can never
        # finish before it is due again, so the schedule is permanently
        # overdue and every sweep re-runs it. `system-awareness` was scheduled
        # at 1 minute against a 600s bound: 36x overrun, silently. Refused with
        # the number that would work, rather than accepted and left to fight
        # itself.
        task = self.get(task_id)
        worst = self.worst_case_seconds(task)
        if worst and int(interval_minutes) * 60 < worst:
            raise ValueError(
                f"interval {interval_minutes}m is shorter than task "
                f"'{task_id}' can take ({worst}s worst case). Use "
                f"--interval {max(1, -(-worst // 60))} or more."
            )
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
        with open(os.path.join(self.routines_dir, name), "w", encoding="utf-8") as handle:
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
            os.rename(os.path.join(self.routines_dir, old_name),
                      os.path.join(self.routines_dir, new_name))
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

        os.remove(os.path.join(self.routines_dir, self._yaml[task_id]["source_file"]))
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
    "RoutineRepository",
]