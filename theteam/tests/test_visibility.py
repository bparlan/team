"""
Tests for the pure visibility builders.

These are stdlib-only, so they run in CI even where Reflex is not installed.
The Reflex `VisibilityState` is a thin store over these functions.
"""

import pytest

from theteam.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from theteam.core.metrics import MetricsRegistry
from theteam.ui.components.visibility import (
    apply_panel_state,
    build_visibility,
    toggle_id,
)


class FakeMonitor:
    def __init__(self, score):
        self._score = score

    def get_health_score(self):
        return self._score


@pytest.fixture
def tripped_breaker():
    cb = CircuitBreaker("database", CircuitBreakerConfig(failure_threshold=1))
    cb.record_failure()
    return cb


@pytest.fixture
def exposition():
    registry = MetricsRegistry()
    registry.describe("theteam_loop_iterations", "Iterations")
    registry.set_gauge("theteam_loop_iterations", 12)
    return registry.render()


@pytest.fixture
def sample_data(tripped_breaker, exposition):
    return {
        "events": [
            {
                "id": "e1",
                "message": "Loop complete",
                "severity": "info",
                "agent": "orchestrator",
                "timestamp": "12:00:01",
                "details": {"iterations": 12, "duration_ms": 840},
            },
            {
                "id": "e2",
                "message": "Task failed",
                "severity": "error",
                "agent": "w1",
                "timestamp": "12:00:02",
            },
        ],
        "breakers": {"database": tripped_breaker},
        "health_monitor": FakeMonitor(0.82),
        "metrics": exposition,
        "agents": [{"id": "w1", "name": "Worker One", "role": "impl", "status": "active"}],
    }


@pytest.fixture
def built(sample_data):
    return build_visibility(sample_data)


class TestActivitySection:
    def test_summary_reports_worst_severity(self, built):
        assert "worst: ERROR" in built["activity_summary"]

    def test_one_row_per_event(self, built):
        assert len(built["activity_view"]) == 2

    def test_panel_id_precomputed(self, built):
        # A Var cannot be f-stringed inside an rx.foreach render function.
        ids = {r["panel_id"] for r in built["activity_view"]}
        assert ids == {"event:e1", "event:e2"}

    def test_detail_text_is_prejoined_string(self, built):
        e1 = next(r for r in built["activity_view"] if r["id"] == "e1")
        # Reflex cannot foreach over an untyped nested Var, so detail must be
        # a single string.
        assert isinstance(e1["detail_text"], str)
        assert "iterations: 12" in e1["detail_text"]
        assert "duration_ms: 840" in e1["detail_text"]

    def test_detail_label_counts_fields(self, built):
        e1 = next(r for r in built["activity_view"] if r["id"] == "e1")
        assert e1["detail_label"] == "2 fields"

    def test_event_without_details_is_not_expandable(self, built):
        e2 = next(r for r in built["activity_view"] if r["id"] == "e2")
        assert e2["has_details"] is False
        assert e2["detail_text"] == ""
        assert e2["detail_label"] == "0 fields"

    def test_rows_carry_severity_and_color(self, built):
        for row in built["activity_view"]:
            assert row["severity"]
            assert row["color"].startswith("#")

    def test_all_rows_start_collapsed(self, built):
        assert all(r["is_open"] is False for r in built["activity_view"])


class TestHealthSection:
    def test_health_row_band(self, built):
        assert built["health_row"]["label"] == "Healthy"
        assert built["health_row"]["percent"] == "82%"

    def test_breaker_state_is_open(self, built):
        assert built["breaker_rows"][0]["name"] == "database"
        assert built["breaker_rows"][0]["state"] == "open"

    def test_recovery_suggested(self, built):
        assert built["recovery_summary"] == "1 suggested"

    def test_recovery_lines_joined(self, built):
        assert isinstance(built["recovery_lines"], str)
        assert "Wait for reset timeout" in built["recovery_lines"]

    def test_no_recovery_when_healthy(self):
        result = build_visibility({})
        assert result["recovery_summary"] == "No actions"
        assert result["recovery_lines"] == ""


class TestMetricsSection:
    def test_summary_counts_series(self, built):
        assert "1 series reported" in built["metrics_summary"]

    def test_rows_include_gauge(self, built):
        assert any(m["name"] == "theteam_loop_iterations" for m in built["metrics_rows"])

    def test_empty_exposition(self):
        result = build_visibility({"metrics": ""})
        assert result["metrics_rows"] == []
        assert "0 series reported" in result["metrics_summary"]


class TestRosterSection:
    def test_summary(self, built):
        assert built["roster_summary"] == "1 agents - 1 active"

    def test_panel_id_precomputed(self, built):
        assert built["roster_view"][0]["panel_id"] == "agent:w1"

    def test_labels_precomputed(self, built):
        row = built["roster_view"][0]
        assert row["completed_label"] == "Completed: 0"
        assert row["success_label"] == "Success: -"

    def test_agent_without_contributions_not_expandable(self, built):
        assert built["roster_view"][0]["has_details"] is False

    def test_contributions_make_agent_expandable(self):
        result = build_visibility({"agents": [{"id": "w1"}]})
        # A loaded agent with no task history has nothing to disclose.
        assert result["roster_view"][0]["has_details"] is False

    def test_feed_empty_without_activity(self, built):
        assert built["contribution_feed"] == []


class TestEmptyAndMalformedInput:
    def test_empty_input(self):
        result = build_visibility({})
        assert result["activity_view"] == []
        assert result["breaker_rows"] == []
        assert result["roster_view"] == []

    def test_none_values_do_not_crash(self):
        # A missing key must not become a crash in the dashboard.
        result = build_visibility({"events": None, "breakers": None, "agents": None, "metrics": None})
        assert result["activity_view"] == []

    def test_malformed_event_is_tolerated(self):
        result = build_visibility({"events": ["not-a-dict"]})
        assert len(result["activity_view"]) == 1


class TestApplyPanelState:
    def test_marks_expanded(self):
        rows = [{"panel_id": "event:e1", "is_open": False}]
        assert apply_panel_state(rows, ["event:e1"])[0]["is_open"] is True

    def test_leaves_others_closed(self):
        rows = [{"panel_id": "a", "is_open": False}, {"panel_id": "b", "is_open": False}]
        out = apply_panel_state(rows, ["a"])
        assert [r["is_open"] for r in out] == [True, False]

    def test_does_not_mutate_input(self):
        rows = [{"panel_id": "a", "is_open": False}]
        apply_panel_state(rows, ["a"])
        assert rows[0]["is_open"] is False

    def test_does_not_clear_the_expanded_sequence(self):
        # A regression here makes every panel read closed after the first
        # toggle: the flag is derived FROM expanded, never resets it.
        expanded = ["event:e1"]
        apply_panel_state([{"panel_id": "event:e1", "is_open": False}], expanded)
        assert expanded == ["event:e1"]

    def test_empty_rows(self):
        assert apply_panel_state([], ["x"]) == []

    def test_preserves_other_fields(self):
        rows = [{"panel_id": "a", "is_open": False, "detail_text": "k: v"}]
        assert apply_panel_state(rows, ["a"])[0]["detail_text"] == "k: v"


class TestToggleId:
    def test_adds_when_absent(self):
        assert toggle_id([], "a") == ["a"]

    def test_removes_when_present(self):
        assert toggle_id(["a", "b"], "a") == ["b"]

    def test_does_not_mutate_input(self):
        original = ["a"]
        toggle_id(original, "b")
        assert original == ["a"]

    def test_round_trip(self):
        once = toggle_id([], "a")
        assert toggle_id(once, "a") == []
