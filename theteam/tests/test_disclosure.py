"""Tests for progressive disclosure state shared across UI components."""

import pytest

from theteam.ui.components.disclosure import (
    COLLAPSED,
    EXPANDED,
    DisclosureGroup,
    disclosure_view,
)


@pytest.fixture
def group():
    return DisclosureGroup()


class TestDisclosureGroup:
    def test_starts_collapsed(self, group):
        assert group.is_open("panel") is False
        assert group.state("panel") == COLLAPSED

    def test_default_open_panels(self):
        group = DisclosureGroup(default_open=["a"])
        assert group.is_open("a") is True

    def test_toggle_flips_and_returns_new_state(self, group):
        assert group.toggle("p") is True
        assert group.toggle("p") is False

    def test_toggle_is_idempotent_per_call(self, group):
        group.toggle("p")
        group.toggle("p")
        assert group.is_open("p") is False

    def test_open_and_close(self, group):
        group.open("p")
        assert group.is_open("p")
        group.close("p")
        assert group.is_open("p") is False

    def test_collapse_all(self):
        group = DisclosureGroup(default_open=["a", "b", "c"])
        group.collapse_all()
        assert group.open_ids() == []

    def test_panels_are_independent(self, group):
        # The point of a shared group: expanding one must not close another.
        group.toggle("a")
        group.toggle("b")
        assert group.is_open("a") and group.is_open("b")
        group.toggle("a")
        assert group.is_open("b") is True

    def test_open_ids_is_sorted(self):
        group = DisclosureGroup(default_open=["z", "a", "m"])
        assert group.open_ids() == ["a", "m", "z"]

    def test_row_reports_state_and_icon(self, group):
        row = group.row("p", "Details")
        assert row["state"] == COLLAPSED
        assert row["icon"] == "▶"
        group.open("p")
        row = group.row("p", "Details")
        assert row["state"] == EXPANDED
        assert row["icon"] == "▼"

    def test_row_title_defaults_to_id(self, group):
        assert group.row("panel-1")["title"] == "panel-1"

    def test_rows_preserve_input_order(self):
        group = DisclosureGroup(default_open=["b"])
        rows = group.rows(["a", "b", "c"], {"a": "Alpha"})
        assert [r["id"] for r in rows] == ["a", "b", "c"]
        assert rows[0]["title"] == "Alpha"
        assert rows[1]["open"] is True


class TestDisclosureView:
    def test_detail_hidden_when_collapsed(self, group):
        # Progressive disclosure means the detail is not materialized at all
        # while collapsed - not merely hidden with CSS.
        view = disclosure_view(group, "p", "Title", summary="s", detail_rows=[("a", 1)])
        assert view["detail"] == []
        assert view["summary"] == "s"

    def test_detail_present_when_expanded(self, group):
        group.open("p")
        view = disclosure_view(group, "p", "Title", detail_rows=[("a", 1), ("b", 2)])
        assert view["detail"] == [["a", 1], ["b", 2]]

    def test_toggle_reveals_detail(self, group):
        view = disclosure_view(group, "p", "T", detail_rows=[("a", 1)])
        assert view["detail"] == []
        group.toggle("p")
        view = disclosure_view(group, "p", "T", detail_rows=[("a", 1)])
        assert len(view["detail"]) == 1

    def test_no_detail_rows_is_safe(self, group):
        group.open("p")
        assert disclosure_view(group, "p", "T")["detail"] == []

    def test_view_carries_state(self, group):
        assert disclosure_view(group, "p", "T")["state"] == COLLAPSED
        group.open("p")
        assert disclosure_view(group, "p", "T")["state"] == EXPANDED


class TestIntegrationAcrossComponents:
    def test_group_spans_activity_and_agents(self):
        # The shared group is what lets a caller collapse every detail panel
        # across different components at once.
        from theteam.ui.components.activity_stream import ActivityStream
        from theteam.ui.components.agent_roster import AgentRoster

        group = DisclosureGroup()
        stream = ActivityStream()
        stream.add({"id": "e1", "message": "m", "details": {"k": "v"}})
        roster = AgentRoster()
        roster.load([{"id": "w1"}])
        roster.tracker.record_task("w1", "T-1", success=True)

        group.open("event:e1")
        group.open("agent:w1")
        assert stream.detail_rows("e1") == [("k", "v")]
        assert len(roster.detail("w1")["contributions"]) == 1

        group.collapse_all()
        assert group.state("event:e1") == COLLAPSED
        assert group.state("agent:w1") == COLLAPSED
