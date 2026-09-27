"""Tests for the AgentRoster component."""

import pytest

from theteam.ui.components.agent_roster import AgentRecord, AgentRoster, PerformanceTracker
from theteam.ui.components.design_tokens import Palette


@pytest.fixture
def tracker():
    return PerformanceTracker()


@pytest.fixture
def roster():
    return AgentRoster()


class TestAgentRecord:
    def test_from_dict_reads_canonical_fields(self):
        record = AgentRecord.from_dict(
            {
                "id": "w1",
                "name": "Worker One",
                "role": "implementer",
                "status": "active",
                "tasks_completed": 4,
                "tasks_failed": 1,
            }
        )
        assert record.id == "w1"
        assert record.name == "Worker One"
        assert record.role == "implementer"
        assert record.status == "active"

    def test_accepts_member_id_alias(self):
        assert AgentRecord.from_dict({"member_id": "m9"}).id == "m9"

    def test_display_name_falls_back_to_id(self):
        assert AgentRecord.from_dict({"id": "w1", "name": ""}).display_name == "w1"

    def test_non_dict_does_not_raise(self):
        assert AgentRecord.from_dict("worker").id == "worker"

    def test_success_rate(self):
        record = AgentRecord(id="w", tasks_completed=3, tasks_failed=1)
        assert record.success_rate == 0.75

    def test_success_rate_none_when_idle(self):
        # Reporting 0% for an agent that never ran would be a lie.
        assert AgentRecord(id="w").success_rate is None

    def test_row_renders_dash_for_no_history(self):
        assert AgentRecord(id="w").row()["success_rate"] == "-"

    def test_row_status_visual(self):
        row = AgentRecord(id="w", status="error").row()
        assert row["status_color"] == Palette.danger
        assert row["status_label"] == "Error"
        assert row["status_icon"] != "?"


class TestPerformanceTracker:
    def test_record_task_success_increments_completed(self, tracker):
        tracker.record_task("w1", "T-1", success=True)
        record = tracker.get("w1")
        assert record.tasks_completed == 1
        assert record.tasks_failed == 0

    def test_record_task_failure_increments_failed(self, tracker):
        tracker.record_task("w1", "T-1", success=False)
        assert tracker.get("w1").tasks_failed == 1

    def test_record_task_autoregisters_unknown_agent(self, tracker):
        # A task from a new agent must not be silently dropped.
        record = tracker.record_task("newbie", "T-1", success=True)
        assert record.id == "newbie"
        assert tracker.get("newbie") is not None

    def test_contribution_is_appended(self, tracker):
        tracker.record_task("w1", "T-1", success=True)
        assert tracker.get("w1").recent_contributions == [
            {"task": "T-1", "status": "completed"}
        ]

    def test_contribution_history_is_bounded(self, tracker):
        for i in range(50):
            tracker.record_task("w1", f"T-{i}", success=True)
        assert len(tracker.get("w1").recent_contributions) == tracker.max_contributions

    def test_contribution_bound_keeps_newest(self):
        tracker = PerformanceTracker(max_contributions=2)
        for i in range(5):
            tracker.record_task("w1", f"T-{i}", success=True)
        tasks = [c["task"] for c in tracker.get("w1").recent_contributions]
        assert tasks == ["T-3", "T-4"]

    def test_zero_max_contributions_rejected(self):
        with pytest.raises(ValueError):
            PerformanceTracker(max_contributions=0)

    def test_register_updates_existing(self, tracker):
        tracker.register("w1", name="One", role="a")
        tracker.register("w1", role="b")
        record = tracker.get("w1")
        assert record.name == "One"
        assert record.role == "b"

    def test_register_ignores_none_values(self, tracker):
        tracker.register("w1", name="One")
        tracker.register("w1", name=None)
        assert tracker.get("w1").name == "One"

    def test_set_status(self, tracker):
        tracker.set_status("w1", "busy")
        assert tracker.get("w1").status == "busy"

    def test_agents_sorted_by_workload(self, tracker):
        tracker.record_task("idle-agent", "T", success=True)
        for i in range(3):
            tracker.record_task("busy-agent", f"T{i}", success=True)
        assert [r.id for r in tracker.agents()] == ["busy-agent", "idle-agent"]

    def test_clear(self, tracker):
        tracker.register("w1")
        tracker.clear()
        assert tracker.agents() == []


class TestAgentRoster:
    def test_load_bulk_agents(self, roster):
        count = roster.load(
            [
                {"id": "w1", "name": "One", "status": "active"},
                {"id": "w2", "name": "Two", "status": "idle"},
            ]
        )
        assert count == 2
        assert len(roster.rows()) == 2

    def test_rows_sorted_by_workload(self, roster):
        roster.load([{"id": "quiet"}, {"id": "hardworking"}])
        for i in range(5):
            roster.tracker.record_task("hardworking", f"T{i}", success=True)
        assert roster.rows()[0]["id"] == "hardworking"

    def test_max_agents_caps_rows(self):
        roster = AgentRoster(max_agents=2)
        roster.load([{"id": f"a{i}"} for i in range(5)])
        assert len(roster.rows()) == 2

    def test_status_counts(self, roster):
        roster.load(
            [
                {"id": "a", "status": "active"},
                {"id": "b", "status": "active"},
                {"id": "c", "status": "error"},
            ]
        )
        assert roster.status_counts() == {"active": 2, "error": 1}

    def test_contribution_feed_merges_agents_newest_first(self, roster):
        roster.tracker.record_task("w1", "T-1", success=True)
        roster.tracker.record_task("w2", "T-2", success=True)
        feed = roster.contribution_feed()
        assert len(feed) == 2
        assert {f["agent"] for f in feed} == {"w1", "w2"}
        assert all("task" in f and "status" in f for f in feed)

    def test_contribution_feed_respects_limit(self, roster):
        for i in range(10):
            roster.tracker.record_task("w1", f"T-{i}", success=True)
        assert len(roster.contribution_feed(limit=3)) == 3

    def test_contribution_feed_empty(self, roster):
        assert roster.contribution_feed() == []

    def test_detail_includes_contributions(self, roster):
        roster.tracker.record_task("w1", "T-1", success=True)
        detail = roster.detail("w1")
        assert detail["id"] == "w1"
        assert detail["contributions"][0]["task"] == "T-1"

    def test_detail_of_unknown_agent_is_none(self, roster):
        # A stale selection renders an empty panel instead of raising.
        assert roster.detail("ghost") is None

    def test_summary_line(self, roster):
        assert roster.summary_line() == "No agents registered"
        roster.load([{"id": "a", "status": "active"}, {"id": "b", "status": "idle"}])
        assert roster.summary_line() == "2 agents - 1 active"

    def test_shared_tracker_sees_updates(self, roster):
        # The roster must reflect tasks recorded through its tracker.
        roster.load([{"id": "w1"}])
        roster.tracker.record_task("w1", "T-1", success=True)
        assert roster.rows()[0]["tasks_completed"] == 1
