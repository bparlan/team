"""M9 Phase 1: the selector is on the discussion path.

Two defects this milestone closed, both in `theteam/__init__.py` and both
live before it:

1. Every member prompt carried `## Tool Inventory` / `N/A`, because the
   code read `.omp/theteam/tool-manifest.json`, a file that does not exist.
   A boundary the constrained party cannot see is enforced by luck.
2. `run_discussion` spawned every `enabled` member for every topic, so
   `theteam discuss` paid for the whole roster regardless of the topic.

Each test here fails against the pre-Phase-1 code. None of them asserts
that the code "looks right"; each asserts the observable contract.
"""

from theteam import (
    _paths_named_in,
    _permitted_skills,
    _render_skills,
    _topic_slice,
    spawn_member_task,
)
from theteam.advisory.selector import MEMBER_CAP, select_members


ROSTER = {
    "team": [
        {"id": "architect", "role": "Systems Architect", "enabled": True,
         "expertise": "long-term maintainability, coupling, failure modes",
         "voice": "skeptical of shortcuts"},
        {"id": "pragmatist", "role": "Delivery Pragmatist", "enabled": True,
         "expertise": "shipping speed, scope control, bandwidth",
         "voice": "smallest real fix"},
        {"id": "skeptic", "role": "Adversarial Reviewer", "enabled": True,
         "expertise": "edge cases, silent failure modes, unverified claims",
         "voice": "demands raw evidence"},
        {"id": "designer", "role": "UI Designer", "enabled": True,
         "expertise": "ui, ux, layout, css, accessibility",
         "voice": "keyboard and contrast"},
        {"id": "devops", "role": "Infrastructure", "enabled": True,
         "expertise": "deploy, docker, kubernetes, infrastructure",
         "voice": "rollback and recovery"},
    ]
}

# Every member the signals can summon, so a truncation test truncates.
WIDE = {"team": [
    {"id": member, "enabled": True} for member in
    ("architect", "pragmatist", "skeptic", "designer", "api", "data",
     "devops", "security", "analyst")
]}

WIDE_TOPIC = "review a.sql b.py c.yaml d.env e.csv f.tf ui data api security deploy"


class TestToolInventoryIsTheRealBoundary:
    """Defect 1: the tool contract was the literal string `N/A`."""

    def test_member_prompt_names_the_permitted_skills(self):
        member = ROSTER["team"][0]
        prompt = spawn_member_task(member, "topic", {}, ["ponytail", "code-search"], {"provider_bound": True, "docker_available": False, "spawnable_agents": ["task"], "python_version": "3.12", "writable_project": True, "disk_free_mb": 1000})["system_prompt"]
        assert "ponytail" in prompt
        assert "code-search" in prompt

    def test_member_prompt_no_longer_says_the_manifest_is_unavailable(self):
        member = ROSTER["team"][0]
        prompt = spawn_member_task(member, "t", {}, ["ponytail"], {"provider_bound": True, "docker_available": False, "spawnable_agents": ["task"], "python_version": "3.12", "writable_project": True, "disk_free_mb": 1000})["system_prompt"]
        assert "tool-manifest" not in prompt

    def test_an_empty_boundary_is_named_rather_than_blank(self):
        # §3.3: a blank section is a boundary nobody can see.
        assert _render_skills([]) == "none declared by this project's theteam.config"

    def test_the_rendered_list_comes_from_config(self):
        assert _render_skills(_permitted_skills({"permitted_skills": ["a", "b"]})) \
            == "- a\n- b"


class TestSelectionReachesTheSpawn:
    """Defect 2: selection decided the roster and nothing called it."""

    def test_a_topic_selects_fewer_than_the_whole_roster(self):
        selection = select_members(_topic_slice("refactor scheduler.py"), roster=ROSTER)
        assert len(selection["members"]) < len(ROSTER["team"])

    def test_two_different_topics_select_different_members(self):
        code = select_members(_topic_slice("touch the docker deploy pipeline"),
                              roster=ROSTER)
        words = select_members(_topic_slice("should we ship or simplify scope"),
                               roster=ROSTER)
        assert set(code["members"]) != set(words["members"])

    def test_the_same_topic_selects_identically_twice(self):
        topic = "audit the auth token secret rotation"
        first = select_members(_topic_slice(topic), roster=ROSTER)
        second = select_members(_topic_slice(topic), roster=ROSTER)
        assert first == second

    def test_a_quiet_topic_defaults_to_the_lone_skeptic(self):
        selection = select_members(_topic_slice("hm"), roster=ROSTER)
        assert selection["members"] == ["skeptic"]
        assert selection["signals"] == {"default": "skeptic"}

    def test_a_disabled_member_is_never_spawned(self):
        roster = {"team": [dict(m) for m in ROSTER["team"]]}
        for member in roster["team"]:
            member["enabled"] = member["id"] != "skeptic"
        selection = select_members(_topic_slice("verify the claim"), roster=roster)
        assert "skeptic" not in selection["members"]


class TestCapIsRespectedAndReported:
    """§4.5: at most 4 speak, and the overflow is named, not silent."""

    def test_at_most_four_speak(self):
        selection = select_members(_topic_slice(WIDE_TOPIC), roster=WIDE)
        assert len(selection["members"]) <= MEMBER_CAP

    def test_the_overflow_is_reported_rather_than_dropped(self):
        selection = select_members(_topic_slice(WIDE_TOPIC), roster=WIDE)
        assert selection["truncated"] is True
        assert selection["suppressed"] > 0
        assert len(selection["members"]) + selection["suppressed"] > MEMBER_CAP


class TestTopicSliceUsesOnlySignals45AlreadyNames:
    """The selector takes a slice. Building it must not invent a signal."""

    def test_the_topic_arrives_as_the_latest_user_message(self):
        slice_ = _topic_slice("verify the claim")
        assert slice_.last_user_messages == ["verify the claim"]

    def test_a_named_source_file_becomes_a_touched_path(self):
        assert "router.py" in _paths_named_in("please look at router.py today")

    def test_a_prose_word_does_not_become_a_path(self):
        # "api" in prose must not conjure a path, or the extension signal
        # fires on every sentence that mentions a file type.
        assert _paths_named_in("we should simplify the api surface") == []

    def test_a_topic_reaches_the_selector_only_through_named_signals(self):
        selection = select_members(_topic_slice("deploy the ui to the database"),
                                   roster=WIDE)
        assert set(selection["signals"]) <= {"extensions", "message", "task_type",
                                             "phase", "default"}
        assert selection["members"]
