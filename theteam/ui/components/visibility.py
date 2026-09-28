"""
Pure builders for the Phase 5 visibility layer.

Reflex `rx.State` event handlers intercept attribute assignment, so state
mutation cannot be unit-tested outside a running reflex runtime. All the real
work therefore lives here as plain stdlib functions, and `VisibilityState`
only stores their results. This module imports no Reflex, so it is covered by
CI even where Reflex is not installed.
"""

from typing import Any, Dict, List, Sequence

from .disclosure import DisclosureGroup

from .activity_stream import ActivityStream
from .agent_roster import AgentRoster
from .health_dashboard import HealthDashboard
from .metrics_panel import MetricsPanel


def build_visibility(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build every render value the dashboard needs from live core data.

    Everything a template touches is resolved here: reflex Vars cannot be
    f-stringed, iterated, or branched on inside a page render function.

    This function is the **only** data source a renderer may read. A renderer
    that reaches past it - resolving paths, reading files, spawning a
    subprocess - is a second adapter, and that is how
    `task_stack_adapter.py` came to exist in M2. Presentation is a pure
    function of this view model, never a peer of it.

    Purity contract: the returned dict contains no path resolution, no file
    reads, and no subprocess calls. Same input, same output, every time.
    """
    stream = ActivityStream()
    stream.extend(data.get("events") or [])

    dashboard = HealthDashboard()
    status = dashboard.status(data.get("health_monitor"), data.get("breakers") or {})
    actions = status["actions"]

    panel = MetricsPanel()
    exposition = data.get("metrics") or ""

    roster = AgentRoster()
    roster.load(data.get("agents") or [])

    return {
        "activity_summary": stream.summary_line(),
        "activity_view": [_activity_row(stream, row) for row in stream.rows(limit=25)],
        "health_row": status["health"],
        "breaker_rows": status["breakers"],
        "recovery_rows": [
            {"action": a.action, "status": a.status, "description": a.description}
            for a in actions
        ],
        "recovery_summary": f"{len(actions)} suggested" if actions else "No actions",
        "recovery_lines": [f"{a.action}: {a.description}" for a in actions],
        "metrics_rows": panel.counters(exposition),
        "metrics_summary": f"{panel.summary(exposition)['series']} series reported",
        "roster_summary": roster.summary_line(),
        "roster_view": [_roster_row(roster, row) for row in roster.rows()],
        "contribution_feed": roster.contribution_feed(limit=10),
    }


def _activity_row(stream: ActivityStream, row: Dict[str, Any]) -> Dict[str, Any]:
    """Pre-render one activity event, including its drill-down detail."""
    details = stream.detail_rows(row["id"])
    return {
        **{k: v for k, v in row.items() if k != "expandable"},
        "panel_id": f"event:{row['id']}",
        "has_details": row["expandable"] == "True",
        "detail_label": f"{len(details)} fields",
        "detail_text": "\n".join(f"{k}: {v}" for k, v in details),
        "is_open": False,
    }


def _roster_row(roster: AgentRoster, row: Dict[str, Any]) -> Dict[str, Any]:
    """Pre-render one roster row, including its contribution detail."""
    contributions = (roster.detail(row["id"]) or {}).get("contributions") or []
    return {
        **row,
        "panel_id": f"agent:{row['id']}",
        "has_details": bool(contributions),
        "detail_label": f"{len(contributions)} recent tasks",
        "detail_text": "\n".join(f"{c['task']}: {c['status']}" for c in contributions),
        "completed_label": f"Completed: {row['tasks_completed']}",
        "failed_label": f"Failed: {row['tasks_failed']}",
        "success_label": f"Success: {row['success_rate']}",
        "is_open": False,
    }


def apply_panel_state(
    rows: Sequence[Dict[str, Any]], expanded: Sequence[str]
) -> List[Dict[str, Any]]:
    """
    Stamp the open flag onto precomputed rows.

    A reflex dict Var cannot be indexed by a Var key, so the flag is resolved
    here, at update time, and the templates just read a plain field. Delegates
    to DisclosureGroup so the expansion state has exactly one implementation.
    The `expanded` sequence is never mutated - deriving from it and clearing it
    would make every panel read closed after the first toggle.
    """
    return DisclosureGroup(default_open=expanded).stamp(rows)


def toggle_id(expanded: Sequence[str], panel_id: str) -> List[str]:
    """Return the expanded-panel list with `panel_id` flipped."""
    group = DisclosureGroup(default_open=expanded)
    group.toggle(panel_id)
    return group.open_ids()
