#!/usr/bin/env python3
"""The dynamic capability surface: what theteam can actually do right now.

Measured at call time, never cached across runs, never committed. A refusal
names the capability it measured and the value found, so the two cannot
disagree -- which is the defect this module exists to remove. The previous
representation of capability was `scripts/system-awareness-config.json`, a
static file declaring enabled/priority/timeout/health_threshold that nothing
read (loop_health_check.py:25-33 is the only thing that noticed). A file
recording an intention about a dynamic fact is stale the moment the
environment changes, and this one has been stale since its task was retired.

This is the DYNAMIC half of system awareness. The STATIC half -- what files
and tasks exist -- is `tasks/system-awareness/analyze_system_awareness.py`
and is not rebuilt here.

    python3 -m theteam.cli capability
    python3 -c "from theteam.core.capability import capability_surface; print(capability_surface('.'))"

Exits 0 always. This reports the world; it does not judge it.
"""
import os
import platform
import shutil
import sys
from typing import Any, Dict, List

from theteam.core.agent_isolation import AgentIsolation


def _spawnable_agents() -> List[str]:
    """The agent types a session can actually spawn.

    Measured against the host's own registry, not read from theteam.config:
    that file lists project *personas* (`architect`, `pragmatist`,
    `skeptic`, `designer`, `devops`), and a persona is not a spawn target.
    Validating a phase against it certifies a name the host rejects, which is
    worse than no check at all -- the task reports itself runnable and then
    cannot spawn anyone.

    `theteam.tasks.runners.llm.AGENT_TYPES` is that registry's export: it was
    derived by probing the host and is hardcoded precisely because the bare
    CLI has no host to probe. It is re-read on every call so a session that
    registers a new agent type after import is reflected here.
    """
    try:
        from theteam.tasks.runners.llm import AGENT_TYPES
    except Exception:
        return []
    return list(AGENT_TYPES)


def _writable_project(project_root: str) -> bool:
    """True when the project root is writable by this process."""
    try:
        return os.access(project_root, os.W_OK)
    except OSError:
        return False


def _disk_free_mb(project_root: str) -> int:
    """Free space on the volume holding the project root, in MiB."""
    try:
        usage = shutil.disk_usage(project_root)
    except OSError:
        return 0
    return usage.free // (1024 * 1024)


def _provider_bound() -> bool:
    """True when the importing interpreter has bound a provider."""
    module = sys.modules.get("theteam")
    return module is not None and hasattr(module, "default_api")


def capability_surface(project_root: str = ".") -> Dict[str, Any]:
    """Measure what theteam can do right now.

    Every key is computed at call time. Nothing is cached across runs and
    nothing is declared in a file: a value that changes without anyone
    editing anything (a provider binding, a daemon answering) is measured,
    so the surface cannot go stale the way a config file does.

    Exits 0 always. This reports the world; it does not judge it -- the
    caller decides whether a missing capability is a refusal or a fact.
    """
    return {
        "provider_bound": _provider_bound(),
        "docker_available": AgentIsolation.available(),
        "spawnable_agents": _spawnable_agents(),
        "python_version": platform.python_version(),
        "writable_project": _writable_project(project_root),
        "disk_free_mb": _disk_free_mb(project_root),
    }


def write_handoff(project_root: str = ".",
                  out_dir: str = ".omp/theteam/reports") -> str:
    """Write the surface as a JSON handoff and return the path.

    Machine consumer, so it lives under .omp/ -- the agent-facing root -- and
    not in reports/, which is for humans. The directory is created if absent
    so the first call in a fresh checkout does not fail.
    """
    import json
    os.makedirs(out_dir, exist_ok=True)
    surface = capability_surface(project_root)
    path = os.path.join(out_dir, "capability-surface.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(surface, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


__all__ = ["capability_surface", "write_handoff"]