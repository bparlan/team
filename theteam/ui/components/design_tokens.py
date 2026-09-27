"""
Design tokens for the theTeam UI component library.

Single source of truth for color, spacing, type scale, and state semantics so
that the terminal renderer and the optional Reflex renderer cannot drift apart.
"""

from dataclasses import dataclass
from typing import Any, Dict, List
@dataclass(frozen=True)
class Palette:
    """Raw color values."""

    # Accent
    accent = "#2563eb"
    # Semantic
    success = "#16a34a"
    warning = "#d97706"
    danger = "#dc2626"
    critical = "#991b1b"
    neutral = "#64748b"
    # Surfaces
    surface = "#0f172a"
    surface_alt = "#1e293b"
    surface_raised = "#334155"
    border = "#475569"
    text = "#e2e8f0"
    text_muted = "#94a3b8"

    # Severity ramp, low to high.
    debug = "#64748b"
    info = "#0ea5e9"
    success_ramp = "#16a34a"
    warning_ramp = "#d97706"
    error = "#dc2626"
    critical_ramp = "#991b1b"
@dataclass(frozen=True)
class Severity:
    """Named severity levels, ordered by increasing urgency."""

    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @classmethod
    def order(cls) -> List[str]:
        """Return severities from least to most urgent."""
        return [cls.DEBUG, cls.INFO, cls.SUCCESS, cls.WARNING, cls.ERROR, cls.CRITICAL]

    @classmethod
    def normalize(cls, value: Any) -> str:
        """
        Coerce arbitrary input to a known severity.

        Unknown values become INFO rather than raising: a malformed event must
        not take down the stream that exists to report problems.
        """
        if value is None:
            return cls.INFO
        text = str(value).strip().lower()
        if text in cls.order():
            return text
        aliases = {
            "warn": cls.WARNING,
            "err": cls.ERROR,
            "fatal": cls.CRITICAL,
            "crit": cls.CRITICAL,
            "trace": cls.DEBUG,
            "ok": cls.SUCCESS,
            "notice": cls.INFO,
        }
        return aliases.get(text, cls.INFO)
@dataclass(frozen=True)
class CircuitVisual:
    """
    Visual semantics for a circuit breaker state.

    NOTE: `open` is the *bad* state - the breaker has tripped and is blocking
    traffic - so it is red. `closed` is the *good* state (requests flowing) and
    is green. Getting this backwards is the classic circuit-breaker UI bug.
    """

    state: str
    label: str
    icon: str
    color: str
    description: str


# Canonical breaker visuals keyed by CircuitState.value.
CIRCUIT_VISUALS: Dict[str, CircuitVisual] = {
    "closed": CircuitVisual(
        state="closed",
        label="Closed",
        icon="●",
        color=Palette.success,
        description="Healthy - traffic is flowing",
    ),
    "half_open": CircuitVisual(
        state="half_open",
        label="Half-Open",
        icon="◐",
        color=Palette.warning,
        description="Probing - testing whether the dependency recovered",
    ),
    "open": CircuitVisual(
        state="open",
        label="Open",
        icon="○",
        color=Palette.danger,
        description="Tripped - calls are blocked pending recovery",
    ),
}

UNKNOWN_VISUAL = CircuitVisual(
    state="unknown",
    label="Unknown",
    icon="?",
    color=Palette.neutral,
    description="Breaker state unavailable",
)
# Agent lifecycle states.
AGENT_STATUSES: List[str] = ["active", "busy", "idle", "error", "offline"]

AGENT_STATUS_COLORS: Dict[str, str] = {
    "active": Palette.success,
    "busy": Palette.warning,
    "idle": Palette.neutral,
    "error": Palette.danger,
    "offline": Palette.text_muted,
}

AGENT_STATUS_ICONS: Dict[str, str] = {
    "active": "▲",
    "busy": "◆",
    "idle": "■",
    "error": "✕",
    "offline": "·",
}
# Health score bands. Upper bound is exclusive.
HEALTH_BANDS = (
    (0.8, "Healthy", Palette.success),
    (0.5, "Degraded", Palette.warning),
    (0.0, "Critical", Palette.danger),
)


def health_band(score: float) -> CircuitVisual:
    """Map a 0.0-1.0 health score to its band visual."""
    clamped = 0.0 if score < 0.0 else (1.0 if score > 1.0 else float(score))
    for threshold, label, color in HEALTH_BANDS:
        if clamped >= threshold:
            return CircuitVisual(
                state=label.lower(),
                label=label,
                icon="●" if label == "Healthy" else ("◐" if label == "Degraded" else "○"),
                color=color,
                description=f"Health score {clamped:.0%}",
            )
    return UNKNOWN_VISUAL


def circuit_visual(state: Any) -> CircuitVisual:
    """
    Map a CircuitState (enum, string, or object) to its visual semantics.

    Accepts the real `CircuitState` enum so the UI cannot disagree with the
    breaker implementation about what a state is called.
    """
    raw = getattr(state, "value", state)
    if raw is None:
        return UNKNOWN_VISUAL
    return CIRCUIT_VISUALS.get(str(raw).strip().lower(), UNKNOWN_VISUAL)


def agent_status_visual(status: Any) -> CircuitVisual:
    """Map an agent status string to its visual semantics."""
    raw = str(status or "offline").strip().lower()
    return CircuitVisual(
        state=raw,
        label=raw.title() if raw in AGENT_STATUSES else "Unknown",
        icon=AGENT_STATUS_ICONS.get(raw, "?"),
        color=AGENT_STATUS_COLORS.get(raw, Palette.neutral),
        description=f"Agent is {raw}",
    )


class DesignTokens:
    """Namespace object exposing every token to renderers."""

    palette = Palette
    severity = Severity

    def __init__(self):
        self.palette = Palette()
        self.space = {"xs": 1, "sm": 2, "md": 3, "lg": 4, "xl": 6}
        self.radius = {"sm": 3, "md": 6, "lg": 10}

    def severity_color(self, severity: Any) -> str:
        """Color for a severity level."""
        return {
            Severity.DEBUG: self.palette.debug,
            Severity.INFO: self.palette.info,
            Severity.SUCCESS: self.palette.success_ramp,
            Severity.WARNING: self.palette.warning_ramp,
            Severity.ERROR: self.palette.error,
            Severity.CRITICAL: self.palette.critical_ramp,
        }[Severity.normalize(severity)]

    def all_tokens(self) -> Dict[str, Any]:
        """Flat token dump, used by tests and token audits."""
        tokens: Dict[str, Any] = {}
        for name in dir(self.palette):
            if not name.startswith("_"):
                tokens[f"color.{name}"] = getattr(self.palette, name)
        tokens["space"] = dict(self.space)
        tokens["radius"] = dict(self.radius)
        tokens["severity.order"] = Severity.order()
        return tokens