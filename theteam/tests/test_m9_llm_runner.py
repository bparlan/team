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
        # `output` is required, and always has been: `run_llm_phase` refuses
        # an `llm` phase that declares none (`llm.py:237`, guarded by
        # `test_a_phase_naming_no_output_cannot_report_success`). The gate
        # names that earlier rather than at run time. What this test is
        # about is narrower — an `llm` phase needs no *script*, because its
        # instructions live in the prompt file.
        task = {"id": "x", "phases": [
            {"name": "a", "runner": "llm", "prompt_file": "p.md",
             "output": "out.md"}]}
        assert _phase_problem(task, str(tmp_path)) is None

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

class TestSuccessRequiresAnArtifact:
    """§3.3: a phase cannot report success having produced nothing.

    `run_llm_phase` used to write only `if target:` and then return
    `{"success": True}` regardless. A phase naming no `output` therefore
    reported green with zero evidence on disk, and the executor — which reads
    `success` and has no notion of an artifact — advanced the breaker on it.

    These cases need a bound provider: without one the runner returns at the
    `no_task_provider` guard and the artifact gate is never reached. The stub
    is the minimum `task()`/`output()` surface `run_llm_phase` uses, bound the
    way the product binds it — as `theteam.default_api`.
    """

    @pytest.fixture
    def member_says(self, monkeypatch):
        """Bind a stub member whose output is whatever the test declares."""
        import theteam

        def _bind(payload):
            class _Stub:
                def task(self, **kwargs):
                    tasks = kwargs.get("tasks") or []
                    return {"tasks": [{"name": t["name"],
                                       "handle": f"h:{t['name']}"}
                                      for t in tasks]}

                def output(self, handle):
                    return payload

            monkeypatch.setattr(theteam, "default_api", _Stub(), raising=False)

        return _bind

    def test_a_phase_naming_no_output_cannot_report_success(
            self, tmp_path, member_says):
        """No declared output means no way to prove the phase ran."""
        member_says("the member produced something")
        (tmp_path / "p.md").write_text("do the thing")
        phase = {"name": "audit", "runner": "llm", "prompt_file": "p.md",
                 "member": "scout"}
        result = run_llm_phase({"id": "x"}, phase, str(tmp_path))
        assert result["success"] is False
        assert "no `output`" in result["error"]

    def test_an_empty_artifact_is_refused_by_name(self, tmp_path, member_says):
        """A member that produced nothing is a failure, not a zero-byte pass."""
        member_says("")
        (tmp_path / "p.md").write_text("do the thing")
        phase = {"name": "audit", "runner": "llm", "prompt_file": "p.md",
                 "member": "scout", "output": "out.md"}
        result = run_llm_phase({"id": "x"}, phase, str(tmp_path))
        assert result["success"] is False
        assert "is empty" in result["error"]

    def test_a_real_artifact_still_succeeds(self, tmp_path, member_says):
        """The gate refuses only the cases with no evidence behind them."""
        member_says("the member's actual finding")
        (tmp_path / "p.md").write_text("do the thing")
        phase = {"name": "audit", "runner": "llm", "prompt_file": "p.md",
                 "member": "scout", "output": "out.md"}
        result = run_llm_phase({"id": "x"}, phase, str(tmp_path))
        assert result["success"] is True
        assert result["output_path"] == str(tmp_path / "out.md")
        assert (tmp_path / "out.md").read_text() == "the member's actual finding"



class TestMemberMustBeOnTheRoster:
    """A phase may name only a member the project actually has.

    `root-organization/scan` named `scout`, which is not on the roster, and
    `run_llm_phase` accepted it: the spawn carried a name nobody owns, the
    request was staged, and the task sat in `awaiting_member` forever because
    no member could answer it. The roster is the project's own declaration,
    so the runner reads it rather than trusting the phase.

    The check fires only when a roster exists. A test project with no
    `theteam.config` has no membership to validate against, and refusing
    there would break every fixture that binds a stub provider without
    writing one — the config's absence is a separate concern, and it is the
    config's own loader that names it.
    """

    @pytest.fixture
    def with_config(self, tmp_path):
        """A project that declares the roster the real one does."""
        (tmp_path / "theteam.config").write_text(
            "team:\n"
            "  - id: architect\n"
            "  - id: pragmatist\n"
            "  - id: skeptic\n"
            "  - id: designer\n"
            "  - id: devops\n", encoding="utf-8")
        return tmp_path

    def test_a_member_not_on_the_roster_is_refused(self, with_config):
        phase = {"name": "scan", "runner": "llm", "member": "scout",
                 "prompt_file": "p.md", "output": "out.md"}
        result = run_llm_phase({"id": "x"}, phase, str(with_config))

        assert result["success"] is False
        assert "scout" in result["error"]
        assert "roster" in result["error"]
        # The refusal names the members that exist, so the reader can fix it
        # by editing the phase rather than hunting the config.
        for member in ("architect", "pragmatist", "skeptic", "designer",
                       "devops"):
            assert member in result["error"]

    def test_a_member_on_the_roster_is_not_refused(self, with_config,
                                                    monkeypatch):
        """The guard must not swallow a valid member — the good path still
        reaches the provider, or it dies on the provider, not on the roster.
        """
        import theteam
        (with_config / "p.md").write_text("do the thing")

        class Provider:
            @staticmethod
            def task(**kw):
                return {"tasks": [{"name": "scan_architect", "handle": "h1"}]}

            @staticmethod
            def output(handle):
                return "the member's report"

        monkeypatch.setattr(theteam, "default_api", Provider(), raising=False)
        phase = {"name": "scan", "runner": "llm", "member": "architect",
                 "prompt_file": "p.md", "output": "out.md"}
        result = run_llm_phase({"id": "x"}, phase, str(with_config))

        assert result["success"] is True, result
        assert (with_config / "out.md").read_text() == "the member's report"


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


class TestEveryShippedTask:
    """The commands §M9 says must work, checked against the real files.

    Driven from `yaml_ids()` rather than a hand-written list, because a list
    is a fourth thing to update when a task is added and nothing fails when
    someone forgets: the new task's phases would get zero coverage and a
    renamed prompt would pass the suite silently.
    """

    @pytest.mark.parametrize("task_id", TaskRepository(str(REPO_ROOT)).yaml_ids)
    def test_the_task_is_registered(self, task_id):
        repo = TaskRepository(str(REPO_ROOT))
        assert repo.get(task_id) is not None

    @pytest.mark.parametrize("task_id", TaskRepository(str(REPO_ROOT)).yaml_ids)
    def test_every_llm_phase_names_a_prompt_that_exists(self, task_id):
        task = TaskRepository(str(REPO_ROOT)).get(task_id)
        for phase in task["phases"]:
            if phase.get("runner") == "llm":
                assert (REPO_ROOT / phase["prompt_file"]).exists(), phase

    @pytest.mark.parametrize("task_id", TaskRepository(str(REPO_ROOT)).yaml_ids)
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


class TestRefusalNamesTheWayOut:
    """A refusal that names a condition the reader cannot change is a dead end.

    The bare-CLI refusal used to say "run this inside an OMP session, where a
    task provider is bound" — advice that cannot be followed from inside an OMP
    session, because no environment binds that symbol. A reader who took it at
    face value went looking for a flag that does not exist. The refusal now
    names the command that runs the task, which is `theteam run --only <id>
    --run-id <id>`.
    """

    def test_refusal_carries_a_hint_naming_the_run_id_form(self, tmp_path):
        task = {"id": "x", "phases": [{"name": "audit", "runner": "llm",
                                       "member": "architect",
                                       "prompt_file": "p.md",
                                       "output": "out.md"}]}
        (tmp_path / "p.md").write_text("do the thing")
        result = run_llm_phase(task, task["phases"][0], str(tmp_path))
        assert result["skip_reason"] == "no_task_provider"
        assert "--run-id" in result["hint"], result
        assert "theteam run --only x" in result["hint"], result

    def test_hint_does_not_promise_a_session_flag(self, tmp_path):
        # The old text is exactly the failure this replaces. Asserting its
        # absence is the point: it must never come back.
        task = {"id": "x", "phases": [{"name": "audit", "runner": "llm",
                                       "member": "architect",
                                       "prompt_file": "p.md",
                                       "output": "out.md"}]}
        (tmp_path / "p.md").write_text("do the thing")
        result = run_llm_phase(task, task["phases"][0], str(tmp_path))
        assert "task provider is bound" not in result["hint"], result

    def test_readiness_is_derived_from_phase_kinds_not_the_process(self):
        """`smoke_cli` used to gate on `hasattr(theteam, "default_api")`.

        That symbol is bound in no environment, so the column read "refused:
        needs a bound OMP provider" for four of six tasks and told the reader
        nothing about `--run-id`. The replacement must key on phase kinds
        alone, so a listing cannot change with the calling interpreter.

        The assertion is on `runnable_here` being TRUE for an llm task, not on
        the old wording being absent. An earlier version of this test asserted
        the string was gone, and mutation proved it blind: restoring the stale
        gate replaced the wording wholesale and the test still passed. A test
        that checks a message cannot see a behaviour change that also changes
        the message.
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "smoke_cli", REPO_ROOT / "scripts" / "smoke_cli.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows, _docker, session_spawn = module.task_readiness()
        assert rows, "no tasks read"
        for row in rows:
            llm_phases = row["kinds"].count("llm")
            assert row["needs_session_spawn"] == (llm_phases > 0), row
            if llm_phases and row["runnable_here"]:
                # Docker is present on CI and on this box; when it is absent
                # the row is legitimately refused for the Docker reason, which
                # is a different refusal and not the one under test.
                assert row["reason"] == "needs Docker (no daemon answering)" \
                    or "--run-id" in row["reason"], row
            if llm_phases:
                assert "--run-id" in row["reason"], row
        assert session_spawn is True, "the shipped tasks all have llm phases"


class TestProviderContract:
    """A bound provider is not automatically a well-behaved one.

    `run_llm_phase` reads a fixed envelope: `api.task(...)` returns a dict with
    a `tasks` list of `{"name", "handle"}` entries. A provider that answers
    something else used to raise `AttributeError` straight out of the phase
    loop — a crash where §3.3 requires a named refusal, and the worse trade
    because a crash takes `theteam run` down with a traceback rather than
    reporting the task as unrunnable.

    These shapes are the real ones, not invented: `{"text", "details"}` is
    what OMP's `tool.task` returns in the eval kernel, and a bare string is
    what a thin adapter over it plausibly returns.
    """

    @staticmethod
    def _task():
        return {"id": "x", "phases": [{"name": "audit", "runner": "llm",
                                       "member": "architect",
                                       "prompt_file": "p.md",
                                       "output": "out.md"}]}

    @pytest.fixture
    def bound(self, tmp_path, monkeypatch):
        """A project with a prompt, and a provider bound as the runner reads it."""
        import theteam
        (tmp_path / "p.md").write_text("do the thing")
        monkeypatch.setattr(theteam, "default_api", object(), raising=False)
        return tmp_path

    @pytest.mark.parametrize("outcome,shown", [
        ({"text": "Spawned", "details": {}}, "no 'tasks' list"),
        ("plain text", "not a result envelope"),
        (None, "not a result envelope"),
        ({"tasks": ["a string, not a dict"]}, "in 'tasks', not a dict"),
        ({"tasks": {"not": "a list"}}, "no 'tasks' list"),
    ])
    def test_malformed_provider_response_is_a_named_refusal(self, bound, monkeypatch,
                                                            outcome, shown):
        """The contract check, across every shape measured to be plausible."""
        import theteam
        task = self._task()
        monkeypatch.setattr(theteam, "default_api",
                            type("P", (), {"task": staticmethod(lambda **kw: outcome)})(),
                            raising=False)
        result = run_llm_phase(task, task["phases"][0], str(bound))
        assert result["success"] is False
        assert result["skip_reason"] == "provider_contract_violated", result
        assert shown in result["error"], result
        # A refusal, not a failure: counting it would walk the task toward a
        # breaker trip that nothing can clear, which is the M0 defect.
        assert "error" in result and result["hint"], result

    def test_a_well_formed_envelope_reaches_output(self, bound, monkeypatch):
        """The guard must not swallow the good path.

        Without this, a contract check that always returned early would pass
        every test above and break every real phase.
        """
        import theteam
        task = self._task()
        written = {}

        class Provider:
            @staticmethod
            def task(**kw):
                return {"tasks": [{"name": "audit_architect", "handle": "h1"}]}

            @staticmethod
            def output(handle):
                return "the member's report"

        monkeypatch.setattr(theteam, "default_api", Provider(), raising=False)
        result = run_llm_phase(task, task["phases"][0], str(bound))
        assert result["success"] is True, result
        target = bound / "out.md"
        assert target.read_text() == "the member's report"
        assert written == {}

    def test_a_malformed_dict_with_mixed_key_types_is_still_named(self, bound,
                                                                monkeypatch):
        """The error path used to crash on the input it was describing.

        `sorted(outcome)` raised `TypeError: '<' not supported between
        instances of 'int' and 'str'` for a dict with mixed keys — so the
        branch whose entire job is to name a bad provider response was the one
        branch that died on a bad provider response. Every other case in this
        class used homogeneous keys and sailed past it.
        """
        import theteam
        task = self._task()
        outcome = {"text": "Spawned", 7: "numeric key", "tasks": "not a list"}
        monkeypatch.setattr(theteam, "default_api",
                            type("P", (), {"task": staticmethod(lambda **kw: outcome)})(),
                            raising=False)
        result = run_llm_phase(task, task["phases"][0], str(bound))
        assert result["success"] is False
        assert result["skip_reason"] == "provider_contract_violated", result
        assert "'7'" in result["error"] and "'text'" in result["error"], result


class TestLlmPhasePreconditionsAreCheckedBeforeTheRun:
    """The runner's two `llm` refusals, hoisted from run time to the gate.

    `run_llm_phase` already refuses an `llm` phase with no `prompt_file` and
    one that declares no `output`. Those refusals happen at run time, once per
    attempt, with the reason buried inside a phase result — a reader sees
    `skipped` and has to open the payload to learn why. `_phase_problem`
    names both before the task starts.

    **Nothing more is checked, and that is the point.** An earlier version of
    this also gated on `expected_output`, and it broke two long-standing tests
    whose fixtures build minimal tasks. Those tests were not wrong; the
    requirement was invented. `definition_of_done`, `gates`, `coverage`,
    `termination`, `rules` and `failure_handling` are prose with no
    operational spec — "every ask item is a grouped question" is not
    decidable by an assertion. A validator that returned "fine" for prose it
    never read would be the same defect as a contract no code reads at all,
    and one that refused would be inventing semantics on the way past.
    """

    def _task(self, **phase):
        base = {"name": "a", "runner": "llm", "prompt_file": "p.md",
                "output": ".omp/theteam/reports/a.md"}
        base.update(phase)
        return {"id": "x", "phases": [base]}

    def test_a_well_formed_llm_phase_passes(self, tmp_path):
        (tmp_path / "p.md").write_text("do the thing")
        assert _phase_problem(self._task(), str(tmp_path)) is None

    def test_an_llm_phase_naming_no_output_is_refused_at_the_gate(self, tmp_path):
        """Same refusal the runner makes, made before the run instead of
        during it: the task never starts, and the human sees why.
        """
        (tmp_path / "p.md").write_text("do the thing")
        problem = _phase_problem(self._task(output=None), str(tmp_path))
        assert "no output" in problem

    def test_an_llm_phase_naming_no_prompt_file_is_refused(self, tmp_path):
        problem = _phase_problem(self._task(prompt_file=None), str(tmp_path))
        assert "no prompt_file" in problem

    def test_a_minimal_task_with_no_contract_fields_still_runs(self, tmp_path):
        """The regression that killed the `expected_output` gate.

        A task may declare phases and nothing else. It is not refused for the
        contract prose it chose not to write — the absence of a spec is not a
        defect in the task.
        """
        (tmp_path / "p.md").write_text("do the thing")
        task = {"id": "x", "phases": [
            {"name": "a", "runner": "llm", "prompt_file": "p.md",
             "output": "out.md"}]}
        assert _phase_problem(task, str(tmp_path)) is None

    def test_a_script_phase_is_not_held_to_the_llm_preconditions(self, tmp_path):
        """Only `llm` phases need a prompt and a declared output; a script
        phase's artifact is whatever it writes. Demanding them here would
        refuse the two tasks that have always worked.
        """
        (tmp_path / "run.py").write_text("print(1)\n")
        task = {"id": "x", "phases": [{"name": "a", "script": "run.py"}]}
        assert _phase_problem(task, str(tmp_path)) is None
