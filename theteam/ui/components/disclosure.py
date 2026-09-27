"""
Progressive disclosure - expand/collapse state shared across UI components.

The expansion state is kept here rather than duplicated in each panel, so a
caller can collapse every detail panel at once (or open several) without each
component inventing its own bookkeeping.
"""

from typing import Any, Dict, Iterable, List, Optional, Set

EXPANDED = "expanded"
COLLAPSED = "collapsed"


class DisclosureGroup:
    """
    Tracks which disclosure panels are expanded.

    Backed by a set of panel ids; a bounded LRU is not needed because panel ids
    are a small closed set, but `collapse_all` keeps long sessions from leaving
    every panel open.
    """

    def __init__(self, default_open: Iterable[str] = ()):
        self._expanded: Set[str] = set(default_open)

    def is_open(self, panel_id: str) -> bool:
        return panel_id in self._expanded

    def state(self, panel_id: str) -> str:
        """Literal state string for rendering."""
        return EXPANDED if self.is_open(panel_id) else COLLAPSED

    def toggle(self, panel_id: str) -> bool:
        """Flip a panel; returns its new open state."""
        if panel_id in self._expanded:
            self._expanded.discard(panel_id)
        else:
            self._expanded.add(panel_id)
        return self.is_open(panel_id)

    def open(self, panel_id: str) -> None:
        self._expanded.add(panel_id)

    def close(self, panel_id: str) -> None:
        self._expanded.discard(panel_id)

    def collapse_all(self) -> None:
        """Collapse every panel."""
        self._expanded.clear()

    def open_ids(self) -> List[str]:
        return sorted(self._expanded)

    def row(self, panel_id: str, title: str = "") -> Dict[str, Any]:
        """Render row describing one panel's disclosure state."""
        is_open = self.is_open(panel_id)
        return {
            "id": panel_id,
            "title": title or panel_id,
            "state": EXPANDED if is_open else COLLAPSED,
            "icon": "▼" if is_open else "▶",
            "open": is_open,
        }

    def rows(self, panel_ids: Iterable[str], titles: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """Render rows for many panels, preserving input order."""
        titles = titles or {}
        return [self.row(pid, titles.get(pid, "")) for pid in panel_ids]


    def stamp(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Write the open flag onto precomputed render rows.

        A reflex dict Var cannot be indexed by a Var key, so the flag is
        resolved here, at state-update time, and templates read a plain field.
        Returns new rows; the input is not mutated.
        """
        return [{**row, "is_open": row["panel_id"] in self._expanded} for row in rows]


def disclosure_view(
    group: DisclosureGroup,
    panel_id: str,
    title: str,
    summary: str = "",
    detail_rows: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Build the payload a renderer needs for one collapsible panel.

    Detail rows are only included while expanded - that is the point of
    progressive disclosure: collapsed means the detail is not even materialized.
    """
    row = group.row(panel_id, title)
    row["summary"] = summary
    if row["open"]:
        row["detail"] = [list(r) for r in (detail_rows or [])]
    else:
        row["detail"] = []
    return row
