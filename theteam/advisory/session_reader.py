#!/usr/bin/env python3
"""
theteam.advisory.session_reader - read the user's real OMP session.

The session is a JSONL file on disk, not an API. That is the whole reason this
layer is affordable: reading a 1.85 MB file is cheap, pasting its contents into
a prompt is not. So this module returns *structure* - the last few things the
user said, the names of the tools that ran, the paths they were pointed at -
and never a tool result. A `read` result is an entire file; letting one into a
member prompt is the cost risk ARCHITECTURE.md §4.3 names.

The depth rule (C2) is the part that is easy to get wrong. A session directory
holds one top-level `.jsonl` for the user's session plus a `__advisor.jsonl`
per subagent in a subdirectory. Measured on this machine: 59 top-level files
against 285 subagent transcripts. "Newest `.jsonl`" without the depth rule
comments on a subagent and presents it as the user's work, which is the exact
class of confident-wrong-output failure the product's one rule forbids.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

# §4.4 caps. K defaults to 4 messages and is hard-capped at 8.
DEFAULT_MESSAGES = 4
MAX_MESSAGES = 8
MESSAGE_CHARS = 400
ACTIVITY_LIMIT = 8

# A subagent's own transcript, at any depth. Never a session.
SUBAGENT_MARKER = "__advisor.jsonl"

SESSIONS_DIR_ENV = "THETEAM_SESSIONS_DIR"


class SessionFormatError(ValueError):
    """A session line is not parseable. Names the file and the line, always.

    §3.2 says malformed input raises rather than degrading. A session we
    half-understand is worse than one we refuse: the reader would report a
    digest over half a session and the team would comment on a session that
    does not exist.
    """


@dataclass
class SessionSlice:
    """The four small things §4.4 says a reader returns."""

    last_user_messages: List[str] = field(default_factory=list)
    recent_activity: List[str] = field(default_factory=list)
    touched_paths: List[str] = field(default_factory=list)
    digest: str = ""


@dataclass
class SessionResult:
    """What a read produced, or why it produced nothing.

    `spoke` is carried here so the §3.2 failure rows have one shape wherever
    they are read: either a slice exists, or `reason` names why not. There is
    no third state, and in particular no default slice standing in for a real
    one.
    """

    spoke: bool
    reason: Optional[str] = None
    slice: Optional[SessionSlice] = None
    session_path: Optional[str] = None
    event_count: int = 0


def sessions_root() -> Path:
    """Where OMP keeps sessions. Overridable so a test need not touch $HOME."""
    override = os.environ.get(SESSIONS_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".omp" / "agent" / "sessions"


def session_slug(project_root: str) -> str:
    """The directory name OMP gives a project root.

    Home-relative when the project is under home, absolute otherwise, with
    every separator turned into a dash. Verified against the 44 session
    directories on this machine: `/Users/bparlan/devcode/team` is
    `-devcode-team`, `/Users/bparlan/devcode` is `-devcode`, a bare
    `/Users/bparlan` is `-`, and `/private/tmp` is `--private-tmp` (absolute,
    so the leading separator doubles up).
    """
    root = Path(project_root).expanduser().resolve()
    home = Path.home().resolve()
    try:
        relative = root.relative_to(home).as_posix()
    except ValueError:
        relative = root.as_posix()
    return relative.replace("/", "-")


def _is_subagent(path: Path) -> bool:
    return path.name == SUBAGENT_MARKER


def resolve_session_path(project_root: str, session_path: Optional[str] = None) -> SessionResult:
    """Find the session to read, or say why there is none.

    The depth rule lives here: a candidate must be a *direct child* of the
    session directory. Anything one level deeper belongs to a subagent.
    """
    if session_path is None:
        directory = sessions_root() / session_slug(project_root)
        if not directory.is_dir():
            return SessionResult(
                spoke=False, reason="no_session", session_path=str(directory)
            )
        candidates = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            return SessionResult(
                spoke=False, reason="no_session", session_path=str(directory)
            )
        return SessionResult(spoke=True, session_path=str(candidates[-1]))

    candidate = Path(session_path).expanduser().resolve()
    if _is_subagent(candidate):
        return SessionResult(
            spoke=False, reason="no_session", session_path=str(candidate)
        )
    sessions_dir = sessions_root()
    try:
        candidate.relative_to(sessions_dir)
    except ValueError:
        pass
    else:
        parent = candidate.parent
        if parent.parent != sessions_dir and _within_sessions(sessions_dir, candidate):
            return SessionResult(
                spoke=False, reason="no_session", session_path=str(candidate)
            )
    if not candidate.is_file():
        return SessionResult(
            spoke=False, reason="no_session", session_path=str(candidate)
        )
    return SessionResult(spoke=True, session_path=str(candidate))


def _within_sessions(sessions_dir: Path, candidate: Path) -> bool:
    """Whether the path sits under any slug directory rather than beside one."""
    try:
        relative = candidate.relative_to(sessions_dir)
    except ValueError:
        return False
    return len(relative.parts) >= 2


def _iter_events(path: Path):
    """Every event in the file, in order. Raises naming the file and line."""
    with open(path, "r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise SessionFormatError(
                    f"{path}:{number}: not valid JSON ({exc.msg})"
                ) from exc
            if not isinstance(event, dict):
                raise SessionFormatError(
                    f"{path}:{number}: expected a JSON object, got {type(event).__name__}"
                )
            yield event


def _parts(event: dict) -> List[dict]:
    message = event.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [part for part in content if isinstance(part, dict)]


def _paths_from_arguments(arguments: Any) -> List[str]:
    """File paths a tool was pointed at. Names only, never content."""
    if not isinstance(arguments, dict):
        return []
    found: List[str] = []
    single = arguments.get("path")
    if isinstance(single, str) and single:
        found.append(single)
    many = arguments.get("paths")
    if isinstance(many, list):
        found.extend(item for item in many if isinstance(item, str) and item)
    return found


def _digest_of(messages: List[str], activity: List[str], paths: List[str]) -> str:
    payload = json.dumps(
        {"messages": messages, "activity": activity, "paths": paths},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_session(project_root: str, session_path: Optional[str] = None,
                 messages: int = DEFAULT_MESSAGES) -> SessionResult:
    """Read a session into a `SessionSlice`, or report why there is not one.

    `messages` is K from §4.4. It defaults to 4 and is hard-capped at 8; the
    cap is enforced here rather than trusted, because a caller passing 500 is
    a bug that would otherwise quietly cost 500x the budget.
    """
    limit = min(max(int(messages), 0), MAX_MESSAGES)
    resolved = resolve_session_path(project_root, session_path)
    if not resolved.spoke:
        return resolved

    path = Path(resolved.session_path)
    user_texts: List[str] = []
    activity: List[str] = []
    touched: List[str] = []
    event_count = 0

    for event in _iter_events(path):
        if event.get("type") != "message":
            continue
        event_count += 1
        message = event.get("message")
        role = message.get("role") if isinstance(message, dict) else None
        for part in _parts(event):
            kind = part.get("type")
            if kind == "text" and role == "user":
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    user_texts.append(text.strip()[:MESSAGE_CHARS])
            elif kind == "toolCall":
                name = part.get("name")
                if isinstance(name, str) and name:
                    activity.append(name)
                for touched_path in _paths_from_arguments(part.get("arguments")):
                    if touched_path not in touched:
                        touched.append(touched_path)

    if event_count == 0:
        # An empty or all-noise file. There is no session to comment on, and
        # guessing is what §3.3 forbids.
        return SessionResult(
            spoke=False, reason="no_session", session_path=str(path)
        )

    tail = user_texts[-limit:] if limit else []
    recent = activity[-ACTIVITY_LIMIT:]
    slice_ = SessionSlice(
        last_user_messages=tail,
        recent_activity=recent,
        touched_paths=touched,
        digest=_digest_of(tail, recent, touched),
    )
    return SessionResult(
        spoke=True, slice=slice_, session_path=str(path), event_count=event_count
    )


class SessionReader:
    """The reader, held. `read()` is the only thing callers need."""

    def __init__(self, project_root: str, session_path: Optional[str] = None,
                 messages: int = DEFAULT_MESSAGES):
        self.project_root = project_root
        self.session_path = session_path
        self.messages = messages

    def read(self) -> SessionResult:
        return read_session(
            self.project_root, self.session_path, messages=self.messages
        )
