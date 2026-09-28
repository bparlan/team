#!/usr/bin/env python3
"""
theteam.advisory.roster - bootstrap and persistence for the advisory team.

This module owns exactly two things: generating a team for a project from its
structure, and persisting that team so the commentary layer can read it back.
It does not select members, it does not run a discussion, and it does not know
about the CLI. Those live in `selector` and `commentary`; this module is the
roster's source of truth.

The roster is a plain JSON document at `<state_dir>/roster.json`. It is
written once per project (by `bootstrap`) and read on every tick. Nothing else
writes it, so there is one writer and one reader and no race between them.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from theteam.state import StateStore

# The file the roster lives in, relative to the state directory. Kept as a
# module constant so `load_roster` and `save_roster` cannot drift apart.
ROSTER_FILE = "roster.json"


def _roster_path(project_root: Optional[str]) -> Path:
    """The one path this module resolves. Always through StateStore."""
    return StateStore(project_root).root / ROSTER_FILE


def bootstrap_roster(project_root: str) -> Dict[str, Any]:
    """Generate a team for `project_root` and persist it.

    Calls `generate_team_members_from_context` (the package's own context
    analyser) and writes the result to `<state_dir>/roster.json`. Returns the
    roster that was written, so a caller can report it without re-reading.

    Raises if context analysis fails: a roster built from nothing is the
    §3.3 defect in another shape, and the caller should see the error rather
    than inherit a confident-looking empty team.
    """
    # Imported here, not at module top, so this module carries no dependency on
    # the package's bootstrap flow. The advisory layer sits at the top of the
    # stack and must not reach past it.
    from theteam import generate_team_members_from_context

    roster = generate_team_members_from_context(project_root)
    save_roster(project_root, roster)
    return roster


def load_roster(project_root: Optional[str]) -> Optional[Dict[str, Any]]:
    """Read the persisted roster, or None when none has been bootstrapped.

    A missing file is the normal "no team yet" state, not an error. A file that
    exists but is not valid JSON raises: a corrupted roster is evidence, and
    the commentary layer should not silently fall back to an empty team.
    """
    path = _roster_path(project_root)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_roster(project_root: str, roster: Dict[str, Any]) -> None:
    """Write `roster` to `<state_dir>/roster.json`.

    The state directory is created if it does not exist, so a fresh project can
    bootstrap without a separate setup step.
    """
    StateStore(project_root).ensure()
    with open(_roster_path(project_root), "w", encoding="utf-8") as handle:
        json.dump(roster, handle, indent=2, sort_keys=True, default=str)