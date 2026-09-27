#!/usr/bin/env python3
"""Live proof that per-agent container isolation is real, not just argv.

These run an actual `docker run` against the local image. They skip cleanly
when no Docker daemon is present, so the suite is green in both environments
and the contract is demonstrated on real hardware when it is available.
"""

import os

import pytest
from theteam.core.agent_isolation import AgentIsolation, IsolationPolicy

IMAGE = os.environ.get("THETEAM_AGENT_IMAGE", "theteam:p4final")


def _run(policy, code):
    # The image has its own interpreter; using the host's `sys.executable`
    # passes a path that does not exist inside the container.
    iso = AgentIsolation(policy)
    return iso.run(
        ["python3", "-c", code],
        container_name="tt-live-" + os.urandom(4).hex(),
        project_root=".",
    )


@pytest.mark.skipif(not AgentIsolation.available(), reason="no Docker daemon")
def test_live_root_filesystem_is_read_only():
    """A container with read-only rootfs cannot write to /."""
    r = _run(IsolationPolicy(image=IMAGE, timeout_seconds=90),
             "import os; print('writable:', os.access('/', os.W_OK))")
    assert r["success"], r["stderr"]
    assert "writable: False" in r["stdout"]


@pytest.mark.skipif(not AgentIsolation.available(), reason="no Docker daemon")
def test_live_project_mount_is_read_only():
    """The project is mounted read-only by default."""
    r = _run(IsolationPolicy(image=IMAGE, timeout_seconds=90),
             "import os; print('workspace writable:', os.access('/workspace', os.W_OK))")
    assert r["success"], r["stderr"]
    assert "workspace writable: False" in r["stdout"]


@pytest.mark.skipif(not AgentIsolation.available(), reason="no Docker daemon")
def test_live_memory_cap_is_enforced():
    """An agent that exceeds the memory ceiling is killed, not allowed to grow."""
    r = _run(IsolationPolicy(image=IMAGE, memory_limit="64m", timeout_seconds=90),
             "import sys; b=bytearray(200*1024*1024); sys.stdout.write('survived')")
    assert r["success"] is False
    assert r["exit_code"] == 137, "expected OOM kill (SIGKILL), got " + str(r["exit_code"])
    assert "survived" not in r["stdout"]


@pytest.mark.skipif(not AgentIsolation.available(), reason="no Docker daemon")
def test_live_network_is_off_by_default():
    """A default policy must not reach the network."""
    r = _run(IsolationPolicy(image=IMAGE, timeout_seconds=90),
             "import socket; s=socket.socket(); s.settimeout(2); s.connect(('1.1.1.1',53)); print('NETWORK OPEN')")
    assert r["success"] is False
    assert "NETWORK OPEN" not in r["stdout"]


@pytest.mark.skipif(not AgentIsolation.available(), reason="no Docker daemon")
def test_live_network_can_be_opted_in():
    """The policy is a knob: a caller can turn network on."""
    r = _run(IsolationPolicy(image=IMAGE, network="bridge", timeout_seconds=90),
             "import socket; s=socket.socket(); s.settimeout(2); s.connect(('1.1.1.1',53)); print('NETWORK OPEN')")
    # Either it connected (network on) or it timed out inside the bridge
    # network - both mean the flag was honoured. The key is that the
    # default policy above rejected it, so the two are not equivalent.
    assert r["success"] or "NETWORK OPEN" in r["stdout"]
