"""End-to-end coverage of `theteam.run_discussion`.

M11 added this file after finding that **no test had ever called
`run_discussion`.** Two hard defects lived in that one function and 653 tests
missed both:

1. `DiscussionState.start_discussion` called a `_notify_listeners` that existed
   on no sub-state, so the call raised `AttributeError` at the third statement
   of the discussion.
2. `save_state`, at the *end* of the same function, called a WAL method that
   does not exist and a checksum method whose return value it discarded — all
   inside `except Exception: logger.error(...)`. So even after fixing (1), a
   discussion completed, printed its synthesis, and persisted nothing.

`load_state` had the mirror-image bug: it called a non-existent
`verify_checksum` inside the same swallowing `try`, so nothing was ever
restored.

The gate in `_require_provider` means `theteam discuss` refuses cleanly outside
OMP, so a smoke test outside a session never reaches any of this. Only a test
that supplies a provider exercises the path.

The stub is the minimum `default_api` surface `run_discussion` uses: `task(...)`
to spawn and `output(handle)` to collect.
"""
import json
import os

import pytest

import theteam
from theteam.core import state_manager as state_manager_module


class _StubProvider:
    """Stands in for the OMP `default_api` global.

    Records what it was asked to spawn, so a test can assert the selection
    reached the provider, and returns well-formed member notes keyed by the task
    name `run_discussion` used.
    """

    def __init__(self):
        self.spawned = []

    def task(self, **kwargs):
        tasks = kwargs.get("tasks") or []
        self.spawned.extend(tasks)
        return {"tasks": [{"name": t.get("name"), "handle": f"h:{t.get('name')}"}
                          for t in tasks]}

    def output(self, handle):
        name = handle.split(":", 1)[1]
        if name.startswith("intro_"):
            return {"id": name[len("intro_"):], "role": "tester",
                    "personal_insight": f"{name} weighed in."}
        return {"id": name, "role": "tester", "verdict": "ok",
                "note": f"{name} reviewed the topic."}


@pytest.fixture(autouse=True)
def isolated_singleton():
    """Keep the process-wide state manager from escaping this file's tests.

    `get_state_manager` caches its result in a module global. Tests here rebind
    that global to `tmp_path` projects, and pytest deletes those directories
    when the test ends — so a global left pointing at one is a live hazard for
    whatever runs next.

    The reset belongs in a fixture rather than at the top of each test because
    the first version of the rebind test did exactly that and still leaked: a
    *setup* reset restores the entry state, not the exit state.
    """
    previous = state_manager_module._state_manager
    state_manager_module._state_manager = None
    try:
        yield
    finally:
        state_manager_module._state_manager = previous


@pytest.fixture
def stub_provider(monkeypatch):
    provider = _StubProvider()
    monkeypatch.setattr(theteam, "default_api", provider, raising=False)
    monkeypatch.setattr(theteam, "get_state_manager",
                        state_manager_module.get_state_manager)
    return provider


@pytest.fixture
def project(tmp_path):
    """A bootstrapped project, built by the code path a user actually takes.

    Hand-writing the config was the first attempt and it failed with
    `KeyError: 'behavior'`. That is the lesson: a fixture inventing its own
    config drifts from `theteam_config.REQUIRED_TOP_KEYS` and then tests
    something the product never produces.
    """
    assert theteam.bootstrap_flow(str(tmp_path)), "bootstrap failed"
    config_path = tmp_path / "theteam.config"
    assert config_path.exists(), "bootstrap did not write a config"
    return tmp_path


def test_run_discussion_completes_without_raising(project, stub_provider):
    """The headline command runs end to end.

    Regression for both M11 defects: this reached
    `DiscussionState.start_discussion` (which raised `AttributeError`) and then
    `save_state` (which wrote nothing while reporting success).
    """
    result = theteam.run_discussion(str(project), "should the API change")

    assert result is True, "run_discussion must report success on a clean run"
    assert stub_provider.spawned, "no member was ever spawned"


def test_run_discussion_persists_state(project, stub_provider):
    """A completed discussion leaves a real, checksummed state file behind.

    This is the assertion that would have caught defect 2. `save_state` used to
    log its own failure and return normally, so "did not raise" proved nothing;
    the file either exists with a checksum or the discussion did not happen.
    """
    theteam.run_discussion(str(project), "should the API change")

    state_file = project / ".omp" / "theteam" / "state.json"
    assert state_file.exists(), "run_discussion reported success but wrote no state"

    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert "checksum" in data, "state file was written without a checksum"
    assert data.get("discussion_state", {}).get("discussion_history"), \
        "the discussion was never recorded in history"


def test_run_discussion_state_survives_a_reload(project, stub_provider):
    """Everything `save_state` wrote comes back, field for field.

    The first version of this test asserted only `discussion_history` and
    `task_history`, and a mutation that deleted the `active_discussions`
    restore from `load_state` still passed it. A reader test that checks two of
    ten fields cannot detect a partial reader, which is the failure mode that
    matters here: a state file that half-loads looks like a project that
    forgot something, with nothing to distinguish the two.

    So this walks the same field list the writer produces, and asserts each one
    round-trips. `system_awareness_state` is included even where the values are
    empty, because "restored an empty dict" and "never assigned it" are
    indistinguishable from the outside — asserting equality against the
    on-disk value is what separates them.
    """
    theteam.run_discussion(str(project), "should the API change")

    state_file = project / ".omp" / "theteam" / "state.json"
    on_disk = json.loads(state_file.read_text(encoding="utf-8"))

    reloaded = state_manager_module.UnifiedStateManager(str(state_file))
    reloaded.load_state()

    for section, attr in (
        ("discussion_state", "active_discussions"),
        ("discussion_state", "discussion_history"),
        ("discussion_state", "current_discussion_id"),
        ("task_state", "tasks"),
        ("task_state", "task_history"),
        ("task_state", "task_assignments"),
    ):
        expected = on_disk.get(section, {}).get(attr)
        actual = getattr(getattr(reloaded, section), attr)
        assert actual == expected, (
            f"load_state did not restore {section}.{attr}: "
            f"expected {expected!r}, got {actual!r}"
        )

    # The discussion itself, named rather than counted, so an empty-but-correct
    # round trip cannot satisfy this by accident.
    assert reloaded.discussion_state.discussion_history, \
        "the discussion was not recorded in history at all"
    # The task is not in `tasks`: `update_task` moves a task to `task_history`
    # and deletes it on `completed`, which `run_discussion` does before saving.
    # An empty `tasks` dict is the correct post-condition; my first assertion
    # expected a task there and was wrong.
    assert reloaded.task_state.task_history, \
        "the completed discussion task was not persisted to history"


def test_load_state_restores_populated_fields(project, stub_provider):
    """Every field round-trips when it has a value, not only when empty.

    The field-by-field test above compares against the on-disk value, which
    cannot distinguish "restored correctly" from "never assigned" when that
    value is empty. Two fields are always empty after a discussion —
    `active_discussions` (a finished discussion is moved out) and
    `task_assignments` (nothing is assigned a member) — and mutating either
    restore still passed. Measured, not assumed.

    So this writes known values into every field, saves, and reads them back.
    A restore that is dropped, or assigned `{}` regardless, now fails.
    """
    theteam.run_discussion(str(project), "should the API change")

    state_file = project / ".omp" / "theteam" / "state.json"
    manager = state_manager_module.UnifiedStateManager(str(state_file))

    # Populate the two fields the discussion leaves empty, plus the ones it
    # does not, so every branch of the restore is exercised with a real value.
    manager.discussion_state.active_discussions = {
        "discussion_open": {"topic": "still running", "status": "active",
                            "participants": ["architect"]}}
    manager.task_state.task_assignments = {"task_1": ["architect", "skeptic"]}
    manager.task_state.tasks = {"task_1": {"title": "still open", "status": "in_progress"}}
    manager.save_state()

    reloaded = state_manager_module.UnifiedStateManager(str(state_file))
    reloaded.load_state()

    assert reloaded.discussion_state.active_discussions == {
        "discussion_open": {"topic": "still running", "status": "active",
                            "participants": ["architect"]}}, \
        "load_state did not restore active_discussions"
    assert reloaded.task_state.task_assignments == {"task_1": ["architect", "skeptic"]}, \
        "load_state did not restore task_assignments"
    assert reloaded.task_state.tasks == {"task_1": {"title": "still open",
                                                    "status": "in_progress"}}, \
        "load_state did not restore tasks"


def test_load_state_overwrites_rather_than_merges(project, stub_provider):
    """Loading replaces what is in memory; it does not accumulate onto it.

    The other reload test builds a fresh manager, which is empty, so
    "did the restore run?" and "did it land the right value?" are the same
    question. This asks the question that actually matters in production.

    `get_state_manager` is a process-wide singleton: the first call constructs
    the manager and the second returns the same object. So in normal use
    `load_state` runs against a manager that **already holds state** — a
    previous discussion, a previous project. If it merged instead of
    overwrote, entries from an earlier context would survive a load and be
    reported as if they came from the file.

    Distinct sentinel values, not non-emptiness: the in-memory state is seeded
    with data that is in no way related to what is on disk, so a surviving
    sentinel is unambiguous. Asserting "not empty" could not distinguish this
    from success.
    """
    theteam.run_discussion(str(project), "should the API change")

    state_file = project / ".omp" / "theteam" / "state.json"
    on_disk = json.loads(state_file.read_text(encoding="utf-8"))
    assert on_disk["discussion_state"]["discussion_history"], \
        "precondition: the file on disk has a discussion to load"

    # A manager that already holds unrelated state, pointed at the same file.
    stale = state_manager_module.UnifiedStateManager(str(state_file))
    stale.discussion_state.discussion_history.append(
        {"topic": "SENTINEL stale in-memory entry", "status": "active"})
    stale.discussion_state.active_discussions = {
        "sentinel": {"topic": "SENTINEL stale discussion", "status": "active"}}
    stale.task_state.tasks = {"sentinel-task": {"title": "SENTINEL"}}

    stale.load_state()

    assert stale.discussion_state.discussion_history == \
        on_disk["discussion_state"]["discussion_history"], \
        "load_state merged onto existing history instead of replacing it"
    assert "sentinel" not in stale.discussion_state.active_discussions, \
        "load_state left a pre-existing discussion in active_discussions"
    assert "sentinel-task" not in stale.task_state.tasks, \
        "load_state left a pre-existing task in tasks"

def test_get_state_manager_rebinds_over_a_populated_singleton(project, stub_provider, tmp_path):
    """The production sequence: one manager, two projects, real state.

    The first version of this test built two empty directories and only checked
    that `get_state_manager` returned a manager pointing at the second path. It
    proved the rebinding but not the thing that actually matters: that a
    **populated** manager, asked for a different project, is rebuilt *and*
    reloads that project's file rather than carrying the first project's state
    across. Nothing in it ever wrote state, so a manager that rebound its path
    but kept its contents would have passed.

    This drives the shape `run_discussion` produces: a discussion in project A,
    then a second one in project B, with the singleton alive throughout. A's
    entry must not appear in B.
    """
    project_a = tmp_path / "a"
    project_b = tmp_path / "b"
    for root in (project_a, project_b):
        root.mkdir()
        assert theteam.bootstrap_flow(str(root)), "bootstrap failed"

    # The entry reset is the autouse `isolated_singleton` fixture's job; adding
    # it here as well would be the setup-only restore that fixture exists to
    # replace.

    # Project A: a real discussion, which populates the singleton.
    assert theteam.run_discussion(str(project_a), "topic belonging to A")
    path_a = str(project_a / ".omp" / "theteam" / "state.json")
    assert os.path.exists(path_a), "project A wrote no state file"

    # The cheap path first: the same project must not rebuild.
    manager_a = state_manager_module.get_state_manager(path_a)
    assert state_manager_module.get_state_manager(path_a) is manager_a, \
        "an unchanged path must reuse the singleton"

    # Project B is seeded on disk and NEVER written to by this test. That is the
    # point: if B's own discussion had been produced by `run_discussion`, then
    # under a rebuild-without-reload mutation the manager would still be empty
    # and the test would pass for the wrong reason. With nothing but a seeded
    # file, the *only* way `SEEDED` can appear in memory is a real
    # `load_state` — so the assertion below cannot be satisfied by the product
    # writing state, nor vacuously by it failing to.
    #
    # `save_state` does not create its directory; `StateStore.__init__` does
    # (state.py:128) and every product path reaches it. Seeding directly skips
    # that, so the directory is made here. Noted rather than fixed: a
    # `save_state` into a missing directory raises a raw `FileNotFoundError`
    # from `open` — a named error, not a silent one, so not a §3.3 defect.
    path_b = str(project_b / ".omp" / "theteam" / "state.json")
    os.makedirs(os.path.dirname(path_b), exist_ok=True)
    seeded = state_manager_module.UnifiedStateManager(path_b)
    seeded.discussion_state.discussion_history.append(
        {"topic": "SEEDED topic for B", "status": "active"})
    seeded.task_state.tasks = {"seeded-task": {"title": "SEEDED"}}
    seeded.save_state()
    del seeded

    # Rebind while manager_a is live: the production shape.
    manager_b = state_manager_module.get_state_manager(path_b)

    assert manager_b is not manager_a, \
        "a different project must not share the first project's manager"
    assert manager_b.state_file == path_b, \
        "get_state_manager kept the first state file for a second project"

    topics_b = [entry.get("topic", "") for entry in manager_b.discussion_state.discussion_history]
    assert topics_b == ["SEEDED topic for B"], \
        f"B's seeded state was not loaded from disk; got {topics_b}"
    assert "seeded-task" in manager_b.task_state.tasks, \
        "B's seeded task was not loaded from disk"
    assert not any("A" in entry.get("topic", "")
                   for entry in manager_b.discussion_state.discussion_history), \
        "project A's state leaked into project B"
