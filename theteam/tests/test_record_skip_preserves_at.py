"""
`RoutineRepository.record_skip` records a skip without restamping `at` or
clearing the breaker reading.

The defect this file guards: `record_run` unconditionally writes
`at = _now()` and `breaker`/`breaker_consecutive_failures` (defaulting to
`None`). Calling it for a skip therefore (a) re-stamped `at`, re-anchoring
the circuit breaker's 60s recovery window so it could never elapse under
repeated invocation, and (b) erased a real breaker reading to null. `record_skip`
preserves `at` and the breaker fields when the caller passes None, while
writing result="skipped" and the new detail. It does not touch
`scheduled_tasks` / `next_run`.
"""

import json
from datetime import datetime, timedelta, timezone

import yaml

from theteam.routines.repository import RoutineRepository


# ======= scratch project =======


def _project(root, tasks=None, schedule=None):
    """Build an isolated project: `tasks/task-*.yaml` and the state files."""
    routines_dir = root / "tasks"
    routines_dir.mkdir(parents=True, exist_ok=True)
    for task_id, fields in (tasks or {}).items():
        payload = {"id": task_id, "order": 0}
        payload.update(fields)
        (routines_dir / f"task-{task_id}.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
        )
    state = root / ".omp" / "theteam"
    if schedule is not None:
        state.mkdir(parents=True, exist_ok=True)
        (state / "task-schedule.json").write_text(
            json.dumps(schedule, indent=2), encoding="utf-8"
        )
    return root


def _last_run(root, task_id):
    path = root / ".omp" / "theteam" / "task-schedule.json"
    return json.loads(path.read_text(encoding="utf-8"))["last_run"][task_id]


# ======= 1. record_skip preserves an existing `at` =======


def test_record_skip_preserves_at_from_prior_run(tmp_path):
    """
    `record_run` stamps `at = now`; `record_skip` must not overwrite it.

    REVERTING-CHECK: this assertion is the one that fails if `record_skip`
    falls back to writing `_now()` for `at`. Under the old
    `record_run`-on-skip behaviour every skip re-stamped `at`, re-anchoring
    the circuit breaker's 60s recovery window so it could never elapse under
    repeated invocation -- the task stayed permanently unrunnable.
    """
    root = _project(tmp_path, tasks={"solo": {"name": "Solo"}})
    repo = RoutineRepository(str(root))

    repo.record_run("solo", "failed", "boom", breaker="open", consecutive_failures=5)
    previous = _last_run(root, "solo")
    at_before = previous["at"]

    repo.record_skip("solo", "tripped")

    after = _last_run(root, "solo")
    assert after["at"] == at_before
    assert after["result"] == "skipped"
    assert after["detail"] == "tripped"


# ======= 2. no prior entry still writes a parseable `at` =======


def test_record_skip_writes_at_when_no_prior_entry(tmp_path):
    """
    A task with no `last_run` entry has nothing to preserve, so `record_skip`
    falls back to `previous.get("at") or _now()` and writes a real timestamp.
    """
    root = _project(tmp_path, tasks={"fresh": {"name": "Fresh"}})
    repo = RoutineRepository(str(root))

    repo.record_skip("fresh", "never ran")

    after = _last_run(root, "fresh")
    parsed = datetime.fromisoformat(after["at"])
    assert parsed.tzinfo is not None
    assert after["result"] == "skipped"
    assert after["detail"] == "never ran"


# ======= 3. record_skip with no breaker args preserves the reading =======


def test_record_skip_preserves_breaker_when_unspecified(tmp_path):
    """
    Calling `record_skip` with no breaker arguments must NOT null out a
    previously stored breaker reading and consecutive-failure count.

    REVERTING-CHECK: this assertion is the one that fails if `record_skip`
    writes `breaker=None` / `breaker_consecutive_failures=None` unconditionally.
    Under the old `record_run`-on-skip behaviour a task seeded open with five
    consecutive failures came back `breaker: null` after one skipped run,
    discarding the trip.
    """
    root = _project(tmp_path, tasks={"solo": {"name": "Solo"}})
    repo = RoutineRepository(str(root))

    repo.record_run("solo", "failed", "boom", breaker="open", consecutive_failures=5)

    repo.record_skip("solo", "tripped")

    after = _last_run(root, "solo")
    assert after["breaker"] == "open"
    assert after["breaker_consecutive_failures"] == 5
    assert after["result"] == "skipped"
    assert after["detail"] == "tripped"


# ======= 4. record_skip with explicit breaker args writes them =======


def test_record_skip_writes_explicit_breaker_args(tmp_path):
    """Explicit breaker arguments override the preserved reading."""
    root = _project(tmp_path, tasks={"solo": {"name": "Solo"}})
    repo = RoutineRepository(str(root))

    repo.record_run("solo", "failed", "boom", breaker="open", consecutive_failures=5)

    repo.record_skip(
        "solo", "probing", breaker="half_open", consecutive_failures=3
    )

    after = _last_run(root, "solo")
    assert after["breaker"] == "half_open"
    assert after["breaker_consecutive_failures"] == 3
    assert after["result"] == "skipped"
    assert after["detail"] == "probing"


# ======= 5. record_skip does not advance `next_run` =======


def test_record_skip_does_not_advance_next_run(tmp_path):
    """A skip is not a run: `scheduled_tasks` / `next_run` is untouched."""
    root = _project(tmp_path, tasks={"solo": {"name": "Solo"}})
    repo = RoutineRepository(str(root))

    repo.schedule_task("solo", interval_minutes=30)
    next_run_before = repo.schedule()["scheduled_tasks"]["solo"]["next_run"]

    repo.record_skip("solo", "tripped")

    after = _last_run(root, "solo")
    assert after["result"] == "skipped"
    assert after["detail"] == "tripped"
    assert repo.schedule()["scheduled_tasks"]["solo"]["next_run"] == next_run_before


# ======= 6. repeated skips still let the breaker recover =======


def test_repeated_skips_do_not_re_anchor_the_recovery_window(tmp_path):
    """
    The end-to-end property cases 1 and 3 exist to protect: a burst of skips
    must not stop the breaker from ever probing again.

    `RoutineExecutor._breaker` anchors `recovery_deadline` to `last_run[tid].at`.
    So a skip that restamps `at` pushes the whole window forward again, and a
    retry loop or a `serve` tick faster than 60s re-arms it forever. Measured
    before the fix: three consecutive skips each moved the deadline a further
    60s out, and the task stayed unrunnable.

    REVERTING-CHECK: with `at` restamped by the skip, the first
    `allow_request()` is False and `at` drifts from `tripped_at`. Both fail.
    """
    from theteam.routines.executor import RoutineExecutor

    root = _project(tmp_path, tasks={"solo": {"name": "Solo"}})
    repo = RoutineRepository(str(root))
    repo.record_run("solo", "failed", "boom", breaker="open", consecutive_failures=5)

    # Age the trip past the 60s recovery window, the way a real failure would be.
    tripped_at = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
    ).isoformat()
    state = _last_run(root, "solo")
    state["at"] = tripped_at
    (root / ".omp" / "theteam" / "task-schedule.json").write_text(
        json.dumps({"scheduled_tasks": {}, "last_run": {"solo": state}}, indent=2),
        encoding="utf-8",
    )

    for _ in range(5):
        repo.record_skip("solo", "breaker_open", breaker="open", consecutive_failures=5)
        current = _last_run(root, "solo")
        assert current["at"] == tripped_at, "a skip restamped the failure time"
        breaker = RoutineExecutor(str(root), breaker_states={"solo": current})._breaker("solo")
        assert breaker.allow_request(), "the breaker never became probeable again"