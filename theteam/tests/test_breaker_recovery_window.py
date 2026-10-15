"""
`RoutineExecutor._breaker` restores the circuit breaker's recovery deadline from
the persisted `at` timestamp rather than recomputing it from process start.

The defect this file guards: `record_failure()` was replayed N times on every
reconstruction, and each replay stamped `recovery_deadline = now + 60s`. A CLI
invocation lives milliseconds and `serve` rebuilds the executor on every tick,
so the 60s window could never elapse -- the breaker reopened on each attempt
and the task was permanently unrunnable.

The fix restores `recovery_deadline` from `last_run[task_id].at` (already
persisted) plus `recovery_timeout`, then calls `_evaluate_state()`. These tests
exercise that restoration directly through the public-ish `_breaker` method.
"""

from datetime import datetime, timedelta, timezone

from theteam.routines.executor import RoutineExecutor


def _executor(breaker_states):
    """A RoutineExecutor that never touches the filesystem for breaker state."""
    return RoutineExecutor(".", breaker_states=breaker_states)


def _past(minutes=10):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ======= 1. an old trip admits a request (the fix) =======


def test_breaker_with_old_failure_admits_a_request(tmp_path):
    """
    Five consecutive failures recorded ten minutes ago: the recovery window
    has long elapsed, so the rebuilt breaker must NOT be permanently open.
    `allow_request()` is True (half_open admits a probe).

    REVERTING-CHECK: this assertion is the one that fails if the `at`-restoration
    block in `RoutineExecutor._breaker` is removed. Without it, `record_failure()`
    leaves `recovery_deadline = now + 60s` (stamped during replay), the window
    never elapses across process boundaries, and `allow_request()` returns
    False -- the task stays permanently unrunnable, which is the exact defect
    this file exists to catch.
    """
    executor = _executor({
        "solo": {
            "breaker": "open",
            "breaker_consecutive_failures": 5,
            "at": _past(minutes=10),
        }
    })

    breaker = executor._breaker("solo")

    assert breaker.stats.state.value in ("half_open", "closed")
    assert breaker.allow_request() is True


# ======= 2. a fresh trip still blocks (opposite over-correction) =======


def test_breaker_with_recent_failure_stays_open(tmp_path):
    """
    Five consecutive failures recorded just now: the recovery window has not
    elapsed, so the rebuilt breaker must still block. Guards against the
    opposite over-correction -- always admitting, which would nullify the
    breaker entirely.
    """
    executor = _executor({
        "solo": {
            "breaker": "open",
            "breaker_consecutive_failures": 5,
            "at": _now_iso(),
        }
    })

    breaker = executor._breaker("solo")

    assert breaker.stats.state.value == "open"
    assert breaker.allow_request() is False


# ======= 3. malformed `at` must not crash =======


def test_breaker_with_unparseable_at_falls_back_safely(tmp_path):
    """
    An `at` value that cannot be parsed must not raise. The restoration is
    skipped, the breaker stays where replay left it (open, with a deadline
    measured from this process), and no exception escapes `_breaker`.
    """
    executor = _executor({
        "solo": {
            "breaker": "open",
            "breaker_consecutive_failures": 5,
            "at": "not-a-timestamp",
        }
    })

    breaker = executor._breaker("solo")

    # Falls back to the replayed state: still open, still blocking.
    assert breaker.stats.state.value == "open"
    assert breaker.allow_request() is False


# ======= 4. naive (tz-unaware) ISO must not raise TypeError =======


def test_breaker_with_naive_iso_timestamp_does_not_raise(tmp_path):
    """
    A naive ISO 8601 string (no tzinfo) is a legitimate persisted value. The
    restoration must normalize it to UTC instead of raising TypeError when
    compared against an aware datetime.
    """
    naive = (datetime.now(timezone.utc) - timedelta(minutes=10)).replace(
        tzinfo=None
    ).isoformat()

    executor = _executor({
        "solo": {
            "breaker": "open",
            "breaker_consecutive_failures": 5,
            "at": naive,
        }
    })

    breaker = executor._breaker("solo")

    # No TypeError; the old window admits the request.
    assert breaker.allow_request() is True