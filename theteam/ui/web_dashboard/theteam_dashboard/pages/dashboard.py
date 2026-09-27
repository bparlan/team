import reflex as rx
from ..state import DashboardState
from theteam.ui.web_dashboard.theteam_dashboard.visibility_state import VisibilityState
from theteam.ui.components.reflex_renderers import disclosure_panel


def metric_card(label: str, value, color: str = "blue") -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(label, size="2", color=rx.color("gray", 9)),
            rx.text(value, size="8", weight="bold", color=rx.color(color, 8)),
            spacing="1",
        ),
        padding="4",
        width="100%",
    )



def health_section() -> rx.Component:
    """Phase 5 (b): circuit breaker states, health score, recovery actions."""
    return rx.card(
        rx.vstack(
            rx.heading("System Health", size="5"),
            # Health score chip
            rx.cond(
                VisibilityState.health_row.length() > 0,
                rx.hstack(
                    rx.text(
                        VisibilityState.health_row.get("icon", ""),
                        color=VisibilityState.health_row.get("color", "gray"),
                        size="3",
                    ),
                    rx.text(
                        VisibilityState.health_row.get("percent", "0%"),
                        size="5",
                        weight="bold",
                    ),
                    rx.badge(
                        VisibilityState.health_row.get("label", "Unknown"),
                        color=VisibilityState.health_row.get("color", "gray"),
                        variant="soft",
                    ),
                    spacing="2",
                    align="center",
                ),
            ),
            # Circuit breakers
            rx.cond(
                VisibilityState.breaker_rows.length() > 0,
                rx.foreach(
                    VisibilityState.breaker_rows,
                    lambda b: rx.hstack(
                        rx.text(b["name"], size="2", weight="medium"),
                        rx.badge(
                            f"{b['icon']} {b['label']}",
                            color=b["color"],
                            variant="soft",
                            size="1",
                        ),
                        rx.text(
                            f"{b['failures']}/{b['threshold']} failures",
                            size="1",
                            color_scheme="gray",
                        ),
                        spacing="2",
                        align="center",
                        width="100%",
                        justify="between",
                    ),
                ),
                rx.text("No circuit breakers", size="2", color_scheme="gray"),
            ),
            # Recovery actions, collapsed by default
            rx.cond(
                VisibilityState.recovery_rows.length() > 0,
                disclosure_panel(
                    "health:recovery",
                    "Recovery actions",
                    VisibilityState.recovery_summary,
                    VisibilityState.recovery_lines,
                    on_toggle=VisibilityState.toggle_health_recovery,
                    is_open=VisibilityState.health_recovery_open,
                ),
            ),
            spacing="3",
            width="100%",
        ),
        padding="4",
        width="100%",
    )


def metrics_section() -> rx.Component:
    """Phase 5 (c): system metrics and performance monitoring."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("System Metrics", size="5"),
                rx.badge(
                    VisibilityState.metrics_summary,
                    color_scheme="blue",
                    variant="soft",
                ),
                justify="between",
                width="100%",
            ),
            rx.cond(
                VisibilityState.metrics_rows.length() > 0,
                rx.foreach(
                    VisibilityState.metrics_rows,
                    lambda m: rx.hstack(
                        rx.text(m["name"], size="2", weight="medium"),
                        rx.text(m["label"], size="1", color_scheme="gray"),
                        rx.text(m["display"], size="2", weight="bold"),
                        spacing="2",
                        align="center",
                        width="100%",
                        justify="between",
                    ),
                ),
                rx.text("No metrics reported", size="2", color_scheme="gray"),
            ),
            spacing="3",
            width="100%",
        ),
        padding="4",
        width="100%",
    )

@rx.page(route="/", title="Team Dashboard")
def dashboard() -> rx.Component:
    return rx.container(
        rx.vstack(
            # Header
            rx.hstack(
                rx.heading("Team Dashboard", size="6"),
                rx.badge(
                    rx.cond(DashboardState.connection_ok, "Connected", "Disconnected"),
                    color_scheme=rx.cond(DashboardState.connection_ok, "green", "red"),
                    variant="solid",
                ),
                justify="between",
                width="100%",
                padding="4",
            ),
            rx.divider(),
            # Metric cards row
            rx.grid(
                metric_card("Registered Tasks", DashboardState.task_count, "blue"),
                metric_card("Scheduled", DashboardState.scheduled_count, "green"),
                metric_card(
                    "Daemon",
                    DashboardState.daemon_running_text,
                    rx.cond(DashboardState.daemon_running_text == "Running", "green", "orange"),
                ),
                metric_card("Last Check", DashboardState.daemon_last_check_text, "purple"),
                columns="4",
                spacing="4",
                width="100%",
            ),
            # Phase 5 (b): health status - breakers, health score, recovery
            health_section(),
            # Folder hygiene (pre-existing) folded into the health surface
            rx.card(
                rx.vstack(
                    rx.heading("Folder Health", size="5"),
                    rx.hstack(
                        rx.text("Critical folders: ", size="3"),
                        rx.badge(
                            rx.cond(DashboardState.critical_folders_ok, "OK", "Needs attention"),
                            color_scheme=rx.cond(DashboardState.critical_folders_ok, "green", "orange"),
                        ),
                    ),
                    rx.text(f"Root clutter: {DashboardState.root_clutter} items", size="3"),
                    spacing="2",
                ),
                padding="4",
                width="100%",
            ),
            # Phase 5 (c): system metrics and performance monitoring
            metrics_section(),
            # Recent execution log
            rx.card(
                rx.vstack(
                    rx.heading("Recent Activity", size="5"),
                    rx.cond(
                        DashboardState.execution_log.length() > 0,
                        rx.foreach(
                            DashboardState.execution_log,
                            lambda entry: rx.hstack(
                                rx.text(entry.get("task_id", "unknown"), weight="bold", size="2"),
                                rx.badge(
                                    rx.cond(entry.get("overall_success", False), "Success", "Failed"),
                                    color_scheme=rx.cond(
                                        entry.get("overall_success", False), "green", "red"
                                    ),
                                ),
                                rx.text(entry.get("timestamp_short", ""), size="1", color=rx.color("gray", 9)),
                                spacing="4",
                            ),
                        ),
                        rx.text("No recent activity", size="3", color=rx.color("gray", 9)),
                    ),
                    spacing="2",
                ),
                padding="4",
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        padding="4",
        max_width="1200px",
        on_mount=DashboardState.load_all,
    )