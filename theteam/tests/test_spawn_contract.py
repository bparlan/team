#!/usr/bin/env python3
"""The spawn parameters every member and llm phase actually sends.

This suite passed 792 tests while every `runner: llm` phase and every
discussion member was rejected at OMP task preflight. The reason: each
component was tested against a stub that accepts whatever it is handed,
so `"isolated": true` was asserted nowhere against the real bridge.

The bridge rejects it with:

    Subagent isolated execution requires task.isolation.mode to be set;
    current mode is "none".

Measured 2026-10-02 against the live bridge. Passing `"isolated": true`
*alongside* `"isolation": {"mode": "worktree"}` is rejected too — `worktree`
alone is the only form that spawns.

Two layers:

* a hermetic layer that asserts the three production spawn sites carry the
  accepted shape and no longer carry the rejected one. It needs no session.
* a live layer, marked and skipped by default, that spawns through the real
  bridge and fails on a preflight rejection. Run it in a session:

      pytest theteam/tests/test_spawn_contract.py -m live

The live test is what makes the next parameter drift a named failure instead
of a silent one.
"""

import inspect
import re

import pytest

import theteam
from theteam.tasks.runners import llm as llm_runner


def _spawn_sites():
    """Every dict literal that is handed to a provider's `task()` call.

    Located by source, not by a hardcoded line number — a line-based
    assertion is a maintenance trap that fails on every unrelated edit above
    it, which is how a real regression gets ignored as noise.
    """
    sources = {
        "spawn_member_task": inspect.getsource(theteam.spawn_member_task),
        "run_discussion_intro": inspect.getsource(theteam.run_discussion),
        "run_llm_phase": inspect.getsource(llm_runner.run_llm_phase),
    }
    return sources


#: The rejected form, and the preflight message that names it.
REJECTED_KEY = "isolated"
ACCEPTED = '"isolation": {"mode": "worktree"}'


class TestSpawnParametersAreTheAcceptedShape:
    """Hermetic: production spawn sites carry the form the bridge accepts."""

    @pytest.mark.parametrize("name", ["spawn_member_task", "run_discussion_intro"])
    def test_discussion_sites_isolate_by_mode(self, name):
        source = _spawn_sites()[name]
        assert ACCEPTED in source, (
            f"{name} must isolate members with {ACCEPTED}; the bridge "
            f"rejects the bare `isolated` flag at preflight"
        )

    def test_llm_phase_isolates_by_mode(self):
        source = _spawn_sites()["run_llm_phase"]
        assert ACCEPTED in source, (
            f"run_llm_phase must isolate its member with {ACCEPTED}; this is "
            f"the only spawn path for `runner: llm` tasks"
        )

    @pytest.mark.parametrize("name", [
        "spawn_member_task", "run_discussion_intro", "run_llm_phase",
    ])
    def test_no_site_passes_the_bare_isolated_flag(self, name):
        """`isolated` as a *task payload* key is the rejected form.

        `theteam/core/agent_isolation.py` reports `result["isolated"]` for a
        Docker container — a result field, not a spawn parameter, and out of
        scope here. This asserts on the three spawn sites only.
        """
        source = _spawn_sites()[name]
        offenders = [
            line.strip()
            for line in source.splitlines()
            if re.search(rf'"{REJECTED_KEY}"\s*:', line)
        ]
        assert not offenders, (
            f"{name} still passes the rejected spawn flag: {offenders}. "
            f"Use {ACCEPTED}; both keys together are rejected as well."
        )

    def test_agent_isolation_result_field_is_untouched(self):
        """The Docker `result["isolated"]` field is a different thing.

        Guarding it explicitly: a well-meaning sweep for `isolated: True`
        would otherwise delete a field two tests assert on, and the failure
        would read as a broken Docker layer rather than an over-broad search.
        """
        from theteam.core.agent_isolation import AgentIsolation
        source = inspect.getsource(AgentIsolation)
        assert '"isolated": True' in source, (
            "AgentIsolation._result must keep reporting `isolated: True` — "
            "it is a Docker result field, not an OMP spawn parameter"
        )


def _live_bridge_present() -> bool:
    """True only inside an OMP session's eval kernel.

    A module-level function rather than a method on the class below: a
    `skipif` referencing `TestAgainstTheLiveBridge` is evaluated while the
    class body is still executing, so the name does not exist yet and the
    whole module fails to collect.
    """
    import os
    return os.environ.get("PI_TOOL_BRIDGE_URL") is not None


needs_live_bridge = pytest.mark.skipif(
    not _live_bridge_present(),
    reason="no live OMP bridge (shell subprocess)",
)

@pytest.mark.live
@needs_live_bridge
class TestAgainstTheLiveBridge:
    """Live: the exact parameters production uses, against the real bridge.

    Skipped unless `PI_TOOL_BRIDGE_URL` is present, which is true only
    inside an OMP session's eval kernel. In a plain shell this whole class
    skips and the hermetic layer above is what runs.
    """

    def test_worktree_mode_is_accepted(self, tmp_path):
        """The parameter `spawn_member_task` sends actually spawns.

        Spawned, then cancelled immediately: the assertion is that
        preflight *passes*, which is decided synchronously at spawn. A
        subagent asked to do real work would cost minutes for a claim
        already decided at spawn time.
        """
        import asyncio

        async def _probe():
            return await tool.task({
                "i": "spawn contract",
                "context": "Preflight acceptance probe; the task body is ignored.",
                "tasks": [{
                    "task": "Reply with exactly: OK",
                    "name": "spawn_contract_probe",
                    "agent": "task",
                    "isolation": {"mode": "worktree"},
                }],
            })

        try:
            result = asyncio.get_event_loop().run_until_complete(_probe())
        except NameError:  # pragma: no cover - kernel shape dependent
            pytest.skip("no `tool` in this interpreter")

        text = str(result.get("text", ""))
        assert "failed preflight" not in text, (
            f"the accepted isolation form was rejected: {text}"
        )
        assert "isolated execution requires" not in text, (
            f"preflight still demands task.isolation.mode: {text}"
        )