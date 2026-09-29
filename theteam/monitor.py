"""
Frame-over-frame change detection and alerting, over the payloads `watch` reads.

The watch loop already re-reads its payload every tick. Everything a monitoring
overlay needs is the *previous* frame: what changed, and which of those changes
is a state transition worth naming. So this module gathers nothing, polls
nothing, and holds no state file. It compares two dicts.

**An alert is a transition, not a level.** A breaker that is open has been open
since the first frame; the moment worth reporting is when it opened. Emitting
"open" every tick trains the reader to ignore the line, which makes the whole
surface useless exactly when it matters.

**The first frame has no previous frame.** It is recorded as the baseline and
reports no change, because a baseline is not evidence of stability. The renderer
says so on screen; this module just does not lie about it.
"""

import time
from collections import deque
from typing import Any, Dict, Iterator, List, Optional, Tuple

# Events kept for the timeline. Bounded: a watch loop is not a log store, and an
# unbounded deque in a process that runs all day is a slow leak.
MAX_EVENTS = 100

# Events shown on screen at once. The rest stay in the buffer.
VISIBLE_EVENTS = 5


# ======= diffing =======

def _leaves(before: Any, after: Any, path: str) -> Iterator[Tuple[str, Any, Any]]:
    """
    Yield `(path, was, now)` for every leaf that differs between two values.

    Dicts are walked. Lists are walked too, keyed by each row's `id` where every
    row has one, and otherwise by position. A task list diffed as one opaque
    value reports "the list changed" and names nothing, which loses the two
    views that are mostly lists; keying by `id` makes "breaker opened: idle"
    survive a reordering, which is the only part of a reorder a reader acts on.

    A key present on only one side is reported whole, not descended into. That
    is not a shortcut: recursing into a key that appeared this frame yields
    every leaf under it as `None -> value`, so the very first time a task runs
    the payload gains `breakers.idle` and the diff returns a subtree instead of
    the transition. The alert rules match a leaf - `...state`, not `breakers` -
    so descending here is exactly how a real breaker trip goes unnamed.
    """
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}" if path else str(key)
            if key in before and key in after:
                yield from _leaves(before[key], after[key], child)
            else:
                yield child, before.get(key), after.get(key)
    elif isinstance(before, list) and isinstance(after, list):
        for child, old, new in _rows(before, after, path):
            yield from _leaves(old, new, child)
    elif before != after:
        yield path, before, after


def _rows(before: List[Any], after: List[Any],
          path: str) -> Iterator[Tuple[str, Any, Any]]:
    """
    Pair up two lists for diffing, by `id` when every row has one.

    An `id` on one side only yields a `None` counterpart, so a removal reaches
    the alert rules as a dropped row instead of silently shortening the list.
    Rows without an `id` fall back to position, which is all that can honestly
    be said about them.
    """
    if not all(isinstance(row, dict) and "id" in row for row in before + after):
        for index in range(max(len(before), len(after))):
            yield (f"{path}[{index}]",
                   before[index] if index < len(before) else None,
                   after[index] if index < len(after) else None)
        return

    old_ids = [row["id"] for row in before]
    for key in old_ids + [r["id"] for r in after if r["id"] not in old_ids]:
        old = next((r for r in before if r["id"] == key), None)
        new = next((r for r in after if r["id"] == key), None)
        # The `.id` suffix on a one-sided row is what gives the removal rule
        # something to match and the message a name to print.
        yield (f"{path}[{key}].id" if old is None or new is None
               else f"{path}[{key}]"), old, new


def diff(before: Any, after: Any) -> List[Dict[str, Any]]:
    """
    What changed between two payloads: `[{path, was, now}]`, empty if equal.

    Pure. No state, no clock, no I/O, so the interesting part of monitoring can
    be checked without running a watch loop.
    """
    return [{"path": path, "was": was, "now": now}
            for path, was, now in _leaves(before, after, "")]


# ======= naming =======

def _breaker(change: Dict[str, Any]) -> Optional[Tuple[str, Any]]:
    """
    The task id and the state a change carries, if it is a breaker at all.

    Matched by the value's shape rather than by the path's suffix, because the
    same breaker arrives three ways across the three payloads: a `breakers.id
    .state` leaf when the task was already known, a whole `breakers.idle` dict
    when it appeared this frame, and a `tasks[idle].breaker` leaf. A rule
    written against one path misses the other two, and the one that misses is
    whichever view the reader is watching at the moment it matters.
    """
    path, now = change["path"], change["now"]
    if path.startswith("breakers."):
        task_id = path.split(".")[1]
        if isinstance(now, dict):
            return task_id, now.get("state")
        if path.endswith(".state"):
            return task_id, now
    if path.startswith("tasks[") and path.endswith("].breaker"):
        return _task_name(path), now
    return None


def _task_name(path: str) -> str:
    """
    The task a path belongs to, from either shape.

    `breakers.idle.state` and `tasks[idle].breaker` both name `idle`. A path
    naming no task falls back to itself, which is honest: a raw path beats a
    guess at which task it meant.
    """
    if path.startswith("breakers."):
        return path.split(".")[1]
    if "[" in path:
        return path.split("[", 1)[1].split("]", 1)[0]
    return path


# ======= alerting =======

def alerts(changed: List[Dict[str, Any]]) -> List[str]:
    """
    Name the transitions worth interrupting for. Nothing measured, nothing said.

    Every rule matches a field the payload already carries, and every one fires
    on a transition. A rule that fired on a level would train the reader to
    ignore it; a rule with no measured field behind it would be the fabricated
    opinion §3.3 forbids, so there are none.
    """
    out = []
    for change in changed:
        path, was, now = change["path"], change["was"], change["now"]
        # A breaker that opened, or reopened. `was` is the comparison, so an
        # already-open breaker stays quiet on later frames, and an unmeasured
        # one (`None` -> `open`) is the transition that matters.
        tripped = _breaker(change)
        if tripped and tripped[1] == "open" and was != "open":
            out.append(f"breaker opened: {tripped[0]}")
        # A chain that stopped verifying. `intact` is None when no audit file
        # exists, and only a True -> not-True step is a chain that broke.
        elif path == "audit_chain.intact" and was is True and now is not True:
            out.append(f"audit chain no longer intact ({now})")
        # A task that vanished. An unmeasured breaker is deliberately NOT here:
        # a `None` there is a task that never ran, which is a measurement.
        elif now is None and path.endswith(".id"):
            out.append(f"removed task: {_task_name(path)}")
    return out


class Monitor:
    """
    The previous frame, the change count, and the recent transitions.

    One instance per watch loop. It is a value, not a service: there is nothing
    to start, nothing to poll, and nothing to shut down. `observe` is the whole
    interface.
    """

    def __init__(self, view: str):
        self.view = view
        self.events: deque = deque(maxlen=MAX_EVENTS)
        self.changes = 0
        self.frames = 0
        self._last: Optional[Dict[str, Any]] = None

    def observe(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compare against the previous frame and record what changed.

        Returns the change list, empty on the first frame: a baseline is not a
        change. `self.changes` counts frames that differed, so it is the number
        of times something moved, not the number of fields.
        """
        self.frames += 1
        if self._last is None:
            self._last = payload
            return []

        changed = diff(self._last, payload)
        self._last = payload
        if not changed:
            return []

        self.changes += 1
        stamp = time.strftime("%H:%M:%S")
        for line in alerts(changed):
            self.events.append((stamp, line))
        return changed

    def recent(self) -> List[str]:
        """The last few transitions, newest last, formatted for a frame."""
        return [f"{stamp}  {line}"
                for stamp, line in list(self.events)[-VISIBLE_EVENTS:]]

    def baseline(self) -> bool:
        """True on the first frame only: nothing has been compared yet."""
        return self.frames <= 1 and not self.changes
