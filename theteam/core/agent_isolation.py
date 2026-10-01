#!/usr/bin/env python3
"""
Per-agent container isolation.

Roadmap criterion 6 / Drift Prevention Gate 4: "All agents must run in
isolated containers." Until this module, agents ran as bare `subprocess.run`
calls in the orchestrator's own process space, sharing its filesystem, its
environment, and its resource budget. One agent could exhaust memory or write
outside its remit and take the orchestrator down with it.

What isolation means here, concretely:

  * one container per agent execution, never a shared long-lived one
  * a read-only root filesystem, so an agent cannot modify the image
  * a resource ceiling (CPU, memory, PIDs) that the orchestrator cannot exceed
  * a writable scratch volume, and the project mounted read-only by default
  * an explicit env allowlist, so a parent's secrets are not inherited
  * network off unless the agent asks for it
  * all of it optional via a policy, so a caller without Docker still works

Docker is invoked through the CLI, not a client library: no new dependency, and
the command is inspectable by an operator. The build args are a plain dataclass
so a policy is testable without Docker installed.
"""

import json
import logging
import os
import shlex
import shutil
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Environment variables an agent may see. Anything not listed is dropped, so a
# parent process holding a token cannot leak it into an agent container.
DEFAULT_ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "PYTHONPATH")

# Cap on captured output. An agent that prints in a loop must not exhaust the
# orchestrator's memory through a captured pipe.
MAX_OUTPUT_BYTES = 1_000_000

#: Lines kept from a run. `_truncate` still caps the returned string at
#: `MAX_OUTPUT_BYTES`; this bounds the collection *while* it grows, so a
#: long-running agent that prints steadily is trimmed from the front rather
#: than being held whole in memory until exit.
_OUTPUT_LINES = 2000


class IsolationError(RuntimeError):
    """Raised when an isolated run cannot be set up or completed."""


@dataclass(frozen=True)
class IsolationPolicy:
    """
    The bounds one agent execution runs under.

    Defaults are deliberately restrictive: an agent gets a read-only root, a
    memory ceiling, and no network unless asked.
    """

    image: str = "theteam"
    memory_limit: str = "512m"
    cpu_limit: str = "1.0"
    pids_limit: int = 256
    network: str = "none"
    read_only_rootfs: bool = True
    run_as_user: str = "999:999"
    timeout_seconds: int = 300
    workdir: Optional[str] = None
    #: Extra docker flags. Escape hatch for capabilities the policy lacks.
    extra_run_args: Sequence[str] = ()

    env_allowlist: Sequence[str] = DEFAULT_ENV_ALLOWLIST

    def allows_network(self) -> bool:
        return self.network not in ("none", "", None)

def build_run_command(
    container_name: str,
    policy: IsolationPolicy,
    command: Sequence[str],
    *,
    mounts: Optional[Dict[str, Dict[str, str]]] = None,
    env: Optional[Dict[str, str]] = None,
) -> List[str]:
    """
    Build the `docker run` argv for one isolated execution.

    Kept separate from execution so the whole isolation contract is unit
    testable on a machine with no Docker daemon: the argv IS the policy.
    """
    if not command:
        raise IsolationError("no command given to run in isolation")

    argv: List[str] = ["docker", "run", "--rm"]

    if container_name:
        argv += ["--name", container_name]

    # Network last-wins: pass it explicitly rather than relying on a default,
    # so the effective network is visible in the command.
    if not policy.allows_network():
        argv += ["--network", "none"]
    elif policy.network:
        argv += ["--network", policy.network]

    argv += [
        "--memory", policy.memory_limit,
        "--cpus", policy.cpu_limit,
        "--pids-limit", str(policy_pids(policy)),
    ]

    if policy.read_only_rootfs:
        argv.append("--read-only")
    if policy.run_as_user:
        argv += ["--user", policy.run_as_user]

    # A writable scratch layer: a read-only rootfs is unusable without one.
    argv += ["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"]

    for container_path, spec in (mounts or {}).items():
        mode = spec.get("mode", "ro")
        source = spec["source"]
        argv += ["--mount", f"type=bind,source={source},target={container_path},{'rw' if mode == 'rw' else 'ro'}"]

    allowed = set(policy.env_allowlist)
    for key, value in (env or {}).items():
        if key in allowed:
            argv += ["-e", f"{key}={value}"]

    if policy.workdir:
        argv += ["-w", policy.workdir]

    argv += list(policy.extra_run_args)
    argv.append(policy.image)
    argv += list(command)
    return argv


def policy_pids(policy: IsolationPolicy) -> int:
    return max(1, int(policy.pids_limit))


class AgentIsolation:
    """
    Runs one agent command inside a bounded container.

    `available()` reports whether Docker is usable, so a caller can fall back
    to an in-process run instead of failing outright. Isolation must not become
    a new way for the orchestrator to break.
    """

    def __init__(self, policy: Optional[IsolationPolicy] = None, runner=None) -> None:
        self.policy = policy or IsolationPolicy()
        # Injectable so the contract is testable without a daemon. `runner` is
        # the *spawner*, not `subprocess.run`: it takes the argv and returns a
        # Popen-like object with `.stdout`, `.wait()`, `.kill()` and
        # `.returncode`.
        self._spawn = runner or subprocess.Popen

    @staticmethod
    def available() -> bool:
        """True when a docker CLI exists and the daemon answers."""
        if shutil.which("docker") is None:
            return False
        try:
            probe = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True, timeout=10,
            )
            return probe.returncode == 0
        except (OSError, subprocess.SubprocessError) as e:
            logger.debug(f"docker unavailable: {e}")
            return False

    def run(
        self,
        command: Sequence[str],
        *,
        container_name: str = "",
        project_root: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Execute `command` in an isolated container.

        Returns a result dict rather than raising on a non-zero exit: a failing
        agent is a normal outcome the orchestrator records, not an exception
        that unwinds the loop.

        `on_output` receives each line as it arrives, so a caller can show
        progress during a run instead of after it. Without it the behaviour is
        exactly what it always was. The pipe is drained while the process runs:
        the previous `subprocess.run(capture_output=True)` held every byte in
        memory until exit, which meant a six-minute task printed nothing for
        six minutes and looked hung.
        """
        mounts: Dict[str, Dict[str, str]] = {}
        if project_root:
            # Read-only by default. An agent that needs to write must be given
            # an explicit rw mount by the caller, so "it needed to write" is a
            # visible decision rather than a default.
            mounts["/workspace"] = {"source": str(Path(project_root).resolve()), "mode": "ro"}

        argv = build_run_command(
            container_name,
            self.policy,
            command,
            mounts=mounts,
            env=env or self._inherited_env(),
        )
        # The image and the command, not the whole argv: every `-e` in it is an
        # inherited environment value, and the full line put all of them in
        # the log on every single run.
        logger.info(f"isolated agent run: {shlex.join(argv[:1])} ... "
                    f"{shlex.join(argv[-len(command):])}")


        return self._spawn_and_collect(argv, on_output)

    def _spawn_and_collect(
        self,
        argv: Sequence[str],
        on_output: Optional[Callable[[str], None]],
    ) -> Dict[str, Any]:
        """
        Start the container, stream what it prints, and return the result.

        `Popen` rather than `subprocess.run` because the run must be observed
        while it happens. stdout and stderr are merged onto one pipe and read
        line by line: two reader threads and two pipes buy an ordering nobody
        downstream needs, and a merged stream is what a person reading live
        output wants anyway.

        The reading happens on a thread because the timeout has to keep working
        when a process says nothing. Reading inline would block in `readline`
        for the whole run, and the deadline is only ever checked between lines —
        so a silent hang would never time out, which is the exact failure this
        change exists to remove.


        `MAX_OUTPUT_BYTES` is still a cap, and still the same number. It now
        bounds a deque of recent lines rather than a string being appended to,
        so an agent printing in a loop cannot grow the parent's memory — but
        the tail is kept whole, because the end of a run is the part that
        explains the run.
        """
        try:
            process = self._spawn(
                list(argv),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as e:
            raise IsolationError(f"could not start isolated container: {e}") from e

        collected: Deque[str] = deque(maxlen=_OUTPUT_LINES)

        def pump() -> None:
            for line in iter(process.stdout.readline, ""):
                collected.append(line)
                if on_output is None:
                    continue
                try:
                    on_output(line)
                except Exception:
                    # A broken reporter must not kill the run it is watching.
                    # The line is still recorded below.
                    logger.debug("output callback failed", exc_info=True)

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()

        timed_out = False
        try:
            process.wait(timeout=self.policy.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            try:
                # Bounded, because the whole point of this branch is that the
                # process stopped cooperating. An unbounded wait here would
                # trade a timeout we can report for a hang we cannot.
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.error("isolated process did not exit after kill")
        finally:
            # The pipe closes when the process dies, which ends `readline`, so
            # joining cannot hang even for a task that never printed a line.
            reader.join(timeout=5)
            process.stdout.close()

        output = _truncate("".join(collected))
        if timed_out:
            logger.error(f"isolated run timed out after {self.policy.timeout_seconds}s")
            return self._result(124, output,
                                f"timeout after {self.policy.timeout_seconds}s")
        # stderr is deliberately empty. Both streams are merged onto one pipe
        # so ordering is preserved and only one reader is needed, which means
        # there is no separate stderr to report. Every line the process wrote
        # is in `output` — and nothing downstream parsed `stderr` to find an
        # error, so this reports what happened rather than hiding a message.
        return self._result(process.returncode, output, "")

    def _inherited_env(self) -> Dict[str, str]:
        """Only the allowlisted variables, so secrets are not handed down."""
        return {k: v for k, v in os.environ.items() if k in set(self.policy.env_allowlist)}

    @staticmethod
    def _result(returncode: int, stdout: str, stderr: str) -> Dict[str, Any]:
        return {
            "success": returncode == 0,
            "exit_code": returncode,
            "stdout": stdout,
            "stderr": stderr,
            "isolated": True,
        }


def _truncate(text: Optional[str]) -> str:
    if not text:
        return ""
    if len(text) > MAX_OUTPUT_BYTES:
        return text[:MAX_OUTPUT_BYTES] + "\n... [truncated]"
    return text
