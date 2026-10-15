"""
The audit chain contract: every task mutation and execution is recorded, and
`theteam status` reports a real check against the file it names.

§1.2 promises "nothing changes unrecorded" and says the promise is checkable
by running `theteam status`. These tests are that check. They defend three
things a regression would break silently:

  * the four mutation events - create, edit, delete, execution - actually land
    in the chain, at the path `status` names;
  * `status` reports what `verify_chain()` returned, and reports a broken
    chain as broken;
  * a chain that was never written is `absent` / `empty`, never `intact`.
    `verify_chain()` returns `True` on an empty list, so a reader that does not
    handle the empty case claims a verified chain for a file that has no
    entries in it - the §3.3 `MockAPI` defect with a friendlier name.

No Docker: the execution case drives `RoutineExecutor.execute_task` with a phase
whose script is absent, which is a real attempt that really fails, and the
audit entries are written the same way on the success and failure paths.
"""

import json

import pytest
import yaml

from theteam.cli import main
from theteam.core.audit_chain import audit_file, read_chain_state
from theteam.routines.executor import RoutineExecutor
from theteam.routines.repository import RoutineRepository


CONFIG = {
    "schema_version": 1,
    "team": [
        {"id": "architect", "enabled": True},
        {"id": "skeptic", "enabled": True},
    ],
}


# ======= scratch project =======


def _project(root, tasks=None, schedule=None, config=True):
    """
    An isolated project: `tasks/task-*.yaml` and `.omp/theteam/`. Nothing is
    read from the real repo, and `THETEAM_STATE_DIR` is not involved, so the
    state directory resolves under this root.
    """
    if config:
        (root / "theteam.config").write_text(
            yaml.safe_dump(CONFIG, sort_keys=False), encoding="utf-8"
        )
    routines_dir = root / "tasks"
    routines_dir.mkdir(parents=True, exist_ok=True)
    for task_id, fields in (tasks or {}).items():
        payload = {"id": task_id, "order": len(tasks or {})}
        payload.update(fields)
        (routines_dir / f"task-{task_id}.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
        )
    if schedule is not None:
        state = root / ".omp" / "theteam"
        state.mkdir(parents=True, exist_ok=True)
        (state / "task-schedule.json").write_text(
            json.dumps(schedule, indent=2), encoding="utf-8"
        )
    return root


def _cli(root, *argv, capsys):
    """Drive the CLI and hand back (exit code, parsed JSON payload)."""
    code = main(["--project-root", str(root), *argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def _entries(root):
    """Every chain entry, in file order."""
    path = audit_file(str(root))
    if not path.is_file():
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _events(root, kind):
    return [e for e in _entries(root) if e.get("event") == kind]


# ======= 1. every mutation is in the chain =======


def test_create_edit_and_delete_each_append_to_the_chain(tmp_path):
    """Three writes, three entries, each naming the id it touched."""
    root = _project(tmp_path, tasks={"keep": {"phases": []}})

    repo = RoutineRepository(str(root))
    repo.create({"id": "added", "phases": []})
    repo.update("added", {"name": "Renamed"})
    repo.delete("added")

    assert [e["task_id"] for e in _events(root, "task_created")] == ["added"]
    assert [e["task_id"] for e in _events(root, "task_edited")] == ["added"]
    assert [e["task_id"] for e in _events(root, "task_deleted")] == ["added"]
    # The edit names what it changed, so the trail reads without the repo.
    assert _events(root, "task_edited")[0]["fields"] == ["name"]


def test_an_execution_is_in_the_chain_with_its_outcome(tmp_path):
    """
    A run is recorded before it happens and with how it ended.

    The phase's script does not exist, so the execution really is attempted
    and really fails. The chain says so either way - the point is that an
    execution is not silent.
    """
    root = _project(tmp_path, tasks={"probe": {
        "phases": [{"name": "probe", "script": "phases/absent.py",
                    "memory_limit_mb": 64}]
    }})

    result = RoutineExecutor(str(root)).execute_task(
        {"id": "probe", "phases": [
            {"name": "probe", "script": "phases/absent.py", "memory_limit_mb": 64}
        ]}
    )
    assert result["overall_success"] is False

    starts = _events(root, "task_start")
    failures = _events(root, "task_failed")
    assert [e["task"] for e in starts] == ["probe"]
    assert [e["task"] for e in failures] == ["probe"]
    assert "absent.py" in failures[0]["error"]


def test_the_chain_is_in_the_state_directory_and_named_by_status(tmp_path, capsys):
    """
    The file `status` names is the file the writers appended to.

    A report of a path nobody wrote to is the defect this milestone closes,
    so the assertion is on the path itself, not on a boolean.
    """
    root = _project(tmp_path, tasks={"keep": {"phases": []}})
    RoutineRepository(str(root)).create({"id": "added", "phases": []})

    code, payload = _cli(root, "status", capsys=capsys)

    assert code == 0
    reported = payload["audit_chain"]["file"]
    assert reported == str(root / ".omp" / "theteam" / "audit" / "audit.jsonl")
    assert reported == str(audit_file(str(root)))
    # It exists, and the entry the repository wrote is the one inside it.
    assert (root / ".omp" / "theteam" / "audit" / "audit.jsonl").is_file()
    assert payload["audit_chain"]["entries"] == len(_entries(root)) == 1


# ======= 2. status verifies, and reports a break as a break =======


def test_status_reports_intact_for_a_chain_that_verifies(tmp_path, capsys):
    """Real entries, real `verify_chain()` behind the word `intact`."""
    root = _project(tmp_path, tasks={"keep": {"phases": []}})
    repo = RoutineRepository(str(root))
    repo.create({"id": "a", "phases": []})
    repo.update("a", {"name": "B"})
    repo.delete("a")

    code, payload = _cli(root, "status", capsys=capsys)
    chain = payload["audit_chain"]

    assert code == 0
    assert chain["exists"] is True
    assert chain["state"] == "intact"
    assert chain["intact"] is True
    assert chain["entries"] == 3
    assert chain["reason"] is None


def test_tampering_with_one_line_is_reported_as_a_broken_chain(tmp_path, capsys):
    """
    The promise is tamper *evidence*, so the proof is the edit.

    One line is rewritten in place - the file's line count, its entry count
    and its `prev_hash` linkage are all untouched - and the chain must report
    itself broken rather than merely suspicious.
    """
    root = _project(tmp_path, tasks={"keep": {"phases": []}})
    repo = RoutineRepository(str(root))
    repo.create({"id": "a", "phases": []})
    repo.update("a", {"name": "B"})
    repo.delete("a")

    path = audit_file(str(root))
    lines = path.read_text(encoding="utf-8").splitlines()
    forged = json.loads(lines[1])
    forged["fields"] = ["something_else"]          # the edit; hash not recomputed
    lines[1] = json.dumps(forged)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    code, payload = _cli(root, "status", capsys=capsys)
    chain = payload["audit_chain"]

    assert code == 0
    assert chain["state"] == "broken"
    assert chain["intact"] is False
    assert chain["entries"] == 3, "the tampered line is still a line"
    assert "does not verify" in chain["reason"]


def test_a_broken_chain_marks_what_is_written_after_it(tmp_path):
    """
    §3.2: writes continue, and every entry after the break is marked.

    A break must not stop the trail, and it must not be invisible in it.
    """
    root = _project(tmp_path, tasks={"keep": {"phases": []}})
    repo = RoutineRepository(str(root))
    repo.create({"id": "a", "phases": []})

    path = audit_file(str(root))
    line = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    line["task_id"] = "forged"
    path.write_text(json.dumps(line) + "\n", encoding="utf-8")

    assert read_chain_state(str(root))["state"] == "broken"

    RoutineRepository(str(root)).create({"id": "b", "phases": []})

    marked = _events(root, "task_created")
    assert [e["task_id"] for e in marked] == ["forged", "b"]
    assert marked[0].get("chain_broken") is None, "written while the chain held"
    assert marked[1]["chain_broken"] is True, "written after the break"


# ======= 3. nothing written is not the same as verified =======


def test_an_absent_chain_is_reported_as_absent_not_intact(tmp_path, capsys):
    """
    `verify_chain()` returns `True` on an empty list, so a reader that only
    asks the boolean reports a verified chain for a file that has never been
    written. `intact` is `None` here: nothing was measured.
    """
    root = _project(tmp_path, tasks={"keep": {"phases": []}})

    code, payload = _cli(root, "status", capsys=capsys)
    chain = payload["audit_chain"]

    assert code == 0
    assert chain["exists"] is False
    assert chain["state"] == "absent"
    assert chain["intact"] is None, "no chain was measured, so none is claimed"
    assert "no audit file" in chain["reason"]
    assert not (root / ".omp" / "theteam" / "audit" / "audit.jsonl").exists()


def test_an_empty_chain_file_is_reported_as_empty_not_intact(tmp_path, capsys):
    """
    The file exists and holds no entry. `verify_chain()` says `True`; the
    report must not, because there is nothing in it to have verified.
    """
    root = _project(tmp_path, tasks={"keep": {"phases": []}})
    path = audit_file(str(root))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")

    code, payload = _cli(root, "status", capsys=capsys)
    chain = payload["audit_chain"]

    assert code == 0
    assert chain["exists"] is True
    assert chain["state"] == "empty"
    assert chain["intact"] is None
    assert chain["entries"] == 0
    assert "empty" in chain["reason"]


def test_a_chain_of_unparseable_lines_is_reported_as_empty_with_the_count(
    tmp_path, capsys
):
    """
    A file of garbage is not a verified chain, and it is not silent either:
    the line count is reported so the reader can see that bytes exist and no
    entry was read out of them.
    """
    root = _project(tmp_path, tasks={"keep": {"phases": []}})
    path = audit_file(str(root))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json\nstill not json\n", encoding="utf-8")

    code, payload = _cli(root, "status", capsys=capsys)
    chain = payload["audit_chain"]

    assert code == 0
    assert chain["state"] == "empty"
    assert chain["intact"] is None
    assert chain["lines"] == 2
    assert chain["entries"] == 0
    assert "no parseable entry" in chain["reason"]


# ======= 4. the human line reads the same fields =======


@pytest.mark.parametrize("state,word", [
    ({"state": "absent", "reason": "no audit file at /x"}, "absent"),
    ({"state": "empty", "reason": "/x is empty"}, "empty"),
    ({"state": "broken", "intact": False, "reason": "no verify", "entries": 4,
      "file": "/x"}, "BROKEN"),
    ({"state": "intact", "intact": True, "reason": None, "entries": 4,
      "file": "/x"}, "intact"),
])
def test_the_human_line_says_the_same_thing_the_json_does(state, word):
    """`theteam status` in prose must not be more confident than its JSON."""
    from theteam.core.audit_chain import chain_line

    assert word in chain_line(state)
