"""
Agent roster page - status indicators, contribution feed, per-agent metrics.
Phase 5 task (d).
"""

from typing import Dict

import reflex as rx

from theteam.ui.web_dashboard.theteam_dashboard.visibility_state import VisibilityState
from theteam.ui.components.reflex_renderers import disclosure_panel, page_header


def _agent_item(agent: Dict) -> rx.Component:
    """Render one agent: status icon, name, role, and expandable metrics.

    Every value is pre-computed in `VisibilityState.roster_view`: a Var cannot
    be f-stringed, iterated, or branched on inside an `rx.foreach` render fn.
    """
    return rx.vstack(
        rx.hstack(
            rx.text(agent["status_icon"], color=agent["status_color"], size="3"),
            rx.vstack(
                rx.text(agent["name"], weight="bold", size="2"),
                rx.text(agent["role"], size="1", color_scheme="gray"),
                spacing="0",
            ),
            rx.badge(
                agent["status_label"],
                color=agent["status_color"],
                variant="soft",
                size="1",
            ),
            spacing="3",
            align="center",
            width="100%",
        ),
        rx.hstack(
            rx.text(agent["completed_label"], size="1", color_scheme="gray"),
            rx.text(agent["failed_label"], size="1", color_scheme="gray"),
            rx.text(agent["success_label"], size="1", color_scheme="gray"),
            spacing="3",
        ),
        rx.cond(
            agent["has_details"],
            disclosure_panel(
                agent["panel_id"],
                "Contribution feed",
                agent["detail_label"],
                agent["detail_text"],
                on_toggle=VisibilityState.toggle_panel(agent["panel_id"]),
                is_open=agent["is_open"],
            ),
        ),
        spacing="1",
        width="100%",
        padding_y="3",
    )


@rx.page(route="/agents", title="Agent Roster")
def agents() -> rx.Component:
    """Render the agent roster page."""

    return rx.container(
        rx.vstack(
            page_header(
                "Agent Roster",
                VisibilityState.roster_summary,
                on_collapse=VisibilityState.collapse_all,
            ),
            rx.divider(),
            # Roster
            rx.card(
                rx.vstack(
                    rx.heading("Agents", size="5"),
                    rx.cond(
                        VisibilityState.roster_view.length() > 0,
                        rx.foreach(
                            VisibilityState.roster_view,
                            lambda agent: _agent_item(agent),
                        ),
                        rx.text("No agents registered", size="3", color_scheme="gray"),
                    ),
                    spacing="3",
                    width="100%",
                ),
                padding="4",
                width="100%",
            ),
            # Contribution feed
            rx.card(
                rx.vstack(
                    rx.heading("Recent Contributions", size="5"),
                    rx.cond(
                        VisibilityState.contribution_feed.length() > 0,
                        rx.foreach(
                            VisibilityState.contribution_feed,
                            lambda c: rx.hstack(
                                rx.badge(c["agent"], variant="soft", size="1"),
                                rx.text(c["task"], size="2"),
                                rx.badge(
                                    c["status"],
                                    color_scheme=rx.cond(
                                        c["status"] == "completed", "green", "red"
                                    ),
                                    variant="soft",
                                    size="1",
                                ),
                                spacing="2",
                                align="center",
                                width="100%",
                            ),
                        ),
                        rx.text("No contributions yet", size="3", color_scheme="gray"),
                    ),
                    spacing="3",
                    width="100%",
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
