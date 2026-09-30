"""M9 Phase 4: `runner: llm` and prompt-shaped work as registered tasks.

Three contracts, each of which fails against the pre-Phase-4 code:

1. **A phase names exactly one runner.** `script:` and `runner: llm` are
   mutually exclusive, and a phase naming neither is refused by name rather
   than silently skipped. Without the check, a check that only understood
   `script` would turn every llm phase into a "missing script" skip — the
   exact hole §3.3 forbids.
2. **A missing provider is a named failure, not a synthesized result.** This
   is the M0 defect in a new place: the prompt is real, the member is not.
3. **`--only` means "run this now".** It previously filtered the due set, so
   naming an unscheduled task reported `nothing due`.
"""

import os
from pathlib import Path

import pytest
import yaml

from theteam.cli import _phase_problem
from theteam.tasks.repository import TaskRepository
from theteam.tasks.runners.llm import run_llm_phase

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _project(tmp_path, task):
    """A project whose only task is `task`."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    with open(tasks_dir / "task-x.yaml", "w") as handle:
        yaml.dump(task, handle)
    return str(tmp_path)


class TestOneRunnerPerPhase:
    """A phase names `script:` or `runner: llm`, never both, never neither."""

    def test_a_script_phase_with_the_script_present_is_fine(self, tmp_path):
        (tmp_path / "run.py").write_text("print(1)\n")
        task = {"id": "x", "phases": [{"name": "a", "script": "run.py"}]}
        assert _phase_problem(task, str(tmp_path)) is None

    def test_an_llm_phase_needs_no_script(self, tmp_path):
        task = {"id": "x", "phases": [
            {"name": "a", "runner": "llm", "prompt_file": "p.md"}]}
        assert _phase_problem(task, str(tmp_path)) is None

    def test_a_phase_naming_both_is_refused(self, tmp_path):
        (tmp_path / "run.py").write_text("print(1)\n")
        task = {"id": "x", "phases": [
            {"name": "a", "script": "run.py", "runner": "llm"}]}
        problem = _phase_problem(task, str(tmp_path))
        assert "both" in problem

    def test_a_phase_naming_neither_is_refused(self, tmp_path):
        task = {"id": "x", "phases": [{"name": "a", "memory_limit_mb": 64}]}
        problem = _phase_problem(task, str(tmp_path))
        assert "no runner" in problem

    def test_a_missing_script_is_still_named(self, tmp_path):
        task = {"id": "x", "phases": [{"name": "a", "script": "absent.py"}]}
        assert "missing script" in _phase_problem(task, str(tmp_path))


class TestNoProviderIsANamedFailure:
    """The M0 rule, in its Phase 4 shape."""

    def test_an_llm_phase_outside_omp_fails_by_name(self, tmp_path):
        (tmp_path / "p.md").write_text("do the thing")
        phase = {"name": "audit", "runner": "llm", "prompt_file": "p.md"}
        result = run_llm_phase({"id": "x"}, phase, str(tmp_path))
        assert result["success"] is False
        assert "OMP session" in result["error"]

    def test_it_does_not_invent_a_result(self, tmp_path):
        (tmp_path / "p.md").write_text("do the thing")
        phase = {"name": "audit", "runner": "llm", "prompt_file": "p.md",
                 "output": "out.md"}
        result = run_llm_phase({"id": "x"}, phase, str(tmp_path))
        assert not os.path.exists(str(tmp_path / "out.md"))

    def test_a_missing_prompt_file_is_a_named_failure_not_a_traceback(self, tmp_path):
        phase = {"name": "audit", "runner": "llm", "prompt_file": "absent.md"}
        result = run_llm_phase({"id": "x"}, phase, str(tmp_path))
        assert result["success"] is False
        assert "prompt_file not found" in result["error"]

    def test_a_phase_with_no_prompt_file_is_refused(self, tmp_path):
        phase = {"name": "audit", "runner": "llm"}
        result = run_llm_phase({"id": "x"}, phase, str(tmp_path))
        assert result["success"] is False
        assert "no prompt_file" in result["error"]


class TestOnlyBypassesTheSchedule:
    """`--only <id>` means run it now, scheduled or not."""

    def _task(self):
        return {"id": "x", "name": "X", "type": "analysis", "order": 0,
                "phases": [{"name": "a", "runner": "llm", "prompt_file": "p.md",
                            "memory_limit_mb": 64}]}

    def test_a_named_unscheduled_task_is_due(self, tmp_path):
        root = _project(tmp_path, self._task())
        repo = TaskRepository(root)
        assert repo.schedule()["scheduled_tasks"] == {}
        assert [t["id"] for t in repo.due(only="x")] == ["x"]

    def test_an_unscheduled_task_is_not_due_without_only(self, tmp_path):
        root = _project(tmp_path, self._task())
        assert TaskRepository(root).due() == []

    def test_naming_an_unknown_id_returns_nothing(self, tmp_path):
        root = _project(tmp_path, self._task())
        assert TaskRepository(root).due(only="nope") == []

    def test_due_still_advances_nothing(self, tmp_path):
        root = _project(tmp_path, self._task())
        repo = TaskRepository(root)
        repo.due(only="x")
        assert repo.schedule()["scheduled_tasks"] == {}


class TestTheThreeShippedTasks:
    """The commands §M9 says must work, checked against the real files."""

    @pytest.mark.parametrize("task_id", ["ground-truth-audit",
                                         "doc-harmonization",
                                         "native-feature-loop"])
    def test_the_task_is_registered(self, task_id):
        repo = TaskRepository(str(REPO_ROOT))
        assert repo.get(task_id) is not None

    @pytest.mark.parametrize("task_id", ["ground-truth-audit",
                                         "doc-harmonization",
                                         "native-feature-loop"])
    def test_every_llm_phase_names_a_prompt_that_exists(self, task_id):
        task = TaskRepository(str(REPO_ROOT)).get(task_id)
        for phase in task["phases"]:
            if phase.get("runner") == "llm":
                assert (REPO_ROOT / phase["prompt_file"]).exists(), phase

    @pytest.mark.parametrize("task_id", ["ground-truth-audit",
                                         "doc-harmonization",
                                         "native-feature-loop"])
    def test_every_phase_names_exactly_one_runner(self, task_id):
        task = TaskRepository(str(REPO_ROOT)).get(task_id)
        assert _phase_problem(task, str(REPO_ROOT)) is None

    def test_the_test_phase_of_native_feature_loop_is_a_script(self):
        # "a test suite is deterministic and must not be judged by a model"
        task = TaskRepository(str(REPO_ROOT)).get("native-feature-loop")
        kinds = [p.get("runner") or "script" for p in task["phases"]]
        assert kinds == ["llm", "llm", "script", "llm"]
        test_phase = next(p for p in task["phases"] if p["name"] == "test")
        assert (REPO_ROOT / test_phase["script"]).exists()
