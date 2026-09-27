"""
Activity Stream page - chronological, severity-coded agency events with
drill-down. Phase 5 task (a).
"""

from typing import Dict, List

import reflex as rx

from theteam.ui.web_dashboard.theteam_dashboard.visibility_state import VisibilityState
from theteam.ui.components.reflex_renderers import (
    disclosure_panel,
    page_header,
    severity_badge,
)



def _event_item(event: Dict) -> rx.Component:
    """Render one event: severity badge, agent, time, message, drill-down.

    Every value used here is pre-computed in `VisibilityState.activity_view`;
    a Var cannot be interpolated into an f-string or branched on with `if`
    inside an `rx.foreach` render function.
    """
    return rx.vstack(
        rx.hstack(
            severity_badge(event["severity"], event["color"]),
            rx.text(event["agent"], size="1", color_scheme="gray"),
            rx.text(event["timestamp"], size="1", color_scheme="gray"),
            spacing="2",
            align="center",
            width="100%",
        ),
        rx.text(event["message"], size="2"),
        rx.cond(
            event["has_details"],
            disclosure_panel(
                event["panel_id"],
                "Details",
                event["detail_label"],
                event["detail_text"],
                on_toggle=VisibilityState.toggle_panel(event["panel_id"]),
                is_open=event["is_open"],
            ),
        ),
        spacing="1",
        width="100%",
        padding_y="2",
    )


@rx.page(route="/activity", title="Activity Stream")
def activity() -> rx.Component:
    """Render the activity stream page."""

    return rx.container(
        rx.vstack(
            page_header(
                "Activity Stream",
                VisibilityState.activity_summary,
                on_collapse=VisibilityState.collapse_all,
            ),
            rx.cond(
                VisibilityState.error != "",
                rx.callout(VisibilityState.error, color="red"),
            ),
            rx.divider(),
            rx.card(
                rx.cond(
                    VisibilityState.activity_view.length() > 0,
                    rx.foreach(
                        VisibilityState.activity_view,
                        lambda row: _event_item(row),
                    ),
                    rx.text("No events recorded", size="3", color_scheme="gray"),
                ),
                padding="4",
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        padding="4",
        max_width="1200px",
    )
