#!/usr/bin/env python3
"""
theteam.cli - the only entry point. Layer 0: arguments, exit codes, JSON.

Every command takes an explicit project root, returns a real exit code, and
supports `--json`. Nothing in here knows a domain object; it dispatches and
formats.

Commands that belong to a later milestone refuse themselves out loud rather
than returning a plausible-looking empty result. That is the §3.3 rule: a
default is fine when the user asked for a default, and not fine when it reads
like a measurement.
"""

import argparse
import functools
import json
import os
import sys
from typing import Any, List, Optional

from theteam.state import StateStore

EXIT_OK = 0
EXIT_ERROR = 1


# ======= helpers =======

def _project_root(args: argparse.Namespace) -> str:
    return os.path.abspath(args.project_root or os.getcwd())


def _emit(args: argparse.Namespace, payload: Any, text: str) -> int:
    """Print the payload as JSON or the human line. One code path for both."""
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(text)
    return EXIT_OK


def _fail(args: argparse.Namespace, command: str, reason: str) -> int:
    """A command that exists and failed. Report the reason, nothing else."""
    if getattr(args, "json", False):
        print(json.dumps({"ok": False, "command": command, "reason": reason}, indent=2))
    else:
        print(f"theteam {command}: {reason}", file=sys.stderr)
    return EXIT_ERROR


def _refuse(args: argparse.Namespace, command: str, reason: str) -> int:
    """A command that does not exist yet. Say so, and when it lands."""
    if getattr(args, "json", False):
        print(json.dumps({"ok": False, "command": command, "reason": reason}, indent=2))
    else:
        print(f"theteam {command}: {reason}")
        print(f"It lands in {MILESTONE_OF[command]}. "
              "'theteam bootstrap' and 'theteam status' work today.")
    return EXIT_ERROR


# ======= commands =======

def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Generate a team for a project. Non-interactive unless asked."""
    from theteam import bootstrap_flow

    project_root = os.path.abspath(args.path or _project_root(args))
    if not os.path.isdir(project_root):
        return _fail(args, "bootstrap", f"Not a directory: {project_root}")

    if args.interactive:
        print("Interactive bootstrap is not implemented; the generated team is the default.")
    if not bootstrap_flow(project_root):
        return EXIT_ERROR
    config_path = os.path.join(project_root, "theteam.config")
    state = StateStore(project_root).ensure()
    return _emit(args,
                 {"ok": True, "config": config_path, "state_dir": str(state)},
                 f"Config written to {config_path}\nState directory: {state}")


def cmd_status(args: argparse.Namespace) -> int:
    """The trust surface: roster, state directory, task counts."""
    from theteam.core.member import load_config

    project_root = _project_root(args)
    store = StateStore(project_root)
    config, error = load_config(project_root)
    if config is None:
        return _fail(args, "status", f"{error}. Run: theteam bootstrap {project_root}")

    roster = [m.get("id") for m in config.get("team", []) if m.get("enabled", True)]
    tasks = store.read_json(store.task_registry).get("tasks", {})
    scheduled = store.read_json(store.task_schedule).get("scheduled_tasks", {})

    payload = {
        "project_root": project_root,
        "state_dir": str(store.root),
        "roster": {"active": len(roster), "members": roster},
        "tasks": {"registered": len(tasks), "scheduled": len(scheduled)},
        "audit_chain": {
            "file": str(store.audit_dir / "chain.jsonl"),
            "verified": False,
            "reason": "chain verification lands with the M4 audit wiring",
        },
    }
    lines = [
        f"project        {project_root}",
        f"state          {store.root}",
        f"roster         {len(roster)} members active ({', '.join(roster) or 'none'})",
        f"tasks          {len(tasks)} registered, {len(scheduled)} scheduled",
        f"audit chain    not verifiable yet ({payload['audit_chain']['reason']})",
    ]
    return _emit(args, payload, "\n".join(lines))


def cmd_discuss(args: argparse.Namespace) -> int:
    """One-shot discussion. Outside OMP it fails; it never invents an opinion."""
    from theteam import run_discussion

    project_root = _project_root(args)
    return EXIT_OK if run_discussion(project_root, args.topic) else EXIT_ERROR


def cmd_loop(args: argparse.Namespace) -> int:
    """Schedule one registered task to run on an interval."""
    from theteam.subskills.task_stack.orchestrator import TaskStackOrchestrator

    if args.interval <= 0:
        return _fail(args, "loop", f"--interval must be positive, got {args.interval}")

    result = TaskStackOrchestrator(_project_root(args)).loop_task(args.task_id, args.interval)
    if not result.get("success"):
        return _fail(args, "loop", result.get("error", "loop failed"))
    return _emit(args, result,
                 f"{result['task_id']} scheduled every {result['interval_minutes']}m, "
                 f"next run {result['next_run']}")


def cmd_serve(args: argparse.Namespace) -> int:
    """The metrics endpoint. The only thing in the product that starts a server."""
    from theteam.core.metrics import MetricsCollector
    from theteam.core.unified_loop import LoopConfig, UnifiedLoop

    project_root = _project_root(args)
    loop = UnifiedLoop(project_root, LoopConfig(loop_id="theteam", project_root=project_root))
    loop.start()
    collector = MetricsCollector(port=args.port)
    collector.bind(loop=loop, limiter=loop.resource_limiter)
    if not collector.start_http_server():
        print("Metrics endpoint failed to start.", file=sys.stderr)
        loop.stop()
        return EXIT_ERROR
    print(f"theteam serving /metrics and /health on port {args.port}")
    try:
        import threading

        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        collector.stop()
        loop.stop()
    return EXIT_OK


# ======= parser =======

MILESTONE_OF = {
    "comment": "M5",
    "tasks": "M2",
    "task": "M3",
    "run": "M2",
    "history": "M4",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="theteam",
        description="A panel of expert reviewers that reads your real session, "
                    "plus your scheduled project tasks.",
    )
    parser.add_argument("--project-root", default=os.environ.get("THETEAM_PROJECT_ROOT"),
                        help="Project the command applies to. Defaults to $PWD.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap", help="Generate a team for this project.")
    bootstrap.add_argument("path", nargs="?", help="Project root. Defaults to --project-root.")
    bootstrap.add_argument("--interactive", action="store_true", help="Ask before writing.")
    bootstrap.set_defaults(func=cmd_bootstrap)

    status = sub.add_parser("status", help="Roster, state directory, task counts.")
    status.set_defaults(func=cmd_status)

    discuss = sub.add_parser("discuss", help="One-shot team discussion, this turn only.")
    discuss.add_argument("topic")
    discuss.set_defaults(func=cmd_discuss)

    serve = sub.add_parser("serve", help="Prometheus metrics endpoint.")
    serve.add_argument("--port", type=int,
                       default=int(os.environ.get("THETEAM_METRICS_PORT", "8000")))
    serve.set_defaults(func=cmd_serve)

    loop = sub.add_parser("loop", help="Schedule a registered task to run on an interval.")
    loop.add_argument("task_id")
    loop.add_argument("--interval", type=int, default=60,
                      help="Minutes between runs. Default 60.")
    loop.set_defaults(func=cmd_loop)

    # Declared so the surface in ARCHITECTURE.md §2 is discoverable from
    # `--help`; each refuses until its milestone lands.
    for name, milestone in MILESTONE_OF.items():
        pending = sub.add_parser(name, add_help=False)
        pending.set_defaults(func=functools.partial(
            _refuse, command=name, reason=f"not implemented yet ({milestone})"))

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return EXIT_ERROR
    except Exception as exc:
        # A named failure with its cause. Never a stack trace the user has to
        # read, never a value that looks like a result.
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"theteam {args.command}: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
