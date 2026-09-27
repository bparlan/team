"""
AgentRoster - status indicators, contribution feed, per-agent metrics.

Pure-stdlib view model so it is testable in CI. Aggregates per-agent records
into render rows; a `PerformanceTracker` accumulates task outcomes so the roster
reports real counts rather than whatever the caller remembered to pass in.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .design_tokens import agent_status_visual

MAX_CONTRIBUTIONS = 20


@dataclass
class AgentRecord:
    """One agent, normalized for display."""

    id: str
    name: str = ""
    role: str = "worker"
    status: str = "idle"
    last_active: str = ""
    tasks_completed: int = 0
    tasks_failed: int = 0
    recent_contributions: List[Dict[str, str]] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Name if known, else the id."""
        return self.name or self.id

    @property
    def total_tasks(self) -> int:
        return self.tasks_completed + self.tasks_failed

    @property
    def success_rate(self) -> Optional[float]:
        """Completed / total, or None when the agent has done no work."""
        if self.total_tasks == 0:
            return None
        return self.tasks_completed / self.total_tasks

    @property
    def visual(self):
        """Status icon/color/label from the design tokens."""
        return agent_status_visual(self.status)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "AgentRecord":
        """Build a record from an arbitrary dict, never raising."""
        if not isinstance(raw, dict):
            raw = {"id": str(raw)}
        ident = str(raw.get("id") or raw.get("member_id") or raw.get("agent_id") or "unknown")
        return cls(
            id=ident,
            name=str(raw.get("name") or raw.get("display_name") or ""),
            role=str(raw.get("role") or raw.get("member_type") or "worker"),
            status=str(raw.get("status") or "idle"),
            last_active=str(raw.get("last_active") or ""),
            tasks_completed=int(raw.get("tasks_completed") or 0),
            tasks_failed=int(raw.get("tasks_failed") or 0),
            recent_contributions=[dict(c) for c in (raw.get("recent_contributions") or [])],
        )

    def row(self) -> Dict[str, Any]:
        """Flat render row."""
        rate = self.success_rate
        return {
            "id": self.id,
            "name": self.display_name,
            "role": self.role,
            "status": self.status,
            "status_label": self.visual.label,
            "status_icon": self.visual.icon,
            "status_color": self.visual.color,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "success_rate": "-" if rate is None else f"{rate * 100:.0f}%",
            "last_active": self.last_active,
        }


class PerformanceTracker:
    """
    Accumulates task outcomes per agent.

    Contribution history is bounded per agent so a long-running roster cannot
    grow without limit.
    """

    def __init__(self, max_contributions: int = MAX_CONTRIBUTIONS):
        if max_contributions < 1:
            raise ValueError("max_contributions must be >= 1")
        self.max_contributions = max_contributions
        self._records: Dict[str, AgentRecord] = {}

    def register(self, agent_id: str, **fields: Any) -> AgentRecord:
        """Register an agent, or update an existing one."""
        record = self._records.get(agent_id)
        if record is None:
            record = AgentRecord(id=agent_id)
            self._records[agent_id] = record
        for key, value in fields.items():
            if hasattr(record, key) and value is not None:
                setattr(record, key, value)
        return record

    def record_task(self, agent_id: str, task: str, success: bool) -> AgentRecord:
        """
        Record a completed task for an agent.

        The agent is auto-registered if unknown, so a task from a new agent is
        never silently dropped.
        """
        record = self.register(agent_id)
        if success:
            record.tasks_completed += 1
        else:
            record.tasks_failed += 1
        record.recent_contributions.append(
            {"task": str(task), "status": "completed" if success else "failed"}
        )
        if len(record.recent_contributions) > self.max_contributions:
            del record.recent_contributions[: len(record.recent_contributions) - self.max_contributions]
        return record

    def set_status(self, agent_id: str, status: str) -> AgentRecord:
        """Update an agent's lifecycle status."""
        return self.register(agent_id, status=status)

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        return self._records.get(agent_id)

    def agents(self) -> List[AgentRecord]:
        """All records, busiest first then by id for a stable order."""
        return sorted(
            self._records.values(),
            key=lambda r: (-r.total_tasks, r.id),
        )

    def clear(self) -> None:
        self._records.clear()


class AgentRoster:
    """Renders agent records plus their contribution feed."""

    def __init__(self, tracker: Optional[PerformanceTracker] = None, max_agents: int = 50):
        self.tracker = tracker or PerformanceTracker()
        self.max_agents = max_agents

    def load(self, raws: Iterable[Dict[str, Any]]) -> int:
        """Bulk-load agent dicts into the tracker. Returns the count loaded."""
        count = 0
        for raw in raws:
            record = AgentRecord.from_dict(raw)
            self.tracker.register(
                record.id,
                name=record.name or None,
                role=record.role,
                status=record.status,
                last_active=record.last_active or None,
                tasks_completed=record.tasks_completed or None,
                tasks_failed=record.tasks_failed or None,
            )
            count += 1
        return count

    def rows(self) -> List[Dict[str, Any]]:
        """Render rows for every agent, busiest first."""
        return [r.row() for r in self.tracker.agents()[: self.max_agents]]

    def status_counts(self) -> Dict[str, int]:
        """Agent count per lifecycle status."""
        counts: Dict[str, int] = {}
        for record in self.tracker.agents():
            counts[record.status] = counts.get(record.status, 0) + 1
        return counts

    def contribution_feed(self, limit: int = 10) -> List[Dict[str, str]]:
        """
        Most recent contributions across all agents, newest first.

        Each row carries the agent id so the feed is readable without joining
        against the roster.
        """
        feed: List[Dict[str, str]] = []
        for record in self.tracker.agents():
            for contribution in reversed(record.recent_contributions):
                feed.append({"agent": record.id, **contribution})
        feed.reverse()
        return feed[:limit]

    def detail(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Full detail payload for one agent, including its contribution feed.

        Returns None for an unknown agent so a stale selection renders an empty
        panel instead of raising.
        """
        record = self.tracker.get(agent_id)
        if record is None:
            return None
        row = record.row()
        row["contributions"] = list(reversed(record.recent_contributions))
        return row

    def summary_line(self) -> str:
        """One-line roster summary."""
        total = len(self.tracker.agents())
        if not total:
            return "No agents registered"
        active = self.status_counts().get("active", 0)
        return f"{total} agents - {active} active"