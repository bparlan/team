"""
theteam UI component library.

Pure-stdlib view models for the Phase 5 visibility layer. Every module here
imports nothing outside the standard library and `theteam.core`, so the whole
library is unit-testable in CI where Reflex is not installed.

The optional Reflex renderer in `reflex_renderers.py` imports from this
package; this package never imports Reflex.
"""

from .activity_stream import ActivityEvent, ActivityStream, stream_from_events
from .agent_roster import AgentRecord, AgentRoster, PerformanceTracker
from .design_tokens import (
    AGENT_STATUSES,
    CIRCUIT_VISUALS,
    DesignTokens,
    Palette,
    Severity,
    agent_status_visual,
    circuit_visual,
    health_band,
)
from .disclosure import (
    COLLAPSED,
    EXPANDED,
    DisclosureGroup,
    disclosure_view,
)
from .health_dashboard import HealthDashboard, RecoveryAction
from .metrics_panel import MetricsPanel, parse_exposition

__all__ = [
    "ActivityEvent",
    "ActivityStream",
    "stream_from_events",
    "AgentRecord",
    "AgentRoster",
    "PerformanceTracker",
    "AGENT_STATUSES",
    "CIRCUIT_VISUALS",
    "DesignTokens",
    "Palette",
    "Severity",
    "agent_status_visual",
    "circuit_visual",
    "health_band",
    "COLLAPSED",
    "EXPANDED",
    "DisclosureGroup",
    "disclosure_view",
    "HealthDashboard",
    "RecoveryAction",
    "MetricsPanel",
    "parse_exposition",
]
