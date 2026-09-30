#!/usr/bin/env python3
"""
theteam.advisory.manager - grow the roster from the topic. M9 Phase 2.

`theteam discuss` spawns whoever is on the roster. M9 Phase 1 made it spawn
whoever the *selector* picks; this module decides who is *on the roster* at
all, which until now was frozen at bootstrap.

## The split that makes this testable

The manager is the one part of the advisory layer that may be an LLM, and
§4.5's prior art is explicit that the selector may not. That boundary is
kept here in the same place:

* **`detect_triggers` is deterministic.** It reads the project flags and the
  topic's vocabulary and returns the candidate members. Zero LLM calls, and a
  test asserts two identical calls agree.
* **The LLM only narrates.** It receives the detected candidates, the project
  context, and any search results, and writes a *reason* per candidate. It
  cannot add a member that `detect_triggers` did not return, and it cannot
  remove one. A model that invents a member is a fabricated roster, which is
  the §3.3 defect in a new place.

## Two independent triggers, per §M9

`analyze_project_context` derives members from *project* flags. A topic about
rate limiting adds nobody; only a project with `infrastructure_focus` does.
The requirement is topic-driven, so a member is a candidate when **either**:

1. the project has a focus flag no current member covers (`uncovered flag`), or
2. the topic has vocabulary no current member's `expertise` covers
   (`uncovered vocabulary`).

Project context alone gives the same team for every question. Topic alone
gives a team blind to what the repo contains.

## The cap is the catalog, not a number

§M9 asked "what caps roster size?" and warned that a manager which grows
every run reaches 30 members, at which point the selector picks 4 from 30
using signals stale by construction. The answer was already in the code:
`theteam.BASE_MEMBERS` plus `theteam.FOCUS_MEMBERS` define every member that
can exist. There are 9. A member outside the catalog is not a member this
milestone can add, and asking for one is reported as `uncatalogued` rather
than invented.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from theteam import BASE_MEMBERS, FOCUS_FLAG_BY_MEMBER, FOCUS_MEMBERS

# Every member id that can exist, base plus focus. The roster cap.
CATALOG: Dict[str, Dict[str, Any]] = {m["id"]: m for m in BASE_MEMBERS}
CATALOG.update({m["id"]: m for m in FOCUS_MEMBERS.values()})

# Words too common to be evidence of a focus, mirroring the selector's table.
# Duplicated deliberately and *narrowly*: the selector's own set is the
# contract for who speaks, and this module must not become a second source of
# truth for it. This list only guards the topic-vocabulary trigger, and a
# token in this set is never counted as uncovered vocabulary.
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
    "theteam", "project", "team", "member", "topic", "discussion",
})

_WORD = re.compile(r"[a-z0-9][a-z0-9._-]*")


def topic_tokens(topic: str) -> List[str]:
    """Content words in a topic, in order, stop words removed."""
    return [t for t in _WORD.findall(str(topic).lower()) if t not in STOP_TOKENS]


def _vocabulary(member: Dict[str, Any]) -> Set[str]:
    """The tokens a member's `expertise` and `role` declare."""
    text = f"{member.get('expertise', '')} {member.get('role', '')}"
    return {t for t in _WORD.findall(text.lower()) if t not in STOP_TOKENS}


def uncovered_flags(context: Dict[str, Any], roster: List[Dict[str, Any]]) -> Dict[str, str]:
    """Focus flags the project has that no current member covers.

    Returns `{member_id: flag}`. A flag is covered when the roster already
    contains the member that flag produces — not when a member merely sounds
    related, because "sounds related" is the judgement that made the earlier
    relevance filter collapse.
    """
    on_roster = {m.get("id") for m in roster}
    gaps: Dict[str, str] = {}
    for flag, enabled in sorted(context.items()):
        if not enabled:
            continue
        member_id = next((mid for mid, f in FOCUS_FLAG_BY_MEMBER.items()
                          if f == flag), None)
        if member_id and member_id not in on_roster:
            gaps[member_id] = flag
    return gaps


def uncovered_vocabulary(topic: str, roster: List[Dict[str, Any]]) -> List[Tuple[str, List[str]]]:
    """Catalog members whose vocabulary a topic uses and no member covers.

    Returns `[(member_id, [matched_tokens])]`, one per catalog member that is
    not on the roster and matches at least one topic token. A token counts as
    covered when any roster member's `expertise`/`role` declares it.
    """
    covered: Set[str] = set()
    for member in roster:
        covered |= _vocabulary(member)
    on_roster = {m.get("id") for m in roster}
    tokens = topic_tokens(topic)

    hits: List[Tuple[str, List[str]]] = []
    for member_id, member in CATALOG.items():
        if member_id in on_roster:
            continue
        matched = [t for t in tokens if t in _vocabulary(member) and t not in covered]
        if matched:
            hits.append((member_id, matched))
    return hits


def detect_triggers(
    topic: str,
    context: Dict[str, Any],
    roster: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Who the topic and the project say is missing. Deterministic, no LLM.

    Returns `{add: [{member, reasons: [...]}], covered_flags: {...}}`. Every
    candidate carries the evidence that produced it: either a focus flag name
    or the topic tokens that matched. A candidate with no evidence is not
    returned, because "you might want a database person" is not a reason.
    """
    flag_gaps = uncovered_flags(context, roster)
    vocab_gaps = dict(uncovered_vocabulary(topic, roster))

    add: List[Dict[str, Any]] = []
    for member_id in sorted(flag_gaps):
        add.append({
            "member": member_id,
            "reasons": [f"project has {flag_gaps[member_id]}, and no member covers it"],
        })
    for member_id, tokens in sorted(vocab_gaps.items()):
        if member_id in flag_gaps:
            add[[a["member"] for a in add].index(member_id)]["reasons"].append(
                f"topic vocabulary no member covers: {', '.join(tokens)}"
            )
            continue
        add.append({
            "member": member_id,
            "reasons": [f"topic vocabulary no member covers: {', '.join(tokens)}"],
        })

    return {
        "add": add,
        "covered_flags": {
            FOCUS_FLAG_BY_MEMBER[m["id"]]: m["id"]
            for m in roster if m.get("id") in FOCUS_FLAG_BY_MEMBER
        },
    }


def reasons_for(member_id: str, context: Dict[str, Any],
                topic: Optional[str] = None,
                member: Optional[Dict[str, Any]] = None) -> List[str]:
    """Why a member is on the roster, from evidence. Used by `--status`.

    Three sources, in order of authority:

    1. `added_reason` recorded on the member when `manager --apply` added it.
       That is a historical fact and outranks everything below it.
    2. The focus flag the project currently fires.
    3. The base roster every project starts with.

    A member matching none of those is reported as having no recorded reason.
    It is not given one: "you might want a database person" is not a reason,
    and inventing a plausible line here is the §3.3 defect in a small place.
    """
    if member_id not in CATALOG:
        return [f"{member_id} is not in the team catalog"]

    if member and member.get("added_reason"):
        recorded = list(member["added_reason"])
        topic_for = member.get("added_for_topic")
        if topic_for:
            recorded.append(f"added for topic: {topic_for}")
        return recorded

    if member_id in {m["id"] for m in BASE_MEMBERS}:
        return ["base roster member: present in every project's team"]
    flag = FOCUS_FLAG_BY_MEMBER.get(member_id)
    if flag and context.get(flag):
        return [f"project has {flag}"]
    if topic:
        matched = [t for t in topic_tokens(topic) if t in _vocabulary(CATALOG[member_id])]
        if matched:
            return [f"topic vocabulary: {', '.join(matched)}"]
    return [f"{member_id} has no recorded reason and should not be on the roster"]


def reset_roster(project_root: str) -> List[Dict[str, Any]]:
    """The roster a fresh bootstrap would produce for this project.

    Regenerated rather than remembered: a reset that restored a stored copy
    would restore a roster bootstrapped before the project changed, which is
    not what "reset" means to anyone standing at the command.
    """
    from theteam import generate_team_members_from_context

    return list(generate_team_members_from_context(project_root)["team"])
