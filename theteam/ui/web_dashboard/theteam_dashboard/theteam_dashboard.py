"""
Reflex app entry point for the theTeam dashboard.

Pages are auto-registered via the @rx.page decorators in their modules.
"""

import reflex as rx

from .pages import activity, agents, dashboard, tasks

app = rx.App(
    theme=rx.theme(appearance="dark", accent_color="blue", gray_color="slate"),
)
