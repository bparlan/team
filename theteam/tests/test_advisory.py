"""
The advisory layer: session reading, member selection, and the tick loop.

Every test here is a claim the product makes in ARCHITECTURE.md and a user can
otherwise only check by hand. Three of them are the reason this file exists at
all:

1. **The team reads your real session.** The depth rule is the whole test. A
   session directory holds one top-level `.jsonl` and a `__advisor.jsonl` per
   subagent; picking the newest file without the depth rule comments on a
   subagent and presents it as your work.

2. **The team is silent rather than filler.** Every tick returns `spoke: false`
   with a reason, or at most 2 fragments. The quiet-tick case - an unchanged
   digest costs *zero* engine calls - is asserted across a controller restart,
   because holding the digest in memory is what made it pass in one process
   and fail in the next.

3. **Opinions are never invented.** An unavailable engine and an engine that
   returns nothing both produce `spoke: false` with a reason and zero fragments.
   There is no path through this layer that renders a plausible-looking opinion
   it did not receive.

Tests build their session tree in `tmp_path` and redirect both state and
sessions through their environment variables, so nothing here touches the
user's real `~/.omp` or this repository's real `.omp/theteam`.
"""

import json
import os
from pathlib import Path

import pytest

from theteam.advisory import selector as selector_module
from theteam.advisory.commentary import (
    MAX_FRAGMENTS,
    CommentaryController,
    is_stop,
    leading_clause,
)
from theteam.advisory.roster import (
    ROSTER_FILE,
    bootstrap_roster,
    load_roster,
    save_roster,
)
from theteam.advisory.selector import MEMBER_CAP, select_members
from theteam.advisory.session_reader import (
    SessionFormatError,
    SessionResult,
    SessionSlice,
    read_session,
    session_slug,
)


# ======= fixtures =======


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    """Redirect team state into tmp_path so no test writes the real state dir."""
    root = tmp_path / ".omp" / "theteam"
    monkeypatch.setenv("THETEAM_STATE_DIR", str(root))
    return root


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    """Redirect the session tree into tmp_path."""
    root = tmp_path / "sessions"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("THETEAM_SESSIONS_DIR", str(root))
    return root


def _event(role, text=None, tool=None, path=None):
    """One session event, shaped the way OMP writes them."""
    parts = []
    if text is not None:
        parts.append({"type": "text", "text": text})
    if tool is not None:
        parts.append({"type": "toolCall", "name": tool, "arguments": {"path": path}})
    return {"type": "message", "message": {"role": role, "content": parts}}


def _write_session(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    return path


def _slice(digest="d1", message="review this", paths=("a.sql",)):
    return SessionSlice(
        last_user_messages=[message],
        recent_activity=["read"],
        touched_paths=list(paths),
        digest=digest,
    )


def _result(slice_=None, path="/tmp/session.jsonl"):
    return SessionResult(
        spoke=True,
        slice=slice_ if slice_ is not None else _slice(),
        session_path=path,
        event_count=7,
    )


def _counting_engine(calls):
    """An engine that records every call and returns one opinion per member.

    The count of calls is the budget measurement: a tick that spent a member
    call shows up here even when its rendered output looks identical.
    """
    def engine(members, slice_):
        calls.append(list(members))
        return [
            {"id": m, "role": m, "verdict": "concern", "note": f"{m} fragment"}
            for m in members
        ]
    return engine


# A roster wide enough that selection can actually reach the cap.
FULL_ROSTER = {
    "team": [
        {"id": "architect", "enabled": True},
        {"id": "pragmatist", "enabled": True},
        {"id": "skeptic", "enabled": True},
        {"id": "designer", "enabled": True},
        {"id": "api", "enabled": True},
        {"id": "data", "enabled": True},
    ]
}
FRONTEND_SLICE = SessionSlice(
    last_user_messages=["the layout is broken on mobile, fix the css"],
    recent_activity=["read", "edit"],
    touched_paths=["src/components/App.tsx", "src/styles/main.css"],
    digest="fe",
)
DATABASE_SLICE = SessionSlice(
    last_user_messages=["this migration will lock the table, review the schema"],
    recent_activity=["read", "bash"],
    touched_paths=["migrations/0003_add_index.sql", "schema.sql"],
    digest="db",
)


# ======= session_reader: the depth rule (C2) =======


def test_session_slug_carries_the_leading_dash_omp_uses(tmp_path):
    """OMP names the directory `-devcode-team`, not `devcode-team`.

    Without the leading dash the reader looks in a directory that does not
    exist and reports no_session against a live session - which is exactly
    what happened before the slug was measured against the real filesystem.
    """
    project = tmp_path / "devcode" / "team"
    project.mkdir(parents=True)
    slug = session_slug(str(project))
    assert slug.startswith("-")
    assert "/" not in slug


def test_newest_top_level_session_is_the_one_read(sessions_dir, tmp_path):
    """The newest maxdepth-1 `.jsonl` wins."""
    slug_dir = sessions_dir / session_slug(str(tmp_path))
    _write_session(slug_dir / "2026-01-01T00-00-00.jsonl",
                   [_event("user", text="old message")])
    newest = _write_session(slug_dir / "2026-01-02T00-00-00.jsonl",
                            [_event("user", text="new message")])
    os.utime(newest, (2_000_000_000, 2_000_000_000))

    result = read_session(str(tmp_path))
    assert result.spoke is True
    assert result.session_path == str(newest)
    assert result.slice.last_user_messages == ["new message"]


def test_a_subagent_transcript_is_never_read_as_a_session(sessions_dir, tmp_path):
    """285 subagent transcripts against 59 real sessions on this machine.

    A subagent's transcript is the user's session in every respect except the
    one that matters, and commenting on it presents someone else's work as the
    user's. It is refused, not ranked lower.
    """
    slug_dir = sessions_dir / session_slug(str(tmp_path))
    _write_session(slug_dir / "2026-01-02T00-00-00.jsonl",
                   [_event("user", text="the real session")])
    subagent = _write_session(
        slug_dir / "2026-01-03T00-00-00-abc" / "__advisor.jsonl",
        [_event("user", text="a subagent's own transcript")],
    )

    # Explicitly asking for the subagent file is refused.
    refused = read_session(str(tmp_path), session_path=str(subagent))
    assert refused.spoke is False
    assert refused.reason == "no_session"

    # And the depth rule means discovery never surfaces it either.
    discovered = read_session(str(tmp_path))
    assert discovered.spoke is True
    assert "a subagent's own transcript" not in discovered.slice.last_user_messages


def test_missing_session_file_reports_no_session_and_a_path(sessions_dir, tmp_path):
    """`{spoke: false, reason: "no_session"}` plus the path, per the 3.2 table."""
    result = read_session(str(tmp_path))
    assert result.spoke is False
    assert result.reason == "no_session"
    assert result.session_path, "the path it looked for is part of the contract"


def test_a_missing_slug_directory_is_no_session_not_a_crash(sessions_dir, tmp_path):
    """No directory at all is the same refusal, not an exception."""
    result = read_session(str(tmp_path / "nonexistent"))
    assert result.spoke is False
    assert result.reason == "no_session"


def test_malformed_session_raises_naming_the_file_and_line(sessions_dir, tmp_path):
    """§3.2: raise. A session we half-understand is worse than one we refuse.

    The reader would otherwise report a digest over half a session and the team
    would comment on a session that does not exist.
    """
    slug_dir = sessions_dir / session_slug(str(tmp_path))
    path = slug_dir / "2026-01-02T00-00-00.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_event("user", text="fine")) + "\n"
        + "{ this line is not json }\n",
        encoding="utf-8",
    )

    with pytest.raises(SessionFormatError) as caught:
        read_session(str(tmp_path))

    message = str(caught.value)
    assert path.name in message
    assert ":2:" in message


def test_an_empty_session_is_no_session(sessions_dir, tmp_path):
    """An empty file has no events, and no events means no session."""
    slug_dir = sessions_dir / session_slug(str(tmp_path))
    path = slug_dir / "2026-01-02T00-00-00.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")

    result = read_session(str(tmp_path))
    assert result.spoke is False
    assert result.reason == "no_session"


def test_tool_results_are_never_returned(sessions_dir, tmp_path):
    """§4.4: names and the paths they were given, never the payload.

    A `read` result can be an entire file. The whole affordability of this
    layer rests on the reader returning structure rather than content, so a
    slice that could carry a tool result is a cost bug, not a style one.
    """
    slug_dir = sessions_dir / session_slug(str(tmp_path))
    secret = "SECRET_FILE_CONTENT_DO_NOT_LEAK"
    _write_session(
        slug_dir / "2026-01-02T00-00-00.jsonl",
        [
            _event("user", text="read the config", tool="read", path="config.py"),
            {"type": "message", "message": {
                "role": "toolResult",
                "content": [{"type": "text", "text": secret}],
            }},
        ],
    )

    result = read_session(str(tmp_path))
    assert result.spoke is True

    # The tool NAME and its PATH are the signal. The RESULT is not.
    assert "read" in result.slice.recent_activity
    assert "config.py" in result.slice.touched_paths
    assert secret not in " ".join(result.slice.last_user_messages)
    assert secret not in " ".join(result.slice.recent_activity)
    assert secret not in " ".join(result.slice.touched_paths)
    assert secret not in result.slice.digest


def test_the_message_cap_is_enforced_not_trusted(sessions_dir, tmp_path):
    """K defaults to 4 and is hard-capped at 8.

    A caller passing 500 is a bug that would otherwise quietly cost 500x the
    per-turn budget of 4.6.
    """
    slug_dir = sessions_dir / session_slug(str(tmp_path))
    _write_session(
        slug_dir / "2026-01-02T00-00-00.jsonl",
        [_event("user", text=f"message {n}") for n in range(30)],
    )

    assert len(read_session(str(tmp_path), messages=500).slice.last_user_messages) <= 8
    assert len(read_session(str(tmp_path)).slice.last_user_messages) <= 4


def test_the_digest_changes_when_the_session_changes(sessions_dir, tmp_path):
    """The promise `theteam status` rests on: the digest tracks the session."""
    slug_dir = sessions_dir / session_slug(str(tmp_path))
    _write_session(slug_dir / "2026-01-02T00-00-00.jsonl",
                   [_event("user", text="first")])
    first = read_session(str(tmp_path)).slice.digest

    _write_session(slug_dir / "2026-01-02T00-00-00.jsonl",
                   [_event("user", text="first"), _event("user", text="second")])
    second = read_session(str(tmp_path)).slice.digest

    assert first != second


def test_the_digest_is_stable_for_an_unchanged_session(sessions_dir, tmp_path):
    """The other half of the same promise: no change means no change.

    Without this, "digest changes when the session changes" could be satisfied
    by a digest that changes on every read, which is what the quiet-tick
    budget in 4.6 depends on not happening.
    """
    slug_dir = sessions_dir / session_slug(str(tmp_path))
    _write_session(slug_dir / "2026-01-02T00-00-00.jsonl",
                   [_event("user", text="steady")])
    assert read_session(str(tmp_path)).slice.digest == \
        read_session(str(tmp_path)).slice.digest


# ======= selector: deterministic, and it differentiates =======


def test_the_selector_is_deterministic():
    """Same slice in, same members out. Twice, or the gate cannot assert it."""
    first = select_members(FRONTEND_SLICE, roster=FULL_ROSTER)
    second = select_members(FRONTEND_SLICE, roster=FULL_ROSTER)
    assert first["members"] == second["members"]
    assert first["signals"] == second["signals"]


def test_a_frontend_session_and_a_database_session_select_different_members():
    """Gate 2. A selector returning the same roster regardless of input has
    not selected anything."""
    frontend = select_members(FRONTEND_SLICE, roster=FULL_ROSTER)
    database = select_members(DATABASE_SLICE, roster=FULL_ROSTER)

    assert frontend["members"] == ["designer"]
    assert set(database["members"]) != set(frontend["members"])
    assert "data" in database["members"]


def test_no_signal_selects_the_skeptic_alone():
    """§4.5: a lone skeptic is the correct default.

    The alternative is a unanimous chorus, which is one voice repeated.
    """
    quiet = SessionSlice(last_user_messages=["ok"], recent_activity=[],
                         touched_paths=[], digest="q")
    assert select_members(quiet, roster=FULL_ROSTER)["members"] == ["skeptic"]


def test_selection_is_capped_at_four_and_records_the_truncation():
    """More than 4 selected truncates and says so, rather than dropping
    members silently.

    The roster here is every member the signals can summon, not FULL_ROSTER:
    with three of them absent the selection never reaches four, and a
    truncation test that does not truncate asserts nothing.
    """
    everyone = {"team": [
        {"id": member, "enabled": True} for member in
        ("architect", "pragmatist", "skeptic", "designer", "api", "data",
         "devops", "security", "analyst")
    ]}
    wide = SessionSlice(
        last_user_messages=["review the api security deploy schema ui data"],
        recent_activity=["read"],
        touched_paths=["a.sql", "b.py", "c.yaml", "d.env", "e.csv", "f.tf"],
        digest="w",
    )
    result = select_members(wide, roster=everyone)
    assert len(result["members"]) == MEMBER_CAP
    assert result["truncated"] is True


def test_a_member_absent_from_the_roster_is_never_selected():
    """The roster decides who exists. A `.sql` file in a project with no data
    reviewer does not conjure one."""
    backend_only = {"team": [
        {"id": "architect", "enabled": True},
        {"id": "pragmatist", "enabled": True},
        {"id": "skeptic", "enabled": True},
    ]}
    result = select_members(DATABASE_SLICE, roster=backend_only)
    assert set(result["members"]) <= {"architect", "pragmatist", "skeptic"}


def test_the_selector_makes_no_llm_call():
    """Zero LLM calls, zero cost, reproducible - grepped, not read.

    An import of a client would reintroduce the cost this module exists to
    avoid, and no behavioural test would catch it.
    """
    source = Path(selector_module.__file__).read_text(encoding="utf-8")
    for forbidden in ("default_api", "openai", "anthropic", "litellm", "genai"):
        assert forbidden not in source, f"selector.py references {forbidden}"
    assert "completion(" not in source


# ======= roster =======


def test_bootstrap_persists_a_roster_and_load_reads_it_back(state_dir, tmp_path):
    """One writer, one reader, no race between them."""
    roster = bootstrap_roster(str(tmp_path))
    assert roster["team"]
    assert (state_dir / ROSTER_FILE).exists()
    assert load_roster(str(tmp_path))["team"] == roster["team"]


def test_loading_an_unbootstrapped_project_returns_none(state_dir, tmp_path):
    """No team yet is the normal state, and it stays distinct from an empty
    team - which would read like a measurement."""
    assert load_roster(str(tmp_path)) is None


def test_a_corrupt_roster_raises_rather_than_reading_as_empty(state_dir, tmp_path):
    """A corrupted roster is evidence. Falling back to an empty team is the
    3.3 defect: a confident answer with nothing behind it."""
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / ROSTER_FILE).write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_roster(str(tmp_path))


def test_a_disabled_member_survives_a_round_trip(state_dir, tmp_path):
    """`enabled: False` is persisted, not silently defaulted back to True."""
    save_roster(str(tmp_path), {"team": [{"id": "ghost", "enabled": False}]})
    assert load_roster(str(tmp_path))["team"][0]["enabled"] is False


# ======= commentary: silence explained, never fabricated =======


def test_ten_ticks_never_render_more_than_two_fragments(state_dir, tmp_path):
    """The promise a user checks by reading: at most 2 opinions per turn."""
    calls = []
    controller = CommentaryController(str(tmp_path), engine=_counting_engine(calls),
                                      max_members=4)
    save_roster(str(tmp_path), FULL_ROSTER)

    for tick in range(10):
        result = controller.tick(_result(_slice(
            digest=f"d{tick}",
            message="review the api schema deploy css",
            paths=("a.sql", "b.tsx", "c.yaml"))))
        assert result.spoke is True
        assert len(result.fragments) <= MAX_FRAGMENTS
        # Anything beyond the cap is counted, not silently dropped.
        assert result.suppressed == len(result.members_called) - len(result.fragments)

    assert controller.tick_count == 10


def test_more_opinions_than_the_cap_are_suppressed_and_recorded(state_dir, tmp_path):
    """4 members opine, 2 are rendered, 2 are named as suppressed."""
    calls = []
    controller = CommentaryController(str(tmp_path), engine=_counting_engine(calls),
                                      max_members=4)
    save_roster(str(tmp_path), FULL_ROSTER)

    result = controller.tick(_result(_slice(
        digest="wide", message="the api contract and css layout need review",
        paths=("a.sql", "b.tsx"))))

    assert len(result.members_called) > MAX_FRAGMENTS
    assert len(result.fragments) == MAX_FRAGMENTS
    assert result.suppressed == len(result.members_called) - MAX_FRAGMENTS
    assert result.to_dict()["suppressed"] == result.suppressed


def test_a_quiet_tick_costs_zero_engine_calls(state_dir, tmp_path):
    """§4.6: in a quiet session, zero calls.

    An unchanged digest means nothing happened, so nothing is asked of anybody.
    """
    calls = []
    controller = CommentaryController(str(tmp_path), engine=_counting_engine(calls))
    controller.tick(_result(_slice(digest="stable")))
    assert len(calls) == 1

    quiet = controller.tick(_result(_slice(digest="stable")))
    assert quiet.spoke is False
    assert quiet.reason == "no_change"
    assert len(calls) == 1, "a quiet tick called the engine"


def test_a_quiet_tick_costs_zero_calls_across_a_restart(state_dir, tmp_path):
    """The digest is read back from state, not merely held in memory.

    Holding it in-process is what made this pass in one run and fail in the
    next: a fresh controller would read an unchanged session as new work and
    spend a member call on it.
    """
    calls = []
    first = CommentaryController(str(tmp_path), engine=_counting_engine(calls))
    first.tick(_result(_slice(digest="stable")))

    second = CommentaryController(str(tmp_path), engine=_counting_engine(calls))
    assert second._last_digest == "stable"

    result = second.tick(_result(_slice(digest="stable")))
    assert result.spoke is False
    assert result.reason == "no_change"
    assert len(calls) == 1


def test_a_new_user_message_reopens_the_team(state_dir, tmp_path):
    """`no_change` is about an unchanged session, not about being quiet for
    good. A new digest speaks again - otherwise the team speaks exactly once
    and is never useful."""
    calls = []
    controller = CommentaryController(str(tmp_path), engine=_counting_engine(calls))
    controller.tick(_result(_slice(digest="first")))

    again = controller.tick(_result(_slice(digest="second", message="actually, look at this")))
    assert again.spoke is True
    assert len(calls) == 2


@pytest.mark.parametrize("word", ["stop", "halt", "quiet", "enough", "that's all", "Stop."])
def test_a_stop_word_stops_the_team_and_says_why(state_dir, tmp_path, word):
    controller = CommentaryController(str(tmp_path), engine=_counting_engine([]))
    result = controller.tick(_result(_slice(digest=word, message=word)))
    assert result.spoke is False
    assert result.reason == "stopped"
    assert result.fragments == []


@pytest.mark.parametrize("message", [
    "stop the current phase",
    "halt the deploy",
    "enough of this already",
    "quietly rename the variable",
])
def test_a_stop_word_matches_only_as_the_whole_leading_clause(state_dir, tmp_path, message):
    """§4.2: "stop the current phase" does not silence the team.

    It is a request to stop a phase. A substring match would silence the team
    on nearly every instruction that begins with a stop word.
    """
    assert is_stop(message) is False
    controller = CommentaryController(str(tmp_path), engine=_counting_engine([]))
    assert controller.tick(_result(_slice(digest=message, message=message))).spoke is True


def test_leading_clause_stops_at_the_first_clause_boundary():
    assert leading_clause("Stop.") == "stop"
    assert leading_clause("stop, please") == "stop"
    assert leading_clause("STOP THE THING") == "stop the thing"
    assert leading_clause("") == ""


def test_the_stop_sentinel_outranks_everything(state_dir, tmp_path):
    """`comment off` writes it; the next tick reports `stopped` and calls
    nobody, whatever the digest says."""
    calls = []
    controller = CommentaryController(str(tmp_path), engine=_counting_engine(calls))
    assert controller.tick(_result(_slice(digest="d1"))).spoke is True

    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "commentary.stop").write_text("stop\n", encoding="utf-8")

    stopped = controller.tick(_result(_slice(digest="d2")))
    assert stopped.spoke is False
    assert stopped.reason == "stopped"
    assert len(calls) == 1, "the sentinel must be checked before the engine"


def test_no_engine_means_no_opinion_not_an_invented_one(state_dir, tmp_path):
    """§3.3. M0's rule, tested hardest here: the controller runs unattended and
    nobody is watching for a crash that produces a plausible-looking answer."""
    controller = CommentaryController(str(tmp_path), engine=None)
    result = controller.tick(_result(_slice(digest="d1")))
    assert result.spoke is False
    assert result.reason == "engine_unavailable"
    assert result.fragments == []


def test_an_engine_that_opines_nothing_renders_nothing(state_dir, tmp_path):
    """An empty result is silence with a reason, not a filler fragment."""
    controller = CommentaryController(str(tmp_path), engine=lambda m, s: [])
    result = controller.tick(_result(_slice(digest="d1")))
    assert result.spoke is False
    assert result.reason == "no_opinion"
    assert result.fragments == []


def test_a_missing_session_is_reported_not_guessed(state_dir, tmp_path):
    """The trust surface: if the session file is missing, commentary reports
    why. It does not fall back to a guess."""
    controller = CommentaryController(str(tmp_path), engine=_counting_engine([]))
    result = controller.tick(SessionResult(spoke=False, reason="no_session",
                                           session_path="/nope/session.jsonl"))
    assert result.spoke is False
    assert result.reason == "no_session"
    assert result.fragments == []
    assert result.session_path == "/nope/session.jsonl"


def test_every_tick_explains_itself(state_dir, tmp_path):
    """§7.1.8: `spoke: true` with at most 2 fragments, or `spoke: false` with a
    reason. There is no third state."""
    calls = []
    controller = CommentaryController(str(tmp_path), engine=_counting_engine(calls),
                                      max_members=4)
    save_roster(str(tmp_path), FULL_ROSTER)

    outcomes = [
        _result(_slice(digest="a")),                      # speaks
        _result(_slice(digest="a")),                      # no_change
        _result(_slice(digest="b", message="stop")),      # stopped
        _result(_slice(digest="c")),                      # speaks
        SessionResult(spoke=False, reason="no_session"),  # no_session
    ]

    for outcome in outcomes:
        result = controller.tick(outcome)
        if result.spoke:
            assert 0 < len(result.fragments) <= MAX_FRAGMENTS
        else:
            assert result.reason, "a silent tick must name why it was silent"
            assert result.fragments == []


def test_a_corrupt_state_file_does_not_stop_the_controller(state_dir, tmp_path):
    """A constructor that raises is silence with no reason.

    An unreadable commentary.json leaves the digest *unknown* rather than
    empty, so the first tick speaks: it cannot honestly claim a session is
    unchanged when it does not know what it last saw.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "commentary.json").write_text("{ not json", encoding="utf-8")

    controller = CommentaryController(str(tmp_path), engine=_counting_engine([]))
    assert controller._last_digest is None

    result = controller.tick(_result(_slice(digest="d1")))
    assert result.spoke is True
    # The corrupt file was replaced with a real one rather than left to fail
    # every subsequent tick.
    assert json.loads((state_dir / "commentary.json").read_text(encoding="utf-8"))


def test_status_reports_what_actually_happened(state_dir, tmp_path):
    """`comment status` reports the last digest and opinion, not a default."""
    calls = []
    controller = CommentaryController(str(tmp_path), engine=_counting_engine(calls))
    save_roster(str(tmp_path), FULL_ROSTER)
    controller.tick(_result(_slice(digest="recorded-digest")))

    state = controller.load_state()
    assert state["tick_count"] == 1
    assert state["last_digest"] == "recorded-digest"
    assert state["last_spoke"] is True
    assert state["last_opinion"] is not None
