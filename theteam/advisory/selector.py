#!/usr/bin/env python3
"""
theteam.advisory.selector - pick which roster members speak. No LLM.

ARCHITECTURE.md 4.5 is explicit that selection is deterministic: "the same
session state selects the same members, so a test can assert it." That is the
whole reason this module costs nothing. A selection that needed a model call
would cost money on every tick and could not be asserted, which would make the
2-fragment budget of 4.6 unenforceable - you cannot cap what you cannot
reproduce.

Signals come from three places, all already in hand:

* the file extensions in the session's `touched_paths`
* tokens in the latest user message, matched against each member's focus
* the active task's `type` and the loop's current phase

The extension and task-type tables below are transcribed from 4.5. The token
table is derived from the `expertise` strings that
`generate_team_members_from_context` already declares, so a member's declared
focus and the words that summon it cannot drift apart.

If nothing fires, the skeptic speaks alone. A lone skeptic is the correct
default; the alternative is a unanimous chorus, which is one voice repeated
four times.
"""

import re
from typing import Any, Dict, List, Optional, Set

from theteam.advisory.session_reader import SessionSlice

# The cap from 4.5. Exceeding it truncates and records `truncated: true`
# rather than dropping members silently.
MEMBER_CAP = 4

# The three members `generate_team_members_from_context` always includes.
# They are the floor of every roster.
ALWAYS_PRESENT = ("architect", "pragmatist", "skeptic")

# The default when nothing fires (4.5).
SOLO_DEFAULT = "skeptic"

# 4.5's extension table. Only members actually on the roster are selected, so
# a `.sql` file in a project with no database focus does not conjure a data
# reviewer.
EXTENSION_SIGNALS = {
    "designer": (".tsx", ".jsx", ".css", ".scss", ".sass", ".less"),
    "devops": (".py", ".rs", ".go", ".sh", ".tf", ".dockerfile"),
    "data": (".sql",),
    "api": (".yaml", ".yml", ".json", ".proto"),
    "analyst": (".ipynb", ".csv", ".parquet"),
    "security": (".env", ".pem", ".key"),
}

# 4.5's task-type table.
TASK_TYPE_SIGNALS = {
    "analysis": ("architect", "skeptic"),
    "ops": ("devops",),
    "security": ("security",),
    "data": ("data", "analyst"),
    "design": ("designer",),
    "api": ("api",),
}

# 4.5's phase table.
PHASE_SIGNALS = {
    "executing": ("devops",),
    "planning": ("skeptic",),
    "reviewing": ("skeptic",),
    "designing": ("designer",),
}

# The words that summon a member, derived from the `expertise` field each
# member already declares. Token matching, not substring: "api" must not fire
# on "capital" and "css" must not fire on "access".
FOCUS_TOKENS = {
    "architect": frozenset({
        "architecture", "architect", "coupling", "maintainability",
        "blast", "design", "structure", "boundary", "boundaries",
        "interface", "contract", "layering", "dependency",
    }),
    "pragmatist": frozenset({
        "ship", "shipping", "scope", "speed", "quick", "fast",
        "pragmatic", "simplify", "simplest", "yagni", "overengineering",
        "over-engineering", "bandwidth", "lean",
    }),
    "skeptic": frozenset({
        "skeptical", "skeptic", "verify", "verification", "evidence",
        "edge", "fail", "failing", "failure", "silent", "bug", "bugs",
        "wrong", "confirm", "proof", "claim", "unverified", "risk",
    }),
    "security": frozenset({
        "security", "auth", "authentication", "secret", "secrets",
        "vulnerability", "vulnerabilities", "injection", "xss", "csrf",
        "credential", "credentials", "token", "tokens", "exploit",
    }),
    "analyst": frozenset({
        "data", "metric", "metrics", "analysis", "leakage", "sample",
        "distribution", "reproducibility", "notebook", "statistical",
    }),
    "designer": frozenset({
        "ui", "ux", "layout", "css", "design", "accessibility",
        "a11y", "visual", "responsive", "component", "interaction",
        "keyboard", "contrast", "frontend", "front-end",
    }),
    "api": frozenset({
        "api", "apis", "endpoint", "endpoints", "contract", "contracts",
        "versioning", "schema", "openapi", "rest", "graphql", "compat",
        "compatibility", "backwards",
    }),
    "data": frozenset({
        "database", "databases", "schema", "migration", "migrations",
        "index", "indexes", "transaction", "transactions", "sql", "query",
        "queries", "table", "postgres", "mysql", "sqlite",
    }),
    "devops": frozenset({
        "deploy", "deployment", "deploys", "docker", "kubernetes", "k8s",
        "terraform", "infrastructure", "infra", "ci", "cd", "pipeline",
        "recover", "recovery", "rollback", "resource", "host", "cluster",
    }),
}

# Words too common to mean anything. A 6-letter word like "design" can appear
# in a thousand contexts; "the" and "should" are not evidence of a focus.
STOP_TOKENS = frozenset({
    "the", "and", "for", "with", "this", "that", "from", "have", "has",
    "was", "were", "are", "you", "your", "our", "not", "but", "all",
    "can", "will", "would", "should", "could", "just", "now", "new",
    "use", "using", "used", "make", "made", "get", "got", "set", "put",
    "add", "run", "fix", "work", "works", "working", "need", "needs",
    "want", "let", "lets", "how", "why", "what", "when", "where", "who",
    "here", "there", "then", "than", "them", "they", "some", "any",
    "into", "out", "off", "over", "under", "again", "also", "more",
    "most", "much", "many", "very", "one", "two", "see", "look",
    "please", "thanks", "thank", "yes", "ok", "okay", "no",
})

_WORD = re.compile(r"[a-z0-9][a-z0-9._-]*")


def _tokens(text: str) -> Set[str]:
    """Lowercase word tokens, split on anything that is not word-ish.

    Hyphens and dots are kept inside a token so `over-engineering` and
    `front-end` arrive as one word. Without that, the two most useful
    pragmaticist signals would never match anything anyone actually types.
    """
    return {token for token in _WORD.findall(text.lower()) if token}


def _member_ids(roster: Optional[Dict[str, Any]]) -> List[str]:
    """The enabled member ids on a roster, or the always-present floor.

    A roster that was never bootstrapped still has three people to talk to.
    Inventing a wider roster from nothing would be the 3.3 defect.
    """
    if not roster:
        return list(ALWAYS_PRESENT)
    ids = [
        member.get("id")
        for member in roster.get("team", [])
        if member.get("enabled", True) and member.get("id")
    ]
    return ids or list(ALWAYS_PRESENT)


def _extension_signals(paths: List[str]) -> Dict[str, List[str]]:
    """Which member each touched file's extension belongs to."""
    fired: Dict[str, List[str]] = {}
    for path in paths:
        name = str(path).rsplit("/", 1)[-1].lower()
        for member_id, extensions in EXTENSION_SIGNALS.items():
            if name.endswith(extensions):
                fired.setdefault(member_id, []).append(name)
    return fired


def _message_signals(message: str) -> Set[str]:
    """Members whose focus tokens appear in the latest user message."""
    found = set()
    for token in _tokens(message):
        if token in STOP_TOKENS:
            continue
        for member_id, focus in FOCUS_TOKENS.items():
            if token in focus:
                found.add(member_id)
    return found


def select_members(
    slice_: SessionSlice,
    context: Optional[Dict[str, Any]] = None,
    task_type: Optional[str] = None,
    phase: Optional[str] = None,
    roster: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Which members speak this turn. Deterministic, zero LLM calls.

    `context` is the flag dict `analyze_project_context` returns. It is
    accepted and ignored: 4.5 lists four signals and it is not one of them.
    It was tried as a relevance filter and it collapsed the whole
    differentiation the gate exists to check - a project with
    `database_focus` set and one without both fell back to the same member,
    because the filter ran after selection and overwrote it. A gate that
    cannot fail is not a gate. The flags still matter for who is on the
    roster, which is `roster`'s job, not this module's.

    Returns `{"members": [...], "truncated": bool, "signals": {...}}`.
    """
    del context  # not a 4.5 signal; see docstring
    available = _member_ids(roster)
    available_set = set(available)
    signals: Dict[str, Any] = {}

    # 1. File extensions in the paths the session touched.
    extensions = _extension_signals(list(slice_.touched_paths or []))
    if extensions:
        signals["extensions"] = {
            member: sorted(set(names)) for member, names in extensions.items()
        }

    # 2. Tokens in the latest user message.
    latest = (slice_.last_user_messages or [""])[-1]
    from_message = _message_signals(latest)
    if from_message:
        signals["message"] = sorted(from_message)

    # 3. The active task's declared type.
    from_task = {m for m in TASK_TYPE_SIGNALS.get(task_type or "", ())}
    if from_task:
        signals["task_type"] = task_type

    # 4. The loop's current phase.
    from_phase = set(PHASE_SIGNALS.get(phase or "", ()))
    if from_phase:
        signals["phase"] = phase

    selected: List[str] = []
    # Roster order first, so a member two signals agree on is not ranked
    # above one that only one signal picked. Determinism is the point; a
    # stable, explainable order beats a clever one.
    def take(candidates: Set[str]) -> None:
        for member_id in available:
            if member_id in candidates and member_id not in selected:
                selected.append(member_id)

    take(set(extensions))
    take(from_message)
    take(from_task)
    take(from_phase)

    if not selected:
        # 4.5: a lone skeptic is the correct default.
        return {
            "members": [SOLO_DEFAULT] if SOLO_DEFAULT in available_set
                        else available[:1],
            "truncated": False,
            "suppressed": 0,
            "signals": {"default": SOLO_DEFAULT},
        }

    truncated = len(selected) > MEMBER_CAP
    suppressed = len(selected) - MEMBER_CAP if truncated else 0
    if truncated:
        selected = selected[:MEMBER_CAP]

    return {
        "members": selected,
        "truncated": truncated,
        # How many were dropped, so a caller can report the truncation
        # instead of inferring it. A caller that re-derives this from
        # `len(members)` after the slice sees zero by construction, which is
        # how a "1 suppressed" report line becomes one that can never fire.
        "suppressed": suppressed,
        "signals": signals,
    }
