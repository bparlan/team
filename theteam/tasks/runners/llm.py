#!/usr/bin/env python3
"""
theteam.tasks.runners.llm - run a task phase that is instructions, not a script.

§M9 Phase 4 adds a second kind of phase. A `script:` phase runs a Python
file; a `runner: llm` phase hands `prompt_file` to a team member and records
what it wrote. Both live under the same executor, the same breaker, and the
same `ok` / `failed` / `skipped` outcomes, so a run of the two kinds is
indistinguishable from the outside except by what it produced.

## The rule this module exists to enforce

**A missing provider is a named failure, never a synthesized result.** M0
removed `MockAPI` because the system's whole value is honest opinion, and M0
deleted it *for this shape of problem*: a function returning something
plausible when it had nothing. An `llm` phase outside an OMP session is
exactly that shape — the prompt is real, the member is not. So
`run_llm_phase` refuses, with the command to run inside OMP, exactly as
`run_discussion` does.

The prompt is never executed as a shell command and never partially
applied. An `llm` phase writes exactly one output file, and only when the
member actually produced one.

## What it is not

Not a synthesis engine, not a general agent loop, and not a second way to
run a script. `script:` remains the kind for anything deterministic, and
Phase 4 keeps a `pytest` phase as `script:` in `native-feature-loop`
precisely because a test suite is not a judgement call.
"""

import os
from typing import Any, Dict, Optional

#: The provider `theteam/__init__.py` exposes inside an OMP session. Named
#: once so the check and the call cannot disagree about what "the provider"
#: is — the M9 Phase 1 bug was two places believing two things about a
#: manifest that did not exist.
PROVIDER = "default_api"

#: Exit-code-free failure shape. A phase returns a dict; the executor reads
#: `success` and `error`, exactly as it does for a script phase. An `llm`
#: phase has no returncode, and inventing one would be a number nobody
#: measured.
NO_PROVIDER = "llm runner requires an OMP session"


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

    `None` when the phase names no output. An `llm` phase that produces a
    result nobody reads is still recorded in the execution log, so this is
    about durability, not about whether the phase ran.
    """
    output = phase.get("output")
    if not output:
        return None
    return os.path.join(project_root, output)


def run_llm_phase(task: Dict[str, Any], phase: Dict[str, Any],
                  project_root: str) -> Dict[str, Any]:
    """Run one `runner: llm` phase. Returns the same shape a script phase does.

    Three outcomes, matching `execute_phase`:

    * `{"success": True, "output_path": ...}` — the member ran and wrote.
    * `{"success": False, "error": "llm runner requires an OMP session"}` —
      no provider. A failure, not a skip: the task did not do its work.
    * `{"success": False, "error": "..."}` — a named refusal, such as a
      missing `prompt_file` or a member that is not on the roster.
    """
    name = phase.get("name", "?")

    # A missing `prompt_file` is a named failure, not a traceback: the
    # executor reads `phase_result["success"]` and has no except clause for
    # a raised FileNotFoundError, so raising here would take down `theteam
    # run` with a stack trace instead of naming the phase.
    try:
        prompt = _read_prompt(project_root, phase)
    except (FileNotFoundError, OSError) as error:
        return {"success": False, "error": f"phase '{name}': {error}"}

    import theteam

    if not hasattr(theteam, PROVIDER):
        task_id = task.get("id", "?")
        return {
            "success": False,
            # `skip_reason`, not just `error`: the task did not fail, it never
            # got to run. The executor reads this and declines to count the
            # attempt, so a machine with no OMP session does not walk three
            # tasks into a breaker trip that can never be cleared.
            "skip_reason": "no_task_provider",
            "error": (f"{NO_PROVIDER} (phase '{name}')."),
            # The old text said "run this inside an OMP session, where a task
            # provider is bound" — advice that cannot be followed. A session
            # reading it while already inside an OMP session is told to find a
            # flag that does not exist, which `SKILL.md` explicitly warns
            # against. The spawn is still the session's job; the only thing
            # that changed is that the message now says which command does it.
            "hint": (f"this task is unspawned, not blocked. Re-run with a run id "
                     f"and let the session drive the members:\n"
                     f"    theteam run --only {task_id} --run-id <id>"),
        }

    member_id = phase.get("member")
    if not member_id:
        return {
            "success": False,
            "error": f"phase '{name}': runner is llm but names no member",
        }

    api = getattr(theteam, PROVIDER)
    outcome = api.task(
        i=f"Task phase: {name}",
        context=f"Phase of task {task.get('id', '?')}",
        tasks=[{
            "task": prompt,
            "agent": "task",
            "name": f"{name}_{member_id}",
            "isolated": True,
        }],
    )

    # A bound provider is not automatically a well-behaved one. `tool.task`
    # in an OMP eval kernel returns `{"text", "details"}` — no `tasks` key at
    # all — and a provider that returned a bare string raised
    # `AttributeError: 'str' object has no attribute 'get'` out of the phase
    # loop, which is a crash where §3.3 requires a named refusal. Measured,
    # not assumed: all three shapes are in the test that guards this.
    #
    # It is a refusal, not a failure, for the reason `no_task_provider` is
    # one: a provider that cannot answer the contract it was bound to is
    # structurally incapable of running this task, so counting it would walk
    # the task toward a breaker trip that nothing can clear.
    if not isinstance(outcome, dict):
        return {
            "success": False,
            "skip_reason": "provider_contract_violated",
            "error": (f"phase '{name}': provider returned "
                      f"{type(outcome).__name__}, not a result envelope"),
            "hint": ("the bound provider did not answer the contract "
                     f"`run_llm_phase` reads. Expected a dict with a 'tasks' "
                     f"list of {{'name', 'handle'}} entries."),
        }
    if not isinstance(outcome.get("tasks"), list):
        return {
            "success": False,
            "skip_reason": "provider_contract_violated",
            "error": (f"phase '{name}': provider returned no 'tasks' list "
                      f"(keys: {sorted(outcome)})"),
            "hint": ("the bound provider did not answer the contract "
                     f"`run_llm_phase` reads. Expected a dict with a 'tasks' "
                     f"list of {{'name', 'handle'}} entries."),
        }
    # Each entry is read defensively for the same reason: a list of strings is
    # a plausible provider response and `r.get` on a str is the crash above
    # one level down.
    handles = {}
    for entry in outcome["tasks"]:
        if isinstance(entry, dict):
            handles[entry.get("name")] = entry.get("handle")
        else:
            return {
                "success": False,
                "skip_reason": "provider_contract_violated",
                "error": (f"phase '{name}': provider returned a "
                          f"{type(entry).__name__} in 'tasks', not a dict"),
                "hint": ("expected each entry to be "
                         f"{{'name': ..., 'handle': ...}}"),
            }
    handle = handles.get(f"{name}_{member_id}")
    if not handle:
        return {
            "success": False,
            "error": f"phase '{name}': no handle returned for member {member_id}",
        }

    try:
        produced = api.output(handle)
    except Exception as error:  # the provider's own failure, named not hidden
        return {"success": False, "error": f"phase '{name}': {error}"}

    target = _output_path(project_root, phase)

    # Validate before writing: a phase must declare an output to be considered successful
    if not target:
        return {
            "success": False,
            "error": (f"phase '{name}': runner is llm but names no `output`, "
                      f"so it cannot prove it ran"),
        }

    # Write the produced content to the target file
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle_out:
        handle_out.write(_render(produced))

    # After writing, verify the file is not empty. This closes the fabrication hole
    # where a session could handwrite a file and have it accepted as success.
    if os.path.getsize(target) == 0:
        return {
            "success": False,
            "error": f"phase '{name}': declared output {target} is empty",
        }

    return {
        "success": True,
        "output_path": target,
        "member": member_id,
    }


def _render(produced: Any) -> str:
    """What a phase writes when a member produced a result.

    A string is written as-is. Anything else is written as JSON, because a
    dict rendered with `str()` loses its structure and a reader cannot tell
    a list from a dict with one key.
    """
    if isinstance(produced, str):
        return produced
    import json
    return json.dumps(produced, indent=2, default=str)
