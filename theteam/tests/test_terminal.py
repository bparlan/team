"""
Tests for the terminal renderer.

Stdlib only, because the renderer is stdlib only. These run in a clean CI
checkout where `rich` is not installed, which is the point: a module-scope
import of an undeclared library would pass the suite on a developer machine
and turn it red on every clean runner.
"""

import ast
import io
import json
import os
import tempfile
from contextlib import redirect_stdout

import pytest

from theteam import cli
from theteam.ui import terminal
from theteam.ui.terminal import (
    RENDERERS,
    UNMEASURED,
    render_history,
    render_status,
    render_tasks,
    watch,
)


def payload(project_root, view):
    """
    The payload `watch <view>` renders, or a test failure.

    The `None` case is the not-bootstrapped path, which `watch` reports rather
    than rendering; a test that got one was asking the wrong question.
    """
    reader = {
        "status": cli.status_payload,
        "tasks": cli.tasks_payload,
        "history": cli.history_payload,
    }[view]
    data, _ = reader(project_root)
    assert data is not None, f"{view} returned no payload for {project_root}"
    return data


def run_json(argv):
    """Run a command with `--json` and return the parsed payload."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        assert cli.main(argv) == 0
    return json.loads(buffer.getvalue())


@pytest.fixture
def empty_project():
    """Bootstrapped, no audit chain, no runs, no scheduled tasks."""
    with tempfile.TemporaryDirectory() as tmp:
        assert cli.main(["--project-root", tmp, "bootstrap"]) == 0
        yield tmp


@pytest.fixture
def unrun_task(empty_project):
    """The empty project, plus one registered task that has never executed."""
    os.mkdir(os.path.join(empty_project, "tasks"))
    with open(os.path.join(empty_project, "tasks", "task-idle.yaml"), "w",
              encoding="utf-8") as handle:
        handle.write(
            "id: idle\nname: Idle\ntype: monitoring\npriority: 1\norder: 0\n"
            "schedule:\n  enabled: false\n"
        )
    return empty_project


@pytest.fixture
def tripped_project(unrun_task):
    """The unrun project, plus a breaker a real call recorded as tripped."""
    from theteam.tasks.repository import TaskRepository

    repo = TaskRepository(unrun_task)
    for _ in range(5):
        repo.record_run("idle", "failed", "returncode 1",
                        breaker="open", consecutive_failures=5)
    return unrun_task


# ======= R3: no fabricated values =======

class TestHonesty:
    def test_absent_chain_is_never_reported_as_intact(self, empty_project):
        frame = render_status(payload(empty_project, "status"))
        assert "absent" in frame
        # The literal state names that would be a claim about something
        # nobody measured (§3.3).
        assert "intact" not in frame
        assert "closed" not in frame

    def test_unrun_task_is_never_reported_as_closed(self, unrun_task):
        frame = render_tasks(payload(unrun_task, "tasks"))
        assert "never run" in frame
        assert "closed" not in frame
        assert "0%" not in frame

    def test_task_with_no_runs_reports_no_rate(self, unrun_task):
        frame = render_history(payload(unrun_task, "history"))
        # A rate of zero is indistinguishable from a task that has never
        # once passed; an unmeasured rate prints as `-`.
        assert "0%" not in frame
        assert UNMEASURED in frame

    def test_tripped_breaker_is_shown(self, tripped_project):
        frame = render_status(payload(tripped_project, "status"))
        assert "flaky" not in frame and "idle" in frame
        assert "open" in frame
        assert "5 consecutive failures" in frame

    def test_tripped_breaker_is_shown_in_tasks_and_history(self, tripped_project):
        for view, render in (("tasks", render_tasks), ("history", render_history)):
            frame = render(payload(tripped_project, view))
            assert "open" in frame, f"{view} hid the trip"

    def test_no_trips_claims_none_rather_than_healthy(self, unrun_task):
        frame = render_status(payload(unrun_task, "status"))
        # No trips is not the same as every breaker measured closed.
        assert "none tripped" in frame
        assert "closed" not in frame
    def test_unbootstrapped_project_reports_why_not_a_calm_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            assert watch(tmp, "status", once=True, stream=out) == 1
            # The reason is named, and no frame is drawn: a table with no
            # rows reads like a healthy project, and this one is not.
            assert "not found" in out.getvalue()
            assert "roster" not in out.getvalue()


# ======= R2: the three views =======

class TestViews:
    def test_exactly_three_views(self):
        assert set(RENDERERS) == {"status", "tasks", "history"}

    def test_each_view_renders_once_and_exits_zero(self, unrun_task):
        for view in RENDERERS:
            out = io.StringIO()
            assert watch(unrun_task, view, once=True, stream=out) == 0
            assert out.getvalue().strip()

    def test_frames_carry_the_view_name(self, unrun_task):
        assert "watch status" in render_status(payload(unrun_task, "status"))
        assert "watch tasks" in render_tasks(payload(unrun_task, "tasks"))
        assert "watch history" in render_history(payload(unrun_task, "history"))

    def test_empty_task_list_reports_it(self, empty_project):
        frame = render_tasks(payload(empty_project, "tasks"))
        assert "no tasks registered" in frame

    def test_null_order_renders_as_a_dash_not_a_zero(self, empty_project):
        # A task with no `order` key has no measured position; `0` is a
        # position, and a real one.
        os.mkdir(os.path.join(empty_project, "tasks"))
        with open(os.path.join(empty_project, "tasks", "task-unordered.yaml"), "w",
                  encoding="utf-8") as handle:
            handle.write("id: unordered\nname: U\ntype: ops\npriority: 3\n")
        frame = render_tasks(payload(empty_project, "tasks"))
        assert UNMEASURED in frame


# ======= R2: the environment story =======

class TestDependencies:
    UNDECLARED = ("rich", "curses", "textual", "blessed", "prompt_toolkit")

    def test_no_third_party_import_at_module_scope(self):
        """
        The `rich` decision, asserted rather than documented.

        `rich` 14.3.4 is installed in this pyenv transitively and declared
        nowhere, so a module-scope import would pass the full suite here and
        turn it red in CI. Asserting the absence makes the choice enforceable.
        """
        with open(terminal.__file__, "r", encoding="utf-8") as handle:
            source = handle.read()
        for undeclared in self.UNDECLARED:
            assert f"import {undeclared}" not in source, (
                f"{undeclared} is not declared in pyproject.toml; a module-scope "
                f"import of it is green here and red in CI"
            )

    def test_renders_with_every_optional_library_unimportable(self, monkeypatch):
        """The fallback path: no `rich`, no `curses`, still a frame."""
        import builtins

        real_import = builtins.__import__
        blocked = set(self.UNDECLARED)

        def _blocked_import(name, *args, **kwargs):
            if name.split(".")[0] in blocked:
                raise ImportError(f"{name} is not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _blocked_import)
        with tempfile.TemporaryDirectory() as tmp:
            assert cli.main(["--project-root", tmp, "bootstrap"]) == 0
            out = io.StringIO()
            assert watch(tmp, "status", once=True, stream=out) == 0
            assert "roster" in out.getvalue()


# ======= C3: the machine surface is unchanged =======

class TestMachineSurfaceUnchanged:
    def test_status_json_matches_what_the_renderer_read(self, empty_project):
        """`watch status` reads the same payload `status --json` emits."""
        assert payload(empty_project, "status") == run_json(
            ["--project-root", empty_project, "status", "--json"])

    def test_tasks_json_matches_what_the_renderer_read(self, unrun_task):
        assert payload(unrun_task, "tasks") == run_json(
            ["--project-root", unrun_task, "tasks", "--json"])

    def test_history_json_matches_what_the_renderer_read(self, unrun_task):
        assert payload(unrun_task, "history") == run_json(
            ["--project-root", unrun_task, "history", "--json"])

    def test_renderer_does_not_reprint_command_output(self, unrun_task):
        """
        §2: these commands are the machine surface. A frame that is a copy of
        the command's stdout has rewritten the contract agentic consumers read.
        """
        _, lines = cli.tasks_payload(unrun_task)
        frame = render_tasks(payload(unrun_task, "tasks"))
        assert frame.strip() != "\n".join(lines).strip()


# ======= R1: one boundary, written down =======

class TestSingleBoundary:
    """
    R1, asserted rather than documented: the renderer reads `cli.py`'s
    `*_payload` functions and nothing else. A second data source is a second
    adapter, which is how `task_stack_adapter.py` came to exist in M2.
    """

    READERS = ("status_payload", "tasks_payload", "history_payload")

    def test_renderer_reads_only_the_three_payload_functions(self):
        for reader in self.READERS:
            assert f"cli.{reader}" in _code()
        # The whole import surface, by AST rather than by text: a docstring
        # that *mentions* a module in order to say it does not use one is not
        # a use of it. `theteam` is the function-local `from theteam import cli`
        # the watch loop uses - the one data source it is allowed.
        #
        # `theteam.monitor` joined this set with `--monitor`. It is a new
        # import, so it is named here rather than the assertion loosened: it
        # reads nothing. It takes the two payloads the loop already fetched and
        # returns the difference between them, so the data path is still
        # `state.py` -> `*_payload` -> renderer. A monitor that resolved a path
        # or opened a file would be the second adapter R1 forbids, and the two
        # assertions below are what would catch it.
        assert {name for name, _ in _imports()} == {
            "theteam",
            "theteam.core.audit_chain",
            "theteam.monitor",
            "theteam.ui.components.design_tokens",
            "shutil",
            "sys",
            "time",
            "typing",
        }

    def test_renderer_does_not_import_the_peer_view_model(self):
        """
        `build_visibility` is a peer builder for the unwired reflex dashboard,
        not this renderer's source. Importing it would be the second adapter
        R1 forbids, and the peer docstring says so in as many words.
        """
        names = {name for name, _ in _imports()}
        assert "theteam.ui.components.visibility" not in names

    def test_renderer_does_not_reach_past_the_payloads(self):
        """It reads payloads, not files. `state.py` and the store stay below."""
        names = {name for name, _ in _imports()}
        for forbidden in ("theteam.state", "theteam.tasks",
                          "theteam.core.member"):
            assert forbidden not in names, (
                f"the renderer must read payloads, not {forbidden!r}"
            )


def _code():
    """The renderer's own source."""
    with open(terminal.__file__, "r", encoding="utf-8") as handle:
        return handle.read()


def _imports():
    """Every `import X` / `from X import` in the renderer, as `(module, name)`.

    Parsed rather than grepped so a function-local import - which is how the
    renderer reaches `cli` without a module-scope dependency - counts the same
    as any other.
    """
    found = []
    tree = ast.parse(_code())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, alias.asname) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.extend((node.module, alias.asname) for alias in node.names)
    return found
