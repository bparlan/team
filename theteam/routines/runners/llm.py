#!/usr/bin/env python3
"""
theteam.routines.runners.llm - run a task phase that is instructions, not a script.

A `script:` phase runs a Python file. A `runner: llm` phase is *instructions to
a model*, and this module does not run them. It resolves which phase is next and
whether that phase is done. Spawning belongs to the session, because spawning
is a capability that exists in the session and nowhere else.

## Why Python does not spawn, measured

This module used to gate every `llm` phase on `hasattr(theteam, "default_api")`
and call `default_api.task(...)`. That symbol's only assignment in the whole
repository was a `monkeypatch` in a test file, so the gate could not pass in any
environment — the refusal was correct everywhere and the tasks were unrunnable
by construction.

The host does offer a subagent helper, `agent(prompt, agent=..., handle=True)`
(`omp://python-repl.md`, `src/eval/agent-bridge.ts`). It is injected as a
builtin into the *eval kernel's* retained subprocess. It is not importable, not
an env var, and not on any port:

    $ python3 -c "print(callable(agent))"
    NameError: name 'agent' is not defined

Every call site here is `python3 -m theteam.cli` — a fresh process launched by
`bash`. So a provider adapter is not possible, and writing one would have been
a guess dressed as an integration. The gap is not a missing import; it is a
process boundary.

## The loop, in full

    1. theteam run --only <id>   → names the next phase: member, prompt path,
                                   output path. No spawn.
    2. the session spawns         → native `task` tool, writes the result to the
                                   declared output path.
    3. theteam run --only <id>   → the output exists and is non-empty, so the
                                   phase is done and the next one is named.

Three steps, no provider, no staging area, no run id. Re-running step 1 is
always safe: it either names the next unfinished phase or reports the task
complete.

## The one rule this module enforces

**A phase is done when its declared output exists and is not empty.**

That was once contested. `handoff.py` argued the opposite — that accepting "the
file exists" is worse than refusing, because a report left over from last week
is also non-empty. That argument was sound *while a Python-side collector was
accepting results*. It no longer is: there is no collector, so nothing else
decides, and a phase that cannot produce its declared artifact has not run.

The honest cost: a stale output reads as done. That is the price of the simplest
thing that works, and the remedy is visible — delete the output to re-run. A
run manifest would fix it and is exactly the bookkeeping this design exists to
avoid.

## What this is not

Not a synthesis engine, not an agent loop, and not a second way to run a script.
`script:` remains the kind for anything deterministic, and
`native-feature-loop` keeps its `pytest` phase as `script:` precisely because a
test suite is not a judgement call.
"""

import os
from typing import Any, Dict, Optional

#: The agent types a session can actually spawn. Measured against the host's
#: own registry — `agent(prompt, agent="architect")` raises
#: `RuntimeError: Unknown agent "architect"` — so this list is what a phase may
#: name, and it is deliberately not read from `theteam.config`.
#:
#: That config lists project *personas* (`architect`, `pragmatist`, `skeptic`,
#: `designer`, `devops`), and a persona is not a spawn target. Validating a
#: phase against it certifies a name the host rejects, which is worse than no
#: check at all: the task reports itself runnable and then cannot spawn anyone.
AGENT_TYPES = (
    "advisor", "default", "designer", "explore", "scout", "task",
    "Tester", "vision", "reviewer", "security-reviewer", "librarian", "sonic",
)

#: The agent a phase gets when it names none. `task` is the general-purpose
#: agent, and the one the previous hardcoded `"agent": "task"` used.
DEFAULT_AGENT_TYPE = "task"


def _read_prompt(project_root: str, phase: Dict[str, Any]) -> str:
    """The prompt text, or a named failure.

    A `prompt_file` that does not exist is refused rather than replaced with
    a summary of the phase: a prompt nobody wrote is not a short prompt.
    """
    path = phase.get("prompt_file")
    if not path:
        raise FileNotFoundError(
            f"phase '{phase.get('name', '?')}': runner is llm but names no prompt_file")
    full = os.path.join(project_root, path)
    if not os.path.exists(full):
        raise FileNotFoundError(
            f"phase '{phase.get('name', '?')}': prompt_file not found: {path}")
    with open(full, "r", encoding="utf-8") as handle:
        return handle.read()


def _output_path(project_root: str, phase: Dict[str, Any]) -> Optional[str]:
    """Where this phase's result goes, relative to the project root.

    `None` when the phase names no output. Such a phase cannot report success:
    an `llm` phase that produces a result nobody reads has no evidence it ran.
    """
    output = phase.get("output")
    if not output:
        return None
    return os.path.join(project_root, output)


def agent_type_for(phase: Dict[str, Any]) -> str:
    """The agent type a session should spawn for this phase.

    A phase may name `agent_type:` directly. Failing that it falls back to
    `agent:`, which is the field OMP's own `task` tool spells that way, so a
    task written against either name does the obvious thing.

    `member:` is deliberately not consulted. It names a project persona for the
    prompt's framing — "You are the skeptic" — and personas are not spawn
    targets. Wiring it to the spawn was the mistake that made every task in
    this repository look runnable while naming agents the host rejects.
    """
    return (phase.get("agent_type") or phase.get("agent")
            or DEFAULT_AGENT_TYPE)


def _exists_nonempty(target: str) -> bool:
    return os.path.exists(target) and os.path.getsize(target) > 0


def resolve_phase(project_root: str, task: Dict[str, Any],
                  phase: Dict[str, Any]) -> Dict[str, Any]:
    """What the session must do for this phase, and whether it is already done.

    Two outcomes, and the second is not an error:

    * `{"done": True, "output_path": ...}` — the declared output exists and is
      not empty. The phase is finished; move to the next one.
    * `{"done": False, "spawn": {...}}` — everything the session needs to run
      the member: the agent type, the prompt text, and where to write it.

    Refusals — a missing `prompt_file`, a missing `output`, an agent type the
    host does not offer — are raised by the caller as named errors. This
    function answers only "is it done, and if not what is needed".
    """
    name = phase.get("name", "?")
    target = _output_path(project_root, phase)

    if target is None:
        return {"done": False, "phase": name,
                "error": (f"phase '{name}': runner is llm but names no "
                          f"`output`, so it cannot prove it ran")}
    if _exists_nonempty(target):
        return {"done": True, "phase": name, "output_path": target}

    try:
        prompt = _read_prompt(project_root, phase)
    except (FileNotFoundError, OSError) as error:
        return {"done": False, "phase": name, "error": f"phase '{name}': {error}"}

    agent = agent_type_for(phase)
    if agent not in AGENT_TYPES:
        from theteam.core.capability import capability_surface
        surface = capability_surface(project_root)
        return {"done": False, "phase": name,
                "error": (f"phase '{name}': agent_type '{agent}' is not "
                          f"one a session can spawn (measured "
                          f"spawnable_agents has {len(surface['spawnable_agents'])} "
                          f"entries: {', '.join(surface['spawnable_agents'])})")}
    return {
        "done": False,
        "phase": name,
        "spawn": {
            "agent": agent,
            "member": phase.get("member"),
            "prompt_file": phase.get("prompt_file"),
            "prompt": prompt,
            "output": phase.get("output"),
            "output_path": target,
        },
    }


def run_llm_phase(task: Dict[str, Any], phase: Dict[str, Any],
                  project_root: str) -> Dict[str, Any]:
    """Resolve one `runner: llm` phase. Never spawns.

    Returns the same shape `execute_phase` reads, so the executor, the breaker
    and the CLI are unchanged:

    * `{"success": True, "output_path": ...}` — the phase is done.
    * `{"success": False, "awaiting": True, "spawn": {...}}` — the phase needs
      the session to run a member. Not a failure and not a refusal: the task
      did not fail, it has not been asked to do this phase yet.
    * `{"success": False, "error": "..."}` — a named defect in the task's own
      declaration: no `prompt_file`, no `output`, or an agent type the host
      does not offer.
    """
    resolved = resolve_phase(project_root, task, phase)
    name = resolved.get("phase", "?")

    if resolved.get("done"):
        return {"success": True, "output_path": resolved["output_path"],
                "phase": name}

    if resolved.get("error"):
        return {"success": False, "error": resolved["error"]}

    return {
        "success": False,
        # `awaiting`, not `skip_reason`: the executor must NOT decline to count
        # this as a refusal. A refusal means "this task structurally cannot
        # run here". This means "this phase is next, and the session is the
        # one that runs it" — the normal state of every unfinished llm phase.
        "awaiting": True,
        "spawn": resolved["spawn"],
        "error": (f"phase '{name}': output {phase.get('output')} does not exist "
                  f"yet — spawn `{resolved['spawn']['agent']}` and write the "
                  f"result there"),
    }


__all__ = [
    "AGENT_TYPES",
    "DEFAULT_AGENT_TYPE",
    "agent_type_for",
    "resolve_phase",
    "run_llm_phase",
]
