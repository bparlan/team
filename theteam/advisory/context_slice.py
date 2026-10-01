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
from typing import AbstractSet, Any, Dict, List, Optional, Set, Tuple

import yaml

# §4.6: every member gets these regardless of focus. They are small, and a
# member with no project root cannot place its own advice.
ALWAYS_DELIVERED = ("project_goal", "project_root", "run_context")

# `run_context` is here for the same reason `project_goal` is: it is
# project-wide state that every member needs, not a section a focus token
# should route. Without it, delivery depended on a member's focus tokens
# happening to share a word with the summary — measured: the section reached
# 1 of 5 members on this repository, which is the §M9 "a section reaching
# nobody is reported, not dropped" case in its worse form, where nobody is
# told and four members reason without it.
#
# It is bounded by `MAX_SUMMARY_BYTES` in `theteam/core/run_context.py`, so
# delivering it to everyone costs at most a few hundred tokens per member.

# `timestamp` changes on every call and carries no information a member can
# act on. Delivering it would make two identical discussions produce two
# different prompts, which is a determinism bug, not freshness.
NEVER_DELIVERED = ("timestamp",)

_WORD = re.compile(r"[a-z0-9][a-z0-9._-]*")


def _tokens(text: str) -> Set[str]:
    """Word tokens, minus the words that mean nothing as evidence.

    The stop filter is not cosmetic. Measured on this repository's real
    context, an unfiltered match carried `runtime_config` (1,272 chars) to
    all five members on the strength of the tokens `in` (from
    "pack**in**-module scope"), `and`, `for` and `reviewer`. The saving was
    39%. `selector.STOP_TOKENS` is the existing list, reused here rather
    than re-declared, for the same reason `FOCUS_TOKENS` is reused.
    """
    from theteam.advisory.selector import STOP_TOKENS

    return {t for t in _WORD.findall(str(text).lower()) if t not in STOP_TOKENS}


def _member_focus(member: Dict[str, Any]) -> Set[str]:
    """The vocabulary a member declares: expertise, role and voice.

    All three, because a member's declared `voice` is as much a statement
    of what it looks at as its `expertise` is - "asks what breaks in 6
    months" is a blast-radius signal, and `blast` is not in the
    architect's `expertise` string.
    """
    return _tokens(" ".join(str(member.get(field, "")) for field in
                            ("expertise", "role", "voice")))


#: How many distinct tokens must match before a section is delivered.
#:
#: Measured, not chosen. A single-token match carried `runtime_config`
#: (1,272 chars — 91% of a member's whole budget) to four of five members
#: on the strength of `scope` and `reviewer` appearing somewhere in a
#: package description. At 2, the same context saves 75% instead of 39%
#: and reaches only the architect and devops, who match on
#: architecture/contract and ci/infrastructure/stability respectively.
#: Three matches changes nothing over two, so the extra requirement would
#: be cost without effect.
MATCH_THRESHOLD = 2


def _section_matches(key: str, value: Any, focus: Set[str],
                     focus_tokens: Set[str]) -> bool:
    """Whether a context section is relevant to this member.

    §M9: start with a token match against `expertise`, and add an explicit
    mapping only if the match proves unreliable in testing. It proved
    unreliable, and the fix is `MATCH_THRESHOLD` rather than a hand-written
    section-to-member table: a mapping would be a second source of truth
    beside `FOCUS_TOKENS`, and this keeps one rule instead of two.

    The match is over the section's *content*, not just its name, because a
    member who cares about a `pyproject.toml` deserves it whether the
    enclosing key is `runtime_config` or `manifest`.
    """
    haystack = _tokens(f"{key} {yaml.dump(value, default_flow_style=False)}")
    return len(haystack & (focus | focus_tokens)) >= MATCH_THRESHOLD


def slice_context(
    project_context: Any,
    member: Dict[str, Any],
    focus_tokens: Optional[AbstractSet[str]] = None,
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
        # An empty section carries nothing. Delivering `token_budget: {}` to
        # everyone is noise that reads like a measurement.
        #
        # Checked *before* the always-delivered shortcut, which used to bypass
        # it entirely. That ordering mattered for `run_context`, whose wrapper
        # is non-empty even when it has no summary: measured, a project that
        # had never run `theteam run` handed all five members a note saying
        # there was nothing to read.
        if value in (None, "", [], {}):
            continue
        #
        # So for `run_context` the emptiness that matters is the summary's, not
        # the wrapper's — but only when there is genuinely nothing to say. An
        # `error` key means the writer ran and failed, which is itself a fact a
        # member needs; dropping it makes a broken writer indistinguishable
        # from a project that has never run, and both then read as silence.
        if (key == "run_context"
                and not (value or {}).get("summary")
                and not (value or {}).get("error")):
            continue
        if key in ALWAYS_DELIVERED:
            delivered[key] = value
            continue
        if _section_matches(key, value, focus, set(table)):
            delivered[key] = value
        else:
            undelivered.append(key)

    return _render(delivered), undelivered


class _Markdown(str):
    """A string that must reach the reader as text, not as an escaped blob.

    A `str` subclass so it can carry a rendering intent that plain `str` cannot:
    `yaml.dump` quotes and escapes an ordinary string's newlines, which is right
    for data and wrong for a document a member is meant to read.
    """


class _MarkdownDumper(yaml.SafeDumper):
    """Dumps `_Markdown` as a literal block scalar, so newlines stay newlines."""


def _represent_markdown(dumper: yaml.SafeDumper, data: _Markdown):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data),
                                   style="|")


_MarkdownDumper.add_representer(_Markdown, _represent_markdown)


def _render(sections: Dict[str, Any]) -> str:
    """Deliver `run_context` as readable text inside a valid YAML document.

    It is a markdown document, and `yaml.dump` escaped it whole — measured, a
    member received:

        run_context:
          summary: "# project context \\u2014 last run ...\\n\\n\\
            ## what is failing\\n- doc-harmonization\\n"

    So the headings arrived as the character `#` and every line break as the two
    characters `\\n`. That is worse than absent: a member cannot tell a file
    that was truncated from one whose newlines were escaped.

    Fixed with a YAML literal block scalar rather than by appending raw markdown
    after the document. Appending is the obvious fix and it is wrong twice over:
    the result stops parsing as YAML, and `test_m9_context_slice.py` asserts
    that it does — nine assertions across that file read the delivered prompt
    back with `yaml.safe_load` to check which sections a member received. A
    prompt no test can read is a prompt nobody can assert on.

    `|` keeps the content verbatim and unescaped while leaving the document
    parseable, so both consumers are served: a member reads the markdown, and a
    test reads the structure.
    """
    document = dict(sections)
    context = document.get("run_context")

    if isinstance(context, dict):
        summary = context.get("summary")
        if summary:
            document["run_context"] = {
                **context,
                "summary": _Markdown(str(summary).rstrip()),
            }
        elif context.get("error"):
            document["run_context"] = {
                **context,
                "summary": f"unavailable: {context['error']}",
            }

    if not document:
        # `yaml.dump({})` is "{}\n" and every consumer here parses the result,
        # so an empty delivery stays a parseable empty document rather than an
        # empty string that raises on `safe_load`.
        return yaml.dump({}, default_flow_style=False)
    return yaml.dump(document, Dumper=_MarkdownDumper,
                     default_flow_style=False)


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
