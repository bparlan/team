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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Environment variables an agent may see. Anything not listed is dropped, so a
# parent process holding a token cannot leak it into an agent container.
DEFAULT_ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "PYTHONPATH")

# Cap on captured output. An agent that prints in a loop must not exhaust the
# orchestrator's memory through a captured pipe.
MAX_OUTPUT_BYTES = 1_000_000


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
        # Injectable so the contract is testable without a daemon.
        self._run = runner or subprocess.run

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
    ) -> Dict[str, Any]:
        """
        Execute `command` in an isolated container.

        Returns a result dict rather than raising on a non-zero exit: a failing
        agent is a normal outcome the orchestrator records, not an exception
        that unwinds the loop.
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
        logger.info(f"isolated agent run: {shlex.join(argv)}")

        try:
            completed = self._run(
                argv,
                capture_output=True,
                text=True,
                timeout=self.policy.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            # A container that ignores its timeout is killed by `docker run`
            # only on SIGINT; --rm plus the timeout leaves no artifact behind
            # either way, but the caller must not hang.
            logger.error(f"isolated run timed out after {self.policy.timeout_seconds}s")
            return self._result(124, "", f"timeout after {self.policy.timeout_seconds}s")
        except OSError as e:
            raise IsolationError(f"could not start isolated container: {e}") from e

        return self._result(
            completed.returncode,
            _truncate(completed.stdout),
            _truncate(completed.stderr),
        )

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
