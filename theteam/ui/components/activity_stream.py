"""
ActivityStream - chronological, severity-coded rendering of agency events.

Pure-stdlib view model: no Reflex import, so it is unit-testable in CI where
reflex is not installed. The Reflex renderer lived in `reflex_renderers.py`,
which M10 deleted as unreachable, and
imports this module, never the reverse.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence
import logging

from .design_tokens import DesignTokens, Severity

logger = logging.getLogger(__name__)

MAX_EVENTS = 500
@dataclass
class ActivityEvent:
    """One agency event, normalized for display."""

    id: str
    message: str
    severity: str = Severity.INFO
    agent: str = "system"
    timestamp: str = ""
    event_type: str = "event"
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def color(self) -> str:
        """Severity color from the design tokens."""
        return DesignTokens().severity_color(self.severity)

    @property
    def has_details(self) -> bool:
        """Whether this event carries drill-down detail."""
        return bool(self.details)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any], index: int = 0) -> "ActivityEvent":
        """
        Build an event from an arbitrary dict.

        Never raises: a malformed event degrades to an INFO event rather than
        breaking the stream.
        """
        if not isinstance(raw, dict):
            raw = {"message": str(raw)}
        message = raw.get("message") or raw.get("event") or raw.get("description") or ""
        return cls(
            id=str(raw.get("id") or raw.get("event_id") or f"evt-{index}"),
            message=str(message),
            severity=Severity.normalize(raw.get("severity") or raw.get("level")),
            agent=str(raw.get("agent") or raw.get("source") or "system"),
            timestamp=_format_timestamp(raw.get("timestamp") or raw.get("time")),
            event_type=str(raw.get("event_type") or raw.get("type") or "event"),
            details=dict(raw.get("details") or {}),
        )


def _format_timestamp(value: Any) -> str:
    """Render a timestamp as HH:MM:SS, tolerating anything."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")
    return str(value)


def _sort_key(event: ActivityEvent) -> tuple:
    """
    Sort key that orders newest last and never raises on mixed types.

    Unparseable timestamps sort first so they cluster at the top of the
    stream instead of interleaving unpredictably.
    """
    if not event.timestamp:
        return (0, 0.0, event.id)
    try:
        return (1, float(event.timestamp), event.id)
    except (TypeError, ValueError):
        return (1, 0.0, event.id)


class ActivityStream:
    """
    Bounded, chronologically ordered collection of activity events.

    Retention is bounded at MAX_EVENTS so a long-running process cannot grow
    the stream without limit.
    """

    def __init__(self, max_events: int = MAX_EVENTS):
        if max_events < 1:
            raise ValueError("max_events must be >= 1")
        self.max_events = max_events
        self._events: List[ActivityEvent] = []

    def __len__(self) -> int:
        return len(self._events)

    def add(self, raw: Dict[str, Any]) -> ActivityEvent:
        """Append a raw event dict, applying retention."""
        event = ActivityEvent.from_dict(raw, index=len(self._events))
        self._events.append(event)
        if len(self._events) > self.max_events:
            del self._events[: len(self._events) - self.max_events]
        return event

    def extend(self, raws: Iterable[Dict[str, Any]]) -> int:
        """Append many raw events. Returns the count actually added."""
        added = 0
        for raw in raws:
            self.add(raw)
            added += 1
        return added

    def events(self, newest_first: bool = True, limit: Optional[int] = None) -> List[ActivityEvent]:
        """Return ordered events, optionally capped."""
        ordered = sorted(self._events, key=_sort_key, reverse=newest_first)
        if limit is not None:
            return ordered[: max(0, limit)]
        return ordered

    def visible(self, limit: int = 25) -> List[ActivityEvent]:
        """The most recent `limit` events, newest first - what the UI renders."""
        return self.events(newest_first=True, limit=limit)

    def counts_by_severity(self) -> Dict[str, int]:
        """Event count per severity level, in canonical order."""
        counts = {level: 0 for level in Severity.order()}
        for event in self._events:
            counts[event.severity] = counts.get(event.severity, 0) + 1
        return counts

    def worst_severity(self) -> str:
        """Highest severity currently present, or INFO when empty."""
        counts = self.counts_by_severity()
        for level in reversed(Severity.order()):
            if counts.get(level):
                return level
        return Severity.INFO

    def filter_by_severity(self, severity: str, limit: Optional[int] = None) -> List[ActivityEvent]:
        """Events at or above the given severity."""
        wanted = Severity.normalize(severity)
        floor = Severity.order().index(wanted)
        keep = [
            e for e in self.events()
            if Severity.order().index(e.severity) >= floor
        ]
        return keep[:limit] if limit is not None else keep

    def filter_by_agent(self, agent: str) -> List[ActivityEvent]:
        """Events emitted by one agent."""
        return [e for e in self.events() if e.agent == agent]

    def detail_rows(self, event_id: str) -> List[tuple]:
        """
        Sorted key/value rows for one event's drill-down panel.

        Returns [] for an unknown id rather than raising, so a stale UI
        selection cannot crash the render.
        """
        for event in self._events:
            if event.id == event_id:
                return sorted((str(k), str(v)) for k, v in event.details.items())
        return []

    def rows(self, limit: int = 25) -> List[Dict[str, str]]:
        """Flat render rows: severity, color, agent, time, message."""
        return [
            {
                "severity": e.severity,
                "color": e.color,
                "agent": e.agent,
                "timestamp": e.timestamp,
                "message": e.message,
                "id": e.id,
                "expandable": str(e.has_details),
            }
            for e in self.visible(limit)
        ]

    def summary_line(self) -> str:
        """One-line status summary, e.g. '3 events - worst: ERROR'."""
        if not self._events:
            return "No events"
        plural = "event" if len(self._events) == 1 else "events"
        return f"{len(self._events)} {plural} - worst: {self.worst_severity().upper()}"

    def clear(self) -> None:
        """Drop all retained events."""
        self._events.clear()


def stream_from_events(raws: Sequence[Dict[str, Any]], max_events: int = MAX_EVENTS) -> ActivityStream:
    """Build a stream from an existing sequence of event dicts."""
    stream = ActivityStream(max_events=max_events)
    stream.extend(raws)
    return stream