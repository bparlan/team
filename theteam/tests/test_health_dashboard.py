"""Tests for the HealthDashboard component, against real circuit breakers."""

import time

import pytest

from theteam.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from theteam.ui.components.design_tokens import Palette
from theteam.ui.components.health_dashboard import HealthDashboard, RecoveryAction


class FakeMonitor:
    """Minimal stand-in exposing the HealthMonitor surface the dashboard reads."""

    def __init__(self, score):
        self._score = score

    def get_health_score(self):
        return self._score


@pytest.fixture
def dashboard():
    return HealthDashboard()


def tripped_breaker(name="db", threshold=3, recovery=60):
    """A breaker driven to OPEN."""
    cb = CircuitBreaker(name, CircuitBreakerConfig(failure_threshold=threshold, recovery_timeout=recovery))
    for _ in range(threshold):
        cb.record_failure()
    return cb


class TestHealthScore:
    def test_reads_score_from_monitor(self, dashboard):
        assert dashboard.health_score(FakeMonitor(0.87)) == 0.87

    def test_missing_monitor_is_zero_not_a_crash(self, dashboard):
        assert dashboard.health_score(None) == 0.0

    @pytest.mark.parametrize("junk", ["high", None, object()])
    def test_unreadable_score_degrades_to_zero(self, dashboard, junk):
        assert dashboard.health_score(FakeMonitor(junk)) == 0.0

    @pytest.mark.parametrize(
        "raw,expected", [(-3.0, 0.0), (7.0, 1.0), (0.5, 0.5)]
    )
    def test_score_is_clamped(self, dashboard, raw, expected):
        assert dashboard.health_score(FakeMonitor(raw)) == expected

    def test_falls_back_to_status_dict(self, dashboard):
        class DictMonitor:
            def get_health_status(self):
                return {"health_score": 0.42}

        assert dashboard.health_score(DictMonitor()) == 0.42

    def test_raising_monitor_degrades(self, dashboard):
        class Exploding:
            def get_health_score(self):
                raise RuntimeError("boom")

        assert dashboard.health_score(Exploding()) == 0.0

    def test_health_row_reports_band(self, dashboard):
        row = dashboard.health_row(FakeMonitor(0.9))
        assert row["label"] == "Healthy"
        assert row["percent"] == "90%"
        assert row["color"] == Palette.success

    def test_health_row_critical(self, dashboard):
        row = dashboard.health_row(FakeMonitor(0.1))
        assert row["label"] == "Critical"
        assert row["color"] == Palette.danger


class TestBreakerRows:
    def test_reads_live_breaker_state(self, dashboard):
        cb = tripped_breaker("db", threshold=3)
        rows = dashboard.breaker_rows({"db": cb})
        assert rows[0]["name"] == "db"
        assert rows[0]["state"] == "open"
        assert rows[0]["color"] == Palette.danger

    def test_failures_and_threshold_come_from_config(self, dashboard):
        cb = CircuitBreaker("api", CircuitBreakerConfig(failure_threshold=7))
        cb.record_failure()
        row = dashboard.breaker_rows({"api": cb})[0]
        assert row["failures"] == 1
        assert row["threshold"] == 7

    def test_closed_breaker_reads_green(self, dashboard):
        cb = CircuitBreaker("cache")
        row = dashboard.breaker_rows({"cache": cb})[0]
        assert row["state"] == "closed"
        assert row["color"] == Palette.success

    def test_tripped_breakers_sorted_first(self, dashboard):
        breakers = {
            "aaa-closed": CircuitBreaker("aaa"),
            "zzz-open": tripped_breaker("zzz", threshold=2),
        }
        rows = dashboard.breaker_rows(breakers)
        assert rows[0]["state"] == "open"
        assert rows[1]["state"] == "closed"

    def test_empty_breakers(self, dashboard):
        assert dashboard.breaker_rows({}) == []

    def test_max_breakers_caps_rows(self):
        dash = HealthDashboard(max_breakers=2)
        breakers = {f"b{i}": CircuitBreaker(f"b{i}") for i in range(5)}
        assert len(dash.breaker_rows(breakers)) == 2

    def test_half_open_is_not_treated_as_healthy(self, dashboard):
        cb = CircuitBreaker("half", CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0))
        cb.record_failure()
        cb.record_failure()  # deadline elapsed -> half open
        assert cb.stats.state == CircuitState.HALF_OPEN
        row = dashboard.breaker_rows({"half": cb})[0]
        assert row["state"] == "half_open"
        assert row["color"] == Palette.warning


class TestRecoveryActions:
    def test_open_breaker_produces_pending_action(self, dashboard):
        actions = dashboard.recovery_actions({"db": tripped_breaker("db", threshold=2)})
        assert len(actions) == 1
        assert actions[0].status == "pending"
        assert actions[0].target == "db"

    def test_half_open_produces_in_progress_action(self, dashboard):
        cb = CircuitBreaker("half", CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0))
        cb.record_failure()
        cb.record_failure()
        actions = dashboard.recovery_actions({"half": cb})
        assert actions[0].status == "in_progress"

    def test_closed_breakers_produce_no_actions(self, dashboard):
        assert dashboard.recovery_actions({"ok": CircuitBreaker("ok")}) == []

    def test_critical_health_adds_triage_action(self, dashboard):
        actions = dashboard.recovery_actions({}, FakeMonitor(0.05))
        assert any("Triage" in a.action for a in actions)

    def test_healthy_health_adds_no_triage_action(self, dashboard):
        assert dashboard.recovery_actions({}, FakeMonitor(0.95)) == []

    def test_missing_monitor_adds_no_triage_action(self, dashboard):
        # A dashboard with no monitor is not the same as a critical system.
        assert dashboard.recovery_actions({}, None) == []

    def test_action_color_reflects_status(self):
        assert RecoveryAction("a", "completed", "d").color == Palette.success
        assert RecoveryAction("a", "failed", "d").color == Palette.danger
        assert RecoveryAction("a", "weird", "d").color == Palette.neutral


class TestStatus:
    def test_status_payload_has_all_sections(self, dashboard):
        status = dashboard.status(FakeMonitor(0.9), {"db": tripped_breaker("db", threshold=2)})
        assert set(status) == {"health", "breakers", "tripped", "actions", "summary"}
        assert status["health"]["label"] == "Healthy"
        assert len(status["tripped"]) == 1

    def test_summary_counts_closed_breakers(self, dashboard):
        breakers = {"ok": CircuitBreaker("ok"), "bad": tripped_breaker("bad", threshold=2)}
        assert "1/2 breakers closed" in dashboard.summary(FakeMonitor(0.9), dashboard.breaker_rows(breakers))

    def test_status_with_no_monitor_and_no_breakers(self, dashboard):
        status = dashboard.status(None, {})
        assert status["breakers"] == []
        assert status["health"]["label"] == "Critical"
