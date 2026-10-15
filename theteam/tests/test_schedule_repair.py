"""
Defends two properties of the schedule file.

**Atomicity.** `task-schedule.json` is read by every sweep. It was written with
a bare `open(path, "w")` in three places, which truncates before it writes — so
a process killed mid-dump leaves zero bytes, and then every later `schedule()`
raises `JSONDecodeError`. `RoutineScheduler.tick` catches that and records the same
`last_error` on every subsequent run, forever. Measured consequence: one Ctrl-C
during a write was a permanent outage with no recovery except deleting the file
by hand. Now temp-file plus `os.replace`, in one writer all three paths use.

**Self-healing intervals.** `schedule_task` refuses an interval shorter than a
task's worst case, but that guard is on the *write* path only. `record_run`
re-stamps `next_run` from `interval_minutes` without validating it, so an entry
that predates the guard — or was hand-edited into the file — is copied forward on
every run and never corrects itself. Measured: an entry at 1 minute against a
600s bound, 36x overrun, `due()` true on every sweep forever. `repair_schedules`
repairs it where it is read, and reports what it changed rather than doing it
quietly.
"""

import json
import os

import pytest

from theteam.routines.repository import RoutineRepository


def _project(root, tasks=None, schedule=None):
    """A scratch project: `tasks/task-*.yaml` plus state under `.omp/theteam/`.

    `tasks` maps an id to `{"phases": [{"timeout_seconds": N}, ...]}`. An empty
    phase list yields a task with `phases: []`, which the repository reads as a
    zero worst case and the repair therefore leaves alone.
    """
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    for task_id, definition in (tasks or {}).items():
        body = "".join(
            f"  - name: p{i}\n"
            f"    script: scripts/s.py\n"
            f"    timeout_seconds: {phase.get('timeout_seconds', 300)}\n"
            f"    memory_limit_mb: 128\n"
            for i, phase in enumerate(definition.get("phases", []))
        )
        (root / "tasks" / f"task-{task_id}.yaml").write_text(
            f"id: {task_id}\nname: {task_id}\norder: 0\nphases:\n{body}"
        )
    state = root / ".omp" / "theteam"
    state.mkdir(parents=True, exist_ok=True)
    (state / "task-schedule.json").write_text(json.dumps(
        schedule or {"scheduled_tasks": {}, "last_run": {}}))
    return root


# ===== atomicity =====

def test_the_schedule_write_is_atomic(tmp_path, monkeypatch):
    """Assert the rename, which is the property; a bare write cannot be seen.

    The alternative — killing a writer mid-dump and checking the file — is not
    reproducible here, and the property worth defending is that the destination
    is never opened for writing at all.
    """
    seen = {}
    real_replace = os.replace

    def spy(src, dst):
        seen["replaced"] = True
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    repo = RoutineRepository(str(_project(tmp_path)))
    repo.record_run("worker", "ok", "")

    assert seen.get("replaced"), (
        "the schedule was written in place rather than via a rename, so an "
        "interrupted write truncates it and every later read fails forever")


def test_no_temp_file_survives_a_write(tmp_path):
    repo = RoutineRepository(str(_project(tmp_path)))
    repo.record_run("worker", "ok", "")
    assert not list((tmp_path / ".omp" / "theteam").glob("*.tmp"))


def test_all_three_write_paths_use_the_atomic_writer(tmp_path, monkeypatch):
    """`record_run`, `record_skip` and `schedule_task` share one writer.

    Three separate `open(path, "w")` calls for one file means crash-safety
    applies to whichever call site an author happened to remember.
    """
    repo = RoutineRepository(str(_project(
        tmp_path,
        tasks={"worker": {"phases": [{"timeout_seconds": 60}]}},
    )))
    calls = []
    real_save = RoutineRepository._save_schedule

    def spy(self, schedule):
        calls.append(1)
        return real_save(self, schedule)

    monkeypatch.setattr(RoutineRepository, "_save_schedule", spy)
    repo.schedule_task("worker", 5)
    repo.record_run("worker", "ok", "")
    repo.record_skip("worker", "breaker_open")

    assert len(calls) == 3, (
        "a write path bypasses _save_schedule, so it is not atomic")


def test_the_schedule_survives_a_truncated_prior_file(tmp_path):
    """A zero-byte schedule from a previous crash must not wedge the repository.

    Precondition worth stating: this is the state one interrupted write used to
    leave behind, and it is recoverable from rather than permanent.
    """
    root = _project(tmp_path)
    (root / ".omp" / "theteam" / "task-schedule.json").write_text("")
    repo = RoutineRepository(str(root))
    # The read path must not raise.
    repo.record_run("worker", "ok", "recovered")
    assert (root / ".omp" / "theteam" / "task-schedule.json").stat().st_size > 0


# ===== self-healing intervals =====

def test_an_interval_shorter_than_the_task_is_repaired(tmp_path):
    """The property that makes a hand edit unnecessary.

    `schedule_task` would have refused this entry. It exists anyway — written
    before the guard, or hand-edited — and `record_run` copies it forward
    forever without checking.
    """
    root = _project(
        tmp_path,
        tasks={"worker": {"phases": [{"timeout_seconds": 600}]}},
        schedule={"scheduled_tasks": {"worker": {
            "next_run": "2026-01-01T00:00:00+00:00",
            "interval_minutes": 1}},
            "last_run": {}},
    )
    repo = RoutineRepository(str(root))

    repairs = repo.repair_schedules()

    assert len(repairs) == 1
    repair = repairs[0]
    assert repair["task_id"] == "worker"
    assert repair["was_interval_minutes"] == 1
    assert repair["repaired_interval_minutes"] == 10, "600s needs 10 minutes"
    assert repair["worst_case_seconds"] == 600
    # And the state on disk is what the report says it is.
    on_disk = repo.schedule()["scheduled_tasks"]["worker"]
    assert on_disk["interval_minutes"] == 10


def test_the_repair_is_idempotent(tmp_path):
    """A second sweep finds nothing, so this is not a per-run rewrite."""
    root = _project(
        tmp_path,
        tasks={"worker": {"phases": [{"timeout_seconds": 600}]}},
        schedule={"scheduled_tasks": {"worker": {
            "next_run": "2026-01-01T00:00:00+00:00",
            "interval_minutes": 1}},
            "last_run": {}},
    )
    repo = RoutineRepository(str(root))
    first = repo.repair_schedules()
    after_first = repo.schedule()["scheduled_tasks"]["worker"]
    second = repo.repair_schedules()

    assert len(first) == 1
    assert second == [], "the repair re-fired on already-valid state"
    assert repo.schedule()["scheduled_tasks"]["worker"] == after_first


def test_a_workable_interval_is_left_alone(tmp_path):
    """The converse, so the repair cannot become a constant that always fires."""
    root = _project(
        tmp_path,
        tasks={"worker": {"phases": [{"timeout_seconds": 60}]}},
        schedule={"scheduled_tasks": {"worker": {
            "next_run": "2026-01-01T00:00:00+00:00",
            "interval_minutes": 60}},
            "last_run": {}},
    )
    repo = RoutineRepository(str(root))
    before = repo.schedule()["scheduled_tasks"]["worker"]

    assert repo.repair_schedules() == []
    assert repo.schedule()["scheduled_tasks"]["worker"] == before


def test_an_entry_for_a_deleted_task_is_not_repaired(tmp_path):
    """Purge owns orphans; repair must not resurrect or touch them."""
    root = _project(
        tmp_path,
        tasks={"present": {"phases": [{"timeout_seconds": 60}]}},
        schedule={"scheduled_tasks": {
            "present": {"next_run": "2026-01-01T00:00:00+00:00",
                        "interval_minutes": 60},
            "gone": {"next_run": "2026-01-01T00:00:00+00:00",
                     "interval_minutes": 1}},
            "last_run": {}},
    )
    repo = RoutineRepository(str(root))
    repairs = repo.repair_schedules()

    assert repairs == [], "an orphan entry was repaired instead of left to purge"


@pytest.mark.parametrize("interval,expected", [(1, 10), (5, 10), (10, 10), (11, 11)])
def test_the_repaired_interval_is_the_shortest_that_works(interval, expected):
    """The predicate is shared with the write guard, so they cannot disagree."""
    task = {"phases": [{"timeout_seconds": 600}]}
    worst = RoutineRepository.worst_case_seconds(task)
    assert worst == 600
    if interval * 60 < worst:
        assert max(1, -(-worst // 60)) == expected


def test_the_write_guard_and_the_repair_share_one_predicate():
    """Two copies of "can this task finish in time" would drift silently."""
    task = {"phases": [{"timeout_seconds": 300}, {"timeout_seconds": 300}]}
    assert RoutineRepository.worst_case_seconds(task) == 600, (
        "the shared predicate must sum every phase, because the guard and the "
        "repair both decide on the total")
