#!/usr/bin/env python3
"""Capability surface unit tests.

Every test asserts the MESSAGE, not the source. The probe is the
falsification: if a value changes, the test changes or breaks,
and that is the point.
"""
import os
import tempfile


def test_capability_surface_has_all_keys():
    """The contract from the plan: six keys, never cached, never committed."""
    from theteam.core.capability import capability_surface
    surface = capability_surface(".")
    for key in ("provider_bound", "docker_available", "spawnable_agents",
                "python_version", "writable_project", "disk_free_mb"):
        assert key in surface, f"missing key {key}"


def test_capability_surface_exits_zero():
    """The plan: exits 0 always. This reports the world; it does not judge it."""
    from theteam.core.capability import capability_surface
    result = capability_surface(".")
    # capability_surface returns a dict, not an exit code. The contract
    # is that it never raises -- a function that raises is one that gates.
    assert isinstance(result, dict)


def test_provider_bound_is_bool():
    """Measured, not declared. A boolean, not a string pretending to be one."""
    from theteam.core.capability import capability_surface
    surface = capability_surface(".")
    assert isinstance(surface["provider_bound"], bool)


def test_docker_available_is_bool():
    """Measured via AgentIsolation.available(), not read from a config file."""
    from theteam.core.capability import capability_surface
    surface = capability_surface(".")
    assert isinstance(surface["docker_available"], bool)


def test_spawnable_agents_is_list_of_strings():
    """The host's registry, not a persona list. A persona is not a spawn target."""
    from theteam.core.capability import capability_surface
    surface = capability_surface(".")
    assert isinstance(surface["spawnable_agents"], list)
    for agent in surface["spawnable_agents"]:
        assert isinstance(agent, str), f"non-string agent: {agent!r}"


def test_python_version_is_string():
    from theteam.core.capability import capability_surface
    surface = capability_surface(".")
    assert isinstance(surface["python_version"], str)
    assert "." in surface["python_version"]


def test_writable_project_is_bool():
    from theteam.core.capability import capability_surface
    surface = capability_surface(".")
    assert isinstance(surface["writable_project"], bool)


def test_disk_free_mb_is_int():
    from theteam.core.capability import capability_surface
    surface = capability_surface(".")
    assert isinstance(surface["disk_free_mb"], int)


def test_handoff_written_to_dot_omp():
    """Machine consumer, so it lives under .omp/ -- not reports/."""
    from theteam.core.capability import write_handoff
    with tempfile.TemporaryDirectory() as tmp:
        path = write_handoff(tmp, out_dir=os.path.join(tmp, ".omp", "theteam", "reports"))
        assert ".omp/" in path, f"handoff not in dot-prefix dir: {path}"
        assert path.endswith("capability-surface.json")
        import json
        with open(path) as handle:
            data = json.load(handle)
        assert "provider_bound" in data


def test_handoff_creates_dirs():
    """First call in a fresh checkout does not fail."""
    from theteam.core.capability import write_handoff
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = os.path.join(tmp, ".omp", "theteam", "reports")
        assert not os.path.isdir(out_dir)
        path = write_handoff(tmp, out_dir=out_dir)
        assert os.path.isdir(out_dir)
        assert os.path.isfile(path)


def test_cli_capability_command_exists():
    """The capability subcommand is registered in the parser."""
    from theteam.cli import build_parser
    parser = build_parser()
    subparsers = [a for a in parser._actions
                  if hasattr(a, 'choices') and a.choices]
    assert subparsers, "no subparsers registered"
    choices = subparsers[0].choices
    assert "capability" in choices, "capability not in subcommands"


def test_cli_capability_returns_json(tmp_path, capsys):
    """--json emits the surface dict, not prose."""
    from theteam.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["--project-root", str(tmp_path), "capability", "--json"])
    result = args.func(args)
    assert result == 0
    captured = capsys.readouterr()
    payload = __import__("json").loads(captured.out)
    assert "provider_bound" in payload


def test_cli_capability_returns_exit_zero(tmp_path):
    """The plan: exits 0 always."""
    from theteam.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["--project-root", str(tmp_path), "capability"])
    result = args.func(args)
    assert result == 0


def test_capability_surface_is_not_cached():
    """Every call measures fresh. A config file is the cache this replaces."""
    from theteam.core.capability import capability_surface
    a = capability_surface(".")
    b = capability_surface(".")
    # Same keys, but they are computed independently -- identity is not
    # the contract, freshness is. The test proves the function runs
    # twice without a cached result dict being returned twice.
    assert a is not b
