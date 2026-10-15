"""
The task listing and task run contract.

`theteam tasks` and `theteam run` are the only two surfaces a user touches
for scheduled work, and both are read paths over two sources: canonical YAML
under `routines/`, and the pre-M2 JSON registry that is still served. The
observable promises pinned here are the ones a regression would silently break
while still returning a plausible payload:

  * membership and order come from the `routines/` YAML itself, so the listing
    does not drift when a file gains an entry;
  * an id that lost its YAML file is still listed and flagged, never dropped -
    a task quietly disappearing is indistinguishable from "this project has no
    tasks" and means the opposite;
  * `run` executes what is due and nothing else, so `ran` counts work that
    actually happened and two runs with nothing due are byte-identical.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from theteam.cli import main
from theteam.core.agent_isolation import AgentIsolation
from theteam.routines.repository import (
    TaskDefinitionError,
    RoutineRepository,
)


# ======= scratch project =======


def _project(root, order=(), tasks=None, schedule=None, registry=None, extra=()):
    """
    Build an isolated project: `tasks/task-*.yaml` and the state files under
    `<root>/.omp/theteam/`. Nothing is read from the real repo.

    Ordering comes from each task's own `order:` key. It used to come from
    `tasks/TASK_ORDER`, which no longer exists — `RoutineRepository` dropped it
    when ordering moved onto the tasks themselves, so nothing writes that file
    and this docstring described a layout the repository stopped reading.
    """
    routines_dir = root / "tasks"
    routines_dir.mkdir(parents=True, exist_ok=True)
    tasks = tasks or {}
    rank = {t: i for i, t in enumerate(order)}
    for task_id, fields in tasks.items():
        payload = {"id": task_id, "order": rank.get(task_id, len(rank))}
        payload.update(fields)
        (routines_dir / f"task-{task_id}.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
        )
    for name, text in extra or ():
        (routines_dir / name).write_text(text, encoding="utf-8")

    state = root / ".omp" / "theteam"
    if schedule is not None:
        state.mkdir(parents=True, exist_ok=True)
        (state / "task-schedule.json").write_text(
            json.dumps(schedule, indent=2), encoding="utf-8"
        )
    if registry is not None:
        state.mkdir(parents=True, exist_ok=True)
        (state / "task-registry.json").write_text(
            json.dumps({"tasks": registry}, indent=2), encoding="utf-8"
        )
    return root


def _past(minutes=5):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _future(minutes=30):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _cli(root, *argv, capsys):
    """Drive the CLI and hand back (exit code, parsed JSON payload)."""
    code = main(["--project-root", str(root), *argv, "--json"])
    out = capsys.readouterr().out
    return code, json.loads(out)


# ======= 1. order is the per-task `order:` key =======


def test_tasks_are_listed_in_task_order_sequence(tmp_path):
    """
    The listing order is the `order:` key each task carries - not alphabetical
    and not by priority. Order of execution is the operator's decision, written
    down once on the task; a reader that re-sorts it produces a different run
    order than the one the files document.
    """
    root = _project(
        tmp_path,
        order=["zebra", "middle", "alpha"],
        tasks={
            "alpha": {"name": "A", "priority": 9},
            "middle": {"name": "M", "priority": 1},
            "zebra": {"name": "Z", "priority": 5},
        },
    )
    payload = RoutineRepository(str(root)).list_routines()

    assert [t["id"] for t in payload["tasks"]] == ["zebra", "middle", "alpha"]
    # The listed order is also the recorded position, so `order` agrees with it.
    assert [t["order"] for t in payload["tasks"]] == [0, 1, 2]


# ======= 2. a migrated prompt survives the move to YAML =======


def test_a_migrated_prompt_round_trips_exactly(tmp_path):
    """
    The body a migrated task carried in markdown reads back byte-for-byte out of
    its YAML file. Migration rewrote these documents; if the round trip alters
    one, the task silently runs with different instructions and nothing in the
    listing changes shape to reveal it.
    """
    prompt = (
        "# Nightly Review\n\n"
        "Read `docs/ARCHITECTURE.md` and report:\n\n"
        "1. drift between doc and code\n"
        "2. any file listed but missing\n\n"
        "> Keep it under 200 words. Special chars: `&`, *, #, :, - dash, \\\n"
        "    indented, and a trailing space \n"
    )
    root = _project(tmp_path, order=["review"], tasks={"review": {"prompt": prompt}})

    stored = RoutineRepository(str(root)).get("review")

    assert stored["prompt"] == prompt


# ======= 3-4. a run with nothing due does nothing =======


def test_run_with_nothing_due_reports_no_work_and_writes_no_state(tmp_path, capsys):
    """
    A run with nothing due returns `ran=0, skipped=0, results=[]` and leaves the
    schedule file byte-identical. It is a read of due-ness, not a run: a
    `run` that rewrote the schedule would consume a future task's slot and
    report work it never did.
    """
    root = _project(
        tmp_path,
        order=["later"],
        tasks={"later": {"phases": []}},
        schedule={
            "scheduled_tasks": {"later": {"next_run": _future(), "interval_minutes": 60}},
            "last_run": {},
        },
    )
    schedule_path = root / ".omp" / "theteam" / "task-schedule.json"
    before = schedule_path.read_bytes()

    code, payload = _cli(root, "run", capsys=capsys)

    assert code == 0
    assert (payload["ran"], payload["skipped"], payload["failures"]) == (0, 0, 0)
    assert payload["results"] == []
    assert schedule_path.read_bytes() == before


def test_run_with_nothing_due_writes_no_schedule_when_none_exists(tmp_path, capsys):
    """
    With no schedule file at all, a run with nothing due does not create one.
    Writing a schedule for a project that has never scheduled anything turns an
    absent state into an apparent one.
    """
    root = _project(tmp_path, order=["later"], tasks={"later": {"phases": []}})

    code, payload = _cli(root, "run", capsys=capsys)

    assert code == 0
    assert payload["ran"] == 0
    assert not (root / ".omp" / "theteam" / "task-schedule.json").exists()


def test_two_runs_with_nothing_due_are_byte_identical(tmp_path, capsys):
    """
    Two consecutive runs with nothing due emit the same bytes. Any drift
    between them means the first one moved state, which is what makes a
    scheduler re-run work the operator already saw as finished.
    """
    root = _project(
        tmp_path,
        order=["later"],
        tasks={"later": {"phases": []}},
        schedule={
            "scheduled_tasks": {"later": {"next_run": _future(), "interval_minutes": 60}},
            "last_run": {},
        },
    )

    main(["--project-root", str(root), "run", "--json"])
    first = capsys.readouterr().out
    main(["--project-root", str(root), "run", "--json"])
    second = capsys.readouterr().out

    assert first == second


def test_run_with_nothing_due_says_nothing_due_in_human_output(tmp_path, capsys):
    """
    The human output for a no-op run is the word "nothing due". An empty table
    or a `0 ran` summary is a reading a user has to interpret; the command
    already knows the answer.
    """
    root = _project(tmp_path, order=["later"], tasks={"later": {"phases": []}})

    assert main(["--project-root", str(root), "run"]) == 0
    assert "nothing due" in capsys.readouterr().out


# ======= 5. a due task runs =======


@pytest.mark.skipif(
    not AgentIsolation.available(), reason="no Docker daemon"
)
def test_run_executes_a_due_task_and_advances_its_schedule(tmp_path, capsys):
    """
    A due task whose phase script is a real Python file that exits 0 is
    executed and reported `ok`, and its `next_run` moves forward by its
    interval. Three observable effects: the script really ran (side-effect
    file in the project root), `ran=1`, and the task is no longer due.

    The phase declares `memory_limit_mb` because §5.4 makes the bound
    mandatory and §5.1 requires the run to be Layer 4 guarded, so execution
    happens in a container. This test previously declared an unbounded phase
    and asserted a host-side side-effect file; that was the last artifact in
    the tree assuming a phase could run with no bound, and the refusal is
    covered on its own terms by the isolation tests. The intent is unchanged:
    the script really executed.
    """
    root = _project(
        tmp_path,
        order=["probe"],
        tasks={
            "probe": {
                "phases": [{
                    "name": "probe",
                    "script": "phases/probe.py",
                    "memory_limit_mb": 64,
                    "writable_project": True,
                }]
            }
        },
        schedule={
            "scheduled_tasks": {
                "probe": {"next_run": _past(), "interval_minutes": 60}
            },
            "last_run": {},
        },
    )
    script = root / "phases" / "probe.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "import pathlib\n"
        "pathlib.Path('/workspace/probe-ran.txt').write_text('ran')\n",
        encoding="utf-8",
    )
    before = datetime.now(timezone.utc)

    code, payload = _cli(root, "run", capsys=capsys)

    assert code == 0
    assert payload["ran"] == 1
    assert payload["failures"] == 0
    assert [(r["id"], r["result"]) for r in payload["results"]] == [("probe", "ok")]
    # The script really executed, in the container, and its write landed on
    # the host through the writable mount.
    assert (root / "probe-ran.txt").read_text(encoding="utf-8") == "ran"

    schedule = json.loads(
        (root / ".omp" / "theteam" / "task-schedule.json").read_text(encoding="utf-8")
    )
    next_run = datetime.fromisoformat(schedule["scheduled_tasks"]["probe"]["next_run"])
    assert schedule["last_run"]["probe"]["result"] == "ok"
    assert timedelta(minutes=50) <= next_run - before <= timedelta(minutes=61)
    # Advanced, so the same task is not immediately due again.
    assert RoutineRepository(str(root)).due() == []


# ======= 6. a due task whose script is gone is skipped, not run =======


def test_run_skips_a_due_task_whose_script_is_missing(tmp_path, capsys):
    """
    A due task whose phase script does not exist is reported `skipped` and is
    not counted in `ran`. It was due but never executed, so counting it as ran
    reports work that did not happen; dropping it silently reports nothing at
    all about a task the operator scheduled.
    """
    root = _project(
        tmp_path,
        order=["gone"],
        tasks={"gone": {"phases": [{"name": "gone", "script": "phases/gone.py"}]}},
        schedule={
            "scheduled_tasks": {"gone": {"next_run": _past(), "interval_minutes": 60}},
            "last_run": {},
        },
    )

    code, payload = _cli(root, "run", capsys=capsys)

    assert code == 0
    assert payload["ran"] == 0
    assert payload["skipped"] == 1
    assert payload["failures"] == 0
    assert payload["results"][0]["id"] == "gone"
    assert payload["results"][0]["result"] == "skipped"
    assert "phases/gone.py" in payload["results"][0]["detail"]

    schedule = json.loads(
        (root / ".omp" / "theteam" / "task-schedule.json").read_text(encoding="utf-8")
    )
    assert schedule["last_run"]["gone"]["result"] == "skipped"


# ======= 7. YAML is the only source =======


def test_the_registry_is_no_longer_a_source_of_tasks(tmp_path):
    """
    The dual-read path is closed. An id in the registry whose YAML file is
    gone is not served from the legacy registry: a second store is how a
    deleted task keeps running from a file nobody edits.
    """
    root = _project(
        tmp_path,
        order=["alpha"],
        tasks={"alpha": {"name": "A"}},
        registry={"ghost": {"id": "ghost", "name": "From the registry", "priority": 2}},
    )

    repo = RoutineRepository(str(root))
    payload = repo.list_routines()

    assert [t["id"] for t in payload["tasks"]] == ["alpha"]
    assert payload["count"] == 1
    assert payload["yaml_count"] == 1
    assert repo.get("ghost") is None
    assert "legacy_only" not in payload
def test_legacy_only_entry_is_surfaced_by_the_tasks_command(tmp_path, capsys):
    """
    `theteam tasks` does not list a task that exists only in the legacy
    registry. After the fold, order is a property of the YAML file, so an id
    with no YAML file is not representable as a task.
    """
    root = _project(
        tmp_path,
        order=["alpha"],
        tasks={"alpha": {"name": "Alpha"}},
        registry={"ghost": {"id": "ghost", "name": "From the registry"}},
    )

    code = main(["--project-root", str(root), "tasks"])
    out = capsys.readouterr().out

    assert code == 0
    assert "alpha" in out
    assert "ghost" not in out
def test_a_task_with_no_yaml_file_does_not_exist(tmp_path):
    """
    Under the fold, order is a property of the YAML file itself. An id
    without a YAML file is not representable as a task.
    """
    root = _project(
        tmp_path,
        order=["alpha"],
        tasks={"alpha": {"name": "A"}},
    )

    payload = RoutineRepository(str(root)).list_routines()

    assert [t["id"] for t in payload["tasks"]] == ["alpha"]
    assert payload["count"] == 1


# ======= 9. non-task files in tasks/ are not tasks =======


def test_a_non_task_yaml_in_the_tasks_dir_is_ignored(tmp_path):
    """
    `routines/SECURITY_POLICY.yaml` is not a task and is not even parseable YAML.
    Reading every `*.yaml` in the directory dies on it and takes the whole
    listing down; the `task-` prefix keeps unrelated files out of the read.
    """
    root = _project(
        tmp_path,
        order=["alpha"],
        tasks={"alpha": {"name": "A"}},
        extra=[
            (
                "SECURITY_POLICY.yaml",
                "## Security Policy\n\nno prompt here: [unclosed\n\t- not: yaml\n",
            )
        ],
    )

    payload = RoutineRepository(str(root)).list_routines()

    assert [t["id"] for t in payload["tasks"]] == ["alpha"]
    assert payload["yaml_count"] == 1


# ======= 10. a malformed task file fails loudly =======


@pytest.mark.parametrize(
    "content,reason",
    [
        ("- just\n- a\n- list\n", "a YAML list is not a task definition"),
        ("name: No Identity\n", "a task definition must name an id"),
    ],
)
def test_a_malformed_task_file_raises_a_named_error(tmp_path, content, reason):
    """
    A file named `task-*.yaml` that is not a readable task raises
    `TaskDefinitionError` naming the problem. Skipping it would make a
    conversion bug look like a project with fewer tasks.
    """
    root = _project(tmp_path)
    (root / "tasks" / "task-broken.yaml").write_text(content, encoding="utf-8")

    with pytest.raises(TaskDefinitionError) as caught:
        RoutineRepository(str(root)).list_routines()

    assert "task-broken.yaml" in str(caught.value), reason


def test_a_malformed_task_file_fails_the_command_with_a_reason(tmp_path, capsys):
    """
    `theteam tasks` on a project with a malformed task file exits non-zero and
    says what is wrong. The user sees a named failure, not an empty listing
    that reads like a project with no tasks.
    """
    root = _project(tmp_path, order=["ok"], tasks={"ok": {"name": "A"}})
    (root / "tasks" / "task-broken.yaml").write_text("- a list\n", encoding="utf-8")

    code = main(["--project-root", str(root), "tasks"])

    assert code == 1
    err = capsys.readouterr().err
    assert "task-broken.yaml" in err
    assert "Traceback" not in err


# ======= 11. the write path: create, edit, delete =======
#
# Everything above reads. These four are the write path, and each one pins a
# defect that shipped because nothing here exercised it. A write that is not
# read back is the one §3.3 is about: a plausible-looking result with nothing
# behind it.


def test_delete_does_not_remove_a_task_whose_id_contains_the_deleted_id(tmp_path):
    """
    Deleting `check` must not delete the `health-check` line. Matching the id
    with a bare substring test took out every line mentioning the id, so the
    file was emptied while the surviving task's own YAML file was untouched -
    a task that still exists and can no longer be ordered.
    """
    root = _project(
        tmp_path,
        order=["check", "health-check"],
        tasks={"check": {"name": "C"}, "health-check": {"name": "H"}},
    )

    RoutineRepository(str(root)).delete("check")

    assert [t["id"] for t in RoutineRepository(str(root)).all_tasks()] == ["health-check"]
    # The unrelated task is intact: still on disk, still listed, still first.
    assert (root / "tasks" / "task-health-check.yaml").exists()
    payload = RoutineRepository(str(root)).list_routines()
    assert [t["id"] for t in payload["tasks"]] == ["health-check"]
    assert [t["order"] for t in payload["tasks"]] == [0]

def test_update_writes_no_content_that_fails_validation_on_reload(tmp_path):
    """
    A patch that would not survive a read is refused at the write. Validating
    the file on disk before the patch is applied meant the write was never
    checked, so the invalid content landed and the *next*
    `RoutineRepository()` construction raised - a task edit made the whole
    project unreadable.
    """
    root = _project(tmp_path, order=["t1"], tasks={"t1": {"name": "T"}})

    with pytest.raises(TaskDefinitionError):
        RoutineRepository(str(root)).update(
            "t1", {"phases": [{"name": "run", "script": ".mp/theteam/loop.py"}]}
        )

    # Nothing landed, and the task is still readable.
    assert RoutineRepository(str(root)).get("t1")["name"] == "T"
    assert ".mp/theteam" not in (root / "tasks" / "task-t1.yaml").read_text()


def test_update_renames_the_file_and_carries_the_schedule_entry(tmp_path):
    """
    A rename moves the file, the order entry, the schedule entry and the run
    history. The schedule was the reason the case was refused: a renamed task
    whose schedule stayed on the old id stops being due, and one that
    orphaned it fires forever at a missing task.
    """
    root = _project(
        tmp_path,
        order=["old", "keeper"],
        tasks={"old": {"name": "O"}, "keeper": {"name": "K"}},
        schedule={
            "scheduled_tasks": {"old": {"next_run": _past(5), "interval_minutes": 60}},
            "last_run": {"old": {"result": "ok", "detail": "", "at": "2026-01-01T00:00:00+00:00"}},
        },
    )

    RoutineRepository(str(root)).update("old", {"id": "new"})

    # The file moved with the id.
    assert not (root / "tasks" / "task-old.yaml").exists()
    assert (root / "tasks" / "task-new.yaml").exists()
    # The order follows, by parsed id, and the unrelated task is untouched.
    assert [t["id"] for t in RoutineRepository(str(root)).all_tasks()] == ["new", "keeper"]
    # A rename must not orphan a schedule.
    fresh = RoutineRepository(str(root))
    assert list(fresh.schedule()["scheduled_tasks"]) == ["new"]
    assert list(fresh.schedule()["last_run"]) == ["new"]
    assert [t["id"] for t in fresh.due()] == ["new"]




def test_create_appends_to_the_end_of_the_declared_order(tmp_path):
    """
    `create` appends to the end of the declared order, writing `order:` into the
    new task's YAML. Numbering from the line count rather than the task count,
    and joining onto a trailing newline, produced a blank line and a number
    that skipped ahead - the order is the file, and an order that no longer
    parses stops ordering anything.
    """
    root = _project(tmp_path, order=["alpha", "beta"], tasks={"alpha": {}, "beta": {}})

    repo = RoutineRepository(str(root))
    repo.create({"id": "probe"})
    RoutineRepository(str(root)).create({"id": "probe2"})

    assert [t["id"] for t in RoutineRepository(str(root)).all_tasks()] == ["alpha", "beta", "probe", "probe2"]
    # The order key is written with the file, so a fresh repository reads it
    # back - and it is one past the current maximum, never a line count.
    assert yaml.safe_load((root / "tasks" / "task-probe.yaml").read_text())["order"] == 2
    assert yaml.safe_load((root / "tasks" / "task-probe2.yaml").read_text())["order"] == 3
    assert [t["order"] for t in RoutineRepository(str(root)).all_tasks()] == [0, 1, 2, 3]

def test_the_write_path_survives_a_restart_and_leaves_nothing_dangling(tmp_path, capsys):
    """
    ARCHITECTURE.md M3's falsification test, end to end through the CLI:
    create, edit, delete. The edit is read back by a *fresh* repository, so a
    write that only lands in memory fails here. The delete leaves no file, no
    order entry and no schedule entry behind.
    """
    root = _project(tmp_path, order=["keep"], tasks={"keep": {"name": "Keep"}})
    spec = tmp_path / "probe.yaml"
    spec.write_text(
        "id: probe\nname: Probe\nphases:\n  - name: run\n"
        "    script: scripts/x.py\n    memory_limit_mb: 64\n",
        encoding="utf-8",
    )
    patch = tmp_path / "patch.yaml"
    patch.write_text("name: Probe Renamed\n", encoding="utf-8")

    code, payload = _cli(root, "task", "create", "--path", str(spec), capsys=capsys)
    assert code == 0
    assert payload["id"] == "probe"

    code, _ = _cli(root, "task", "edit", "probe", "--patch", str(patch), capsys=capsys)
    assert code == 0

    # A fresh repository is the restart. The edit is on disk, not in a dict.
    assert RoutineRepository(str(root)).get("probe")["name"] == "Probe Renamed"

    # The plan is stated before the write, and names what it will touch.
    code, plan = _cli(root, "task", "delete", "probe", capsys=capsys)
    assert code == 0
    assert "tasks/task-probe.yaml" in plan["will_remove"]
    assert (root / "tasks" / "task-probe.yaml").exists(), "plan only, no delete"

    code, _ = _cli(root, "task", "delete", "probe", "--yes", capsys=capsys)
    assert code == 0

    fresh = RoutineRepository(str(root))
    assert not (root / "tasks" / "task-probe.yaml").exists()
    assert "probe" not in [t["id"] for t in RoutineRepository(str(root)).all_tasks()]
    assert fresh.get("probe") is None
    assert "probe" not in fresh.schedule()["scheduled_tasks"]
    assert fresh.orphaned_schedules() == []


def test_a_task_is_created_only_if_every_phase_has_a_memory_bound(tmp_path, capsys):
    """
    §5.4: a phase without `memory_limit_mb` is rejected at the write, not
    discovered mid-run against a real process. The rejected definition leaves
    nothing behind - no file, no order entry.
    """
    root = _project(tmp_path, order=["keep"], tasks={"keep": {"name": "Keep"}})
    spec = tmp_path / "unbounded.yaml"
    spec.write_text(
        "id: unbounded\nphases:\n  - name: run\n    script: scripts/x.py\n",
        encoding="utf-8",
    )

    with pytest.raises(TaskDefinitionError) as caught:
        RoutineRepository(str(root)).create(
            {"id": "unbounded", "phases": [{"name": "run", "script": "scripts/x.py"}]}
        )

    assert "memory_limit_mb" in str(caught.value)
    assert not (root / "tasks" / "task-unbounded.yaml").exists()
    assert [t["id"] for t in RoutineRepository(str(root)).all_tasks()] == ["keep"]


def test_a_created_or_edited_task_file_carries_no_reader_internals(tmp_path):
    """
    What lands in `routines/` is the operator's document, in §5.4's format.
    `source_file` is a back-reference the reader adds, and no migrated task
    carries one - writing it into a hand-editable file pushes an internal
    detail into the file the user owns.
    """
    root = _project(tmp_path, order=["t1"], tasks={"t1": {"name": "T"}})
    repo = RoutineRepository(str(root))

    repo.update("t1", {"name": "Renamed"})
    repo.create({"id": "t2", "name": "Second"})

    for name in ("task-t1.yaml", "task-t2.yaml"):
        stored = yaml.safe_load((root / "tasks" / name).read_text())
        assert "source_file" not in stored, name
    # The reader still resolves both: the back-reference is its own, not the
    # file's.
    fresh = RoutineRepository(str(root))
    assert fresh.get("t1")["name"] == "Renamed"
    assert fresh.get("t2")["source_file"] == "task-t2.yaml"


def test_delete_of_an_unknown_id_reports_a_message_naming_only_the_id(tmp_path, capsys):
    """
    Deleting an id that does not exist reports the id and nothing else: no
    `legacy-only` suffix, no wrapping quotes from str(KeyError).
    """
    root = _project(
        tmp_path,
        order=["alpha"],
        tasks={"alpha": {"name": "Alpha"}},
    )

    code = main(["--project-root", str(root), "task", "delete", "nope", "--yes"])
    err = capsys.readouterr().err

    assert code == 1
    assert err == "theteam task: Task 'nope' not found\n"
    # The old path printed str(KeyError(...)), which wraps the message in
    # quotes: `theteam task: 'Task 'nope' not found'`. The new handler prints
    # exc.args[0] verbatim, so no outer wrapping quotes and no legacy-only.
    assert "legacy-only" not in err
    assert "'Task 'nope' not found'" not in err


# ======= depends_on: the pipeline is declared, not implied =======


def test_depends_on_must_be_a_list_not_a_bare_string(tmp_path):
    """
    `depends_on: project-integrity` iterates its characters, so the task
    silently waits on `p`, `r`, `o`, `j` forever. That is worth naming at the
    read, where the mistake is visible, rather than at the run, where it is
    a task that mysteriously never proceeds.
    """
    root = _project(
        tmp_path,
        tasks={"consumer": {"depends_on": "producer"}},
    )

    with pytest.raises(TaskDefinitionError) as excinfo:
        RoutineRepository(str(root))

    assert "must be a list" in str(excinfo.value)
    assert "str" in str(excinfo.value)


def test_a_dependency_that_never_ran_blocks_the_consumer(tmp_path, capsys):
    """
    A task with an unmet dependency is skipped, not run and not failed.

    Nothing is wrong with the consumer — it is waiting. So it must not be
    counted against its breaker, and `theteam run` must say why rather than
    reporting a task with no work.
    """
    root = _project(
        tmp_path,
        order=["producer", "consumer"],
        tasks={
            "producer": {"name": "P", "phases": []},
            "consumer": {"name": "C", "depends_on": ["producer"],
                         "phases": []},
        },
        schedule={"scheduled_tasks": {}, "last_run": {}},
    )

    code, payload = _cli(root, "run", "--only", "consumer", capsys=capsys)

    assert code == 0
    result = payload["results"][0]
    assert result["result"] == "skipped"
    assert result["detail"] == "dependency_unmet"


def test_a_dependency_that_last_ran_ok_lets_the_consumer_run(tmp_path, capsys):
    """
    The gate must not block forever: once the dependency has succeeded, the
    consumer proceeds. This is the good path, and it is the one a gate that
    always returns early would break.
    """
    root = _project(
        tmp_path,
        order=["producer", "consumer"],
        tasks={
            "producer": {"name": "P", "phases": []},
            "consumer": {"name": "C", "depends_on": ["producer"],
                         "phases": []},
        },
        schedule={
            "scheduled_tasks": {},
            "last_run": {"producer": {"result": "ok", "breaker": "closed"}},
        },
    )

    code, payload = _cli(root, "run", "--only", "consumer", capsys=capsys)

    assert code == 0
    result = payload["results"][0]
    # `detail` is omitted when empty on the success path, so the gate is
    # checked by its absence rather than by a sentinel value.
    assert result.get("detail") != "dependency_unmet", result


def test_a_skipped_dependency_does_not_count_as_ok(tmp_path, capsys):
    """
    A dependency that was skipped did not do its work, so whatever it would
    have written is not on disk. Reading `skipped` as success is how a
    consumer ends up building on an input that was never produced.
    """
    root = _project(
        tmp_path,
        order=["producer", "consumer"],
        tasks={
            "producer": {"name": "P", "phases": []},
            "consumer": {"name": "C", "depends_on": ["producer"],
                         "phases": []},
        },
        schedule={
            "scheduled_tasks": {},
            "last_run": {"producer": {"result": "skipped",
                                      "breaker": "closed"}},
        },
    )

    code, payload = _cli(root, "run", "--only", "consumer", capsys=capsys)

    assert code == 0
    assert payload["results"][0]["detail"] == "dependency_unmet"


def test_depends_on_is_visible_in_the_task_listing(tmp_path, capsys):
    """
    A task that waits on another and says nothing reads as a task with no
    work to do. The declaration surfaces in `theteam tasks` so a reader can
    see why a task was or was not due.
    """
    root = _project(
        tmp_path,
        order=["producer", "consumer"],
        tasks={
            "producer": {"name": "P"},
            "consumer": {"name": "C", "depends_on": ["producer"]},
        },
    )

    code, payload = _cli(root, "tasks", capsys=capsys)

    rows = {t["id"]: t for t in payload["tasks"]}
    assert rows["consumer"]["depends_on"] == ["producer"]
    assert rows["producer"]["depends_on"] == []
