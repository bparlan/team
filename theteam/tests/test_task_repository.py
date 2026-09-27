"""
The task listing and task run contract.

`theteam tasks` and `theteam run` are the only two surfaces a user touches
for scheduled work, and both are read paths over two sources: canonical YAML
under `tasks/`, and the pre-M2 JSON registry that is still served. The
observable promises pinned here are the ones a regression would silently break
while still returning a plausible payload:

  * membership and order come from `tasks/TASK_ORDER`, so the listing does not
    drift when either source gains an entry;
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
from theteam.tasks.repository import TaskDefinitionError, TaskRepository


# ======= scratch project =======


def _project(root, order=(), tasks=None, schedule=None, registry=None, extra=()):
    """
    Build an isolated project: `tasks/TASK_ORDER`, `tasks/task-*.yaml`, and the
    state files under `<root>/.omp/theteam/`. Nothing is read from the real repo.
    """
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    tasks = tasks or {}
    if order:
        body = "# execution order\n" + "".join(
            f"{i}. {task_id}\n" for i, task_id in enumerate(order, start=1)
        )
        (tasks_dir / "TASK_ORDER").write_text(body, encoding="utf-8")
    for task_id, fields in tasks.items():
        payload = {"id": task_id}
        payload.update(fields)
        (tasks_dir / f"task-{task_id}.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
        )
    for name, text in extra:
        (tasks_dir / name).write_text(text, encoding="utf-8")

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


# ======= 1. order is TASK_ORDER sequence =======


def test_tasks_are_listed_in_task_order_sequence(tmp_path):
    """
    The listing order is the sequence in `TASK_ORDER` - not alphabetical and
    not by priority. Order of execution is the operator's decision, written
    down once; a reader that re-sorts it produces a different run order than
    the one the file documents.
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
    payload = TaskRepository(str(root)).list_tasks()

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

    stored = TaskRepository(str(root)).get("review")

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


def test_run_executes_a_due_task_and_advances_its_schedule(tmp_path, capsys):
    """
    A due task whose phase script is a real Python file that exits 0 is
    executed and reported `ok`, and its `next_run` moves forward by its
    interval. Three observable effects: the script really ran (side-effect file
    in the project root), `ran=1`, and the task is no longer due.
    """
    root = _project(
        tmp_path,
        order=["probe"],
        tasks={
            "probe": {
                "phases": [{"name": "probe", "script": "phases/probe.py"}]
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
        "import pathlib\npathlib.Path('probe-ran.txt').write_text('ran')\n",
        encoding="utf-8",
    )
    before = datetime.now(timezone.utc)

    code, payload = _cli(root, "run", capsys=capsys)

    assert code == 0
    assert payload["ran"] == 1
    assert payload["failures"] == 0
    assert payload["results"] == [{"id": "probe", "result": "ok"}]
    # The script really executed, as a subprocess, in the project root.
    assert (root / "probe-ran.txt").read_text(encoding="utf-8") == "ran"

    schedule = json.loads(
        (root / ".omp" / "theteam" / "task-schedule.json").read_text(encoding="utf-8")
    )
    next_run = datetime.fromisoformat(schedule["scheduled_tasks"]["probe"]["next_run"])
    assert schedule["last_run"]["probe"]["result"] == "ok"
    assert timedelta(minutes=50) <= next_run - before <= timedelta(minutes=61)
    # Advanced, so the same task is not immediately due again.
    assert TaskRepository(str(root)).due() == []


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


# ======= 7. the migration safety net: a lost YAML file is still a task =======


def test_task_order_id_served_from_the_legacy_registry_is_still_listed(tmp_path):
    """
    An id named in `TASK_ORDER` whose YAML file is gone but which the legacy
    registry still knows stays in the listing, flagged in `legacy_only`. This is
    the migration safety net: a file that failed to convert must read as a
    visible fallback, not as a task that stopped existing.
    """
    root = _project(
        tmp_path,
        order=["alpha", "ghost"],
        tasks={"alpha": {"name": "A"}},
        registry={"ghost": {"id": "ghost", "name": "From the registry", "priority": 2}},
    )

    payload = TaskRepository(str(root)).list_tasks()

    ids = [t["id"] for t in payload["tasks"]]
    assert ids == ["alpha", "ghost"], "a task that lost its YAML is not gone"
    assert payload["legacy_only"] == ["ghost"]
    ghost = next(t for t in payload["tasks"] if t["id"] == "ghost")
    assert ghost["name"] == "From the registry"
    assert ghost["priority"] == 2
    # The read found the task, but not in YAML - the two numbers differ on
    # purpose, and that difference is the migration's progress report.
    assert payload["count"] == 2
    assert payload["yaml_count"] == 1
    assert payload["missing_tasks"] == []


def test_legacy_only_entry_is_surfaced_by_the_tasks_command(tmp_path, capsys):
    """
    `theteam tasks` prints a note naming the ids still served from the registry.
    The JSON payload carries the data; the human line is where an operator
    actually sees that the migration is not finished.
    """
    root = _project(
        tmp_path,
        order=["ghost"],
        registry={"ghost": {"id": "ghost", "name": "From the registry"}},
    )

    code = main(["--project-root", str(root), "tasks"])
    out = capsys.readouterr().out

    assert code == 0
    assert "note:" in out
    assert "ghost" in out


# ======= 8. an id no source can supply is reported, not vanished =======


def test_task_order_id_with_no_source_is_reported_missing(tmp_path):
    """
    An id in `TASK_ORDER` with no YAML file and no registry entry appears in
    `missing_tasks` and not in the listing. Silently dropping it would make a
    broken TASK_ORDER look like a shorter task list.
    """
    root = _project(
        tmp_path,
        order=["alpha", "phantom"],
        tasks={"alpha": {"name": "A"}},
    )

    payload = TaskRepository(str(root)).list_tasks()

    assert payload["missing_tasks"] == ["phantom"]
    assert [t["id"] for t in payload["tasks"]] == ["alpha"]
    assert payload["count"] == 1


# ======= 9. non-task files in tasks/ are not tasks =======


def test_a_non_task_yaml_in_the_tasks_dir_is_ignored(tmp_path):
    """
    `tasks/SECURITY_POLICY.yaml` is not a task and is not even parseable YAML.
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

    payload = TaskRepository(str(root)).list_tasks()

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
        TaskRepository(str(root)).list_tasks()

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
