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
from datetime import datetime, timedelta, timezone
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


# §7.2: an exit code carries a meaning, and there are three of them here rather
# than two. `0` is "the phase ran and found nothing", `1` is "the phase ran and
# found something" — which is a check WORKING, not a phase breaking — and `2` is
# "the phase could not evaluate at all" (a dependency missing, input unreadable),
# which is the only non-zero code that means the phase itself is defective.
#
# Before this, a check that correctly detected a real problem exited 1, which
# `execute_task` read as failure and passed to `breaker.record_failure()`. Five
# genuine detections therefore opened the breaker permanently and the task
# stopped running — the project's real defect became permanently unmonitored,
# and the trip only cleared when the problem was fixed by something nobody was
# watching. Measured: 5 correct detections -> `allow_request() == False`.
# A monitor that disables itself on success is worse than no monitor, because
# it looks healthy in `theteam tasks` while checking nothing.
# 3, not 1: Python exits 1 on an uncaught exception, so a findings code of 1
# would read a crash as a clean measurement. A crash must never look like a
# result — that is the defect class this taxonomy exists to close.
FINDINGS_EXIT_CODE = 3
CANNOT_EVALUATE_EXIT_CODE = 2
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

        # `depends_on` gate state: the last measured result per task id, read
        # from the schedule the caller handed in. §5.1 keeps the schedule in
        # Layer 2, so the executor never opens the file — it is told.
        #
        # Before this, `order` was the only relationship between tasks and
        # nothing read it: it sorted a listing and gated nothing. A task
        # that consumed another task's output — `doc-harmonization` reading
        # `ground-truth-audit` — said so only in prompt prose, so the two
        # could run in either order, concurrently, or not at all.
        self.last_results: Dict[str, str] = {
            task_id: str(state.get("result"))
            for task_id, state in (breaker_states or {}).items()
            if isinstance(state, dict) and state.get("result") is not None
        }

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
            stored = self.breaker_states.get(task_id, {})
            measured = stored.get("breaker_consecutive_failures")
            if isinstance(measured, int) and not isinstance(measured, bool):
                for _ in range(max(0, measured)):
                    breaker.record_failure()
                # Replaying the failures re-derives the count and the state, but
                # `record_failure` also stamps `recovery_deadline = now + 60s` --
                # so the deadline is measured from *this process*, every time.
                # Since a CLI invocation lives milliseconds and `serve` rebuilds
                # the executor on every tick, the window could never elapse: the
                # breaker reopened on each attempt and the task was permanently
                # unrunnable. Observed: `system-awareness` at 0.0% over 5 runs,
                # skipped `breaker_open` on every attempt, including a 140s
                # `serve` with a 20s tick.
                #
                # `at` is the moment the failures were actually recorded and is
                # already persisted, so the deadline is restored from it rather
                # than recomputed. Once the real window has passed,
                # `_evaluate_state` admits a probe exactly as it would have for
                # an in-process breaker.
                tripped_at = stored.get("at")
                if breaker.stats.state.value == "open" and tripped_at:
                    try:
                        when = datetime.fromisoformat(str(tripped_at))
                    except (TypeError, ValueError):
                        when = None
                    if when is not None:
                        if when.tzinfo is None:
                            when = when.replace(tzinfo=timezone.utc)
                        breaker.stats.recovery_deadline = when + timedelta(
                            seconds=breaker.config.recovery_timeout
                        )
                        breaker._evaluate_state()
            self.breakers[task_id] = breaker
        return self.breakers[task_id]

    def _dependency_refusal(self, task_def: Dict) -> Optional[Dict]:
        """Why this task must not run yet, or None if it may.

        A task declares `depends_on: [<task id>, ...]`. It runs only when every
        dependency has a last result of `ok`. Two cases are refusals rather
        than failures, because neither is anything wrong with this task:

        * **never run** — no result has been measured for the dependency, so
          there is no evidence it succeeded. Running anyway is how a
          consumer reads a stale or absent input and produces a confident
          answer from nothing.
        * **not ok** — the dependency ran and did not succeed. Its output is
          absent or untrustworthy, which is the same problem with a receipt.

        A *skipped* dependency counts as not-ok: it did not do its work, so
        whatever it would have produced is not on disk. A dependency that ran
        and reported findings is `ok` — it did its job, and whether the
        project has problems is not this gate's question.

        Neither refusal counts against this task's breaker. It has not been
        attempted, and a task that is merely waiting for a prerequisite must
        not walk to a breaker trip by being asked to run too early.
        """
        depends_on = task_def.get("depends_on") or []
        if not depends_on:
            return None
        unmet = []
        for dependency in depends_on:
            result = self.last_results.get(dependency)
            if result is None:
                unmet.append(f"{dependency} (never run)")
            elif result != "ok":
                unmet.append(f"{dependency} (last result: {result})")
        if not unmet:
            return None
        unmet_detail = "; ".join(unmet)
        return {
            "task_id": task_def["id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phases": [],
            "overall_success": False,
            "skipped": True,
            "skip_reason": "dependency_unmet",
            "unmet_dependencies": unmet,
            "hint": (f"unmet: {unmet_detail}. Run the dependencies first: "
                     f"theteam run --only <dependency>"),
        }

    def execute_phase(self, phase: Dict, task: Optional[Dict] = None,
                      on_output=None) -> Dict:
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

            # No staging, no run id, no collector. An `llm` phase is done when
            # its declared output exists and is not empty; until then it needs
            # the session to spawn a member, and the runner says exactly what.
            #
            # This replaces a two-file protocol: a staged `*.request.json`
            # pinning the prompt hash, a `*.result.meta.json` sidecar the
            # session wrote naming that hash, and an `accept_result` that
            # moved the result into place. All of it existed so a subprocess
            # could ask a session to run a model on its behalf and then verify
            # the answer's provenance. With nothing staging anything, the
            # provenance check had nothing to check and the protocol was three
            # files of bookkeeping around one boolean.
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
                on_output=on_output,
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
        elif exit_code == CANNOT_EVALUATE_EXIT_CODE:
            # The phase told us it could not measure. That is a defect of the
            # phase — a missing dependency or unreadable input — so it counts
            # as failure, named distinctly so a reader can tell "could not
            # check" from "checked and found a problem".
            outcome["success"] = False
            outcome["cannot_evaluate"] = True
            outcome["error"] = outcome.get("error") or (
                f"Phase '{name}' could not evaluate (exit code "
                f"{CANNOT_EVALUATE_EXIT_CODE})"
            )
        elif exit_code == FINDINGS_EXIT_CODE:
            # The phase ran to completion and found something. `success` stays
            # True because the phase did its job; `findings` records that it
            # reported something so `execute_task` can persist the fact without
            # advancing the breaker.
            #
            # This code is 3 and not 1 on purpose. Exit 1 is what Python raises
            # for an uncaught exception, so treating 1 as "findings" would read
            # a traceback as a clean measurement — the very defect class this
            # change exists to remove. A findings code has to be one a crash
            # cannot produce.
            outcome["success"] = True
            outcome["findings"] = True
            outcome["findings_output"] = result["stdout"]
        return outcome

    def execute_task(self, task_def: Dict, on_output=None) -> Dict:
        task_id = task_def["id"]
        breaker = self._breaker(task_id)

        # The dependency gate runs before anything else, including the audit
        # event: a task that is waiting on a prerequisite has not been
        # attempted, and recording a `task_start` for it would put a start on
        # record with no matching finish — which is the same dangling-start
        # shape the audit already has 64 of. `record_task_event` here would
        # make it 65.
        blocked = self._dependency_refusal(task_def)
        if blocked:
            record_task_event(str(self.project_root), "log_state_change",
                              f"runnable:{task_id}", "dependency_unmet",
                              f"waiting on {'; '.join(blocked['unmet_dependencies'])}")
            return {**blocked,
                    # The CLI reads `breaker` and `breaker_consecutive_failures`
                    # off every execute_task result, skipped or not. A refusal
                    # that omitted them raised `KeyError` in the caller's skip
                    # branch — the gate would have turned a wait into a crash.
                    # These are the real readings, unchanged: waiting on a
                    # prerequisite is not an attempt, so nothing moves.
                    "breaker": self._breaker(task_def["id"]).stats.state.value,
                    "breaker_consecutive_failures":
                        self._breaker(task_def["id"]).stats.consecutive_failures}

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
        refusal: Optional[str] = None
        skip_hint: Optional[str] = None
        awaiting: Optional[Dict] = None
        for phase in task_def.get("phases", []):
            phase_result = self.execute_phase(phase, task_def, on_output=on_output)
            phase_result["phase"] = phase["name"]
            results.append(phase_result)
            if phase_result.get("awaiting"):
                # The session runs this phase. Not a refusal and not a
                # failure: nothing is wrong with the task, and later phases
                # cannot start until this one has produced its output. The
                # loop stops here and the payload carries the spawn request.
                awaiting = phase_result.get("spawn")
                break
            if phase_result.get("skip_reason"):
                refusal = phase_result["skip_reason"]
                skip_hint = phase_result.get("hint")
                break
            if not phase_result["success"]:
                break

        if awaiting:
            # A task mid-loop is neither succeeded nor failed. Reporting
            # `failed` would count an unfinished task against its breaker, and
            # three llm tasks on a machine with no session would walk to a
            # permanent trip exactly as they did under `no_task_provider`.
            # So the breaker is neither advanced nor reset, nothing is
            # recorded as a completion, and the caller gets the spawn request.
            return {
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "phases": results,
                "overall_success": False,
                "awaiting": awaiting,
                "completed_phases": [r["phase"] for r in results
                                     if r.get("success")],
                "breaker": breaker.stats.state.value,
                "breaker_consecutive_failures":
                    breaker.stats.consecutive_failures,
            }

        if refusal:
            # The task did not fail — it never got to run. Counting a refusal
            # against the task meant three `llm` tasks climbed to the breaker
            # threshold on a machine where they are structurally unrunnable, and
            # a trip is permanent until something runs green. So the breaker is
            # neither advanced nor reset: nothing was attempted, so nothing is
            # counted, and the counter stays where the last real run left it.
            return {
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "phases": results,
                "overall_success": False,
                "skipped": True,
                "skip_reason": refusal,
                "breaker": breaker.stats.state.value,
                "skip_hint": skip_hint,
                "breaker_consecutive_failures": breaker.stats.consecutive_failures,
            }

        overall_success = all(r["success"] for r in results)
        findings = [r for r in results if r.get("findings")]

        if overall_success:
            # A phase that ran and reported findings did its job, so the task
            # succeeded — and the breaker is advanced exactly as before, because
            # success is success. The findings are carried in the result and
            # persisted by `log_execution`, so `theteam history` can show *that*
            # a check has been reporting something for five runs, which is a
            # fact the schedule alone cannot express.
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
            # `overall_success` answers "did the machinery work"; this answers
            # "did it have something to report". A caller rendering one line
            # needs both — a green task that keeps finding real problems is not
            # a green project, and collapsing the two facts hides exactly that.
            "has_findings": bool(findings),
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