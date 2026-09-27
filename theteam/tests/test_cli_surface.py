"""
The CLI command contract.

Every command returns a real exit code. A command that returns `None` passes
`sys.exit(None)` as success, so a stubbed body looks like a working command -
that is how a broken `theteam discuss` survived a sweep that only read the
last line of output. This asserts the code, not the prose.
"""

import argparse
import json

import pytest
from theteam.cli import build_parser, cmd_serve, main


COMMANDS = ["bootstrap", "status", "discuss", "serve", "comment",
            "tasks", "task", "run", "history", "loop"]


def _subcommands() -> set:
    """The command names the parser actually accepts."""
    parser = build_parser()
    actions = [a for a in parser._actions
               if isinstance(a, argparse._SubParsersAction)]
    assert actions, "no subcommands registered"
    return set(actions[0].choices or {})


def test_every_command_in_the_architecture_surface_exists():
    missing = set(COMMANDS) - _subcommands()
    assert not missing, f"commands missing from the parser: {sorted(missing)}"


# `serve` is asserted through the parser, not invoked: it starts a server and
# blocks on an Event forever, so it cannot be swept like a command that returns.
@pytest.mark.parametrize("command,succeeds,diagnostic", [
    ("bootstrap", True, None),
    ("status", False, "theteam.config not found"),
    ("discuss", False, "OMP"),
    ("loop", False, "Task not found"),
    ("comment", False, "not implemented yet"),
    ("tasks", True, None),
    ("task", False, "not implemented yet"),
    ("run", True, None),
    ("history", False, "not implemented yet"),
])
def test_command_returns_an_int_exit_code(command, succeeds, diagnostic, tmp_path, capsys):
    """
    The exit code is a real int, and a failure says why.

    `isinstance(code, int)` is the assertion that matters: a command that
    returns `None` reaches `sys.exit(None)`, which the shell reads as SUCCESS.
    That is the regression this file exists for - a stubbed body looks like a
    working command.

    The diagnostic is a separate assertion on purpose. `main()`'s exception
    handler and a deliberate refusal both return 1, so the exit code alone
    cannot tell "the task does not exist" from "the command crashed".
    """
    argv = {
        "bootstrap": [], "status": [], "discuss": ["a topic"],
        "loop": ["no-such-task"],
    }.get(command, [])

    code = main(["--project-root", str(tmp_path), command, *argv])
    captured = capsys.readouterr()
    output = captured.out + captured.err

    assert isinstance(code, int), f"theteam {command} returned {code!r}, not an int"
    assert (code == 0) is succeeds, f"theteam {command} exit={code}"
    if diagnostic:
        assert diagnostic in output, f"theteam {command} said nothing about why: {output!r}"
    assert "Traceback" not in output, f"theteam {command} crashed: {output!r}"


def test_serve_is_wired_to_its_handler():
    """Asserted through the parser: invoking it would block forever."""
    parser = build_parser()
    action = [a for a in parser._actions
              if isinstance(a, argparse._SubParsersAction)][0]
    assert "serve" in action.choices
    assert action.choices["serve"].get_default("func") is cmd_serve


@pytest.mark.parametrize("command", ["task", "history", "comment"])
def test_unimplemented_command_names_its_milestone(command, tmp_path, capsys):
    """A command that does not exist says so. It never returns a fake result."""
    assert main(["--project-root", str(tmp_path), command]) == 1
    out = capsys.readouterr().out
    assert "not implemented yet" in out
    assert "M" in out, "the refusal must name the milestone it lands in"


def test_discuss_outside_omp_fails_with_the_command_to_run(tmp_path, capsys):
    """The §1.2 promise: it fails naming OMP and returns no opinion."""
    assert main(["--project-root", str(tmp_path), "discuss", "should we ship"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "OMP" in out
    assert "opinion" not in out.lower().replace("no opinion is returned", "")


def test_json_output_is_valid_json(tmp_path, capsys):
    """--json emits parseable JSON, not prose that happens to look structured."""
    # `history` still refuses, so it exercises the failure path's JSON shape.
    assert main(["--project-root", str(tmp_path), "--json", "history"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["reason"]


def test_tasks_json_is_valid_json_with_the_task_list(tmp_path, capsys):
    """`tasks --json` parses, and the count is a number the caller can trust."""
    assert main(["--project-root", str(tmp_path), "--json", "tasks"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload["count"], int)
    assert payload["count"] == len(payload["tasks"])


def test_loop_rejects_a_non_positive_interval(tmp_path, capsys):
    """A zero or negative interval is refused, not scheduled."""
    assert main(["--project-root", str(tmp_path), "loop", "t", "--interval", "0"]) == 1
    assert "positive" in capsys.readouterr().err


def test_bootstrap_then_status(tmp_path, capsys):
    """The reachable path: generate a team, then read it back."""
    assert main(["--project-root", str(tmp_path), "bootstrap"]) == 0
    capsys.readouterr()

    assert (tmp_path / "theteam.config").is_file()
    assert (tmp_path / ".omp" / "theteam").is_dir()

    assert main(["--project-root", str(tmp_path), "--json", "status"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["roster"]["active"] >= 3


def test_two_disjoint_projects_get_different_rosters(tmp_path):
    """The §1.2 promise: structure decides the team, not a constant."""
    from theteam import generate_team_members_from_context

    web = tmp_path / "pyweb"
    (web / "api").mkdir(parents=True)
    (web / "requirements.txt").write_text("fastapi\nsqlalchemy\npsycopg2-binary\n")
    # security_focus reads pyproject.toml / package.json, not requirements-dev.
    (web / "pyproject.toml").write_text('[tool.poetry.dependencies]\nbandit="*"\n')
    (web / "package.json").write_text('{"dependencies":{"react":"19"}}')

    cli = tmp_path / "rustcli"
    (cli / "src").mkdir(parents=True)
    (cli / "Cargo.toml").write_text('[package]\nname="rustcli"\n[dependencies]\nclap="4"\n')

    web_ids = {m["id"] for m in generate_team_members_from_context(str(web))["team"]}
    cli_ids = {m["id"] for m in generate_team_members_from_context(str(cli))["team"]}

    assert web_ids != cli_ids, "structurally different projects produced the same roster"
    assert {"api", "data", "security", "designer"} <= web_ids, f"web project: {web_ids}"
    assert cli_ids == {"architect", "pragmatist", "skeptic"}, cli_ids
