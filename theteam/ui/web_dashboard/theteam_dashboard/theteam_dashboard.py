"""
Reflex app entry point for the theTeam dashboard.

Pages are auto-registered via the @rx.page decorators in their modules.
"""

import sys
from pathlib import Path

# The dashboard is launched from its own directory (web_dashboard/), where the
# repo root is not on sys.path. Add it so `theteam.*` absolute imports in the
# page modules resolve.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import reflex as rx

from .pages import activity, agents, dashboard, tasks

app = rx.App(
    theme=rx.theme(appearance="dark", accent_color="blue", gray_color="slate"),
)
