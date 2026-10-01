"""
Defends the delivery of `run_context` to discussion members.

`theteam run` writes `.omp/theteam/context.md` (see `theteam/core/run_context.py`
and its tests). This file covers the second half of that path: the file reaching
the members who are supposed to read it.

Two properties, both measured rather than assumed:

  * **every member receives it.** Delivery otherwise depended on a member's
    focus tokens happening to share a word with the summary. Measured on this
    repository before `run_context` joined `ALWAYS_DELIVERED`: 1 of 5 members
    got it, which is §M9's "a section reaching nobody is reported, not dropped"
    in its worse form — four members reasoned without it and nobody was told.
  * **an absent summary delivers nothing.** `run_context` wraps its payload so
    it can carry an error or an absence note, which makes the wrapper non-empty
    even when there is no summary. Measured before the emptiness check: a
    project that had never run `theteam run` handed all five members a note
    saying there was nothing to read.
"""

from pathlib import Path

import pytest

from theteam.advisory.context_slice import (
    ALWAYS_DELIVERED,
    parse_yaml_section,
    NEVER_DELIVERED,
    slice_context,
    undelivered_sections,
)
from theteam.workflow.context_aggregator import (
    aggregate_project_context,
    aggregate_run_context,
)

ROSTER = [{"id": m} for m in
          ("architect", "pragmatist", "skeptic", "designer", "devops")]


def test_run_context_is_always_delivered():
    """Not routed by focus tokens — every member needs project-wide state."""
    assert "run_context" in ALWAYS_DELIVERED


@pytest.mark.parametrize("member", ROSTER, ids=lambda m: m["id"])
def test_every_member_receives_a_real_run_context(member, tmp_path, monkeypatch):
    """Driven against a real summary written into a real state directory."""
    from theteam.core.run_context import write_run_context

    (tmp_path / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "theteam.config").write_text(
        "project:\n  name: probe\n  description: probe project\n")
    monkeypatch.setenv("THETEAM_STATE_DIR", str(tmp_path / ".omp" / "theteam"))
    write_run_context(tmp_path, executed=True)

    rendered, _ = slice_context({"run_context": aggregate_run_context(tmp_path)},
                                member)
    assert "## current run context" in rendered, (
        f"{member['id']} did not receive the run context")
    assert "probe" in rendered, "the section arrived but carried no summary"


def test_every_member_receives_it_in_the_real_aggregate():
    """The whole-context path, which is what `run_discussion` actually calls.

    Token-routing would deliver this to whichever members happen to share a
    word with the summary. Measured on this repo before the fix: 1 of 5.
    """
    context = aggregate_project_context(str(Path(__file__).resolve().parent.parent.parent))
    for member in ROSTER:
        rendered, _ = slice_context(context, member)
        assert "## current run context" in rendered, (
            f"{member['id']} missed the run context in the full aggregate")


def test_an_absent_summary_delivers_nothing(tmp_path, monkeypatch):
    """A project that has never run pays nothing for the section.

    The wrapper is non-empty — it carries a `note` — so the emptiness that
    matters is the summary's, not the wrapper's.
    """
    monkeypatch.setenv("THETEAM_STATE_DIR", str(tmp_path / ".omp" / "theteam"))
    section = aggregate_run_context(tmp_path)

    assert section.get("summary") is None
    assert section.get("note"), "the absence must say so, not read as empty"

    rendered, _ = slice_context({"run_context": section}, {"id": "architect"})
    assert "## current run context" not in rendered, (
        "members were handed a note telling them there was nothing to read, "
        "which costs tokens on every prompt and carries no information")
    assert len(rendered.strip()) <= 3, (
        f"an empty context still produced {len(rendered)} bytes of prompt")


def test_an_error_section_is_still_delivered(tmp_path, monkeypatch):
    """The converse: an unreadable file is a fact, and gets through.

    Skipping on "no summary" must not also skip on "could not read the summary",
    or a broken writer would look exactly like a project that never ran.
    """
    monkeypatch.setenv("THETEAM_STATE_DIR", str(tmp_path / ".omp" / "theteam"))
    rendered, _ = slice_context(
        {"run_context": {"summary": None, "error": "could not read context.md"}},
        {"id": "architect"})
    assert "## current run context" in rendered, (
        "an unreadable context file was delivered as nothing, which reads as "
        "the same as never having run")
    assert "could not read" in rendered, "the reason must reach the member"


def test_the_always_delivered_keys_still_short_circuit():
    """The emptiness reordering must not push them into `undelivered`.

    Removing the `continue` from the always-delivered branch made every such key
    fall through to `_section_matches` and be reported as reaching nobody.
    """
    context = {"project_goal": "a goal", "project_root": "/tmp/x",
               "run_context": {"summary": "# context", "written_at": 1}}
    for member in ROSTER:
        rendered, missed = slice_context(context, member)
        assert "project_goal" in rendered
        assert "project_root" in rendered
        assert missed == [], f"{member['id']} reported {missed} as undelivered"


def test_undelivered_sections_does_not_flag_run_context():
    """The §M9 cross-member check must not report it as reaching nobody."""
    context = {"run_context": {"summary": "# context", "written_at": 1}}
    reached = undelivered_sections(context, ROSTER)
    assert "run_context" not in reached


def test_timestamp_is_still_never_delivered():
    """The reordering must not have disturbed the existing rule.

    `timestamp` changes on every call, so delivering it would make two identical
    discussions produce two different prompts — a determinism bug.
    """
    assert "timestamp" in NEVER_DELIVERED
    rendered, missed = slice_context({"timestamp": "2026-10-01T00:00:00"},
                                     {"id": "architect"})
    assert "timestamp" not in rendered
    assert "timestamp" not in missed, (
        "a never-delivered section must be skipped, not reported as undelivered")


def test_the_context_is_readable_text_not_escaped_yaml():
    """The defect this exists for: present, and unreadable.

    `run_context` is a markdown document. `yaml.dump` escaped it whole, so a
    member received `summary: "# project context \\u2014 last run...\\n\\n## what
    is failing\\n- doc-harmonization"`. The headings arrived as the character
    `#` and every line break as the two characters `\\n`.

    That is worse than absent: a member cannot tell a file that was truncated
    from one whose newlines were escaped, so the escape reads as content.
    """
    context = aggregate_project_context(
        str(Path(__file__).resolve().parent.parent.parent))
    rendered, _ = slice_context(context, {"id": "pragmatist"})

    assert "## current run context" in rendered
    # Real newlines and real markdown headings, not their escaped spellings.
    assert "## what is failing" in rendered, (
        "the summary's own headings did not survive rendering")
    assert "\\n##" not in rendered, (
        "newlines are still escaped, so the member reads the two characters "
        "\\n instead of a line break")
    assert "\\u" not in rendered, "unicode escapes are still present"
    assert rendered.count("## what is failing") == 1, (
        "the summary was embedded more than once")

    # The structured half is still parseable, which is how the m9 suite asserts
    # which sections a member received. Readability cannot be bought by
    # destroying the structure.
    parsed = parse_yaml_section(rendered)
    assert parsed and "project_goal" in parsed, (
        "the structured section is no longer parseable, so nothing can assert "
        "which sections a member received")


def test_structured_sections_keep_their_yaml_rendering():
    """Only the markdown document changed shape; the data sections did not."""
    rendered, _ = slice_context(
        {"project_goal": "a goal", "run_context": {"summary": "# ctx"}},
        {"id": "architect"})
    assert "project_goal: a goal" in rendered, (
        "structured sections stopped being YAML, which is a wider change than "
        "this one was meant to make")
    assert "# ctx" in rendered
