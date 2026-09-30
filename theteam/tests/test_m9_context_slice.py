"""M9 Phase 3: per-member project context.

`theteam/__init__.py:93` used to `yaml.dump(project_context)` into every
member's prompt, so a five-member roster paid for the same 2,499 characters
five times. This milestone slices the context by the focus a member declares.

Two things it must not do:

* **Drop a section silently.** §M9: a flag delivered to nobody is reported,
  not dropped. `undelivered_sections` is that report, and it is the
  assertion most of this file defends.
* **Deliver on one incidental word.** A single-token match was measured
  carrying `runtime_config` — 1,272 characters, 91% of a member's budget —
  to four of five members on the strength of `scope` and `reviewer`
  appearing in a package description. `MATCH_THRESHOLD` is that fix, and
  these tests pin the number rather than the feeling.
"""

from pathlib import Path

import yaml

from theteam.advisory.context_slice import (
    ALWAYS_DELIVERED,
    MATCH_THRESHOLD,
    NEVER_DELIVERED,
    slice_context,
    undelivered_sections,
)

# These two tests read the real project, so they must read *this* project
# from any working directory. The path is walked by hand rather than indexed
# for the same reason as `test_invariant_gate.py`: check 4 of the invariant
# gate forbids the index form in this tree, and naming it here would trip
# that very gate.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


ARCHITECT = {"id": "architect", "role": "Systems Architect",
             "expertise": "long-term maintainability, coupling, failure modes",
             "voice": "skeptical of shortcuts"}
PRAGMATIST = {"id": "pragmatist", "role": "Delivery Pragmatist",
              "expertise": "shipping speed, scope control, bandwidth",
              "voice": "smallest real fix"}
DEVOPS = {"id": "devops", "role": "Infrastructure Reviewer",
          "expertise": "deployment, CI/CD, infrastructure, scalability",
          "voice": "asks what this looks like when the host goes away"}
ROSTER = [ARCHITECT, PRAGMATIST, DEVOPS]

# Shaped like the real `aggregate_project_context` output: the same eight
# keys, so the floor and skip rules are exercised against reality.
REAL_SHAPED_CONTEXT = {
    "project_goal": "A small panel of expert reviewers.",
    "runtime_config": {
        "package.json": {"name": "team", "scripts": {"bootstrap": "python3 init.py"}},
        "pyproject.toml": "[project]\nname = \"theteam\"\n"
                          "description = \"architecture, contract and deployment\"",
    },
    "token_budget": {},
    "registered_structure": [{"name": "src", "type": "directory", "file_count": 12}],
    "last_health_scan": {},
    "production_invariants": {"behavior_settings": {"chat_mode": True}},
    "timestamp": "2026-09-30T15:31:41.705044+00:00",
    "project_root": ".",
}


class TestTheFloorAndTheSkips:
    """`project_goal` goes to everyone. `timestamp` goes to no one."""

    def test_every_member_gets_the_project_goal(self):
        for member in ROSTER:
            delivered, _ = slice_context(REAL_SHAPED_CONTEXT, member)
            assert "project_goal" in yaml.safe_load(delivered)

    def test_every_member_gets_the_project_root(self):
        for member in ROSTER:
            delivered, _ = slice_context(REAL_SHAPED_CONTEXT, member)
            assert "project_root" in yaml.safe_load(delivered)

    def test_no_member_gets_the_timestamp(self):
        # It changes every call, so delivering it makes two identical
        # discussions produce two different prompts: a determinism bug.
        for member in ROSTER:
            delivered, _ = slice_context(REAL_SHAPED_CONTEXT, member)
            assert "timestamp" not in yaml.safe_load(delivered)

    def test_no_member_gets_an_empty_section(self):
        # `token_budget: {}` reads like a measurement and is not one.
        for member in ROSTER:
            delivered, _ = slice_context(REAL_SHAPED_CONTEXT, member)
            assert "token_budget" not in yaml.safe_load(delivered)

    def test_a_non_dict_context_is_rendered_as_text_not_dropped(self):
        rendered, undelivered = slice_context("just a string", ARCHITECT)
        assert rendered == "just a string"
        assert undelivered == []


class TestASingleWordIsNotEvidence:
    """The threshold, pinned by measurement rather than by feeling."""

    def test_the_threshold_is_two_matching_tokens(self):
        assert MATCH_THRESHOLD == 2

    def test_a_section_matching_on_one_incidental_word_is_not_delivered(self):
        # `scope` appears in the pragmatist's expertise and once in a
        # package description. That is not evidence they need it.
        context = {"runtime_config": {"notes.md": "a note about scope"}}
        delivered, undelivered = slice_context(context, PRAGMATIST)
        assert "runtime_config" not in yaml.safe_load(delivered)
        assert "runtime_config" in undelivered

    def test_a_section_matching_on_several_words_is_delivered(self):
        # devops matches `deployment` and `infrastructure` here.
        context = {"deployment_plan": "infrastructure and deployment notes"}
        delivered, _ = slice_context(context, DEVOPS)
        assert "deployment_plan" in yaml.safe_load(delivered)

    def test_a_stop_word_never_counts_as_a_match(self):
        # "in" is a substring of "packin"; the token filter is what stops
        # an article from carrying a section to every member.
        from theteam.advisory.context_slice import _tokens
        assert "in" not in _tokens("the packin-module comment")
        assert "and" not in _tokens("cats and dogs")


class TestTheSlicingActuallySaves:
    """The point of the phase. Asserted on the real shape of the context."""

    def test_a_member_receives_far_less_than_the_whole_context(self):
        whole = len(yaml.dump(REAL_SHAPED_CONTEXT, default_flow_style=False))
        delivered, _ = slice_context(REAL_SHAPED_CONTEXT, PRAGMATIST)
        assert len(delivered) < whole

    def test_the_five_member_roster_pays_less_than_five_whole_contexts(self):
        whole = len(yaml.dump(REAL_SHAPED_CONTEXT, default_flow_style=False))
        total = sum(len(slice_context(REAL_SHAPED_CONTEXT, m)[0]) for m in ROSTER)
        assert total < whole * len(ROSTER)

    def test_the_same_context_slices_identically_twice(self):
        first, _ = slice_context(REAL_SHAPED_CONTEXT, ARCHITECT)
        second, _ = slice_context(REAL_SHAPED_CONTEXT, ARCHITECT)
        assert first == second


class TestNothingIsDroppedSilently:
    """§M9: a flag delivered to nobody is reported, not dropped."""

    def test_a_section_no_member_receives_is_reported(self):
        orphans = undelivered_sections(REAL_SHAPED_CONTEXT, ROSTER)
        assert "production_invariants" in orphans

    def test_the_report_names_every_member_that_missed_it(self):
        orphans = undelivered_sections(REAL_SHAPED_CONTEXT, ROSTER)
        assert sorted(orphans["production_invariants"]) == \
            sorted(m["id"] for m in ROSTER)

    def test_a_section_some_member_receives_is_not_reported(self):
        orphans = undelivered_sections(REAL_SHAPED_CONTEXT, ROSTER)
        assert "runtime_config" not in orphans

    def test_the_per_member_return_and_the_cross_member_report_agree(self):
        for member in ROSTER:
            _, missed = slice_context(REAL_SHAPED_CONTEXT, member)
            orphans = undelivered_sections(REAL_SHAPED_CONTEXT, ROSTER)
            for section in missed:
                if section in orphans:
                    assert member["id"] in orphans[section]

    def test_the_never_delivered_sections_are_never_reported_as_orphans(self):
        # `timestamp` is dropped by design, so reporting it as "reached no
        # member" every discussion would be noise, not information.
        orphans = undelivered_sections(REAL_SHAPED_CONTEXT, ROSTER)
        for key in NEVER_DELIVERED:
            assert key not in orphans

    def test_the_floor_sections_are_never_reported_as_orphans(self):
        orphans = undelivered_sections(REAL_SHAPED_CONTEXT, ROSTER)
        for key in ALWAYS_DELIVERED:
            assert key not in orphans


class TestAgainstThisRepository:
    """The real aggregator output, not a fixture shaped like it."""

    def test_the_real_context_slices_without_error(self):
        from theteam.workflow.context_aggregator import aggregate_project_context
        context = aggregate_project_context(str(REPO_ROOT))
        with open(REPO_ROOT / "theteam.config") as handle:
            roster = yaml.safe_load(handle)["team"]
        for member in roster:
            delivered, _ = slice_context(context, member)
            assert yaml.safe_load(delivered) is not None

    def test_the_real_roster_pays_less_than_the_whole_context_per_member(self):
        from theteam.workflow.context_aggregator import aggregate_project_context
        context = aggregate_project_context(str(REPO_ROOT))
        with open(REPO_ROOT / "theteam.config") as handle:
            roster = yaml.safe_load(handle)["team"]
        whole = len(yaml.dump(context, default_flow_style=False))
        total = sum(len(slice_context(context, m)[0]) for m in roster)
        assert total < whole * len(roster)
