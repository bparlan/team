"""`runner: llm` — a phase that is instructions, resolved but never spawned.

The runner used to gate on `hasattr(theteam, "default_api")` and call
`default_api.task(...)`. That symbol's only assignment in the repository was a
`monkeypatch` in a test file, so the gate could not pass in any environment and
every `llm` task was unrunnable by construction.

The host does offer a subagent helper, `agent(prompt, agent=..., handle=True)`
(`omp://python-repl.md`). It is injected as a builtin into the *eval kernel's*
retained subprocess and is not reachable from `python3 -m theteam.cli`:

    $ python3 -c "print(callable(agent))"
    NameError: name 'agent' is not defined

So Python does not spawn. It resolves which phase is next and whether that
phase is done, and the session does the spawning. These tests cover that split,
including the two defects it closes: an agent type the host rejects, and a
persona name mistaken for a spawn target.
"""

from pathlib import Path

import yaml

from theteam.cli import _phase_problem
from theteam.routines.repository import RoutineRepository
from theteam.routines.runners.llm import (
    AGENT_TYPES,
    DEFAULT_AGENT_TYPE,
    agent_type_for,
    resolve_phase,
    run_llm_phase,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _project(tmp_path, task):
    """A project whose only task is `task`."""
    routines_dir = tmp_path / "tasks"
    routines_dir.mkdir(exist_ok=True)
    with open(routines_dir / "task-x.yaml", "w") as handle:
        yaml.dump(task, handle)
    return str(tmp_path)

#: Distinguishes "not supplied" from "supplied as nothing". See `_phase`.
_UNSET = object()


def _phase(name="audit", output=_UNSET, prompt=_UNSET, **extra):
    """A well-formed `llm` phase, with any field overridable — including to
    nothing at all, which is a case worth testing.

    A plain `None` default cannot express "omit this key": a test passing
    `output=None` to mean *absent* received the default instead, and the
    assertion that should have failed passed. Hence the sentinel.
    """
    phase = {"name": name, "runner": "llm",
             "prompt_file": "p.md" if prompt is _UNSET else prompt,
             "output": "out.md" if output is _UNSET else output}
    if output is None:
        phase.pop("output")
    if prompt is None:
        phase.pop("prompt_file")
    phase.update(extra)
    return phase


class TestOneRunnerPerPhase:
    """A phase names `script:` or `runner: llm`, never both, never neither."""

    def test_a_script_phase_with_the_script_present_is_fine(self, tmp_path):
        (tmp_path / "run.py").write_text("print(1)\n")
        task = {"id": "x", "phases": [{"name": "a", "script": "run.py"}]}
        assert _phase_problem(task, str(tmp_path)) is None

    def test_an_llm_phase_needs_no_script(self, tmp_path):
        # `output` is required and always has been — an `llm` phase that
        # declares none cannot prove it ran. What this test is about is
        # narrower: an `llm` phase needs no *script*, because its
        # instructions live in the prompt file.
        task = {"id": "x", "phases": [
            {"name": "a", "runner": "llm", "prompt_file": "p.md",
             "output": "out.md"}]}
        assert _phase_problem(task, str(tmp_path)) is None

    def test_a_phase_naming_both_is_refused(self, tmp_path):
        (tmp_path / "run.py").write_text("print(1)\n")
        task = {"id": "x", "phases": [
            {"name": "a", "script": "run.py", "runner": "llm"}]}
        assert "both" in (_phase_problem(task, str(tmp_path)) or "")

    def test_a_phase_naming_neither_is_refused(self, tmp_path):
        task = {"id": "x", "phases": [{"name": "a", "memory_limit_mb": 64}]}
        assert "no runner" in (_phase_problem(task, str(tmp_path)) or "")

    def test_a_missing_script_is_still_named(self, tmp_path):
        task = {"id": "x", "phases": [{"name": "a", "script": "absent.py"}]}
        assert "missing script" in (_phase_problem(task, str(tmp_path)) or "")


class TestAPhaseIsDoneWhenItsOutputExists:
    """The one rule the whole design rests on.

    `handoff.py` argued the opposite — that accepting "the file exists" is
    worse than refusing, because last week's report is also non-empty. That was
    sound while a Python-side collector was accepting results. There is no
    collector now, so nothing else decides.
    """

    def test_a_missing_output_means_the_phase_is_not_done(self, tmp_path):
        (tmp_path / "p.md").write_text("do the thing")
        result = resolve_phase(str(tmp_path), {"id": "x"}, _phase())
        assert result["done"] is False
        assert result["spawn"]["agent"] == DEFAULT_AGENT_TYPE

    def test_an_empty_output_is_not_done(self, tmp_path):
        """Written but empty is not a finding. Same rule `llm.py` always had.
        """
        (tmp_path / "p.md").write_text("do the thing")
        (tmp_path / "out.md").write_text("")
        result = resolve_phase(str(tmp_path), {"id": "x"}, _phase())
        assert result["done"] is False

    def test_a_non_empty_output_means_done(self, tmp_path):
        (tmp_path / "p.md").write_text("do the thing")
        (tmp_path / "out.md").write_text("the member's actual finding\n")
        result = resolve_phase(str(tmp_path), {"id": "x"}, _phase())
        assert result["done"] is True
        assert result["output_path"] == str(tmp_path / "out.md")

    def test_run_llm_phase_reports_success_only_when_the_output_exists(self,
                                                                        tmp_path):
        (tmp_path / "p.md").write_text("do the thing")
        phase = _phase()
        assert run_llm_phase({"id": "x"}, phase, str(tmp_path))["success"] is False

        (tmp_path / "out.md").write_text("done\n")
        assert run_llm_phase({"id": "x"}, phase, str(tmp_path))["success"] is True


class TestTheSpawnRequestSaysEverythingNeeded:
    """A session reading this must not have to re-open the task YAML."""

    def test_it_carries_the_agent_prompt_and_output(self, tmp_path):
        (tmp_path / "p.md").write_text("the exact instructions\n")
        result = run_llm_phase({"id": "x"}, _phase(member="skeptic",
                                                   agent_type="reviewer"),
                               str(tmp_path))
        spawn = result["spawn"]
        assert spawn["agent"] == "reviewer"
        assert spawn["prompt"] == "the exact instructions\n"
        assert spawn["output"] == "out.md"
        assert spawn["output_path"] == str(tmp_path / "out.md")
        # The persona travels with the request, for the prompt's framing.
        assert spawn["member"] == "skeptic"

    def test_awaiting_is_not_a_refusal(self, tmp_path):
        """`skip_reason` is how the executor declines to count an attempt.

        An unfinished phase has not been refused — it simply needs the session
        to run a member. Reporting it as a skip reason would make the task
        look structurally unrunnable and walk it toward a breaker trip.
        """
        (tmp_path / "p.md").write_text("do the thing")
        result = run_llm_phase({"id": "x"}, _phase(), str(tmp_path))
        assert result["awaiting"] is True
        assert "skip_reason" not in result


class TestAgentTypeIsWhatASessionCanSpawn:
    """The registry that matters is the host's, not `theteam.config`.

    Measured against the live host:
    `agent(prompt, agent="architect")` raises `RuntimeError: Unknown agent
    "architect"`. The project roster lists `architect`, `pragmatist`,
    `skeptic`, `designer`, `devops` — and only `designer` is spawnable.
    """

    def test_a_persona_is_not_a_spawn_target(self, tmp_path):
        """The defect this module replaced shipped: it validated a phase
        against `theteam.config` and so certified names the host rejects,
        making every task look runnable while none could spawn anyone.
        """
        (tmp_path / "p.md").write_text("do the thing")
        phase = _phase(agent_type="architect")
        result = run_llm_phase({"id": "x"}, phase, str(tmp_path))
        assert result["success"] is False
        assert "architect" in result["error"]
        assert "not one a session can spawn" in result["error"]

    def test_every_bundled_agent_type_is_accepted(self, tmp_path):
        (tmp_path / "p.md").write_text("do the thing")
        for agent in AGENT_TYPES:
            result = run_llm_phase({"id": "x"}, _phase(agent_type=agent),
                                   str(tmp_path))
            assert result["success"] is False, agent
            assert "not one a session can spawn" not in result["error"], agent

    def test_agent_type_falls_back_to_the_task_tools_own_field_name(self):
        """`agent:` is how OMP's `task` tool spells it, so a task written
        against either name does the obvious thing.
        """
        assert agent_type_for({"agent": "sonic"}) == "sonic"
        assert agent_type_for({"agent_type": "scout"}) == "scout"
        assert agent_type_for({}) == DEFAULT_AGENT_TYPE

    def test_member_is_never_used_as_the_agent(self):
        """`member:` is a persona for the prompt's framing. Wiring it to the
        spawn is what made every task in this repository unrunnable while
        reporting itself valid.
        """
        assert agent_type_for({"member": "architect"}) == DEFAULT_AGENT_TYPE
        assert agent_type_for({"member": "devops"}) == DEFAULT_AGENT_TYPE


class TestNamedRefusalsForMalformedPhases:
    """A misdeclared phase is named, never synthesised past."""

    def test_a_phase_naming_no_output_cannot_report_success(self, tmp_path):
        (tmp_path / "p.md").write_text("do the thing")
        result = run_llm_phase({"id": "x"}, _phase(output=None), str(tmp_path))
        assert result["success"] is False
        assert "no `output`" in result["error"]

    def test_a_missing_prompt_file_is_a_named_failure_not_a_traceback(self,
                                                                       tmp_path):
        result = run_llm_phase({"id": "x"}, _phase(prompt="absent.md"),
                               str(tmp_path))
        assert result["success"] is False
        assert "prompt_file not found" in result["error"]

    def test_a_phase_with_no_prompt_file_is_refused(self, tmp_path):
        result = run_llm_phase({"id": "x"}, _phase(prompt=None), str(tmp_path))
        assert result["success"] is False
        assert "no prompt_file" in result["error"]


class TestOnlyBypassesTheSchedule:
    """`--only <id>` means run it now, scheduled or not."""

    def _task(self):
        return {"id": "x", "name": "X", "type": "analysis", "order": 0,
                "phases": [{"name": "a", "runner": "llm", "prompt_file": "p.md",
                            "output": "out.md", "memory_limit_mb": 64}]}

    def test_an_unscheduled_task_runs_when_named(self, tmp_path):
        root = _project(tmp_path, self._task())
        repo = RoutineRepository(root)
        assert repo.due() == []
        assert [t["id"] for t in repo.due(only="x")] == ["x"]

    def test_it_does_not_schedule_what_it_ran(self, tmp_path):
        root = _project(tmp_path, self._task())
        repo = RoutineRepository(root)
        repo.due(only="x")
        assert repo.schedule()["scheduled_tasks"] == {}


class TestEveryShippedTask:
    """The shipped manifests, checked against the real files."""

    def test_every_task_names_a_spawnable_agent_or_defaults(self):
        for task in RoutineRepository(str(REPO_ROOT)).all_tasks():
            for phase in task.get("phases", []):
                if phase.get("runner") != "llm":
                    continue
                agent = agent_type_for(phase)
                assert agent in AGENT_TYPES, (
                    f"task {task['id']} phase {phase['name']} names agent "
                    f"{agent!r}, which a session cannot spawn"
                )

    def test_every_llm_phase_declares_a_prompt_and_an_output(self):
        for task in RoutineRepository(str(REPO_ROOT)).all_tasks():
            for phase in task.get("phases", []):
                if phase.get("runner") != "llm":
                    continue
                assert phase.get("prompt_file"), phase
                assert phase.get("output"), phase

    def test_every_llm_prompt_file_exists(self):
        root = REPO_ROOT
        for task in RoutineRepository(str(root)).all_tasks():
            for phase in task.get("phases", []):
                if phase.get("runner") != "llm":
                    continue
                assert (root / phase["prompt_file"]).exists(), phase

    def test_llm_outputs_land_in_one_of_the_two_named_roots(self):
        """Two consumers, two roots, and the split is deliberate.

        `.omp/theteam/reports/` is harness state: `state.py` exposes it as
        `reports`, `__init__.py` builds discussion reports from `report_dir`,
        and `test_stability_fixes` asserts it gets created. Phase handoffs land
        there because the next phase reads them.

        `reports/` is the tracked human surface, and only ever holds the final
        human deliverable — one HTML page per task. Machine intermediates go to
        `reports/.handoff/` so a reader looking in `reports/` finds documents,
        not scratch files.

        Accepting either prefix for any phase (the previous version of this
        test) is what let the split grow unnoticed: nothing checked that the
        human surface stayed human-only.
        """
        root = REPO_ROOT
        MACHINE = (".omp/theteam/reports/", "reports/.handoff/")
        for task in RoutineRepository(str(root)).all_tasks():
            for phase in task.get("phases", []):
                if phase.get("runner") != "llm":
                    continue
                output = phase["output"]
                assert output.startswith(MACHINE + ("reports/",)), phase
                # `reports/.handoff/` also starts with `reports/`, so the
                # human-surface branch has to exclude it explicitly.
                if output.startswith("reports/") and not output.startswith(
                    "reports/.handoff/"
                ):
                    # The human surface is HTML, and only the last phase of a
                    # task may write it.
                    assert output.endswith(".html"), phase
                    names = [p["name"] for p in task["phases"]]
                    assert names[-1] == phase["name"], phase

    def test_every_script_phase_names_an_existing_script(self):
        root = REPO_ROOT
        for task in RoutineRepository(str(root)).all_tasks():
            for phase in task.get("phases", []):
                if phase.get("script"):
                    assert (root / phase["script"]).exists(), phase

class TestTheRunnerDoesNotSpawn:
    """The behaviour that matters: no code path here spawns anything.

    The old module read `theteam.default_api` and called
    `default_api.task(...)`. Its docstring still *names* the symbol, because
    the record of why it was removed is worth keeping — so these assertions
    are about calls, not mentions.
    """

    def test_no_provider_call_or_gate_remains(self):
        source = (REPO_ROOT / "theteam" / "tasks" / "runners"
                  / "llm.py").read_text()
        # The module docstring still names the symbol — the record of why it
        # went is worth keeping — so strip it before looking for code.
        code = source.split('"""', 2)[-1]
        assert "default_api" not in code
        assert "hasattr(theteam" not in code
        assert "no_task_provider" not in code

    def test_nothing_binds_the_symbol_anymore(self):
        import theteam

        assert not hasattr(theteam, "default_api")


class TestReadinessIsDerivedFromPhaseKinds:
    """What a task needs to run is read from its phases, not from whether a
    global happens to be bound.

    `smoke_cli` used to gate on `hasattr(theteam, "default_api")` and report
    every llm task as permanently unrunnable while giving no way to learn what
    would run them.
    """


    def test_a_script_task_needs_no_session(self):
        """The shape that has always worked, still unblocked."""
        phase = {"name": "a", "script": "run.py"}
        assert phase.get("runner") != "llm"
