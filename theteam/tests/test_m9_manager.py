"""M9 Phase 2: `theteam manager` grows the roster from the topic.

The spec's two gates for this phase, and the honesty rule that sits under
both:

* `--status` states why every member is on the roster.
* An added member names the evidence that triggered it — a focus flag, or
  the topic vocabulary no member covered. "You might want a database
  person" is not a reason.

The decision of *whether* to add is deterministic (`detect_triggers`); these
tests assert that, and they assert that a member with no evidence is
reported rather than given a plausible one.
"""

import os

import yaml

from theteam import BASE_MEMBERS
from theteam.advisory.manager import (
    CATALOG,
    detect_triggers,
    reasons_for,
)


BASE = [
    {"id": "architect", "expertise": "maintainability, coupling", "role": "Systems Architect",
     "voice": "skeptical of shortcuts", "enabled": True},
    {"id": "pragmatist", "expertise": "shipping speed, scope", "role": "Delivery Pragmatist",
     "voice": "smallest real fix", "enabled": True},
    {"id": "skeptic", "expertise": "edge cases, failure", "role": "Adversarial Reviewer",
     "voice": "demands evidence", "enabled": True},
]

ALL_FALSE = {flag: False for flag in (
    "security_focus", "data_science_focus", "frontend_focus",
    "api_focus", "database_focus", "infrastructure_focus")}


class TestTwoIndependentTriggers:
    """§M9: project flags *or* topic vocabulary. Neither alone is enough."""

    def test_an_uncovered_project_flag_proposes_its_member(self):
        context = dict(ALL_FALSE, security_focus=True)
        result = detect_triggers("anything", context, BASE)
        assert [c["member"] for c in result["add"]] == ["security"]
        assert "security_focus" in result["add"][0]["reasons"][0]

    def test_topic_vocabulary_no_member_covers_proposes_a_member(self):
        # No project flag. Only the topic mentions auth.
        result = detect_triggers("rotate the auth token secret", ALL_FALSE, BASE)
        ids = [c["member"] for c in result["add"]]
        assert "security" in ids
        assert any("topic vocabulary" in r for r in
                   result["add"][ids.index("security")]["reasons"])

    def test_project_context_alone_would_have_added_nobody(self):
        # The exact failure §M9 names: a topic about rate limiting adds
        # nobody, because only infrastructure_focus does.
        result = detect_triggers("rate limiting", ALL_FALSE, BASE)
        assert result["add"] == []

    def test_a_topic_alone_gives_a_team_blind_to_the_repo(self):
        # Topic-only would never notice the project has a database at all.
        result = detect_triggers("hello there", dict(ALL_FALSE, database_focus=True), BASE)
        assert [c["member"] for c in result["add"]] == ["data"]

    def test_both_triggers_name_the_same_member_only_once(self):
        context = dict(ALL_FALSE, security_focus=True)
        result = detect_triggers("auth secrets", context, BASE)
        ids = [c["member"] for c in result["add"]]
        assert ids.count("security") == 1
        assert len(result["add"][0]["reasons"]) == 2


class TestDeterminism:
    """The selector's guarantee, extended to the manager's decisions."""

    def test_the_same_topic_detects_identically_twice(self):
        context = dict(ALL_FALSE, api_focus=True)
        first = detect_triggers("fix the schema migration", context, BASE)
        second = detect_triggers("fix the schema migration", context, BASE)
        assert first == second

    def test_an_empty_topic_proposes_nothing_from_vocabulary(self):
        result = detect_triggers("", ALL_FALSE, BASE)
        assert result["add"] == []

    def test_stop_words_never_trigger_anything(self):
        result = detect_triggers("the and for with this that", ALL_FALSE, BASE)
        assert result["add"] == []

    def test_a_member_already_on_the_roster_is_never_re_proposed(self):
        roster = BASE + [{"id": "security", "expertise": "auth", "role": "Security"}]
        result = detect_triggers("auth secrets", dict(ALL_FALSE, security_focus=True), roster)
        assert "security" not in [c["member"] for c in result["add"]]


class TestEvidenceIsNamed:
    """The gate: an added member names what triggered it."""

    def test_every_proposal_carries_at_least_one_reason(self):
        result = detect_triggers("auth and schema", dict(ALL_FALSE, api_focus=True), BASE)
        assert result["add"]
        for candidate in result["add"]:
            assert candidate["reasons"]
            assert all(r.strip() for r in candidate["reasons"])

    def test_the_reason_names_the_specific_tokens_not_a_vague_need(self):
        result = detect_triggers("rotate the auth secret", ALL_FALSE, BASE)
        security = next(c for c in result["add"] if c["member"] == "security")
        text = " ".join(security["reasons"])
        assert "auth" in text or "secret" in text

    def test_a_proposal_cannot_name_a_member_outside_the_catalog(self):
        result = detect_triggers("quantum entanglement", ALL_FALSE, BASE)
        for candidate in result["add"]:
            assert candidate["member"] in CATALOG


class TestStatusReasons:
    """`--status` must state why, for every member, or admit it cannot."""

    def test_a_base_member_is_justified_as_base(self):
        why = reasons_for("architect", ALL_FALSE, member={"id": "architect"})
        assert "base roster" in why[0]

    def test_a_focus_member_is_justified_by_its_flag(self):
        why = reasons_for("security", dict(ALL_FALSE, security_focus=True),
                          member={"id": "security"})
        assert "security_focus" in why[0]

    def test_a_member_with_no_evidence_says_so_rather_than_guessing(self):
        why = reasons_for("data", ALL_FALSE, member={"id": "data"})
        assert "no recorded reason" in why[0]

    def test_a_recorded_reason_outranks_a_current_flag(self):
        # A topic-triggered addition cannot be re-justified from live context.
        # The recorded fact is the only true statement available.
        member = {"id": "security",
                  "added_reason": ["topic vocabulary no member covers: auth"],
                  "added_for_topic": "auth rotation"}
        why = reasons_for("security", ALL_FALSE, member=member)
        assert "topic vocabulary" in why[0]
        assert "auth rotation" in " ".join(why)

    def test_a_member_outside_the_catalog_is_named_as_such(self):
        assert "catalog" in reasons_for("wizard", ALL_FALSE, member={})[0]


class TestRosterCap:
    """§M9 open question 3: what caps roster size? The catalog does."""

    def test_the_catalog_is_finite_and_small(self):
        assert len(CATALOG) == 9

    def test_no_topic_can_propose_more_than_the_catalog(self):
        kitchen_sink = ("auth secrets schema migration deploy docker ui css "
                        "api endpoint data metric notebook kubernetes index query")
        result = detect_triggers(kitchen_sink, {f: True for f in ALL_FALSE}, BASE)
        proposed = {c["member"] for c in result["add"]}
        assert proposed <= set(CATALOG)
        assert len(proposed) <= len(CATALOG) - len(BASE)

    def test_every_base_member_is_in_the_catalog(self):
        assert set(m["id"] for m in BASE_MEMBERS) <= set(CATALOG)


class TestProposalDoesNotWrite:
    """`--topic` proposes. It does not persist. `--apply` persists."""

    def _project(self, tmp_path):
        config = {
            "schema_version": 1,
            "project": {"name": "t", "root": ".", "description": ""},
            "team": [dict(m) for m in BASE],
            "permitted_skills": ["ponytail"],
            "behavior": {"auto_summarization": False, "block_edits_without_plan": True,
                         "proactive_plan_required": True, "pre_analysis_search": True,
                         "chat_mode": True, "dynamic_interaction": True,
                         "enable_persona_comments": True, "gamification_enabled": True,
                         "max_discussion_rounds": 5, "persona_response_variety": True},
            "output": {"report_dir": ".omp/theteam/reports", "keep_last": 20},
        }
        path = os.path.join(str(tmp_path), "theteam.config")
        with open(path, "w") as handle:
            yaml.dump(config, handle)
        return str(tmp_path)

    def _run(self, root, *argv):
        from theteam.cli import main
        return main(["--project-root", root, "manager", *argv])

    def test_a_bare_topic_proposal_writes_nothing(self, tmp_path, capsys):
        root = self._project(tmp_path)
        path = os.path.join(root, "theteam.config")
        before = open(path).read()
        code = self._run(root, "--topic", "audit the auth secrets")
        assert code == 0
        assert open(path).read() == before
        assert "nothing written" in capsys.readouterr().out

    def test_apply_persists_and_the_config_still_validates(self, tmp_path):
        from theteam.bin.theteam_config import validate_config
        root = self._project(tmp_path)
        assert self._run(root, "--topic", "audit the auth secrets", "--apply") == 0
        with open(os.path.join(root, "theteam.config")) as handle:
            written = yaml.safe_load(handle)
        assert "security" in [m["id"] for m in written["team"]]
        assert validate_config(written)[0] is True

    def test_an_added_member_is_justified_after_apply(self, tmp_path, capsys):
        root = self._project(tmp_path)
        self._run(root, "--topic", "audit the auth secrets", "--apply")
        capsys.readouterr()
        assert self._run(root, "--status") == 0
        out = capsys.readouterr().out
        assert "no recorded reason" not in out

    def test_status_reports_a_member_with_no_evidence(self, tmp_path, capsys):
        root = self._project(tmp_path)
        # Hand-add a member no flag or topic justifies.
        path = os.path.join(root, "theteam.config")
        with open(path) as handle:
            config = yaml.safe_load(handle)
        config["team"].append({"id": "data", "role": "Data", "expertise": "schema",
                               "voice": "v", "enabled": True})
        with open(path, "w") as handle:
            yaml.dump(config, handle)
        self._run(root, "--status")
        assert "no recorded reason" in capsys.readouterr().out

    def test_reset_restores_the_bootstrapped_roster(self, tmp_path, capsys):
        root = self._project(tmp_path)
        self._run(root, "--topic", "audit the auth secrets", "--apply")
        capsys.readouterr()
        assert self._run(root, "--reset") == 0
        with open(os.path.join(root, "theteam.config")) as handle:
            written = yaml.safe_load(handle)
        assert "security" not in [m["id"] for m in written["team"]]

    def test_manager_without_a_mode_is_a_named_usage_error(self, tmp_path, capsys):
        root = self._project(tmp_path)
        assert self._run(root) == 1
        assert "one of --topic" in capsys.readouterr().err

    def test_manager_without_a_config_names_the_fix(self, tmp_path, capsys):
        assert self._run(str(tmp_path), "--status") == 1
        assert "bootstrap" in capsys.readouterr().err
