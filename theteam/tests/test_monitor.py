"""
Tests for frame-over-frame change detection and alerting.

`monitor.py` decides what a watch loop says about *transitions*, and the
decisions are almost all about what must NOT be said. A breaker that is open
has been open since the first frame; a task that never ran has a `None` breaker
because nothing measured one, not because it was removed. Every rule here is a
refusal to report a level as an event, so the tests are mostly about the
negative cases - the ones a plausible rewrite gets wrong.

Two things are deliberately not tested. The `Monitor` attribute names are not a
contract (a rename moves the tests, it does not break them), and the banner's
exact wording is not one either - what matters is that the first frame says
"nothing was compared" rather than "0 changes", because those are different
claims about the system.

Payloads come from real bootstrapped projects and real `record_run` calls, not
from hand-built dicts. The claim under test is that the monitor reports what the
system actually did; a monitor fed a fabricated payload would pass those same
assertions while proving nothing, so every integration test drives the real
repository and reads the real `*_payload` functions.
"""

import ast
import io
import json
import os
import re
import tempfile
from contextlib import redirect_stdout

import pytest

from theteam import cli
from theteam import monitor
from theteam.monitor import MAX_EVENTS, VISIBLE_EVENTS, Monitor, alerts, diff
from theteam.ui.terminal import render_status, watch


def payload(project_root, view):
    """
    The payload `watch <view>` renders, or a test failure.

    The same helper `test_terminal.py` uses: a `None` here means the project
    could not be read, which is never what these tests are about.
    """
    reader = {
        "status": cli.status_payload,
        "tasks": cli.tasks_payload,
        "history": cli.history_payload,
    }[view]
    data, _ = reader(project_root)
    assert data is not None, f"{view} returned no payload for {project_root}"
    return data


def run_cli(argv):
    """Run a command, capturing the frame it draws. Returns `(code, stdout)`."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = cli.main(argv)
    return code, buffer.getvalue()


def write_task(project_root, task_id, order):
    """A real task file, so the repository's own read finds it."""
    with open(os.path.join(project_root, "tasks", f"task-{task_id}.yaml"), "w",
              encoding="utf-8") as handle:
        handle.write(
            f"id: {task_id}\nname: {task_id}\ntype: monitoring\npriority: 1\n"
            f"order: {order}\nschedule:\n  enabled: false\n"
        )


def tamper_audit_chain(project_root):
    """
    Corrupt the real audit file on disk, the way a real corruption looks.

    The chain is written through the real `record_event`, so the entry carries a
    real hash; rewriting one field is exactly what a tampered or partially
    rewritten log does, and it is what makes `verify_chain()` return False.
    """
    from theteam.core.audit_chain import audit_file

    path = str(audit_file(project_root))
    with open(path, "r", encoding="utf-8") as handle:
        lines = [line for line in handle if line.strip()]
    first = json.loads(lines[0])
    first["event"] = "tampered"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(first) + "\n" + "".join(lines[1:]))


@pytest.fixture
def empty_project():
    """Bootstrapped, no audit chain, no runs, no scheduled tasks."""
    with tempfile.TemporaryDirectory() as tmp:
        assert cli.main(["--project-root", tmp, "bootstrap"]) == 0
        yield tmp


@pytest.fixture
def two_tasks(empty_project):
    """Two registered tasks, neither of which has ever run."""
    os.mkdir(os.path.join(empty_project, "tasks"))
    write_task(empty_project, "alpha", 0)
    write_task(empty_project, "beta", 1)
    return empty_project


@pytest.fixture
def frozen_clock(monkeypatch):
    """Pin `terminal._frame`'s timestamp so a rendered frame is comparable.

    `_frame` stamps `time.strftime("%Y-%m-%d %H:%M:%S")` into the header row, so
    any test that renders a frame twice and compares them races the wall clock:
    cross a second boundary between the two calls and the header differs for a
    reason that has nothing to do with what is under test.

    Patched on the `time` module the renderer reads through
    (`theteam.ui.terminal.time`), not on a copy of the format string, so this
    still fails if the header stops being drawn at all.
    """
    from theteam.ui import terminal

    monkeypatch.setattr(terminal.time, "strftime",
                        lambda fmt, *a: "2026-10-01 00:00:00")
    return "2026-10-01 00:00:00"


@pytest.fixture
def tripped(two_tasks):
    """`alpha` tripped by real recorded runs; `beta` still unmeasured."""
    from theteam.tasks.repository import TaskRepository

    repo = TaskRepository(two_tasks)
    repo.record_run("alpha", "failed", "returncode 1",
                    breaker="open", consecutive_failures=5)
    return two_tasks


@pytest.fixture
def intact_chain(two_tasks):
    """A real audit chain that verifies, written through the real logger."""
    from theteam.core.audit_chain import record_event

    assert record_event(two_tasks, "monitor_probe", task="alpha")
    assert payload(two_tasks, "status")["audit_chain"]["intact"] is True
    return two_tasks


# ======= R3: an alert is a transition, not a level =======

class TestTransitions:
    """
    The three alert rules, each of which fires on a step and not on a level.

    Every payload here is read from a real project. A `None` that means "never
    measured" is the distinction the whole module turns on: a task that never ran
    and a task that was removed both put a `None` on one side of the diff, and
    only one of them is a thing a reader should act on.
    """

    def test_a_breaker_that_opens_is_named_in_the_status_view(self, two_tasks):
        """`breakers.<id>` arrives as a whole dict the frame it first appears."""
        before = payload(two_tasks, "status")
        from theteam.tasks.repository import TaskRepository

        TaskRepository(two_tasks).record_run("alpha", "failed", "returncode 1",
                                            breaker="open", consecutive_failures=5)
        after = payload(two_tasks, "status")

        assert "breaker opened: alpha" in alerts(diff(before, after))

    def test_a_breaker_that_opens_is_named_in_the_tasks_view(self, two_tasks):
        """
        The same trip in the `tasks` payload arrives as `tasks[<id>].breaker`.

        Two payload shapes, one rule. A monitor that matched only the `breakers`
        path would go silent in whichever view the reader happened to be
        watching when the breaker tripped.
        """
        before = payload(two_tasks, "tasks")
        from theteam.tasks.repository import TaskRepository

        TaskRepository(two_tasks).record_run("alpha", "failed", "returncode 1",
                                            breaker="open", consecutive_failures=5)
        after = payload(two_tasks, "tasks")

        assert "breaker opened: alpha" in alerts(diff(before, after))

    def test_a_breaker_that_is_already_open_does_not_re_alert(self, tripped):
        """
        The core of R3. `alpha` is open and stays open; only `beta` moves.

        Re-alerting the open breaker every frame is the failure that makes the
        whole surface useless: a line that is always on is a line nobody reads.
        """
        before = payload(tripped, "status")
        from theteam.tasks.repository import TaskRepository

        TaskRepository(tripped).record_run("beta", "failed", "returncode 1",
                                           breaker="closed", consecutive_failures=0)
        changed = diff(before, payload(tripped, "status"))

        assert changed, "the frame really did change"
        assert "breaker opened: alpha" not in alerts(changed)
        assert alerts(changed) == []

    def test_a_chain_that_stops_verifying_is_named(self, intact_chain):
        """`True -> False` on a chain that was measured and then stopped."""
        before = payload(intact_chain, "status")
        tamper_audit_chain(intact_chain)
        after = payload(intact_chain, "status")

        assert after["audit_chain"]["intact"] is False, "the tamper did not break it"
        assert alerts(diff(before, after)) == [
            "audit chain no longer intact (False)"]

    def test_a_chain_that_was_never_measured_did_not_break(self):
        """
        `None -> False` is not a break, and this is the case a rewrite gets wrong.

        `intact` is `None` when no audit file exists. A chain that was never
        measured cannot have stopped verifying, and reporting that it broke
        would be a claim about a check that never ran (§3.3).
        """
        changed = diff({"audit_chain": {"intact": None}},
                       {"audit_chain": {"intact": False}})

        assert changed, "the frame really did change"
        assert alerts(changed) == []

    def test_a_removed_task_is_named(self, two_tasks):
        """Deleting the task file drops the row, and the drop is reported."""
        before = payload(two_tasks, "tasks")
        os.remove(os.path.join(two_tasks, "tasks", "task-beta.yaml"))

        assert alerts(diff(before, payload(two_tasks, "tasks"))) == [
            "removed task: beta"]

    def test_an_unmeasured_breaker_is_a_measurement_not_a_removal(self, two_tasks):
        """
        A first run that recorded no breaker state adds `None` values.

        Nothing was removed: `beta` is still there, it simply has no measured
        breaker. This is the `now is None` side of the same shape that a real
        removal produces, so it is where a removal rule written too broadly
        ("anything that became None") shows itself.
        """
        before = payload(two_tasks, "status")
        from theteam.tasks.repository import TaskRepository

        TaskRepository(two_tasks).record_run("beta", "ok", "returncode 0")
        after = payload(two_tasks, "status")

        assert after["breakers"]["beta"]["state"] is None, "nothing measured a state"
        assert alerts(diff(before, after)) == []

    def test_a_task_added_is_not_a_removal(self, two_tasks):
        """The mirror of the removal rule: a row appearing is not a row leaving."""
        before = payload(two_tasks, "tasks")
        write_task(two_tasks, "gamma", 2)

        assert alerts(diff(before, payload(two_tasks, "tasks"))) == []

    def test_reordering_tasks_is_not_a_change(self, tripped):
        """
        The same rows in a different order, which is what keying by `id` buys.

        A reader watching `tasks` sees the roster reshuffle constantly as tasks
        sort and re-rank. Diffing the list positionally would report every
        reordering as a wall of changed fields, and bury the one transition
        worth naming.
        """
        before = payload(tripped, "tasks")
        reversed_rows = dict(before, tasks=list(reversed(before["tasks"])))

        assert [row["id"] for row in before["tasks"]] == ["alpha", "beta"]
        assert [row["id"] for row in reversed_rows["tasks"]] == ["beta", "alpha"]
        assert diff(before, reversed_rows) == []
        assert alerts(diff(before, reversed_rows)) == []

    def test_only_three_transitions_are_reported(self):
        """
        Every other field that moves is a value, not an event.

        `last_result`, `consecutive_failures`, and the row count all change on a
        real run. Reporting them would turn the change block into a diff dump,
        which is the job `theteam status --json` already does.
        """
        changed = diff({"tasks": [{"id": "alpha", "last_result": "ok",
                                   "consecutive_failures": 0}]},
                       {"tasks": [{"id": "alpha", "last_result": "failed",
                                   "consecutive_failures": 4}]})

        assert changed, "the frame really did change"
        assert alerts(changed) == []


# ======= R3: the first frame is a baseline, not evidence of stability =======

class TestBaselineAndSteadyState:
    """
    What the monitor claims before, and while, nothing has moved.

    A first frame has no previous frame, so it cannot have found a change. The
    difference that matters is what gets *said* about that: "0 changes" claims
    the system is stable, which nothing has checked yet.
    """

    def test_the_first_frame_reports_no_change_and_is_the_baseline(self, two_tasks):
        monitor_obj = Monitor("status")

        assert monitor_obj.observe(payload(two_tasks, "status")) == []
        assert monitor_obj.baseline() is True

    def test_a_baseline_is_not_a_steady_system(self, tripped):
        """
        After a change, the monitor is no longer reporting a baseline.

        `baseline()` staying true forever would be the bug: it would tell a
        reader that nothing has been compared on every frame of a run that is
        plainly changing.
        """
        monitor_obj = Monitor("status")
        monitor_obj.observe(payload(tripped, "status"))

        from theteam.tasks.repository import TaskRepository

        TaskRepository(tripped).record_run("beta", "failed", "returncode 1",
                                           breaker="open", consecutive_failures=1)
        monitor_obj.observe(payload(tripped, "status"))

        assert monitor_obj.baseline() is False

    def test_an_unchanged_frame_is_not_counted(self, two_tasks):
        """Same payload twice: no change, no event, counter untouched."""
        monitor_obj = Monitor("status")
        frame = payload(two_tasks, "status")

        assert monitor_obj.observe(frame) == []
        assert monitor_obj.observe(frame) == []
        assert monitor_obj.changes == 0
        assert list(monitor_obj.events) == []

    def test_a_change_counter_counts_frames_not_fields(self):
        """
        Five fields moved in one frame. That is one event, not five.

        A counter that tallied fields would read "5 changes" for a single run,
        and would grow by an amount the reader cannot act on.
        """
        monitor_obj = Monitor("tasks")
        monitor_obj.observe({"tasks": [{"id": "alpha", "breaker": None,
                                        "order": 0}]})
        moved = {"tasks": [{"id": "alpha", "breaker": "open", "order": 3,
                            "last_result": "failed",
                            "breaker_consecutive_failures": 4}]}

        changed = monitor_obj.observe(moved)

        assert len(changed) > 1, "several fields moved"
        assert monitor_obj.changes == 1

    def test_a_trip_is_recorded_once_and_stays_recorded(self, tripped):
        """The open breaker is named on the frame it opens and not afterwards."""
        from theteam.tasks.repository import TaskRepository

        before = payload(tripped, "status")
        monitor_obj = Monitor("status")
        monitor_obj.observe(before)

        TaskRepository(tripped).record_run("beta", "failed", "returncode 1",
                                           breaker="open", consecutive_failures=1)
        monitor_obj.observe(payload(tripped, "status"))
        monitor_obj.observe(payload(tripped, "status"))

        assert monitor_obj.changes == 1
        assert [line for _, line in monitor_obj.events] == [
            "breaker opened: beta"]

    def test_recent_lines_are_timestamped_and_newest_last(self, tripped):
        """The frame renders these verbatim, so each carries its stamp."""
        from theteam.tasks.repository import TaskRepository

        monitor_obj = Monitor("status")
        monitor_obj.observe(payload(tripped, "status"))
        TaskRepository(tripped).record_run("beta", "failed", "returncode 1",
                                           breaker="open", consecutive_failures=1)
        monitor_obj.observe(payload(tripped, "status"))

        recent = monitor_obj.recent()

        assert recent, "the trip left a line to render"
        for line in recent:
            assert re.match(r"^\d{2}:\d{2}:\d{2}  \S", line), line
        assert recent[-1].endswith("breaker opened: beta")


# ======= bounded: a watch loop is not a log store =======

class TestBoundedTimeline:
    """
    The event buffer is capped, because a watch loop runs all day.

    Two separate bounds: the buffer holds every event for the session, and the
    frame shows only the last few. A frame that grew without limit would push
    the table it reports on off the screen.
    """

    def test_the_buffer_drops_the_oldest_events_past_the_bound(self, two_tasks):
        from theteam.tasks.repository import TaskRepository

        repo = TaskRepository(two_tasks)
        # Flip both breakers every frame: exactly one goes closed -> open, so
        # each frame produces one event and the buffer is genuinely overrun
        # rather than merely filled.
        repo.record_run("alpha", "failed", "returncode 1",
                        breaker="closed", consecutive_failures=0)
        repo.record_run("beta", "failed", "returncode 1",
                        breaker="open", consecutive_failures=1)

        monitor_obj = Monitor("status")
        monitor_obj.observe(payload(two_tasks, "status"))
        for step in range(MAX_EVENTS + 20):
            alpha, beta = ("open", "closed") if step % 2 else ("closed", "open")
            repo.record_run("alpha", "failed", "returncode 1",
                            breaker=alpha, consecutive_failures=1)
            repo.record_run("beta", "failed", "returncode 1",
                            breaker=beta, consecutive_failures=1)
            monitor_obj.observe(payload(two_tasks, "status"))

        assert monitor_obj.changes == MAX_EVENTS + 20, "every frame really changed"
        assert len(monitor_obj.events) == 100

    def test_a_frame_shows_only_the_last_few_events(self, tripped):
        from theteam.tasks.repository import TaskRepository

        monitor_obj = Monitor("status")
        monitor_obj.observe(payload(tripped, "status"))
        for name in ("beta", "gamma", "delta", "epsilon", "zeta", "eta"):
            TaskRepository(tripped).record_run(name, "failed", "returncode 1",
                                               breaker="open",
                                               consecutive_failures=1)
            monitor_obj.observe(payload(tripped, "status"))

        assert len(monitor_obj.events) == 6, "six transitions happened"
        assert len(monitor_obj.recent()) == VISIBLE_EVENTS


# ======= R1: the monitor reads payloads, not files =======

class TestPurityAndBoundary:
    """
    `diff` is a function of two dicts, and the module reaches nothing else.

    The monitor's whole advantage over "re-run the command and read it again" is
    that it compares what `watch` already read. The moment it opens a file or
    resolves a state path it becomes a second data adapter - a second source
    that can disagree with the frame above it, which is how
    `task_stack_adapter.py` came to exist in M2.
    """

    def test_diff_is_a_function_of_its_two_arguments(self):
        """
        Same input, same output, twice - and the inputs are left alone.

        `diff` is called once per watch tick on a payload the renderer is also
        drawing, so mutating what it was handed would corrupt the frame.
        """
        before = {"breakers": {"alpha": {"state": None}},
                  "tasks": [{"id": "alpha", "order": 0}]}
        after = {"breakers": {"alpha": {"state": "open"}},
                 "tasks": [{"id": "alpha", "order": 0}]}
        before_copy, after_copy = json.loads(json.dumps(before)), json.loads(
            json.dumps(after))

        first = diff(before, after)
        second = diff(before, after)

        assert first == second
        assert before == before_copy and after == after_copy

    def test_a_frame_compared_with_itself_has_nothing_to_report(self, tripped):
        """The steady state, at the level of the pure function."""
        frame = payload(tripped, "status")

        assert diff(frame, frame) == []

    def test_the_module_imports_nothing_that_could_reach_a_file(self):
        """
        Parsed, not grepped: a docstring that names a module to say it does not
        use one is not a use of it.

        `time` stamps a line, `collections` bounds the buffer, `typing`
        annotates. Everything else - `os`, `pathlib`, `subprocess`, and any
        `theteam` module - would be the monitor reading state the payloads do
        not carry.
        """
        with open(monitor.__file__, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())

        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        assert imported == {"time", "collections", "typing"}


# ======= C2: the flag reaches the frame =======

class TestRendererIntegration:
    """
    `--monitor` through the real renderer, over payloads the system produced.

    The frame below the change block is the frame that was already there. A
    monitor that improved it by rewriting it would have broken the contract the
    three machine commands exist to serve.
    """

    def test_the_first_monitored_frame_says_nothing_was_compared(self, two_tasks):
        out = io.StringIO()

        assert watch(two_tasks, "status", once=True, stream=out, monitoring=True) == 0

        frame = out.getvalue()
        assert "baseline" in frame, (
            "the first frame has no previous frame; '0 changes' would claim a "
            "stability nobody has checked yet")
        assert "changes     0 since baseline" not in frame

    def test_an_unmonitored_watch_draws_no_change_block(self, two_tasks):
        out = io.StringIO()

        assert watch(two_tasks, "status", once=True, stream=out, monitoring=False) == 0

        assert "changes" not in out.getvalue()

    def test_the_flag_does_not_alter_the_frame_it_reports_on(self, two_tasks):
        """
        Byte-identity, not a spot check.

        The table above the change block has to be the frame `theteam watch
        status` drew before `--monitor` existed, or the flag has quietly
        rewritten the machine surface.
        """
        out = io.StringIO()
        watch(two_tasks, "status", once=True, stream=out, monitoring=False)

        assert out.getvalue() == render_status(payload(two_tasks, "status")) + "\n\n"

    def test_a_monitoring_watch_still_draws_the_whole_frame(self, two_tasks, frozen_clock):
        # The clock is frozen because `_frame` stamps the time the frame is
        # drawn, and this test renders twice: once via `watch`, once to build the
        # expected rows. Crossing a second boundary between those two calls made
        # the header line differ, and the test failed on a timestamp rather than
        # on anything about the monitoring flag. It passed 5 runs in 6 and failed
        # under concurrency, which is what a real race looks like.
        out = io.StringIO()
        watch(two_tasks, "status", once=True, stream=out, monitoring=True)

        frame = out.getvalue()
        for line in render_status(payload(two_tasks, "status")).splitlines():
            assert line in frame, f"the flag dropped a row: {line!r}"


# ======= C2: the flag is a flag, not a command =======

class TestCliIntegration:
    """`theteam watch status --once --monitor`, end to end through `main`."""

    def test_the_monitor_flag_exits_zero_and_draws_a_change_block(self, tripped):
        code, out = run_cli(["--project-root", tripped, "watch", "status",
                             "--once", "--monitor"])

        assert code == 0
        assert "baseline" in out

    def test_the_watch_without_the_flag_still_exits_zero(self, tripped):
        code, out = run_cli(["--project-root", tripped, "watch", "status", "--once"])

        assert code == 0
        assert "changes" not in out

    def test_every_view_accepts_the_flag(self, tripped):
        """One flag on one command, not a `--monitor` per view."""
        for view in ("status", "tasks", "history"):
            code, out = run_cli(["--project-root", tripped, "watch", view,
                                 "--once", "--monitor"])
            assert code == 0, view
            assert "baseline" in out, view
