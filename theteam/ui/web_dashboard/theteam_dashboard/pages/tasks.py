import reflex as rx
from ..state import DashboardState


def task_row(task: dict) -> rx.Component:
    colors = {"loop": "blue", "one-shot": "green", "conversation": "purple", "scheduled": "orange"}
    return rx.table.row(
        rx.table.cell(task["id"]),
        rx.table.cell(task["name"]),
        rx.table.cell(rx.badge(task["type"], color_scheme=colors.get(task["type"], "gray"), variant="soft")),
        rx.table.cell(task["priority"]),
        rx.table.cell(rx.badge(task["schedule_text"], color_scheme="gray")),
    )


@rx.page(route="/tasks", title="Task Management")
def tasks() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.hstack(
                rx.heading("Task Management", size="6"),
                rx.button("Refresh", on_click=DashboardState.load_all, color_scheme="blue"),
                justify="between",
                width="100%",
                padding="4",
            ),
            rx.divider(),
            # Scheduled tasks
            rx.card(
                rx.vstack(
                    rx.heading("Scheduled Tasks", size="5"),
                    rx.cond(
                        DashboardState.scheduled_count > 0,
                        rx.table.root(
                            rx.table.header(rx.table.row(
                                rx.table.column_header_cell("Task"),
                                rx.table.column_header_cell("Interval"),
                                rx.table.column_header_cell("Next Run"),
                            )),
                            rx.table.body(rx.foreach(
                                DashboardState.scheduled_tasks_list,
                                lambda s: rx.table.row(
                                    rx.table.cell(s["id"]),
                                    rx.table.cell(s["interval"]),
                                    rx.table.cell(s["next_run"]),
                                ),
                            )),
                            variant="surface",
                        ),
                        rx.text("No scheduled tasks", size="3", color=rx.color("gray", 9)),
                    ),
                    spacing="2",
                ),
                padding="4",
                width="100%",
            ),
            # Daemon status
            rx.card(
                rx.vstack(
                    rx.heading("Daemon Status", size="5"),
                    rx.hstack(
                        rx.text("Status: ", weight="bold"),
                        rx.badge(
                            DashboardState.daemon_running_text,
                            color_scheme=rx.cond(DashboardState.daemon_running_text == "Running", "green", "red"),
                            variant="solid",
                        ),
                        spacing="2",
                    ),
                    rx.text(f"Started: {DashboardState.daemon_display.get('started', '')}", size="2"),
                    rx.text(f"Tasks executed: {DashboardState.daemon_display.get('executed', 0)}", size="2"),
                    rx.cond(
                        DashboardState.daemon_running_text == "Running",
                        rx.text(f"Last check: {DashboardState.daemon_last_check_text}", size="2"),
                    ),
                    spacing="2",
                ),
                padding="4",
                width="100%",
            ),
            # Registered tasks table
            rx.card(
                rx.vstack(
                    rx.heading("All Registered Tasks", size="5"),
                    rx.cond(
                        DashboardState.task_count > 0,
                        rx.table.root(
                            rx.table.header(rx.table.row(
                                rx.table.column_header_cell("ID"),
                                rx.table.column_header_cell("Name"),
                                rx.table.column_header_cell("Type"),
                                rx.table.column_header_cell("Priority"),
                                rx.table.column_header_cell("Schedule"),
                            )),
                            rx.table.body(rx.foreach(DashboardState.tasks, lambda t: task_row(t))),
                            variant="surface",
                        ),
                        rx.text("No tasks registered", size="3", color=rx.color("gray", 9)),
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