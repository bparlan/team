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


@pytest.fixture
def stub_provider(monkeypatch):
    provider = _StubProvider()
    monkeypatch.setattr(theteam, "default_api", provider, raising=False)
    # `get_state_manager` is a process-wide singleton; a stale one from another
    # test would carry a state file this test did not create.
    monkeypatch.setattr(state_manager_module, "_state_manager", None, raising=False)
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
    """What one discussion wrote, a fresh manager can read back."""
    theteam.run_discussion(str(project), "should the API change")

    state_file = project / ".omp" / "theteam" / "state.json"
    reloaded = state_manager_module.UnifiedStateManager(str(state_file))
    reloaded.load_state()

    assert reloaded.discussion_state.discussion_history, \
        "load_state restored nothing from a valid file"
    # The discussion task is not in `tasks`: `update_task` moves a task to
    # `task_history` and deletes it when the status becomes `completed`, which
    # is what `run_discussion` does before it saves. Asserting on `tasks` was
    # my first attempt and it was wrong — an empty dict is the correct
    # post-condition, and history is where a finished task belongs.
    assert reloaded.task_state.task_history, \
        "the completed discussion task was not persisted to history"
