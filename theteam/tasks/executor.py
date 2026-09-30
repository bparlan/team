#!/usr/bin/env python3
"""
Task execution. Layer 3: runs one phase, collects its result.

Moved here from `subskills/task_stack/executor.py`, which §5.3 removes. The
safety wrapper lands on this class, not on a directory that is on its way out.

M4 changed what "runs a phase" means. A phase used to be a bare
`subprocess.run` in the orchestrator's own process space, sharing its
filesystem, its environment, and its resource budget. Now every phase runs
inside an `AgentIsolation` container carrying that phase's declared
`memory_limit_mb` as a hard ceiling (§5.1, §5.4). There is deliberately no
fallback to an unguarded run: if Docker is missing, or the phase carries no
bound, the phase is refused with the reason named. A guard that quietly
degrades to no guard is not a guard.
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from theteam.core.agent_isolation import AgentIsolation, IsolationError, IsolationPolicy
from theteam.core.audit_chain import record_task_event
from theteam.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig


# M4 wiring. §5.1: every phase runs inside an AgentIsolation container, so no
# Layer 3 call to subprocess is left without a Layer 4 guard in the same call
# frame. CircuitBreaker/ResourceLimiter/AuditLogger call sites live in the
# siblings' surfaces (S1, S3) and are not duplicated here.

# Image used for isolated phase execution. Override per environment; the
# default is a tag that exists on this machine (the bare `theteam` image
# does not). Kept as a named constant so the choice is visible and the
# literal is not scattered through the method body.
IMAGE_ENV_VAR = "THETEAM_AGENT_IMAGE"
DEFAULT_IMAGE = "theteam:p4final"

#: Where the project tree appears inside the container.
WORKSPACE_MOUNT = "/workspace"

#: A container killed for exceeding its memory bound exits 137 (SIGKILL).
#: `AgentIsolation.run` reports 124 when the wall-clock timeout fires.
OOM_KILL_EXIT_CODE = 137
TIMEOUT_EXIT_CODE = 124

#: Retention for the execution log: keep the newest N lines, drop the rest.
#: `ResourceLimiter` is a counter registry with no file retention path, so the
#: precedent for a bounded append-only log is `AuditLogger._enforce_retention`
#: (trim to newest, keep it parseable). The log was unbounded at 282 KB / 334
#: lines with no cap of any kind; `history` reads it, so it must stay finite.
EXECUTION_LOG_MAX_LINES = 1000


class TaskExecutor:
    def __init__(self, project_root: str = ".", breaker_states: Optional[Dict] = None):
        from theteam.state import StateStore

        self.project_root = Path(project_root)
        self.execution_log = StateStore(str(self.project_root)).execution_log
        # Per-task breakers, keyed by task id. §7.1.5: five consecutive
        # failures trips one and the task stops burning cycles. The threshold
        # is passed explicitly so the number is visible at the call site and
        # not an invisible default the reader has to open the component to find.
        self.breakers: Dict[str, CircuitBreaker] = {}
        # Real breaker state from earlier runs, `{task_id: {"breaker": ...,
        # "breaker_consecutive_failures": N}}`. The caller reads it and hands
        # it over: §5.1 puts the schedule in Layer 2 and this file in Layer 3,
        # so the executor does not open the schedule file itself.
        self.breaker_states: Dict[str, Dict] = breaker_states or {}

    def _breaker(self, task_id: str) -> CircuitBreaker:
        """The breaker for a task, created lazily and held for the process.

        A process is not the lifetime of a task, so a breaker starts from what
        was really measured for it: `record_failure()` is replayed once per
        consecutive failure an earlier run recorded, which re-drives the
        component's own state machine to where it genuinely was. Assigning
        `stats.state` would be a trip the breaker never evaluated.

        The stored `breaker` string is a rendering of that state for
        `theteam tasks`, not the input here. `record_run` always writes both
        from one outcome, so the two cannot disagree unless the state file was
        edited by hand.
        """
        if task_id not in self.breakers:
            breaker = CircuitBreaker(
                task_id,
                CircuitBreakerConfig(failure_threshold=5),
            )
            measured = self.breaker_states.get(task_id, {}).get(
                "breaker_consecutive_failures"
            )
            if isinstance(measured, int) and not isinstance(measured, bool):
                for _ in range(max(0, measured)):
                    breaker.record_failure()
            self.breakers[task_id] = breaker
        return self.breakers[task_id]

    def execute_phase(self, phase: Dict, task: Optional[Dict] = None) -> Dict:
        """
        Run one phase. Two kinds, M9 Phase 4.

        `script:` runs a Python file inside a bounded container. `runner: llm`
        hands a `prompt_file` to a team member; there is no container,
        because there is no process to bound — the bound that matters is
        that it refuses by name when no provider is bound.

        Three refusals for a script phase, each naming its own reason, and
        none falling back to a bare process:

          * no `memory_limit_mb` - the bound is mandatory, so a phase whose
            file was hand-edited past the write path is refused rather than
            run under an invented default (§5.4, §3.3).
          * no Docker - isolation is not optional, so the phase is refused
            rather than executed unguarded (§5.1).
          * no `script` - refused rather than silently treated as an llm
            phase, which is the silent-skip hole §3.3 forbids.

        A container that exceeds its bound is killed, not left running: the
        OOM kill exits 137, and that code is named in the result so the kill
        is observable rather than inferred (§7.1.6).
        """
        if phase.get("runner") == "llm":
            from theteam.tasks.runners.llm import run_llm_phase
            return run_llm_phase(task or {}, phase, str(self.project_root))

        script = phase.get("script")
        args = phase.get("args", [])
        timeout = phase.get("timeout_seconds", 300)
        name = phase.get("name", "?")

        if not script:
            return {
                "success": False,
                "error": (
                    f"Phase '{name}' has no script and no runner: "
                    f"a phase names exactly one of script or runner: llm"
                ),
            }

        script_path = self.project_root / script
        if not script_path.exists():
            return {"success": False, "error": f"Script not found: {script}"}

        memory_limit_mb = phase.get("memory_limit_mb")
        if not memory_limit_mb:
            return {
                "success": False,
                "error": (
                    f"Phase '{name}' has no memory_limit_mb: the bound is "
                    f"mandatory, and no default may be invented for it"
                ),
            }

        if not AgentIsolation.available():
            return {
                "success": False,
                "error": (
                    f"Phase '{name}' refused: container isolation unavailable "
                    f"(no Docker daemon), and an unguarded run is not permitted"
                ),
            }

        writable = bool(phase.get("writable_project"))
        policy = IsolationPolicy(
            image=os.environ.get(IMAGE_ENV_VAR, DEFAULT_IMAGE),
            memory_limit=f"{memory_limit_mb}m",
            timeout_seconds=timeout,
            workdir=WORKSPACE_MOUNT,
            extra_run_args=_writable_mount_args(self.project_root) if writable else (),
        )

        # The host path means nothing inside the container; passing it would
        # make the failure read as a missing file rather than a bound.
        container_script = _container_script(self.project_root, script_path)
        command = ["python3", container_script] + [str(a) for a in args]

        iso = AgentIsolation(policy)
        try:
            result = iso.run(
                command,
                container_name=f"theteam-phase-{os.urandom(6).hex()}",
                # `project_root` is what makes the component mount the tree.
                # When we supply the writable mount ourselves, passing it too
                # would mount /workspace twice and Docker rejects the argv.
                project_root=None if writable else str(self.project_root),
            )
        except IsolationError as e:
            return {"success": False, "error": f"Isolation failed: {e}"}

        exit_code = result["exit_code"]
        outcome: Dict = {
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "returncode": exit_code,
            "isolated": result["isolated"],
        }
        if exit_code == OOM_KILL_EXIT_CODE:
            outcome["error"] = (
                f"Phase '{name}' exceeded its {memory_limit_mb}m bound and was "
                f"killed (exit code {OOM_KILL_EXIT_CODE}, OOM)"
            )
        elif exit_code == TIMEOUT_EXIT_CODE:
            outcome["error"] = f"Phase '{name}' timed out after {timeout}s"
        return outcome

    def execute_task(self, task_def: Dict) -> Dict:
        task_id = task_def["id"]
        breaker = self._breaker(task_id)

        # §1.2: an execution is in the chain before it runs, so a run that
        # kills the process still leaves the fact that it was attempted.
        record_task_event(str(self.project_root), "log_task_start", task_id, task_def)
        started_at = time.monotonic()

        if not breaker.allow_request():
            # §3.2: the task is skipped, and the reason is the literal
            # `breaker_open`. A skipped attempt is not a failure of the task,
            # so nothing is counted against it - the count stays where the trip
            # happened and the trip stays where it happened. The trip itself is
            # recorded, as its own event, so the trail shows why nothing ran.
            record_task_event(str(self.project_root), "log_state_change",
                              f"runnable:{task_id}", "breaker_open",
                              f"breaker open after "
                              f"{breaker.stats.consecutive_failures} failures")
            return {
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "phases": [],
                "overall_success": False,
                "skipped": True,
                "skip_reason": "breaker_open",
                "breaker": breaker.stats.state.value,
                "breaker_consecutive_failures": breaker.stats.consecutive_failures,
            }

        results = []
        for phase in task_def.get("phases", []):
            phase_result = self.execute_phase(phase, task_def)
            phase_result["phase"] = phase["name"]
            results.append(phase_result)
            if not phase_result["success"]:
                break

        overall_success = all(r["success"] for r in results)
        if overall_success:
            breaker.record_success()
        else:
            breaker.record_failure()

        # A real elapsed time, measured, for the entry the component writes.
        duration = round(time.monotonic() - started_at, 3)
        if overall_success:
            record_task_event(str(self.project_root), "log_task_complete",
                              task_id, {"success": True, "output": ""}, duration)
        else:
            record_task_event(str(self.project_root), "log_task_failed", task_id,
                              results[-1].get("error")
                              or f"returncode {results[-1].get('returncode')}",
                              "phase_failed")
        result = {
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phases": results,
            "overall_success": overall_success,
            "breaker": breaker.stats.state.value,
            "breaker_consecutive_failures": breaker.stats.consecutive_failures,
        }
        # §7.1.7: the execution log is what `theteam history` reads to turn a
        # run into a success rate and a last failure. This was the only writer
        # of the file and nothing in production called it, so history reported
        # `runs: 0` for tasks that had failed five times in a row. One call
        # site, here, so every caller of execute_task - the CLI, the loop, a
        # test - writes the record the reporting surface expects.
        self.log_execution(result)
        return result

    def log_execution(self, result: Dict):
        self.execution_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.execution_log, 'a') as f:
            f.write(json.dumps(result) + "\n")
        self._trim_execution_log()

    def _trim_execution_log(self) -> int:
        """Keep the newest EXECUTION_LOG_MAX_LINES lines. Returns lines dropped."""
        try:
            with open(self.execution_log, "r", encoding="utf-8") as handle:
                lines = handle.readlines()
        except OSError:
            return 0
        if len(lines) <= EXECUTION_LOG_MAX_LINES:
            return 0
        keep = lines[-EXECUTION_LOG_MAX_LINES:]
        with open(self.execution_log, "w", encoding="utf-8") as handle:
            handle.writelines(keep)
        return len(lines) - len(keep)


def _container_script(project_root: Path, script_path: Path) -> str:
    """The host script path rewritten for the container's mount point."""
    relative = os.path.relpath(script_path.resolve(), project_root.resolve())
    return f"{WORKSPACE_MOUNT}/{relative}"


def _writable_mount_args(project_root: Path) -> tuple:
    """
    A writable mount for a phase that declares it needs one.

    The component mounts the project read-only, so a phase that writes into
    the tree cannot work as-is. Only phases that ask are granted it:
    `scripts/sa_runner.py` writes its reports into the project root, and
    giving every phase a writable mount would let any script edit the repo
    and the state files under it.

    The mount goes through the policy's documented `extra_run_args` escape
    hatch rather than the component's `mode` field, because Docker's
    `--mount` parser rejects a bare `rw` field — omitting `mode` is how a
    bind mount is made writable.
    """
    return (
        "--mount",
        f"type=bind,source={project_root.resolve()},target={WORKSPACE_MOUNT}",
    )