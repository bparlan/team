#!/usr/bin/env python3
"""
The one audit chain a project writes to, and the one rule for writing to it.

`AuditLogger` is the hash-chained component; it is not modified here and it
hardcodes its filename. `ARCHITECTURE.md` §5.5 used to sketch the chain as
`audit/chain.jsonl`, which disagreed with the component. That disagreement is
resolved on both sides now: the doc names `audit/audit.jsonl`, the component's
name, and every caller - the task repository, the executor, and
`theteam status` - resolves the path through `audit_file()`, so a reported path
is always a path that was opened.

Two rules live here and nowhere else:

  * A broken chain is marked, never swallowed. `ARCHITECTURE.md` §3.2: writes
    continue, and what follows a break is marked `chain_broken`.
  * An empty chain is not a verified one. `verify_chain()` returns `True` on
    an empty list, so the reader reports `absent` / `empty` rather than
    `intact`, with `intact: None` because nothing was measured.

`AuditLogger` has no create/edit/delete event methods, so mutation events go
through `record_event`, which appends via `_write_entry` - the component's
own path, the one that sets `prev_hash` and the entry hash. That is why the
chain still links when a caller logs something the component has no verb for.
"""

import logging
from pathlib import Path
from typing import Any, Dict

from theteam.core.audit import AuditLogger
from theteam.state import StateStore

logger = logging.getLogger(__name__)

# `AuditLogger` builds `<log_dir>/audit.jsonl`. Named once, so nothing else in
# the tree has to know the filename in order to find the file.
AUDIT_FILENAME = "audit.jsonl"


def audit_file(project_root: str) -> Path:
    """The chain file for a project: `<state_dir>/audit/audit.jsonl`."""
    return StateStore(project_root).audit_dir / AUDIT_FILENAME


def audit_logger(project_root: str) -> AuditLogger:
    """The logger for a project's real state directory, not a scratch one."""
    return AuditLogger(log_dir=str(StateStore(project_root).audit_dir))


def _mark_if_broken(log: AuditLogger, entry: Dict[str, Any]) -> None:
    """Stamp `chain_broken` on an entry that is written onto a broken chain."""
    if not log.verify_chain():
        entry["chain_broken"] = True
        logger.warning("Audit chain broken before '%s'; entry marked chain_broken",
                       entry.get("event"))


def record_event(project_root: str, event: str, **fields: Any) -> bool:
    """
    Append one event to the chain. Returns whether the entry was written.

    Used for the mutations `AuditLogger` has no verb for - task create, edit,
    delete. `ARCHITECTURE.md` §3.2: when the chain no longer verifies, writes
    continue and the entry carries `chain_broken`, so a reader of the trail
    sees the break rather than only `status`.

    An unwritable sink is reported and does not raise: a broken audit file
    must not take down the task operation being audited. The return value is
    how a caller would learn, and it is `False` rather than an exception.
    """
    log = audit_logger(project_root)
    entry: Dict[str, Any] = {"event": event}
    entry.update(fields)
    _mark_if_broken(log, entry)
    try:
        log._write_entry(entry)
        return True
    except OSError as exc:
        logger.error("Audit write failed for '%s': %s", event, exc)
        return False


def record_task_event(project_root: str, method: str, *args: Any, **kwargs: Any) -> bool:
    """
    Append a task execution event through one of `AuditLogger`'s own loggers.

    `log_task_start`, `log_task_complete` and `log_task_failed` build their
    entries inside the component, so a `chain_broken` flag cannot be attached
    to one without editing `theteam/core/audit.py` - which this milestone does
    not do. The break is instead written as its own chained entry immediately
    before the event, so the trail records where the chain stopped verifying
    instead of dropping the signal.
    """
    log = audit_logger(project_root)
    try:
        if not log.verify_chain():
            log._write_entry({"event": "chain_broken", "before": method,
                              "task": args[0] if args else None})
        getattr(log, method)(*args, **kwargs)
        return True
    except OSError as exc:
        logger.error("Audit write failed for '%s': %s", method, exc)
        return False


def read_chain_state(project_root: str) -> Dict[str, Any]:
    """
    What `theteam status` reports about the chain, with a real check behind it.

    Four states, and the three that are not "intact" are not collapsed into it.
    `verify_chain()` returns `True` for an empty list, so an absent file and a
    file with no parseable entries are reported as themselves with
    `intact: None` - nothing was measured, so nothing is claimed.
    """
    path = audit_file(project_root)
    state: Dict[str, Any] = {
        "file": str(path),
        "exists": path.is_file(),
        "entries": 0,
        "lines": 0,
        "state": "absent",
        "intact": None,
        "reason": None,
    }
    if not state["exists"]:
        state["reason"] = f"no audit file at {path}"
        return state

    with open(path, "r", encoding="utf-8") as handle:
        lines = [line for line in handle if line.strip()]
    state["lines"] = len(lines)

    log = audit_logger(project_root)
    entries = log.get_audit_trail()
    state["entries"] = len(entries)
    if not entries:
        state["state"] = "empty"
        state["reason"] = (
            f"{path} has {len(lines)} line(s) and no parseable entry"
            if lines
            else f"{path} is empty; nothing has been audited yet"
        )
        return state

    intact = log.verify_chain()
    state["intact"] = intact
    state["state"] = "intact" if intact else "broken"
    if not intact:
        state["reason"] = f"hash chain does not verify across {len(entries)} entries"
    return state


def chain_line(state: Dict[str, Any]) -> str:
    """The one human line for the chain, reading the same fields the JSON does."""
    if state["state"] == "absent":
        return f"audit chain    absent ({state['reason']})"
    if state["state"] == "empty":
        return f"audit chain    empty ({state['reason']})"
    if state.get("intact"):
        return (f"audit chain    intact, {state.get('entries', 0)} entries "
                f"({state['file']})")
    return f"audit chain    BROKEN ({state['reason']}, {state['file']})"


__all__ = [
    "AUDIT_FILENAME",
    "audit_file",
    "audit_logger",
    "chain_line",
    "read_chain_state",
    "record_event",
    "record_task_event",
]
