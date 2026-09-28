"""
The per-task `CircuitBreaker` in `TaskExecutor` (M4, §7.1.5).

Four claims, each with a distinct failure mode it is here to catch:

1. A task that fails five times in a row is skipped on its next attempt, with
   the literal reason `breaker_open`, and it is skipped in a *later process* -
   a breaker that only lives in one `TaskExecutor` forgets the trip the moment
   `theteam run` exits, which is the same as not having one.
2. A breaker that has never run does not report a fabricated `"closed"`.
   §3.3: a default that looks like a measurement is the defect.
3. The breaker records the real outcome. A task that fails then succeeds has
   its consecutive-failure count reset, so one bad afternoon does not lock a
   healthy task out forever.
4. A tripped breaker does not run the task, and a refused attempt is not a
   failed attempt.

`cmd_run` builds a fresh `TaskExecutor` on every call, so each `_cli` here is
a fresh breaker map reading only persisted state - the same thing a second
`theteam run` from a shell does.
"""

import json
from datetime import datetime, timedelta, timezone

import yaml

from theteam.cli import main
from theteam.tasks.executor import TaskExecutor
from theteam.tasks.repository import TaskRepository


# ======= scratch project =======


def _past(minutes=5):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _future(minutes=30):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _project(root, order=(), tasks=None, schedule=None):
    """A throwaway project. The shape is `test_task_repository._project`."""
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    rank = {t: i for i, t in enumerate(order)}
    for task_id, fields in (tasks or {}).items():
        payload = {"id": task_id, "order": rank.get(task_id, len(rank))}
        payload.update(fields)
        (tasks_dir / f"task-{task_id}.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
        )
    if schedule is not None:
        state = root / ".omp" / "theteam"
        state.mkdir(parents=True, exist_ok=True)
        (state / "task-schedule.json").write_text(
            json.dumps(schedule, indent=2), encoding="utf-8"
        )
    return root


def _script(root, relative, body):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _failing_task(root, task_id="crasher", script="phases/crasher.py"):
    """A scheduled task whose one phase exits non-zero.

    `memory_limit_mb` is present because §5.4 makes it mandatory: without it
    `execute_phase` refuses the phase, and a refusal is a different path than
    the one under test.
    """
    _project(
        root,
        order=[task_id],
        tasks={task_id: {"phases": [
            {"name": "boom", "script": script, "memory_limit_mb": 128},
        ]}},
        schedule={
            "scheduled_tasks": {task_id: {"next_run": _past(), "interval_minutes": 60}},
            "last_run": {},
        },
    )
    _script(root, script, "import sys\nsys.exit(3)\n")
    return root


def _passing_task(root, task_id="well", script="phases/well.py"):
    _project(
        root,
        order=[task_id],
        tasks={task_id: {"phases": [
            {"name": "one", "script": script, "memory_limit_mb": 128},
        ]}},
        schedule={
            "scheduled_tasks": {task_id: {"next_run": _past(), "interval_minutes": 60}},
            "last_run": {},
        },
    )
    _script(root, script, "pass\n")
    return root


def _unscheduled_task(root, task_id="fresh"):
    """A task that exists and has never run."""
    _project(
        root,
        order=[task_id],
        tasks={task_id: {"phases": [
            {"name": "one", "script": "phases/one.py", "memory_limit_mb": 128},
        ]}},
        schedule={
            "scheduled_tasks": {task_id: {"next_run": _future(), "interval_minutes": 60}},
            "last_run": {},
        },
    )
    return root


def _schedule(root):
    return json.loads(
        (root / ".omp" / "theteam" / "task-schedule.json").read_text(encoding="utf-8")
    )


def _last(root, task_id):
    return _schedule(root)["last_run"][task_id]


def _make_due(root, task_id):
    """Put a task back in scope. Every `run` advances `next_run`."""
    path = root / ".omp" / "theteam" / "task-schedule.json"
    schedule = json.loads(path.read_text(encoding="utf-8"))
    schedule["scheduled_tasks"][task_id]["next_run"] = _past()
    path.write_text(json.dumps(schedule, indent=2), encoding="utf-8")


def _cli(root, *argv, capsys):
    code = main(["--project-root", str(root), *argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _run(root, capsys):
    """One `theteam run`. Returns (code, payload)."""
    return _cli(root, "run", capsys=capsys)


# ======= 1. five failures trip it, and the trip outlives the process =======


def test_five_failures_across_five_runs_then_a_sixth_is_skipped_breaker_open(tmp_path, capsys):
    """
    §7.1.5 end to end. Five `theteam run` invocations, each building its own
    `TaskExecutor` and therefore its own breaker map, each recording one real
    failure. The sixth is another fresh invocation and still refuses to run the
    task, naming the literal `breaker_open`.

    This is the claim a single-process test cannot make: a breaker held only in
    memory passes every in-process test and fails this one, because the trip is
    supposed to survive the run that observed it.
    """
    root = _failing_task(tmp_path)

    for attempt in range(1, 6):
        # `run` advances `next_run` by the interval, so the next attempt is
        # only due once that interval has passed. Rewriting `next_run` to the
        # past is time passing, not forcing the task to run.
        _make_due(root, "crasher")
        code, payload = _run(root, capsys)
        assert payload["results"] == [{"id": "crasher", "result": "failed"}], attempt
        assert _last(root, "crasher")["breaker_consecutive_failures"] == attempt

    assert _last(root, "crasher")["breaker"] == "open"

    _make_due(root, "crasher")
    code, payload = _run(root, capsys)
    assert payload["ran"] == 0
    assert payload["skipped"] == 1
    assert payload["failures"] == 0
    assert payload["results"] == [
        {"id": "crasher", "result": "skipped", "detail": "breaker_open"}
    ]
    # The reason survives into a later read, not just into this payload.
    assert _last(root, "crasher")["detail"] == "breaker_open"
    assert _last(root, "crasher")["breaker"] == "open"


def test_the_trip_is_visible_to_a_later_tasks_invocation(tmp_path, capsys):
    """
    §3.2: the trip is visible in `tasks`. `theteam tasks` is a different
    invocation from the `run` that observed the trip, so this only holds if the
    state was persisted rather than held in the executor.
    """
    root = _failing_task(tmp_path)
    for _ in range(5):
        _make_due(root, "crasher")
        _run(root, capsys)

    code, payload = _cli(root, "tasks", capsys=capsys)

    assert code == 0
    row = payload["tasks"][0]
    assert row["breaker"] == "open"
    assert row["breaker_consecutive_failures"] == 5

    assert main(["--project-root", str(root), "tasks"]) == 0
    out = capsys.readouterr().out
    assert "crasher" in out
    assert "open" in out


# ======= 2. a breaker that never ran says so =======


def test_a_task_that_never_ran_reports_no_breaker_state_rather_than_closed(tmp_path):
    """
    §3.3. The old `_row` read `last.get("breaker", "closed")`, so a task that
    had never run printed `"closed"` - indistinguishable from a task whose
    breaker was measured closed. `None` is the honest value: nothing was
    measured, which is a different statement from "measured closed".
    """
    _unscheduled_task(tmp_path)

    row = TaskRepository(str(tmp_path)).list_tasks()["tasks"][0]

    assert row["breaker"] is None
    assert row["breaker_consecutive_failures"] is None


def test_the_tasks_listing_names_an_unmeasured_breaker_rather_than_printing_closed(tmp_path, capsys):
    """The human line must not turn `None` back into a value that reads as a reading."""
    _unscheduled_task(tmp_path)

    assert main(["--project-root", str(tmp_path), "tasks"]) == 0
    out = capsys.readouterr().out

    assert "never run" in out
    assert "closed" not in out


def test_a_successful_run_records_a_measured_closed_breaker(tmp_path, capsys):
    """
    The mirror of the two tests above: once something was measured, the row
    carries the real value. A `closed` here was earned by a run, which is
    exactly what makes it different from the fabricated one.
    """
    root = _passing_task(tmp_path)

    _run(root, capsys)

    row = TaskRepository(str(root)).list_tasks()["tasks"][0]
    assert row["breaker"] == "closed"
    assert row["breaker_consecutive_failures"] == 0


# ======= 3. the breaker records the real outcome =======


def test_a_success_resets_the_consecutive_failure_count(tmp_path, capsys):
    """
    A task that fails twice then succeeds is not left two failures from a
    trip. The count is consecutive, so a recovery has to be visible or the
    breaker locks out a task that is already healthy.
    """
    root = _failing_task(tmp_path)
    _run(root, capsys)
    _make_due(root, "crasher")
    _run(root, capsys)
    assert _last(root, "crasher")["breaker_consecutive_failures"] == 2

    _script(root, "phases/crasher.py", "pass\n")
    _make_due(root, "crasher")

    code, payload = _run(root, capsys)

    assert code == 0
    assert payload["results"] == [{"id": "crasher", "result": "ok"}]
    assert _last(root, "crasher")["breaker_consecutive_failures"] == 0
    assert _last(root, "crasher")["breaker"] == "closed"


def test_a_skipped_attempt_does_not_add_to_the_failure_count(tmp_path, capsys):
    """
    A refused attempt is not a failed attempt. If skipping recorded a failure
    the count would climb forever on a breaker that is never going to let the
    task run again - the trip would be self-sustaining for the wrong reason.
    """
    root = _failing_task(tmp_path)
    for _ in range(5):
        _make_due(root, "crasher")
        _run(root, capsys)
    assert _last(root, "crasher")["breaker_consecutive_failures"] == 5

    _make_due(root, "crasher")
    _run(root, capsys)
    _make_due(root, "crasher")
    _run(root, capsys)

    assert _last(root, "crasher")["breaker_consecutive_failures"] == 5


# ======= 4. the executor's own contract =======


def test_execute_task_reports_the_breaker_state_and_the_failure_count(tmp_path, monkeypatch):
    """
    The keys the CLI persists come from the component, not from a literal:
    `CircuitState.value` and `stats.consecutive_failures`.
    """
    executor = TaskExecutor(str(tmp_path))
    executor.execute_phase = lambda phase: {"success": False, "returncode": 3}
    task = {"id": "solo", "phases": [{"name": "boom", "script": "phases/boom.py"}]}

    first = executor.execute_task(task)

    assert first["breaker"] == "closed"
    assert first["breaker_consecutive_failures"] == 1
    assert first["overall_success"] is False
    assert first.get("skipped") is None

    assert executor.execute_task(task)["breaker_consecutive_failures"] == 2


def test_execute_task_does_not_run_a_tripped_breaker(tmp_path):
    """
    `allow_request()` returning False has to mean the phases never ran, not that
    they ran and were ignored. A stubbed `execute_phase` counts its calls; on a
    tripped breaker it must not be called a sixth time.
    """
    executor = TaskExecutor(str(tmp_path))
    calls = []
    executor.execute_phase = lambda phase: calls.append(phase["name"]) or {
        "success": False, "returncode": 3
    }
    task = {"id": "solo", "phases": [{"name": "boom", "script": "phases/boom.py"}]}

    for _ in range(5):
        executor.execute_task(task)
    assert len(calls) == 5

    outcome = executor.execute_task(task)

    assert len(calls) == 5, "a tripped breaker must not execute the phase"
    assert outcome["skipped"] is True
    assert outcome["skip_reason"] == "breaker_open"
    assert outcome["phases"] == []
    assert outcome["breaker"] == "open"
    assert outcome["breaker_consecutive_failures"] == 5


def test_a_breaker_restored_from_stored_failures_is_already_tripped(tmp_path):
    """
    A new invocation handed five recorded consecutive failures must begin with
    its breaker open. Replaying `record_failure()` re-drives the component's
    state machine; assigning `stats.state` would be a trip it never evaluated.
    """
    executor = TaskExecutor(
        str(tmp_path),
        breaker_states={"solo": {"breaker": "open",
                                 "breaker_consecutive_failures": 5}},
    )

    breaker = executor._breaker("solo")

    assert breaker.stats.state.value == "open"
    assert breaker.allow_request() is False


def test_a_breaker_restored_from_a_healthy_run_still_admits_work(tmp_path):
    """The other half: a task that last succeeded is not left closed out."""
    executor = TaskExecutor(
        str(tmp_path),
        breaker_states={"solo": {"breaker": "closed",
                                 "breaker_consecutive_failures": 0}},
    )

    assert executor._breaker("solo").allow_request() is True


def test_state_with_nothing_measured_does_not_invent_failures(tmp_path):
    """
    `None` is "not measured", and a not-measured count must leave the breaker
    where a fresh one is: closed with nothing against it. Reading a missing
    value as failures would be a fabricated reading, the same defect class as
    a fabricated `"closed"`.
    """
    executor = TaskExecutor(str(tmp_path), breaker_states={"solo": {}})

    breaker = executor._breaker("solo")

    assert breaker.stats.consecutive_failures == 0
    assert breaker.allow_request() is True
