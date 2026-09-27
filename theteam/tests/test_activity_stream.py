"""Tests for the ActivityStream component."""

import pytest

from theteam.ui.components.activity_stream import (
    MAX_EVENTS,
    ActivityEvent,
    ActivityStream,
    stream_from_events,
)
from theteam.ui.components.design_tokens import Severity


@pytest.fixture
def stream():
    return ActivityStream()


class TestEventNormalization:
    def test_from_dict_reads_canonical_fields(self):
        event = ActivityEvent.from_dict(
            {
                "id": "e1",
                "message": "Loop iteration complete",
                "severity": "warning",
                "agent": "orchestrator",
                "timestamp": "12:00:01",
                "details": {"iterations": 3},
            }
        )
        assert event.id == "e1"
        assert event.message == "Loop iteration complete"
        assert event.severity == Severity.WARNING
        assert event.agent == "orchestrator"
        assert event.timestamp == "12:00:01"
        assert event.has_details

    def test_accepts_field_aliases(self):
        event = ActivityEvent.from_dict(
            {"event_id": "e9", "event": "aliased", "level": "err", "source": "sa_runner"}
        )
        assert event.id == "e9"
        assert event.message == "aliased"
        assert event.severity == Severity.ERROR
        assert event.agent == "sa_runner"

    def test_missing_fields_get_safe_defaults(self):
        event = ActivityEvent.from_dict({})
        assert event.severity == Severity.INFO
        assert event.agent == "system"
        assert event.message == ""
        assert not event.has_details

    def test_non_dict_input_does_not_raise(self):
        # A malformed event must not break the stream that reports problems.
        event = ActivityEvent.from_dict("something went wrong")
        assert event.message == "something went wrong"

    def test_generated_id_is_unique_within_batch(self):
        events = [ActivityEvent.from_dict({}, index=i) for i in range(5)]
        assert len({e.id for e in events}) == 5

    def test_severity_drives_color(self):
        from theteam.ui.components.design_tokens import DesignTokens

        tokens = DesignTokens()
        crit = ActivityEvent.from_dict({"severity": "critical"})
        info = ActivityEvent.from_dict({"severity": "info"})
        assert crit.color == tokens.severity_color(Severity.CRITICAL)
        assert crit.color != info.color


class TestOrdering:
    def test_newest_first_by_default(self, stream):
        stream.extend(
            [
                {"id": "a", "message": "first", "timestamp": "12:00:01"},
                {"id": "b", "message": "second", "timestamp": "12:00:02"},
                {"id": "c", "message": "third", "timestamp": "12:00:03"},
            ]
        )
        assert [e.id for e in stream.visible()] == ["c", "b", "a"]

    def test_oldest_first_on_request(self, stream):
        stream.extend(
            [
                {"id": "a", "message": "first", "timestamp": "12:00:01"},
                {"id": "b", "message": "second", "timestamp": "12:00:02"},
            ]
        )
        assert [e.id for e in stream.events(newest_first=False)] == ["a", "b"]

    def test_visible_respects_limit(self, stream):
        for i in range(10):
            stream.add({"id": f"e{i}", "message": f"m{i}", "timestamp": f"12:00:{i:02d}"})
        assert len(stream.visible(limit=3)) == 3

    def test_mixed_timestamp_types_do_not_raise(self, stream):
        from datetime import datetime

        stream.extend(
            [
                {"id": "a", "timestamp": "12:00:01"},
                {"id": "b", "timestamp": datetime(2026, 1, 1, 12, 0, 2)},
                {"id": "c", "timestamp": None},
            ]
        )
        assert len(stream.events()) == 3

    def test_malformed_timestamps_sort_deterministically(self, stream):
        stream.extend(
            [{"id": "a", "timestamp": "not-a-time"}, {"id": "b", "timestamp": "also-bad"}]
        )
        # Unparseable timestamps must not make ordering depend on dict order.
        assert [e.id for e in stream.events()] == [e.id for e in stream.events()]


class TestRetention:
    def test_bounded_at_max_events(self):
        stream = ActivityStream(max_events=5)
        for i in range(20):
            stream.add({"id": f"e{i}", "message": "m", "timestamp": f"12:00:{i:02d}"})
        assert len(stream) == 5

    def test_retention_keeps_the_newest(self):
        stream = ActivityStream(max_events=3)
        for i in range(10):
            stream.add({"id": f"e{i}", "timestamp": f"12:00:{i:02d}"})
        assert {e.id for e in stream._events} == {"e7", "e8", "e9"}

    def test_default_bound_is_finite(self):
        # An unbounded stream would grow without limit in a long-running process.
        assert MAX_EVENTS > 0
        assert MAX_EVENTS <= 100_000

    def test_zero_max_events_is_rejected(self):
        with pytest.raises(ValueError):
            ActivityStream(max_events=0)

    def test_clear_empties(self, stream):
        stream.add({"message": "x"})
        stream.clear()
        assert len(stream) == 0


class TestSeverityAggregation:
    def test_counts_by_severity_includes_zeroes(self, stream):
        stream.add({"message": "a", "severity": "error"})
        counts = stream.counts_by_severity()
        assert counts[Severity.ERROR] == 1
        assert counts[Severity.CRITICAL] == 0

    def test_worst_severity_reports_most_urgent(self, stream):
        stream.extend(
            [{"message": "a", "severity": "info"}, {"message": "b", "severity": "critical"}]
        )
        assert stream.worst_severity() == Severity.CRITICAL

    def test_worst_severity_of_empty_stream_is_info(self, stream):
        assert stream.worst_severity() == Severity.INFO

    def test_filter_by_severity_includes_worse(self, stream):
        stream.extend(
            [
                {"id": "i", "message": "info", "severity": "info"},
                {"id": "w", "message": "warn", "severity": "warning"},
                {"id": "e", "message": "err", "severity": "error"},
            ]
        )
        got = {e.id for e in stream.filter_by_severity("warning")}
        assert got == {"w", "e"}

    def test_filter_by_agent(self, stream):
        stream.extend(
            [
                {"id": "1", "message": "a", "agent": "worker-1"},
                {"id": "2", "message": "b", "agent": "worker-2"},
            ]
        )
        assert [e.id for e in stream.filter_by_agent("worker-2")] == ["2"]


class TestDrillDown:
    def test_detail_rows_for_known_event(self, stream):
        stream.add({"id": "e1", "message": "m", "details": {"b": 2, "a": 1}})
        rows = stream.detail_rows("e1")
        assert rows == [("a", "1"), ("b", "2")]

    def test_detail_rows_for_unknown_event_is_empty(self, stream):
        # A stale UI selection must not crash the render.
        assert stream.detail_rows("does-not-exist") == []

    def test_detail_rows_empty_when_no_details(self, stream):
        stream.add({"id": "e1", "message": "m"})
        assert stream.detail_rows("e1") == []


class TestRenderRows:
    def test_rows_carry_color_and_severity(self, stream):
        stream.add({"id": "e1", "message": "boom", "severity": "error"})
        row = stream.rows()[0]
        assert row["severity"] == Severity.ERROR
        assert row["message"] == "boom"
        assert row["color"].startswith("#")
        assert row["expandable"] == "False"

    def test_expandable_flag_tracks_details(self, stream):
        stream.add({"id": "e1", "message": "m", "details": {"k": "v"}})
        assert stream.rows()[0]["expandable"] == "True"

    def test_summary_line_empty(self, stream):
        assert stream.summary_line() == "No events"

    def test_summary_line_singular_and_plural(self, stream):
        stream.add({"message": "a"})
        assert stream.summary_line() == "1 event - worst: INFO"
        stream.add({"message": "b", "severity": "error"})
        assert stream.summary_line() == "2 events - worst: ERROR"


class TestFactory:
    def test_stream_from_events_populates(self):
        stream = stream_from_events([{"message": "a"}, {"message": "b"}])
        assert len(stream) == 2

    def test_stream_from_honours_max_events(self):
        stream = stream_from_events([{"message": str(i)} for i in range(50)], max_events=4)
        assert len(stream) == 4
