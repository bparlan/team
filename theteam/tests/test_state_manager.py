"""Tests for `theteam.core.state_manager`.

M11 added this file. `state_manager.py` had no test coverage at all, which is
how a crash shipped in the skill's headline command: `DiscussionState`,
`SystemAwarenessState` and `TaskState` each called `self._notify_listeners`,
but the method was defined only on `UnifiedStateManager`. `theteam discuss`
reaches `DiscussionState.start_discussion` from `run_discussion`, so the whole
path raised `AttributeError` before a single member was selected or spawned.

These tests defend the contract, not the implementation: every state class can
raise an event when used standalone, and a listener registered on the manager
still hears events raised by its sub-states.
"""
import os
import tempfile
import pytest

from theteam.core.state_manager import (
    DiscussionState,
    StateEventType,
    SystemAwarenessState,
    TaskState,
    UnifiedStateManager,
)


# -- the crash itself -------------------------------------------------------

@pytest.mark.parametrize("cls", [DiscussionState, SystemAwarenessState, TaskState])
def test_sub_state_can_raise_an_event_standalone(cls):
    """A sub-state constructed on its own must not raise AttributeError.

    This is the regression. Before M11 these classes had no
    `_notify_listeners` at all, so any event they raised was a crash. The
    standalone case is the real one: `DiscussionState()` is constructed
    directly in `UnifiedStateManager.__init__` and in tests, and nothing
    guarantees a notifier was ever injected.
    """
    state = cls()
    assert hasattr(state, "_notify_listeners")
    # The call must simply succeed. Whether anyone is listening is a separate
    # question, answered below.
    state._notify_listeners(StateEventType.DISCUSSION_STARTED, {"probe": True})


def test_start_discussion_does_not_crash():
    """The exact call `theteam discuss` makes, on the exact class it uses."""
    discussion_id = DiscussionState().start_discussion("a topic", "/tmp")
    assert discussion_id.startswith("discussion_")


# -- listeners still work ---------------------------------------------------

def test_manager_listener_hears_a_sub_state_event():
    """Injected notifier: a registered listener fires for a sub-state event.

    The no-op default alone would pass the test above while silently dropping
    every event, which is a quieter version of the same defect. This is the
    check that the injection actually happened.
    """
    manager = UnifiedStateManager()
    seen = []
    manager.add_listener(lambda event_type, data: seen.append((event_type, data)))

    manager.discussion_state.start_discussion("a topic", "/tmp")

    assert [e for e, _ in seen] == [StateEventType.DISCUSSION_STARTED]
    assert seen[0][1]["topic"] == "a topic"


def test_every_sub_state_is_wired_to_the_manager():
    """All three sub-states, not just the one the crash was found through."""
    manager = UnifiedStateManager()
    for sub_state in (manager.discussion_state, manager.system_awareness_state,
                      manager.task_state):
        assert sub_state._listener_notifier == manager._notify_listeners


def test_a_raising_listener_does_not_break_the_transition():
    """One bad listener must not stop the others or fail the state change.

    §3.3: observability failure is not control flow. `_notify_listeners`
    already guards each call; this pins that behaviour so a future refactor
    cannot remove the guard.
    """
    manager = UnifiedStateManager()
    seen = []
    manager.add_listener(lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    manager.add_listener(lambda *_: seen.append(True))

    manager.discussion_state.start_discussion("a topic", "/tmp")

    assert seen == [True], "the healthy listener must still be called"
    assert manager.discussion_state.current_discussion_id is not None


# -- the WAL follows the state file ----------------------------------------

def test_wal_is_written_beside_the_state_file(tmp_path):
    """The log must not escape the project it describes.

    `WriteAheadLog()` defaulted to a bare "wal.json", resolved against the
    process CWD. A manager pointed at a tmpdir therefore appended to whatever
    directory the suite was launched from — which is how the tracked
    `wal.json` at the repo root filled with pytest fixture state.
    """
    state_file = tmp_path / ".omp" / "theteam" / "state.json"
    state_file.parent.mkdir(parents=True)

    manager = UnifiedStateManager(str(state_file))
    manager.discussion_state.start_discussion("a topic", str(tmp_path))
    manager.save_state()

    assert manager.wal.wal_file == str(state_file.parent / "wal.json")
    assert (state_file.parent / "wal.json").exists()


def test_wal_without_a_state_file_never_lands_in_the_cwd():
    """No state file means no project, so the log must not pick the CWD.

    This is the case that actually leaked: `UnifiedStateManager()` with no
    argument still constructed a WAL, and a relative default resolved to
    whichever directory the process happened to start in.
    """
    manager = UnifiedStateManager()
    assert os.path.isabs(manager.wal.wal_file), "a relative WAL path lands in the CWD"
    assert os.path.commonpath([manager.wal.wal_file, tempfile.gettempdir()]) \
        == tempfile.gettempdir()


def test_wal_without_a_state_file_is_unique_per_manager():
    """Two stateless managers must not interleave entries in one log.

    A fixed temp path would satisfy "not in the CWD" while still giving every
    stateless manager the same file — and the suite constructs fourteen of them
    across two files. `replay_entries` would then read another manager's state.
    """
    paths = {UnifiedStateManager().wal.wal_file for _ in range(3)}
    assert len(paths) == 3, f"stateless managers share a WAL: {paths}"
