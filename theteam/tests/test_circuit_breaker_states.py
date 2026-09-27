"""
Tests for the circuit breaker state machine.

Regression cover for the bug the Phase 5 health dashboard exposed:
`record_failure()` incremented counters but nothing ever assigned
`stats.state`, so a breaker could never trip and `allow_request()` always
returned True.
"""

import time

import pytest

from theteam.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)


def make(**kwargs):
    defaults = {"failure_threshold": 3, "recovery_timeout": 60}
    defaults.update(kwargs)
    return CircuitBreaker("test", CircuitBreakerConfig(**defaults))


def trip(cb, times=3):
    for _ in range(times):
        cb.record_failure()


class TestTripping:
    def test_starts_closed(self):
        assert make().stats.state == CircuitState.CLOSED

    def test_stays_closed_below_threshold(self):
        cb = make(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.stats.state == CircuitState.CLOSED

    def test_trips_at_threshold(self):
        cb = make(failure_threshold=3)
        trip(cb)
        assert cb.stats.state == CircuitState.OPEN

    def test_threshold_of_one_trips_immediately(self):
        cb = make(failure_threshold=1)
        cb.record_failure()
        assert cb.stats.state == CircuitState.OPEN

    def test_zero_threshold_is_treated_as_one(self):
        # A zero threshold must not make the breaker permanently open via
        # division or negative comparisons.
        cb = make(failure_threshold=0)
        cb.record_failure()
        assert cb.stats.state == CircuitState.OPEN

    def test_success_resets_consecutive_failures(self):
        cb = make(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        trip(cb, times=2)
        assert cb.stats.state == CircuitState.CLOSED

    def test_open_sets_recovery_deadline(self):
        cb = make(failure_threshold=1, recovery_timeout=30)
        cb.record_failure()
        assert cb.stats.recovery_deadline is not None


class TestBlocking:
    def test_open_breaker_blocks_requests(self):
        cb = make(failure_threshold=1)
        cb.record_failure()
        assert cb.allow_request() is False

    def test_closed_breaker_allows_requests(self):
        assert make().allow_request() is True

    def test_allow_request_does_not_mutate_closed_state(self):
        cb = make()
        for _ in range(10):
            cb.allow_request()
        assert cb.stats.state == CircuitState.CLOSED


class TestHalfOpen:
    def test_opens_to_half_open_after_timeout(self):
        cb = make(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        assert cb.stats.state == CircuitState.OPEN
        cb.allow_request()  # deadline elapsed -> probe admitted
        assert cb.stats.state == CircuitState.HALF_OPEN

    def test_stays_open_before_deadline(self):
        cb = make(failure_threshold=1, recovery_timeout=600)
        cb.record_failure()
        cb.allow_request()
        assert cb.stats.state == CircuitState.OPEN

    def test_half_open_admits_bounded_probes(self):
        cb = make(failure_threshold=1, recovery_timeout=0, max_requests_in_half_open=2)
        cb.record_failure()
        grants = [cb.allow_request() for _ in range(4)]
        assert grants == [True, True, False, False]

    def test_successful_probe_closes_circuit(self):
        cb = make(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        cb.allow_request()
        cb.record_success()
        assert cb.stats.state == CircuitState.CLOSED

    def test_failed_probe_reopens_circuit(self):
        cb = make(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        cb.allow_request()
        cb.record_failure()
        assert cb.stats.state == CircuitState.OPEN

    def test_failed_probe_backs_off(self):
        from datetime import datetime, timedelta, timezone

        cb = make(failure_threshold=1, recovery_timeout=10, backoff_multiplier=2.0)
        cb.record_failure()
        # A probe is only admitted once the recovery deadline has elapsed.
        cb.stats.recovery_deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert cb.allow_request() is True
        assert cb.stats.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.stats.backoff_timeout == 20.0

    def test_backoff_is_capped(self):
        cb = make(
            failure_threshold=1,
            recovery_timeout=10,
            backoff_multiplier=10.0,
            max_backoff=100,
        )
        cb.record_failure()
        for _ in range(5):
            cb.allow_request()
            cb.record_failure()
        assert cb.stats.backoff_timeout <= 100

    def test_recovery_clears_backoff(self):
        cb = make(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        cb.allow_request()
        cb.record_failure()
        assert cb.stats.backoff_timeout > 0

        # A failed probe backs the breaker off, so recovery is not immediate:
        # the deadline must actually elapse before a probe is admitted.
        from datetime import datetime, timedelta, timezone

        cb.stats.recovery_deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
        cb.allow_request()
        assert cb.stats.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.stats.backoff_timeout == 0
        assert cb.stats.state == CircuitState.CLOSED

class TestFullCycle:
    def test_closed_open_halfopen_closed(self):
        cb = make(failure_threshold=2, recovery_timeout=0)
        assert cb.stats.state == CircuitState.CLOSED
        cb.record_failure()
        cb.record_failure()
        assert cb.stats.state == CircuitState.OPEN
        assert cb.allow_request() is True
        assert cb.stats.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.stats.state == CircuitState.CLOSED

    def test_survives_repeated_cycles(self):
        cb = make(failure_threshold=1, recovery_timeout=0)
        seen = []
        for _ in range(4):
            cb.record_failure()
            seen.append(cb.stats.state)
            cb.allow_request()
            seen.append(cb.stats.state)
            cb.record_success()
            seen.append(cb.stats.state)
        assert seen.count(CircuitState.OPEN) == 4
        assert cb.stats.state == CircuitState.CLOSED


class TestHealthScoreTripping:
    def test_low_health_score_trips_breaker(self):
        cb = make(failure_threshold=100, health_score_threshold=0.7)
        cb.set_health_score_callback(lambda: 0.3)
        cb.record_success()  # a success still evaluates health
        assert cb.stats.state == CircuitState.OPEN

    def test_healthy_score_keeps_closed(self):
        cb = make(failure_threshold=100, health_score_threshold=0.7)
        cb.set_health_score_callback(lambda: 0.95)
        cb.record_success()
        assert cb.stats.state == CircuitState.CLOSED

    def test_raising_health_callback_does_not_trip(self):
        # A broken health probe must not take the system down.
        cb = make(failure_threshold=100)

        def boom():
            raise RuntimeError("probe failed")

        cb.set_health_score_callback(boom)
        cb.record_success()
        assert cb.stats.state == CircuitState.CLOSED


class TestCallbacks:
    def test_state_change_callback_fires_on_transitions(self):
        cb = make(failure_threshold=1)
        changes = []
        cb.set_on_state_change_callback(lambda old, new: changes.append((old, new)))
        cb.record_failure()
        assert changes == [(CircuitState.CLOSED, CircuitState.OPEN)]

    def test_callback_not_fired_without_transition(self):
        cb = make(failure_threshold=5)
        changes = []
        cb.set_on_state_change_callback(lambda old, new: changes.append((old, new)))
        cb.record_failure()
        assert changes == []

    def test_raising_callback_does_not_break_breaker(self):
        cb = make(failure_threshold=1)

        def boom(old, new):
            raise RuntimeError("listener exploded")

        cb.set_on_state_change_callback(boom)
        cb.record_failure()
        assert cb.stats.state == CircuitState.OPEN


class TestStateChangeCallbackNoneSafety:
    def test_no_callback_is_fine(self):
        cb = make(failure_threshold=1)
        cb.record_failure()
        assert cb.stats.state == CircuitState.OPEN


class TestConcurrency:
    def test_parallel_failures_trip_exactly_once(self):
        import threading

        cb = make(failure_threshold=5)
        barrier = threading.Barrier(20)

        def worker():
            barrier.wait()
            cb.record_failure()

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert cb.stats.state == CircuitState.OPEN
        assert cb.stats.consecutive_failures == 20
