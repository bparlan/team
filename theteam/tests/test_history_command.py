"""
The `theteam history` reporting contract (§7.1.7, §3.3).

`history` is the one surface that turns recorded state into a number a human
acts on - "is this task healthy or burning cycles?". It derives those numbers
from two files S1 and S3 wrote: the schedule's `last_run` entry and the
execution log. Both are read paths over state nothing else in the suite
reports, so a regression here would be invisible everywhere else.

What is pinned, and why each one matters:

  * a task with runs reports counts that match its log and a rate computed
    from them, plus the breaker state the schedule actually recorded;
  * `last_failure` is the newest *failing* run, not the newest run, and it is
    `None` when nothing ever failed;
  * a task with no runs reports `success_rate: None` and `breaker: None`. A
    0.0 rate or a "closed" breaker is a value that looks like a measurement
    while nothing was measured, which is exactly what §3.3 forbids and the
    one a reader would trust hardest - "this task is failing" vs "this task has
    never run" call for opposite reactions;
  * one task's runs never inflate another task's row, and `--task` selects a
    single row;
  * an unknown id fails with the id named. An empty success would read as
    "that task has no history" - the opposite of "there is no such task".

Everything is built in a scratch project under `tmp_path`; the real repo's
`.omp/`, `tasks/` and execution log are never read.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from theteam.cli import main
from theteam.state import STATE_DIR_ENV
from theteam.tasks.executor import TaskExecutor


# ======= scratch project =======


@pytest.fixture(autouse=True)
def _state_dir_under_root(monkeypatch):
    """
    The state directory resolves under the project root, so a `THETEAM_STATE_DIR`
    left over from the developer's shell cannot redirect these reads to a real
    project's log. Restored by the fixture.
    """
    monkeypatch.delenv(STATE_DIR_ENV, raising=False)


def _project(root, order=(), tasks=None, schedule=None):
    """
    Build an isolated project: `tasks/task-<id>.yaml` plus
    `.omp/theteam/task-schedule.json`. Nothing is read from the real repo.
    """
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    tasks = tasks or {}
    rank = {t: i for i, t in enumerate(order)}
    for task_id, fields in tasks.items():
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


def _run(task_id, minutes_ago, success):
    """One execution-log record, shaped exactly as `TaskExecutor` writes one."""
    return {
        "task_id": task_id,
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
                      ).isoformat(),
        "phases": [{"phase": "verify", "success": success, "returncode": 0 if success else 1}],
        "overall_success": success,
        "breaker": "closed",
        "breaker_consecutive_failures": 0 if success else 1,
    }


def _log(root, *records):
    """
    Seed the execution log through the writer the product uses.

    Not a hand-built file. This helper used to open the log and write JSON
    itself, which meant the suite asserted `history` against a fixture whose
    only producer was the test - and nothing in production ever called
    `log_execution`. A task could fail five times in a row and `history` still
    reported `runs: 0`, and this file passed. Writing through the component
    keeps the fixture honest about the record shape, and the integration test
    in section 7 pins the other half: that a real run actually calls it.
    """
    executor = TaskExecutor(str(root))
    for record in records:
        executor.log_execution(record)
    return executor.execution_log


def _cli(root, *argv, capsys):
    """Drive the CLI and hand back (exit code, parsed JSON payload)."""
    code = main(["--project-root", str(root), *argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _row(payload, task_id):
    """The one history row for `task_id`."""
    return next(r for r in payload["tasks"] if r["id"] == task_id)


# ======= 1. a task with runs reports real numbers =======


def test_a_task_with_runs_reports_its_counts_and_rate(tmp_path, capsys):
    """
    Two successes and one failure out of three runs is 66.7%, and the counts
    have to agree with it. A rate computed from the wrong denominator, or a
    count that drifts from the log, would read as a real health signal.
    """
    root = _project(tmp_path, tasks={"build": {}})
    _log(root, _run("build", 30, True), _run("build", 20, True),
         _run("build", 10, False))

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    row = _row(payload, "build")
    assert (row["runs"], row["successes"], row["failures"]) == (3, 2, 1)
    assert row["success_rate"] == 66.7
    # The rate is derived from the counts, not computed independently.
    assert row["success_rate"] == round(
        100.0 * row["successes"] / row["runs"], 1
    )


def test_a_task_with_runs_reports_the_breaker_state_the_schedule_recorded(tmp_path, capsys):
    """
    Breaker state lives in the schedule, not the log. If `history` reported the
    string it would have to invent instead, an open breaker on a task that has
    tripped would be invisible exactly when it matters.
    """
    at = "2026-03-01T12:00:00+00:00"
    root = _project(
        tmp_path,
        tasks={"build": {}},
        schedule={"scheduled_tasks": {}, "last_run": {
            "build": {
                "at": at,
                "result": "failed",
                "breaker": "open",
                "breaker_consecutive_failures": 5,
            }
        }},
    )
    _log(root, _run("build", 10, False))

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    row = _row(payload, "build")
    assert row["last_run"] == at
    assert row["last_result"] == "failed"
    assert row["breaker"] == "open"
    assert row["consecutive_failures"] == 5


def test_the_last_run_is_reported_even_with_nothing_in_the_execution_log(tmp_path, capsys):
    """
    The two sources are independent. A task the schedule ran but whose log
    entry is gone (retention, a rotated file) still has a last run, and
    reporting `None` would claim it never ran.
    """
    at = "2026-03-01T12:00:00+00:00"
    root = _project(
        tmp_path,
        tasks={"build": {}},
        schedule={"scheduled_tasks": {}, "last_run": {
            "build": {"at": at, "result": "success", "breaker": "closed",
                      "breaker_consecutive_failures": 0}
        }},
    )

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    row = _row(payload, "build")
    assert row["last_run"] == at
    assert row["last_result"] == "success"
    assert row["runs"] == 0


# ======= 2. last_failure is the newest failing run =======


def test_last_failure_is_the_newest_failing_run_not_the_newest_run(tmp_path, capsys):
    """
    The field answers "when did this last break?", not "when did it last run?".
    Taking the newest run of either kind would clear a task's last failure the
    moment it recovered, which is the opposite of what the field is for.
    """
    root = _project(tmp_path, tasks={"build": {}})
    broken = _run("build", 45, False)
    _log(root, broken, _run("build", 30, True), _run("build", 5, True))

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    row = _row(payload, "build")
    assert row["last_failure"] == broken["timestamp"]
    assert row["failures"] == 1
    assert row["success_rate"] == 66.7


def test_a_task_that_has_never_failed_reports_no_last_failure(tmp_path, capsys):
    """
    Nothing failed, so there is no last failure. Any other value - a
    timestamp, a count, a sentinel - reads as a measured event that did not
    happen.
    """
    root = _project(tmp_path, tasks={"build": {}})
    _log(root, _run("build", 20, True), _run("build", 5, True))

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    row = _row(payload, "build")
    assert row["last_failure"] is None
    assert row["failures"] == 0
    assert row["success_rate"] == 100.0


# ======= 3. no runs means no measurement (§3.3) =======


def test_a_task_with_no_runs_reports_no_rate_and_no_breaker(tmp_path, capsys):
    """
    The §3.3 contract, and the one a reader trusts hardest. `success_rate:
    0.0` reads as "this task has never passed"; `breaker: "closed"` reads as
    "this task's breaker was measured and found closed". Both say a task that
    has never run is in some known state. `None` is the only honest answer,
    and it is what distinguishes "never run" from "failing".
    """
    root = _project(tmp_path, order=("build", "lint"), tasks={
        "build": {}, "lint": {},
    })

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    for task_id in ("build", "lint"):
        row = _row(payload, task_id)
        assert row["runs"] == 0, task_id
        assert row["success_rate"] is None, task_id
        assert row["breaker"] is None, task_id
        assert row["last_run"] is None, task_id
        assert row["last_failure"] is None, task_id
        assert row["consecutive_failures"] is None, task_id


def test_a_task_with_no_runs_is_reported_as_unmeasured_in_the_human_line(tmp_path, capsys):
    """
    The rendered line has to carry the same distinction as the payload. A
    0.0% column for a task that never ran is the fabrication in the one place
    a human reads.
    """
    root = _project(tmp_path, tasks={"build": {}})

    code = main(["--project-root", str(root), "history"])
    out = capsys.readouterr().out

    assert code == 0
    assert "-" in out and "never run" in out
    assert "0.0" not in out


# ======= 4. --task selects one row =======


def test_task_selects_exactly_that_task(tmp_path, capsys):
    """
    The filter is on the reported rows, not on what gets computed: the other
    task's numbers must not appear in the payload at all, or a caller cannot
    tell them apart from the selected one.
    """
    root = _project(tmp_path, order=("build", "lint"), tasks={
        "build": {}, "lint": {},
    })
    _log(root, _run("build", 10, True), _run("build", 5, False))

    code, payload = _cli(root, "history", "--task", "build", capsys=capsys)

    assert code == 0
    assert payload["count"] == 1
    assert [r["id"] for r in payload["tasks"]] == ["build"]
    assert _row(payload, "build")["failures"] == 1


def test_task_selecting_an_unrun_task_still_reports_it_as_unmeasured(tmp_path, capsys):
    """
    Filtering to a task is not the same as asking about a run: the row exists
    and says nothing was measured. A filter that dropped unrun tasks would
    turn "this task has never run" into "no such task".
    """
    root = _project(tmp_path, order=("build", "lint"), tasks={
        "build": {}, "lint": {},
    })

    code, payload = _cli(root, "history", "--task", "lint", capsys=capsys)

    assert code == 0
    assert [r["id"] for r in payload["tasks"]] == ["lint"]
    assert payload["tasks"][0]["success_rate"] is None


# ======= 5. an unknown id is an error, not an empty success =======


def test_an_unknown_task_id_fails_and_names_the_id(tmp_path, capsys):
    """
    A successful empty payload would read as "that task has no history" -
    the opposite of "no such task" - and a caller checking only the exit code
    would report a healthy nothing instead of a mistake.
    """
    root = _project(tmp_path, tasks={"build": {}})

    code, payload = _cli(root, "history", "--task", "nope", capsys=capsys)

    assert code == 1
    assert payload["ok"] is False
    assert payload["command"] == "history"
    assert "nope" in payload["reason"]
    assert "tasks" not in payload


def test_an_unknown_task_id_says_so_in_the_human_output(tmp_path, capsys):
    """The non-JSON path names the id too, and exits 1 rather than printing rows."""
    root = _project(tmp_path, tasks={"build": {}})

    code = main(["--project-root", str(root), "history", "--task", "nope"])
    err = capsys.readouterr()

    assert code == 1
    assert "nope" in err.err
    assert "build" not in err.out


# ======= 6. one task's runs never become another's =======


def test_another_tasks_runs_do_not_inflate_this_tasks_row(tmp_path, capsys):
    """
    The log is one file shared by every task, so a reader that stopped
    filtering on `task_id` would count every run in the project for each task.
    `lint` has one clean run; if the filter were dropped it would report four
    runs at 75% instead of one at 100%.
    """
    root = _project(tmp_path, order=("build", "lint"), tasks={
        "build": {}, "lint": {},
    })
    _log(root,
         _run("build", 30, True), _run("build", 20, True),
         _run("build", 10, False),
         _run("lint", 5, True))

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    lint = _row(payload, "lint")
    assert (lint["runs"], lint["successes"], lint["failures"]) == (1, 1, 0)
    assert lint["success_rate"] == 100.0
    assert lint["last_failure"] is None

    build = _row(payload, "build")
    assert (build["runs"], build["successes"], build["failures"]) == (3, 2, 1)
    assert build["success_rate"] == 66.7


def test_another_tasks_failures_never_become_this_tasks_last_failure(tmp_path, capsys):
    """
    The failure filter and the task filter are independent, and dropping
    either one writes a real timestamp into `last_failure` for a task that has
    never failed.
    """
    root = _project(tmp_path, order=("build", "lint"), tasks={
        "build": {}, "lint": {},
    })
    _log(root, _run("build", 10, False), _run("lint", 5, True))

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    assert _row(payload, "lint")["last_failure"] is None
    assert _row(payload, "build")["last_failure"] is not None


def test_a_log_line_for_a_task_that_no_longer_exists_is_not_attributed_to_another(tmp_path, capsys):
    """
    Deleting a task leaves its run records behind. Those runs belong to a task
    that is not in the listing, and folding them into whichever task is left
    would report a health rate for runs that never touched it.
    """
    root = _project(tmp_path, tasks={"build": {}})
    _log(root, _run("ghost", 10, False), _run("ghost", 5, False))

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    assert payload["count"] == 1
    row = _row(payload, "build")
    assert (row["runs"], row["failures"]) == (0, 0)
    assert row["success_rate"] is None
    assert row["last_failure"] is None


# ======= 7. the numbers come from real runs, not from a fixture =======


def _past(minutes=5):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _make_due(root, task_id):
    """Put a task back in scope. Every `run` advances `next_run`."""
    path = root / ".omp" / "theteam" / "task-schedule.json"
    schedule = json.loads(path.read_text(encoding="utf-8"))
    schedule["scheduled_tasks"][task_id]["next_run"] = _past()
    path.write_text(json.dumps(schedule, indent=2), encoding="utf-8")


def _task(root, task_id, script):
    """A scheduled task with one phase, plus the script its phase names."""
    _project(root, order=(task_id,), tasks={
        task_id: {"phases": [{"name": "one", "script": script, "memory_limit_mb": 128}]},
    }, schedule={
        "scheduled_tasks": {task_id: {"next_run": _past(), "interval_minutes": 60}},
        "last_run": {},
    })
    path = root / script
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("pass\n", encoding="utf-8")
    return root


def _stub_phase(monkeypatch, success):
    """
    Make every phase report `success`, the way
    `test_executor_circuit_breaker` does.

    Without this the phase would go to a real Docker container, and the
    assertion would be about Docker being installed rather than about the
    execution log. The outcome still comes from the product's own executor.
    """
    monkeypatch.setattr(
        TaskExecutor, "execute_phase",
        lambda self, phase: {"success": success, "returncode": 0 if success else 3},
    )


def test_history_reports_a_task_the_product_actually_ran(tmp_path, capsys, monkeypatch):
    """
    The defect: `log_execution` was the only writer of the execution log and
    nothing in production called it, so a task that had really run - and
    really failed - reported `runs: 0`, `failures: 0`, `last_failure: null`.
    §7.1.7 requires a per-task success rate and a last failure. It reported
    neither, and this suite passed because every fixture seeded the log by
    hand.

    This test goes through `run`. Seeding through the component (section 1)
    keeps the record shape honest but cannot catch a missing call site: a
    seeded record exists whether or not the product writes one. Only a real
    run separates those two worlds.
    """
    root = _task(tmp_path, "crasher", "phases/boom.py")
    _stub_phase(monkeypatch, success=False)

    for _ in range(2):
        _make_due(root, "crasher")
        _cli(root, "run", capsys=capsys)

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    row = _row(payload, "crasher")
    assert row["runs"] == 2, "a real run must reach the execution log"
    assert row["failures"] == 2
    # A failed task's rate is 0.0. That is a measurement. The `None` an unrun
    # task reports means the opposite, and the two must never be confused.
    assert row["success_rate"] == 0.0
    assert row["last_failure"] is not None, "history must name when it last failed"


def test_a_task_whose_breaker_trips_is_not_counted_as_a_run(tmp_path, capsys, monkeypatch):
    """
    A tripped breaker skips the sixth attempt instead of executing it. A skip
    is not a run: counting it would report six runs when the product executed
    five, and `runs` is what the success rate divides by.
    """
    root = _task(tmp_path, "crasher", "phases/boom.py")
    _stub_phase(monkeypatch, success=False)

    # Five failures trip the breaker (§7.1.5); the sixth attempt is skipped.
    for _ in range(6):
        _make_due(root, "crasher")
        _cli(root, "run", capsys=capsys)

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    row = _row(payload, "crasher")
    assert row["runs"] == 5, "a skipped attempt is not a run"
    assert row["breaker"] == "open"


def test_a_successful_run_reports_a_full_rate_from_a_real_run(tmp_path, capsys, monkeypatch):
    """
    The other side of a real rate. A run that passed is 100.0 with no last
    failure - neither value may come back as `None`, which means "never ran".
    """
    root = _task(tmp_path, "well", "phases/well.py")
    _stub_phase(monkeypatch, success=True)

    _cli(root, "run", capsys=capsys)

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    row = _row(payload, "well")
    assert (row["runs"], row["successes"], row["failures"]) == (1, 1, 0)
    assert row["success_rate"] == 100.0
    assert row["last_failure"] is None


def test_an_unrun_task_still_reports_no_rate_after_a_real_run_of_another(tmp_path, capsys, monkeypatch):
    """
    M4's correct behaviour, kept: a task that has never run reports `None`,
    not 0.0. A real run of a different task must not turn that `None` into a
    number that reads like a measurement.
    """
    root = _task(tmp_path, "well", "phases/well.py")
    _project(root, order=("well", "fresh"), tasks={
        "fresh": {"phases": [{"name": "one", "script": "phases/fresh.py",
                              "memory_limit_mb": 128}]},
    })
    _stub_phase(monkeypatch, success=True)

    _cli(root, "run", capsys=capsys)

    code, payload = _cli(root, "history", capsys=capsys)

    assert code == 0
    row = _row(payload, "fresh")
    assert row["runs"] == 0
    assert row["success_rate"] is None
    assert row["last_failure"] is None
