"""
Reflex state backing the Phase 5 visibility layer.

Thin storage over the pure builders in `theteam.ui.components.visibility`.
All the work happens in stdlib functions that CI can test without Reflex;
this class only stores their results and owns the disclosure panel state.
"""

from typing import Any, Dict, List

import reflex as rx

from theteam.ui.components.visibility import apply_panel_state, build_visibility, toggle_id


class VisibilityState(rx.State):
    """Reactive state for the activity, health, metrics and roster views."""

    activity_view: List[Dict] = []
    activity_summary: str = "No events"

    health_row: Dict = {}
    breaker_rows: List[Dict] = []
    recovery_rows: List[Dict] = []
    recovery_summary: str = "No actions"
    recovery_lines: str = ""

    metrics_rows: List[Dict] = []
    metrics_summary: str = ""

    roster_view: List[Dict] = []
    roster_summary: str = "No agents registered"
    contribution_feed: List[Dict] = []

    error: str = ""

    # Panel ids currently expanded, plus a flag for the static health panel.
    expanded_panels: List[str] = []
    health_recovery_open: bool = False

    def toggle_panel(self, panel_id: str):
        """Expand or collapse one detail panel."""
        self.expanded_panels = toggle_id(self.expanded_panels, panel_id)
        self._apply_panel_state()

    def toggle_health_recovery(self):
        """Expand or collapse the dashboard's recovery-actions panel."""
        self.health_recovery_open = not self.health_recovery_open

    def collapse_all(self):
        """Collapse every detail panel across all components."""
        self.expanded_panels = []
        self.health_recovery_open = False
        self._apply_panel_state()

    def _apply_panel_state(self) -> None:
        """Re-stamp the open flag onto the precomputed rows."""
        self.activity_view = apply_panel_state(self.activity_view, self.expanded_panels)
        self.roster_view = apply_panel_state(self.roster_view, self.expanded_panels)

    def load_visibility(self, data: Dict[str, Any]):
        """
        Rebuild every view from supplied live core data.

        Accepts pre-serialized data so this state behaves identically against a
        live process and against fixtures.
        """
        try:
            for field, value in build_visibility(data).items():
                setattr(self, field, value)
            self._apply_panel_state()
            self.error = ""
        except Exception as exc:  # surfaced in the UI rather than swallowed
            self.error = str(exc)
