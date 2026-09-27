"""
HealthDashboard - circuit breaker states, health scores, and recovery actions.

Pure-stdlib view model so it is testable in CI. Reads the real core objects
(`HealthMonitor`, `CircuitBreaker`) rather than re-describing their state, so
the dashboard cannot disagree with the system it reports on.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from .design_tokens import DesignTokens, circuit_visual, health_band


@dataclass
class RecoveryAction:
    """A suggested operator action derived from breaker/alert state."""

    action: str
    status: str
    description: str
    target: str = ""

    @property
    def color(self) -> str:
        return {
            "pending": DesignTokens().palette.warning,
            "in_progress": DesignTokens().palette.info,
            "completed": DesignTokens().palette.success,
            "failed": DesignTokens().palette.danger,
        }.get(self.status, DesignTokens().palette.neutral)


class HealthDashboard:
    """
    Aggregates circuit breaker and health-monitor state into render rows.

    Every method accepts live core objects directly, so callers do not have to
    hand-translate state before displaying it.
    """

    def __init__(self, max_breakers: int = 20):
        self.max_breakers = max_breakers

    def health_score(self, monitor: Any) -> float:
        """
        Read a 0.0-1.0 health score from a HealthMonitor.

        Returns 0.0 when no monitor is available, so a missing monitor renders
        as 'Critical' rather than a crash.
        """
        if monitor is None:
            return 0.0
        getter = getattr(monitor, "get_health_score", None)
        if callable(getter):
            try:
                return self._clamp(getter())
            except Exception as exc:  # pragma: no cover - defensive
                return 0.0
        status = getattr(monitor, "get_health_status", None)
        if callable(status):
            try:
                return self._clamp(status().get("health_score", 0.0))
            except Exception:
                return 0.0
        return 0.0

    @staticmethod
    def _clamp(value: Any) -> float:
        """Clamp to 0.0-1.0, tolerating junk input."""
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if score < 0.0 else (1.0 if score > 1.0 else score)

    def health_row(self, monitor: Any) -> Dict[str, Any]:
        """Render row for the overall health score."""
        score = self.health_score(monitor)
        band = health_band(score)
        return {
            "score": round(score, 3),
            "percent": f"{score * 100:.0f}%",
            "label": band.label,
            "color": band.color,
            "icon": band.icon,
        }

    def breaker_rows(self, breakers: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Render rows for each circuit breaker.

        Reads `breaker.stats.state`, `.consecutive_failures` and the config
        threshold - the same fields `metrics.breaker_state_value()` uses - so
        the UI and the exported gauge can never disagree.
        """
        rows: List[Dict[str, Any]] = []
        for name, breaker in list(breakers.items())[: self.max_breakers]:
            stats = getattr(breaker, "stats", None)
            state = getattr(stats, "state", None)
            visual = circuit_visual(state)
            config = getattr(breaker, "config", None)
            rows.append(
                {
                    "name": name,
                    "state": visual.state,
                    "label": visual.label,
                    "icon": visual.icon,
                    "color": visual.color,
                    "description": visual.description,
                    "failures": int(getattr(stats, "consecutive_failures", 0) or 0),
                    "threshold": int(getattr(config, "failure_threshold", 0) or 0),
                }
            )
        rows.sort(key=lambda r: (r["state"] == "closed", r["name"]))
        return rows

    def recovery_actions(self, breakers: Dict[str, Any], monitor: Any = None) -> List[RecoveryAction]:
        """
        Derive operator actions from actual system state.

        An OPEN breaker is told to wait for the reset timeout; a HALF_OPEN one
        is told a probe is in flight; critical health raises a triage action.
        """
        actions: List[RecoveryAction] = []
        for row in self.breaker_rows(breakers):
            if row["state"] == "open":
                actions.append(
                    RecoveryAction(
                        action="Wait for reset timeout",
                        status="pending",
                        description=(
                            f"{row['name']} is open; it will probe "
                            f"{row['description'].split('- ')[-1].lower()}"
                        ),
                        target=row["name"],
                    )
                )
            elif row["state"] == "half_open":
                actions.append(
                    RecoveryAction(
                        action="Await recovery probe",
                        status="in_progress",
                        description=(
                            f"{row['name']} is half-open at "
                            f"{row['failures']}/{row['threshold']} failures"
                        ),
                        target=row["name"],
                    )
                )
        score = self.health_score(monitor)
        if monitor is not None and health_band(score).label == "Critical":
            actions.append(
                RecoveryAction(
                    action="Triage health alerts",
                    status="pending",
                    description=f"Health score {score:.0%} is below the critical floor",
                )
            )
        return actions

    def status(self, monitor: Any, breakers: Dict[str, Any]) -> Dict[str, Any]:
        """Full dashboard payload: health row, breaker rows, actions."""
        rows = self.breaker_rows(breakers)
        return {
            "health": self.health_row(monitor),
            "breakers": rows,
            "tripped": [r for r in rows if r["state"] != "closed"],
            "actions": self.recovery_actions(breakers, monitor),
            "summary": self.summary(monitor, rows),
        }

    @staticmethod
    def summary(monitor: Any, rows: List[Dict[str, Any]]) -> str:
        """One-line status, e.g. 'Healthy - 2/2 breakers closed'."""
        band = health_band(HealthDashboard().health_score(monitor))
        total = len(rows)
        closed = sum(1 for r in rows if r["state"] == "closed")
        return f"{band.label} - {closed}/{total} breakers closed"