#!/usr/bin/env python3
"""
theteam.advisory.context_slice - give each member the project context it needs.

`theteam/__init__.py:93` used to `yaml.dump(project_context)` into *every*
member's prompt. Measured on this repository: 2,499 characters per member,
of which `runtime_config` alone is 1,272. For a five-member roster the same
tokens were paid five times, and §4.6 caps the per-turn context budget at
~2k tokens *per member* precisely because a member should not be reading
the whole project.

§M9 Phase 3 is explicit about the shape: slice by the flag the member's focus
implies, start with a token match against `expertise`, and add an explicit
mapping only if the match proves unreliable. The evidence for that match
being good enough is in the test file: every section in the real context is
delivered to at least one member.

## There are no flags in the context

The milestone text says "slice by the flag its focus implies", and the
*project* context does have focus flags - `security_focus`,
`database_focus` and five others, from `analyze_project_context`. Those are
what decide the **roster** (`manager.py` reads them). The dictionary
`aggregate_project_context` returns has no flags in it at all: it is
`project_goal`, `runtime_config`, `token_budget`, `registered_structure`,
`last_health_scan`, `production_invariants`, `timestamp`, `project_root`.

So the phase means: slice the *sections* each member's declared expertise
implies, using the focus-token table the selector already owns. Reusing
that table is the point - a second copy of "what summons the architect"
would be a second source of truth, which is the dead end
`selector.py:201-207` records.

## A section delivered to nobody is reported

§M9: "every fired flag must reach at least one member, and a flag delivered
to nobody is reported, not dropped." Dropping a section silently is how a
member stops knowing something and nothing says so. `undelivered_sections`
names them, and the caller prints them.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

# §4.6: every member gets these regardless of focus. They are small, and a
# member with no project root cannot place its own advice.
ALWAYS_DELIVERED = ("project_goal", "project_root")

# `timestamp` changes on every call and carries no information a member can
# act on. Delivering it would make two identical discussions produce two
# different prompts, which is a determinism bug, not freshness.
NEVER_DELIVERED = ("timestamp",)

_WORD = re.compile(r"[a-z0-9][a-z0-9._-]*")


def _tokens(text: str) -> Set[str]:
    return set(_WORD.findall(str(text).lower()))


def _member_focus(member: Dict[str, Any]) -> Set[str]:
    """The vocabulary a member declares: expertise, role and voice.

    All three, because a member's declared `voice` is as much a statement
    of what it looks at as its `expertise` is - "asks what breaks in 6
    months" is a blast-radius signal, and `blast` is not in the
    architect's `expertise` string.
    """
    return _tokens(" ".join(str(member.get(field, "")) for field in
                            ("expertise", "role", "voice")))


def _section_matches(key: str, value: Any, focus: Set[str],
                     focus_tokens: Set[str]) -> bool:
    """Whether a context section is relevant to this member.

    §M9: start with a token match against `expertise`, and add an explicit
    mapping only if the match proves unreliable. It has not proven
    unreliable, so there is no mapping. The match is over the section's
    *content*, not just its name: a member who knows about `package.json`
    cares about a section called `runtime_config` that happens to contain
    one.
    """
    haystack = _tokens(f"{key} {yaml.dump(value, default_flow_style=False)}")
    return bool(haystack & (focus | focus_tokens))


def slice_context(
    project_context: Any,
    member: Dict[str, Any],
    focus_tokens: Optional[Set[str]] = None,
) -> Tuple[str, List[str]]:
    """The project context this member gets, and what it does not.

    Returns `(rendered_yaml, undelivered_section_names)`. The second value
    is not diagnostic noise: it is the §M9 requirement that a section
    reaching nobody is *reported* rather than dropped, and the caller
    prints it.

    `focus_tokens` is `selector.FOCUS_TOKENS[member_id]` when the member has
    one. It is passed in rather than imported at module scope so this module
    has no dependency on the selector, and so a caller that already has the
    table does not rebuild it.
    """
    if not isinstance(project_context, dict):
        return str(project_context), []

    from theteam.advisory.selector import FOCUS_TOKENS

    member_id = str(member.get("id", ""))
    table = focus_tokens if focus_tokens is not None else FOCUS_TOKENS.get(
        member_id, frozenset())
    focus = _member_focus(member)

    delivered: Dict[str, Any] = {}
    undelivered: List[str] = []

    for key, value in project_context.items():
        if key in NEVER_DELIVERED:
            continue
        if key in ALWAYS_DELIVERED:
            delivered[key] = value
            continue
        # An empty section carries nothing. Delivering `token_budget: {}`
        # to everyone is noise that reads like a measurement.
        if value in (None, "", [], {}):
            continue
        if _section_matches(key, value, focus, set(table)):
            delivered[key] = value
        else:
            undelivered.append(key)

    return yaml.dump(delivered, default_flow_style=False), undelivered


def undelivered_sections(
    project_context: Any,
    roster: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """Which sections no member on the roster would receive.

    §M9: a flag delivered to nobody is reported, not dropped. This is the
    cross-member view that a per-member return value cannot give, and it is
    the one that matters: a section every member misses is a fact the team
    does not know.
    """
    reached: Dict[str, List[str]] = {}
    if not isinstance(project_context, dict):
        return reached

    from theteam.advisory.selector import FOCUS_TOKENS

    for member in roster:
        _, missed = slice_context(project_context, member,
                                  FOCUS_TOKENS.get(str(member.get("id", "")),
                                                   frozenset()))
        member_id = str(member.get("id", ""))
        for key in missed:
            reached.setdefault(key, []).append(member_id)

    return {key: sorted(set(members))
            for key, members in reached.items()
            if len(set(members)) == len(roster)}
