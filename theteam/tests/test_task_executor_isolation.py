"""
The Layer 4 guard on `TaskExecutor.execute_phase`.

Before M4, running a phase meant handing a path to `subprocess.run` in the
orchestrator's own process space: the script saw the developer's filesystem,
the developer's environment, and the developer's memory budget. M4 wraps the
call in `AgentIsolation` and makes the bound mandatory, and the property worth
pinning is not "the container ran" but the shape of the *refusals* and of the
*kill*:

  * a phase with no `memory_limit_mb` is refused by name (§5.4). An invented
    default is the exact failure this milestone exists to remove, because a
    bound nobody wrote is a bound nobody tested;
  * with no Docker, the phase is refused by name (§5.1) - never quietly
    executed unguarded, which is a guard that degrades to no guard;
  * the module keeps no `subprocess` call site at all, so the invariant
    cannot rot back in through an unrelated edit;
  * a container that exceeds its bound is killed and the kill is reported as
    exit code 137 (§7.1.6) - a container left running past its ceiling is
    indistinguishable from one that finished;
  * the project's own tree is mounted read-only unless a phase asks for a
    writable mount, so "it needed to write" stays a visible decision.

The refusal tests run with no Docker daemon and are never skipped: they are
the ones that matter most, because they are the ones CI on a Docker-less box
still executes.
"""

import ast
import inspect
from pathlib import Path

import pytest

from theteam.core.agent_isolation import AgentIsolation
from theteam.tasks import executor as executor_module
from theteam.tasks.executor import (
    DEFAULT_IMAGE,
    IMAGE_ENV_VAR,
    OOM_KILL_EXIT_CODE,
    WORKSPACE_MOUNT,
    TaskExecutor,
)

#: Every Docker-backed test waits on the daemon, never on a wall clock.
DOCKER_TIMEOUT = 120

requires_docker = pytest.mark.skipif(
    not AgentIsolation.available(), reason="no Docker daemon"
)


# ======= scratch project =======


def _phase_script(root: Path, name: str, body: str) -> str:
    """
    A real script file in a scratch project, so a refusal can be proven to
    have not run it. Returns the project-relative path for the phase dict.
    """
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / name).write_text(body)
    return f"scripts/{name}"


#: A script whose only effect is a file in the project tree. If it ran, the
#: host sees the marker; if it was refused, the host sees nothing.
SIDEFECT_SCRIPT = """\
from pathlib import Path

Path(__file__).resolve().parent.parent.joinpath("ran-uncontrolled.txt").write_text("x")
print("ran")
"""


# ======= 1. no bound is refused, by name (§5.4) =======


def test_a_phase_with_no_memory_bound_is_refused_and_says_so(tmp_path):
    """
    Defect: a phase file hand-edited past the write path loses its
    `memory_limit_mb`. The old Layer 3 code ran it anyway under whatever the
    host happened to allow. §5.4 makes the bound mandatory, so the phase is
    refused - and refused *by name*, because a refusal the caller cannot
    explain is indistinguishable from a crash.

    The load-bearing assertion is the last one: the marker file proves the
    script never executed. An error string alone could be produced by a
    refusal that ran the script on the way to refusing.
    """
    script = _phase_script(tmp_path, "greedy.py", SIDEFECT_SCRIPT)
    marker = tmp_path / "ran-uncontrolled.txt"

    result = TaskExecutor(str(tmp_path)).execute_phase(
        {"name": "no-bound", "script": script}
    )

    assert result["success"] is False
    assert "memory_limit_mb" in result["error"]
    assert "returncode" not in result, "a refused phase never ran a process"
    assert not marker.exists(), "the script ran despite the missing bound"


# ======= 2. no Docker is refused, not downgraded (§5.1) =======


def test_no_docker_means_a_named_refusal_and_no_unguarded_run(tmp_path, monkeypatch):
    """
    Defect: a guard that falls back to running the phase directly is not a
    guard - it is a slower path to the same unbounded execution, taken
    exactly when nobody is watching. §5.1 requires the refusal, and the
    marker file proves the refusal is real rather than a message printed on
    the way to running it anyway.

    Patched at the class, not at an instance, because the executor
    constructs its own `AgentIsolation` per phase.
    """
    script = _phase_script(tmp_path, "greedy.py", SIDEFECT_SCRIPT)
    marker = tmp_path / "ran-uncontrolled.txt"
    monkeypatch.setattr(AgentIsolation, "available", staticmethod(lambda: False))

    result = TaskExecutor(str(tmp_path)).execute_phase(
        {"name": "no-docker", "script": script, "memory_limit_mb": 256}
    )

    assert result["success"] is False
    lowered = result["error"].lower()
    assert "isolation" in lowered and "docker" in lowered
    assert not marker.exists(), "the phase ran unguarded with no Docker available"


# ======= 3. the standing §5.1 invariant =======


def test_the_module_has_no_unguarded_subprocess_call_site():
    """
    Defect: the next person adds a `subprocess.run` to the executor "just to
    check something" and every phase silently has a second, unguarded path.
    Tests 1 and 2 only prove the *current* code takes the guarded path; this
    pins the structural fact that the unguarded path does not exist.

    Parsed, not grepped: the module docstring and comments discuss
    `subprocess.run` at length, and only a syntax tree can tell a mention from
    a call site. The bound names come from the module's own imports, so
    `import subprocess as sp` is caught too - a name-matching check would
    walk straight past an alias.
    """
    assert not hasattr(executor_module, "subprocess"), (
        "executor.py imported subprocess; Layer 3 must not hold a raw call site"
    )

    tree = ast.parse(inspect.getsource(executor_module))
    bound = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.split(".")[0] == "subprocess"
    }
    bound |= {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess"
    }
    assert bound == set(), f"executor.py imports subprocess as {sorted(bound)}"

    call_sites = [
        f"{node.func.value.id}.{node.func.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in bound
    ]
    assert call_sites == [], f"unguarded subprocess call sites: {call_sites}"


# ======= 4. exceeding the bound is killed, and the kill is reported =======


@requires_docker
def test_a_phase_over_its_memory_bound_is_killed_and_the_exit_code_is_reported(
    tmp_path,
):
    """
    Defect: an unenforced memory ceiling. The script allocates 400MB under a
    64MB bound; a ceiling that is advisory lets that through and the host
    pays for it. §7.1.6 makes the kill *observable* - the caller sees exit
    code 137, so "killed for memory" is distinguishable from "crashed" and
    from "timed out" (124) without parsing prose.
    """
    script = _phase_script(
        tmp_path,
        "hog.py",
        'ball = bytearray(400 * 1024 * 1024)\nprint(len(ball))\n',
    )

    result = TaskExecutor(str(tmp_path)).execute_phase(
        {
            "name": "hog",
            "script": script,
            "memory_limit_mb": 64,
            "timeout_seconds": DOCKER_TIMEOUT,
        }
    )

    assert result["success"] is False
    assert result["returncode"] == OOM_KILL_EXIT_CODE
    assert str(OOM_KILL_EXIT_CODE) in result["error"]
    assert result["isolated"] is True


# ======= 5. a bound the phase declares is the bound it runs under =======


@requires_docker
def test_the_memory_bound_from_the_phase_reaches_the_container(tmp_path):
    """
    Defect: the phase's declared `memory_limit_mb` parsed out of YAML and
    then dropped on the floor, leaving every phase under whatever default
    the policy happened to carry. The observable proof is the difference
    against test 4: the same shape of phase, a generous bound instead of 64m,
    runs to completion and its stdout comes back. If the bound were ignored
    in the permissive direction this would still pass, so the pair is the
    assertion - 64m kills, 256m completes, on the same image.
    """
    script = _phase_script(
        tmp_path,
        "calm.py",
        'ball = bytearray(32 * 1024 * 1024)\nprint(f"allocated {len(ball)}")\n',
    )

    result = TaskExecutor(str(tmp_path)).execute_phase(
        {
            "name": "calm",
            "script": script,
            "memory_limit_mb": 256,
            "timeout_seconds": DOCKER_TIMEOUT,
        }
    )

    assert result["success"] is True
    assert result["returncode"] == 0
    assert result["isolated"] is True
    assert "allocated 33554432" in result["stdout"]


# ======= 6. the project tree is read-only unless the phase asks =======


@requires_docker
def test_a_read_only_project_mount_blocks_a_write_and_the_writable_flag_allows_it(
    tmp_path,
):
    """
    Defect: an agent phase editing the repo it was pointed at. The project
    tree is mounted read-only, so the same script fails with a read-only
    filesystem error - and succeeds only when the phase declares
    `writable_project`. The script derives its target from `__file__` so it
    writes inside whichever tree it is actually mounted from, not a path
    baked in at authoring time.
    """
    script = _phase_script(
        tmp_path,
        "writer.py",
        'from pathlib import Path\n'
        'target = Path(__file__).resolve().parent.parent / "written.txt"\n'
        'target.write_text("ok")\n'
        'print(f"wrote {target.name}")\n',
    )
    marker = tmp_path / "written.txt"
    phase = {
        "name": "writer",
        "script": script,
        "memory_limit_mb": 256,
        "timeout_seconds": DOCKER_TIMEOUT,
    }
    executor = TaskExecutor(str(tmp_path))

    read_only = executor.execute_phase(dict(phase))
    assert read_only["success"] is False
    assert "Read-only file system" in read_only["stderr"]
    assert not marker.exists(), "the read-only mount let a write through"

    writable = executor.execute_phase(dict(phase, writable_project=True))
    assert writable["success"] is True, writable["stderr"]
    assert marker.read_text() == "ok"

    # The mount is what carries the difference; the two runs must not be
    # reporting the same thing twice under different names.
    assert read_only["returncode"] != writable["returncode"]


# ======= 7. the image is overridable, not a literal =======


def test_the_image_can_be_overridden_by_environment(tmp_path, monkeypatch):
    """
    Defect: the isolation image hardcoded as a string literal in the method
    body, so a deployment on a different tag cannot run a phase at all. The
    executor must read it from `IMAGE_ENV_VAR`; this pins that the env var
    wins over `DEFAULT_IMAGE` by capturing the policy the phase was actually
    run under, without a daemon in the loop.
    """
    captured = {}

    def fake_run(self, command, **kwargs):
        captured["policy"] = self.policy
        return {
            "success": True,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "isolated": True,
        }

    monkeypatch.setenv(IMAGE_ENV_VAR, "sentinel-image:does-not-exist")
    monkeypatch.setattr(AgentIsolation, "available", staticmethod(lambda: True))
    monkeypatch.setattr(AgentIsolation, "run", fake_run)

    script = _phase_script(tmp_path, "noop.py", "print('hi')\n")
    result = TaskExecutor(str(tmp_path)).execute_phase(
        {
            "name": "env-image",
            "script": script,
            "memory_limit_mb": 256,
            "timeout_seconds": DOCKER_TIMEOUT,
        }
    )

    assert result["success"] is True
    assert captured["policy"].image == "sentinel-image:does-not-exist"
    assert captured["policy"].image != DEFAULT_IMAGE
    assert captured["policy"].workdir == WORKSPACE_MOUNT
