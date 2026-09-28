#!/usr/bin/env python3
"""
theteam.advisory.commentary - the controller. It decides *when*; the engine
decides *what*.

ARCHITECTURE.md 4.1 is the constraint this module exists to satisfy: the tick
body is a call to the engine, not a reimplementation of it. Selection lives in
`selector`, the {id, role, verdict, note} contract and its validator live in
`theteam.core.member`, and synthesis lives in the engine. Two discussion
systems cannot drift because there is only one.

Two rules from 3.2 shape everything here:

* **Silence is always explained.** Every tick returns `spoke: false` with a
  reason. A tick that renders nothing and says nothing is indistinguishable
  from a tick that crashed, which is the failure this product exists to avoid.
* **No fabricated opinions.** If the engine is unavailable the tick reports
  `spoke: false` with a reason. It never synthesises a plausible fragment.
  That is M0's rule and this is where it gets tested hardest, because the
  controller runs unattended.

The stop word matches as the *entire leading clause* only, per 4.2. "stop the
current phase" is a request to stop a phase, not to silence the team; only a
message that *is* the stop word silences it.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from theteam.advisory.selector import select_members
from theteam.advisory.session_reader import SessionSlice
from theteam.state import StateStore

# 4.2: at most 2 rendered fragments per tick. The third opinion is recorded
# as suppressed rather than dropped silently, so the user can tell the
# difference between "the team had nothing" and "the team had more than we
# showed".
MAX_FRAGMENTS = 2

# The stop words from 4.2. Matched against the whole leading clause.
STOP_WORDS = frozenset({
    "stop", "halt", "quiet", "enough", "that's all", "thats all",
})

# The members' calls, in the order the budget allows. 4.6 caps a turn at 4
# member calls; the selector caps selection at 4, so a tick can never exceed
# the budget by selecting more.
STOP_SENTINEL = "commentary.stop"


@dataclass
class TickResult:
    """What one tick did. Every field is a measurement, never a guess.

    `spoke: true` carries at most `MAX_FRAGMENTS` fragments. `spoke: false`
    carries a `reason` from the 3.2 table. There is no third state, and in
    particular no default fragment list that could pass for a real one.
    """

    spoke: bool
    reason: Optional[str] = None
    fragments: List[Dict[str, Any]] = field(default_factory=list)
    suppressed: int = 0
    truncated: bool = False
    members_called: List[str] = field(default_factory=list)
    digest: Optional[str] = None
    session_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "spoke": self.spoke,
            "fragments": self.fragments,
            "members_called": self.members_called,
        }
        if not self.spoke:
            payload["reason"] = self.reason
        if self.suppressed:
            payload["suppressed"] = self.suppressed
        if self.truncated:
            payload["truncated"] = True
        if self.digest is not None:
            payload["digest"] = self.digest
        if self.session_path:
            payload["session_path"] = self.session_path
        return payload


def leading_clause(message: str) -> str:
    """The first clause of a message, lowercased and stripped of punctuation.

    "Stop the current phase." -> "stop". "Stop" -> "stop". This is what
    makes the 4.2 rule expressible: only a message whose *whole leading
    clause* is a stop word silences the team.
    """
    text = (message or "").strip().lower()
    if not text:
        return ""
    # A clause ends at a comma, a newline, a full stop followed by a space, an
    # exclamation, or a question mark. Not at every period - "stop." is a
    # stop, and "e.g." is not a clause boundary.
    text = re.split(r"[,\n!?;]|\.\s", text, maxsplit=1)[0]
    return text.strip(" .")


def is_stop(message: str) -> bool:
    """Whether the latest user message is a stop signal."""
    return leading_clause(message) in STOP_WORDS


class CommentaryController:
    """The tick loop. One `tick()` per turn.

    `engine` is the callable the tick body delegates to. It takes the
    selected member ids and the session slice, and returns a list of
    opinion dicts. It is injected, not imported, so the controller does not
    own the discussion path and a test can drive it without a provider.
    """

    def __init__(
        self,
        project_root: str,
        engine: Optional[Callable[..., List[Dict[str, Any]]]] = None,
        max_members: int = 3,
        session_path: Optional[str] = None,
    ):
        self.project_root = project_root
        self.engine = engine
        self.max_members = min(max(int(max_members), 1), 4)
        self.session_path = session_path
        self.store = StateStore(project_root)
        # The quiet-tick budget only holds across a restart if the digest the
        # last tick saw is read back, not just held in memory. Without this a
        # fresh process sees an unchanged session as new work and spends a
        # member call on it - which is the budget 4.6 promises is zero.
        state = self.load_state()
        self._last_digest: Optional[str] = state.get("last_digest")
        self._tick_count = int(state.get("tick_count") or 0)

    # -- state ---------------------------------------------------------

    def _state_path(self):
        return self.store.root / "commentary.json"

    def load_state(self) -> Dict[str, Any]:
        return self.store.read_json(self._state_path())

    def _save_state(self, result: TickResult) -> None:
        """Persist what happened, so `comment status` can report it after a
        restart. Written only from a real tick result."""
        self.store.ensure()
        state = self.load_state()
        state["tick_count"] = self._tick_count
        state["last_digest"] = result.digest
        state["last_opinion"] = (
            result.fragments[0].get("note") if result.spoke and result.fragments else None
        )
        state["last_spoke"] = result.spoke
        state["last_reason"] = result.reason
        import json
        with open(self._state_path(), "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True, default=str)

    @property
    def tick_count(self) -> int:
        return self._tick_count

    # -- the tick ------------------------------------------------------

    def tick(self, slice_result) -> TickResult:
        """One turn. Always returns a result, always explains itself."""
        from theteam.advisory.session_reader import SessionResult

        self._tick_count += 1

        # 1. Stop sentinel beats everything, including a changed digest.
        # `comment off` takes effect next tick, which is this one.
        self.store.ensure()
        if (self.store.root / STOP_SENTINEL).exists():
            return self._finish(TickResult(spoke=False, reason="stopped"))

        # 2. No session, or the session is a subagent transcript.
        if isinstance(slice_result, SessionResult) and not slice_result.spoke:
            return self._finish(TickResult(spoke=False, reason=slice_result.reason or "no_session",
                                            session_path=slice_result.session_path))
        if slice_result is None:
            return self._finish(TickResult(spoke=False, reason="no_session"))
        if isinstance(slice_result, SessionResult):
            slice_ = slice_result.slice
        else:
            slice_ = slice_result
        if slice_ is None:
            return self._finish(TickResult(spoke=False, reason="no_session"))
        digest = slice_.digest
        path = slice_result.session_path if isinstance(slice_result, SessionResult) else None

        # 3. Stop word in the latest user message. Matched on the whole
        # leading clause only, so "stop the current phase" does not silence
        # the team.
        latest = (slice_.last_user_messages or [""])[-1]
        if is_stop(latest):
            return self._finish(TickResult(spoke=False, reason="stopped", digest=digest,
                                            session_path=path))

        # 4. Unchanged digest, no new user message. Zero engine calls. This is
        # the quiet-tick budget: a session that has not moved costs nothing.
        if self._last_digest is not None and digest == self._last_digest:
            return self._finish(TickResult(spoke=False, reason="no_change", digest=digest,
                                            session_path=path))

        # 5. Select members deterministically.
        selection = select_members(slice_, roster=self._roster())
        members = selection["members"][: self.max_members]
        truncated = selection["truncated"] or len(selection["members"]) > self.max_members

        # 6. No engine, no opinions. 3.2: an unavailable engine is a named
        # failure, never a synthesised fragment.
        if self.engine is None:
            return self._finish(TickResult(spoke=False, reason="engine_unavailable",
                                            digest=digest, session_path=path,
                                            members_called=[], truncated=truncated))

        # 7. Call the engine. It owns prompting, validation, and synthesis;
        # this controller owns none of that.
        opinions = self.engine(members, slice_) or []
        if not opinions:
            return self._finish(TickResult(spoke=False, reason="no_opinion", digest=digest,
                                            session_path=path, members_called=members,
                                            truncated=truncated))

        # 8. Render at most 2. The rest are counted, not hidden.
        fragments = list(opinions[:MAX_FRAGMENTS])
        suppressed = len(opinions) - len(fragments)
        return self._finish(TickResult(
            spoke=True,
            fragments=fragments,
            suppressed=suppressed,
            truncated=truncated,
            members_called=members,
            digest=digest,
            session_path=path,
        ))

    # -- helpers -------------------------------------------------------

    def _roster(self) -> Optional[Dict[str, Any]]:
        from theteam.advisory.roster import load_roster
        try:
            return load_roster(self.project_root)
        except (OSError, ValueError):
            return None

    def _finish(self, result: TickResult) -> TickResult:
        """Record the digest and persist. Every path goes through here so
        `comment status` never reports a tick that did not happen."""
        if result.digest is not None:
            self._last_digest = result.digest
        self._save_state(result)
        return result
