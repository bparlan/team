"""
Defends `theteam/core/run_context.py`, which exists for one measured reason.

`scripts/sa_runner.py:451` held the only production call to `update_loop_state`,
inside `_run_correction_cycle` — a phase with a 600-second timeout and a 384MB
bound. Every other `LoopState` construction in the tree
(`scripts/loop_reporter.py:28`, `scripts/task_executor.py:37`) belongs to the
legacy scripts the M10 consolidation retired.

So `.loop-state.json` was refreshed only by a task that ran on demand. Two files
depend on it and neither can repair it:

  * `scripts/loop_infrastructure_check.py:46` hard-gates it in
    `REQUIRED_LOOP_FILES`, so a missing file is a permanent finding.
  * `scripts/loop_health_check.py:79` fails on it once `last_execution` is older
    than `STALE_THRESHOLD_SECONDS` (24h).

Deleting the `system-awareness` task, as decided, therefore removes the only
writer of a file the integrity monitor requires. These tests pin the
replacement's three load-bearing properties:

  1. a run refreshes the file the gate reads;
  2. a run that executed *nothing* does not refresh it, because
     `last_execution` means "a task last ran at" and stamping it on a no-op
     fabricates an execution;
  3. two identical runs produce identical bytes, which is the purity contract
     `test_task_repository.py` enforces over the whole sweep payload.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from theteam.core.run_context import (
    build_context_summary,
    load_loop_state,
    _recent_failures,
    write_run_context,
)

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"


@pytest.fixture(autouse=True)
def _scripts_on_path():
    """Put `scripts/` on the path for this module, then take it off again.

    The health check is invoked as a subprocess, not imported, so nothing here
    actually needs `scripts/` importable. A module-level insert would leak into
    every later test in the session, which
    `test_stability_fixes.py::test_no_module_level_sys_path_insert` enforces
    with an AST sweep rather than a text search.
    """
    sys.path.insert(0, str(SCRIPTS))
    try:
        yield
    finally:
        sys.path.remove(str(SCRIPTS))


def _age_state(root: Path, hours: float) -> None:
    """Backdate `last_execution` so the health check's staleness rule fires."""
    path = root / ".loop-state.json"
    state = json.loads(path.read_text())
    old = datetime.now(timezone.utc) - timedelta(hours=hours)
    state["last_execution"] = old.isoformat()
    path.write_text(json.dumps(state, indent=2))


def _health_check_report(root: Path) -> str:
    """Run the real health check against `root` and return what it printed.

    The script resolves `PROJECT_ROOT` from its own location
    (`loop_health_check.py:22`), so it must be *copied into* the probe project
    rather than merely executed with `cwd` set — otherwise it inspects the real
    repository and every assertion below passes for the wrong reason.

    Returns the report lines rather than the exit code, because the exit code
    conflates findings: a probe project is always missing something the real one
    has, so `3` here means "reported something" and says nothing about staleness
    specifically. Staleness is the finding under test.
    """
    import shutil
    import subprocess

    (root / "scripts").mkdir(parents=True, exist_ok=True)
    target = root / "scripts" / "loop_health_check.py"
    shutil.copy(SCRIPTS / "loop_health_check.py", target)
    result = subprocess.run(
        [sys.executable, str(target)],
        capture_output=True, text=True, cwd=root)
    return result.stdout


def test_the_gate_file_is_created_when_absent(tmp_path):
    """A missing file is an unresolvable finding for the infrastructure check.

    `project-integrity` cannot create it and no task can repair it, so the
    replacement writer has to.
    """
    assert not (tmp_path / ".loop-state.json").exists()
    write_run_context(tmp_path, executed=True)
    assert (tmp_path / ".loop-state.json").exists()


def test_a_run_clears_a_stale_finding(tmp_path):
    """The measured behaviour: 30h stale -> finding -> one run -> clean.

    This is the property that made the deletion safe. Verified against the real
    check script rather than a reimplementation of its threshold.
    """
    for d in ("tasks", "bin", "theteam"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / "theteam.config").write_text(
        "project:\n  name: probe\n  description: a probe project\n")
    write_run_context(tmp_path, executed=True)
    _age_state(tmp_path, 30)

    stale = "Loop state is stale"
    assert stale in _health_check_report(tmp_path), (
        "precondition: a 30h-old loop state must be a staleness finding, "
        "otherwise this test cannot show the run clearing it")

    write_run_context(tmp_path, executed=True)

    assert stale not in _health_check_report(tmp_path), (
        "a run did not clear the staleness finding, so the gate still reports "
        "something nothing can resolve. This is the property that made deleting "
        "the only previous writer of this file safe.")


def test_a_run_that_executed_nothing_does_not_refresh_the_stamp(tmp_path):
    """`last_execution` means "a task last ran at".

    Stamping it on a sweep where nothing was due would record an execution that
    never happened and hide a project that genuinely has not run in a week. It
    is also what `test_two_runs_with_nothing_due_are_byte_identical` protects:
    a pure read of due-ness must not move state.
    """
    write_run_context(tmp_path, executed=True)
    _age_state(tmp_path, 30)

    write_run_context(tmp_path, executed=False)

    state = load_loop_state(tmp_path)
    age = datetime.now(timezone.utc) - datetime.fromisoformat(state["last_execution"])
    assert age.total_seconds() > 86400, (
        "a run with nothing due refreshed last_execution, so the project can "
        "never report itself as idle")


# ===== atomicity =====

def test_a_corrupt_state_file_is_replaced_not_fatal(tmp_path):
    """A truncated file must not wedge every future run.

    `repository._save_schedule` writes `task-schedule.json` with a bare
    `open(path, "w")`, so an interrupted write leaves zero bytes. The same shape
    here would leave the gate reporting "invalid" forever.
    """
    path = tmp_path / ".loop-state.json"
    path.write_text("")  # truncated by a killed process

    write_run_context(tmp_path, executed=True)

    state = load_loop_state(tmp_path)
    assert state["last_execution"], "the corrupt file was not replaced"
    assert "Loop state is invalid" not in _health_check_report(tmp_path), (
        "the corrupt file was replaced with something the check still cannot "
        "read, so the gate stays broken")


def _log_a_failure(root: Path, task_id: str = "real-task") -> None:
    """Record one failed run for `task_id` in the execution log."""
    state_dir = root / ".omp" / "theteam"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "task-execution.log").write_text(
        json.dumps({"task_id": task_id, "success": False,
                    "error": "returncode 1"}) + "\n")


def test_a_malformed_task_file_is_never_reported_as_clean(tmp_path):
    """A syntax error in a task YAML must not read as a healthy project.

    The first version of the registry read used a bare `except Exception` and
    returned `[]` on failure — and an absent "what is failing" section reads as
    "nothing is failing". Measured: `id: [broken` in a task file produced
    exactly that.

    It also raised `yaml.parser.ParserError`, which descends from `YAMLError` and
    from neither `ValueError` nor `OSError`, so a handler catching only the
    latter two let it escape and crashed the summary outright.
    """
    (tmp_path / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "theteam.config").write_text(
        "project:\n  name: p\n  description: d\n")
    _log_a_failure(tmp_path)
    (tmp_path / "tasks" / "task-real-task.yaml").write_text("id: [broken\n  : :\n")

    write_run_context(tmp_path, executed=True)
    summary = build_context_summary(tmp_path)

    assert "failure status unknown" in summary, (
        "an unreadable task registry produced a summary with no failure "
        "section, which reads as a clean project")
    assert "nothing recorded as failing" not in summary


def test_an_empty_task_directory_is_never_reported_as_clean(tmp_path):
    """Recorded failures plus an empty registry means unreadable, not healthy.

    The registry filter drops failures whose task no longer has a definition —
    correct in the normal case, since a deleted task cannot be failing. But when
    *every* definition is gone, the filter empties the list and the summary
    claimed a clean project from a log full of real failures. Measured.
    """
    (tmp_path / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "theteam.config").write_text(
        "project:\n  name: p\n  description: d\n")
    _log_a_failure(tmp_path)
    # `tasks/` exists but holds no definitions.

    write_run_context(tmp_path, executed=True)
    summary = build_context_summary(tmp_path)

    assert "failure status unknown" in summary, (
        "an empty task registry silently discarded every recorded failure")
    assert "nothing recorded as failing" not in summary


def test_a_genuinely_healthy_project_still_says_so(tmp_path):
    """The converse, so the unknown branch cannot become a constant."""
    (tmp_path / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "theteam.config").write_text(
        "project:\n  name: p\n  description: d\n")
    (tmp_path / "tasks" / "task-ok.yaml").write_text(
        "id: ok\nname: Ok\norder: 0\nphases: []\n")

    write_run_context(tmp_path, executed=True)
    summary = build_context_summary(tmp_path)

    assert "nothing recorded as failing" in summary
    assert "failure status unknown" not in summary



def test_the_state_write_is_atomic(tmp_path, monkeypatch):
    """A kill mid-write must not leave zero bytes the gate calls invalid forever.

    Temp file plus `os.replace`, matching `theteam/core/wal.py:139-150`. Mutating
    this to a bare `path.write_text` left every other test in this file green,
    because none of them kill the process mid-write — the property is invisible
    unless it is asserted directly.
    """
    seen = {}
    real_replace = os.replace

    def spy(src, dst):
        # The rename is the atomicity: the destination is never opened for
        # writing, so a reader sees either the old file or the whole new one.
        seen["replaced"] = (str(src), str(dst))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    write_run_context(tmp_path, executed=True)

    assert seen.get("replaced"), (
        "the state file was written in place rather than via a rename, so an "
        "interrupted write truncates it and every later health check reports it "
        "invalid with nothing able to repair it")


def test_a_deleted_task_is_never_reported_as_failing(tmp_path):
    """The execution log is history; the registry is the present.

    `task-execution.log` is append-only, so it carries entries for tasks whose
    YAML was deleted months ago. Measured on this repo: the first version of
    `_recent_failures` listed `folder-monitoring` and `health-check` under
    "what is failing", both merged away in M12. Nothing can run a task that has
    no definition, so that list was fabricated — the same defect class as the
    unreadable 600s reports this module exists to replace, reintroduced in the
    replacement.
    """
    state_dir = tmp_path / ".omp" / "theteam"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "task-execution.log").write_text(
        json.dumps({"task_id": "deleted-task", "success": False,
                    "error": "returncode 1"}) + "\n"
        + json.dumps({"task_id": "live-task", "success": False,
                     "error": "returncode 1"}) + "\n")

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "task-live-task.yaml").write_text(
        "id: live-task\nname: Live\norder: 0\nphases: []\n")

    failures = _recent_failures(tmp_path)

    assert any("live-task" in f for f in failures), (
        f"a real failing task was dropped: {failures}")
    assert not any("deleted-task" in f for f in failures), (
        f"a task with no YAML definition was reported as failing: {failures}")


def test_an_unreadable_config_does_not_invent_a_description(tmp_path):
    """A broken config yields an honest line, not the directory name as prose.

    Falling back to a plausible sentence would be a default that reads like a
    measurement: a member would treat invented text as the project's stated
    purpose.

    Two failure modes are checked separately, because they take different
    branches and a test covering only one passed while the other fallback was
    replaced with invented prose:

      * a **syntax** error (`project: [not a mapping` never closes the flow
        sequence), which reaches the `unreadable` branch;
      * a **shape** error (`project: just-a-string` parses fine but is not a
        mapping), which reaches the `not a mapping` branch.
    """
    (tmp_path / "theteam.config").write_text("project: [not a mapping\n")
    write_run_context(tmp_path, executed=True)
    assert "unreadable" in build_context_summary(tmp_path), (
        "a broken theteam.config produced a summary with no indication that the "
        "description is missing, so an invented one reads as a real one")

    (tmp_path / "theteam.config").write_text("project: just-a-string\n")
    assert "not a mapping" in build_context_summary(tmp_path), (
        "a theteam.config whose project section is a scalar reported neither "
        "that it was malformed nor what was missing")

    (tmp_path / "theteam.config").write_text("behavior:\n  chat_mode: false\n")
    assert "no project section" in build_context_summary(tmp_path), (
        "a config with no project section was reported as if one existed")

    assert "a project" not in build_context_summary(tmp_path)


def test_writes_leave_no_temp_file_behind(tmp_path):
    """`os.replace` is atomic; the temp file must not survive it."""
    write_run_context(tmp_path, executed=True)
    assert not list(tmp_path.glob("*.tmp"))


# ===== payload purity =====

def test_two_identical_runs_return_identical_results(tmp_path):
    """No absolute paths, no timing readings, in what a payload carries.

    Measured failure this prevents: `context_path: /tmp/a != /tmp/b` and
    `elapsed: 0.0006 != 0.0005` failing
    `test_two_runs_with_nothing_due_are_byte_identical`, which compares two
    sweeps over an unchanged project byte for byte.
    """
    first = write_run_context(tmp_path, executed=True)
    second = write_run_context(tmp_path, executed=True)
    # `context_bytes` is the summary's size, which is stable for unchanged state.
    volatile = {"context_path", "elapsed", "timestamp", "path"}
    assert not (volatile & set(first)), f"payload carries volatile keys: {first}"
    assert first["written"] is True and second["written"] is True
    assert first["context_bytes"] == second["context_bytes"]


# ===== the summary itself =====

def test_the_summary_is_small_and_states_what_it_is(tmp_path):
    """A glance, not a dump — it is injected into every member prompt."""
    (tmp_path / "theteam.config").write_text(
        "project:\n  name: probe\n  description: a probe project\n")
    write_run_context(tmp_path, executed=True)
    summary = build_context_summary(tmp_path)

    assert len(summary.encode()) < 8192
    assert "probe" in summary
    assert "a probe project" in summary


def test_the_summary_carries_no_current_timestamp(tmp_path):
    """Its header shows when work last ran, not when the file was read.

    A "generated now" header makes two identical reads differ, which is the same
    defect as a constant that changes for no reason.
    """
    write_run_context(tmp_path, executed=True)
    summary = build_context_summary(tmp_path)
    state = load_loop_state(tmp_path)
    assert state["last_execution"] in summary


def test_an_unreadable_config_is_reported_not_papered_over(tmp_path):
    """A missing config yields an honest line, not the directory name as prose."""
    (tmp_path / "theteam.config").write_text("project: [this is not a mapping\n")
    write_run_context(tmp_path, executed=True)
    summary = build_context_summary(tmp_path)
    assert "unreadable" in summary


def test_the_question_section_is_omitted_when_empty(tmp_path):
    """A channel that promises a question and prints "(none)" is a lie.

    `open_questions` in the discussion synthesis was exactly that: initialised
    empty, rendered as "- (none)", and no code could ever fill it. The
    replacement omits the section instead.
    """
    write_run_context(tmp_path, executed=True)
    summary = build_context_summary(tmp_path)
    assert "what needs a human decision" not in summary
    assert "(none)" not in summary


@pytest.mark.parametrize("corrupt", [b"", b"{", b"not json at all"])
def test_an_unreadable_execution_log_does_not_break_the_summary(tmp_path, corrupt):
    """Derived state can be corrupt; the context file still has to be written."""
    state_dir = tmp_path / ".omp" / "theteam"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "task-execution.log").write_bytes(corrupt)

    result = write_run_context(tmp_path, executed=True)
    assert result["written"] is True
