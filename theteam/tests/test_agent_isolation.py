#!/usr/bin/env python3
"""Contract tests for per-agent container isolation.

The isolation policy IS the `docker run` argv, so these tests assert on the
command rather than needing a Docker daemon. They defend the guarantees that
matter: bounded resources, no network, read-only root, an env allowlist that
cannot leak a parent's secrets, and a project mount that is read-only unless a
caller deliberately asks for writes.
"""

import subprocess

import pytest

from theteam.core.agent_isolation import (
    AgentIsolation,
    IsolationError,
    IsolationPolicy,
    build_run_command,
)


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_default_policy_denies_network():
    """An agent must not reach the network unless explicitly asked."""
    argv = build_run_command("c1", IsolationPolicy(), ["echo", "hi"])
    assert "--network" in argv
    assert argv[argv.index("--network") + 1] == "none"


def test_network_can_be_opted_into():
    policy = IsolationPolicy(network="bridge")
    argv = build_run_command("c1", policy, ["echo", "hi"])
    assert argv[argv.index("--network") + 1] == "bridge"
    assert policy.allows_network() is True


def test_resource_ceilings_are_always_present():
    """Memory/CPU/PID caps are the point of the exercise; assert all three."""
    policy = IsolationPolicy(memory_limit="256m", cpu_limit="0.5", pids_limit=64)
    argv = build_run_command("c1", policy, ["echo", "hi"])
    assert argv[argv.index("--memory") + 1] == "256m"
    assert argv[argv.index("--cpus") + 1] == "0.5"
    assert argv[argv.index("--pids-limit") + 1] == "64"


def test_pids_limit_is_at_least_one():
    """A zero/negative pids-limit would make docker reject the whole run."""
    argv = build_run_command("c1", IsolationPolicy(pids_limit=0), ["true"])
    assert int(argv[argv.index("--pids-limit") + 1]) >= 1


def test_root_filesystem_is_read_only_by_default():
    argv = build_run_command("c1", IsolationPolicy(), ["echo", "hi"])
    assert "--read-only" in argv
    # A read-only root is unusable without a writable scratch layer.
    assert any(a.startswith("--tmpfs") for a in argv)


def test_containers_run_as_non_root():
    """The image user is non-root; the flag must not be dropped."""
    argv = build_run_command("c1", IsolationPolicy(), ["echo", "hi"])
    assert argv[argv.index("--user") + 1] == "999:999"


def test_env_allowlist_drops_everything_else():
    """A parent secret must never be handed to an agent container."""
    argv = build_run_command(
        "c1", IsolationPolicy(), ["echo", "hi"],
        env={"PATH": "/bin", "ANTHROPIC_API_KEY": "sk-secret", "AWS_SECRET": "x"},
    )
    assert "PATH=/bin" in argv
    assert not any("sk-secret" in a for a in argv)
    assert not any("AWS_SECRET" in a for a in argv)


def test_project_mount_is_read_only_unless_the_caller_opts_in():
    """Default is read-only; a write mount is an explicit, visible decision."""
    ro = build_run_command(
        "c1", IsolationPolicy(), ["true"],
        mounts={"/workspace": {"source": "/repo", "mode": "ro"}},
    )
    assert any("target=/workspace" in a and a.endswith(",ro") for a in ro)

    rw = build_run_command(
        "c1", IsolationPolicy(), ["true"],
        mounts={"/workspace": {"source": "/repo", "mode": "rw"}},
    )
    assert any("target=/workspace" in a and a.endswith(",rw") for a in rw)


def test_empty_command_is_rejected():
    with pytest.raises(IsolationError):
        build_run_command("c1", IsolationPolicy(), [])


def test_image_and_command_appear_last():
    """Everything before the image is a flag, so the command cannot be a flag."""
    argv = build_run_command("c1", IsolationPolicy(), ["python", "run.py"])
    assert argv[-3:] == ["theteam", "python", "run.py"]


def test_run_returns_a_result_dict_instead_of_raising():
    """A failing agent is a recorded outcome, not an exception that unwinds."""
    seen = {}

    def runner(argv, **kwargs):
        seen["argv"] = argv
        return _Proc(returncode=3, stdout="out", stderr="boom")

    iso = AgentIsolation(runner=runner)
    result = iso.run(["false"], container_name="c1")

    assert result["success"] is False
    assert result["exit_code"] == 3
    assert result["stdout"] == "out"
    assert result["stderr"] == "boom"
    assert result["isolated"] is True
    assert "--rm" in seen["argv"]


def test_timeout_is_reported_not_propagated():
    """A hung agent must surface as a failure, not hang the orchestrator."""
    def runner(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)

    result = AgentIsolation(runner=runner).run(["sleep", "999"])
    assert result["success"] is False
    assert result["exit_code"] == 124
    assert "timeout" in result["stderr"]


def test_inherited_env_only_contains_allowlisted_keys(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("MY_SECRET_TOKEN", "leak-me")
    env = AgentIsolation()._inherited_env()
    assert env["PATH"] == "/usr/bin"
    assert "MY_SECRET_TOKEN" not in env


def test_large_output_is_truncated():
    """An agent printing in a loop must not exhaust the caller's memory."""
    from theteam.core.agent_isolation import MAX_OUTPUT_BYTES, _truncate

    huge = "x" * (MAX_OUTPUT_BYTES + 5_000)
    out = _truncate(huge)
    assert len(out) < len(huge)
    assert "truncated" in out
