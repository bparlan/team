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
from typing import Any, Dict, List, Optional

import yaml

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
    """The trust surface: roster, state, task counts, audit chain, breaker states."""
    from theteam.core.audit_chain import chain_line, read_chain_state
    from theteam.core.member import load_config

    project_root = _project_root(args)
    store = StateStore(project_root)
    config, error = load_config(project_root)
    if config is None:
        return _fail(args, "status", f"{error}. Run: theteam bootstrap {project_root}")

    roster = [m.get("id") for m in config.get("team", []) if m.get("enabled", True)]
    tasks = store.read_json(store.task_registry).get("tasks", {})
    schedule = store.read_json(store.task_schedule)
    scheduled = schedule.get("scheduled_tasks", {})
    last_run = schedule.get("last_run", {})
    chain = read_chain_state(project_root)

    # Breaker state is read from what a real CircuitBreaker wrote, never
    # inferred. A task that has never run has no measured breaker, and says so.
    breakers = {
        task_id: {
            "state": entry.get("breaker"),
            "consecutive_failures": entry.get("breaker_consecutive_failures"),
        }
        for task_id, entry in last_run.items()
    }
    trips = sorted(t for t, b in breakers.items() if b["state"] == "open")

    payload = {
        "project_root": project_root,
        "state_dir": str(store.root),
        "roster": {"active": len(roster), "members": roster},
        "tasks": {"registered": len(tasks), "scheduled": len(scheduled),
                  "breaker_trips": trips},
        "breakers": breakers,
        "audit_chain": chain,
    }
    lines = [
        f"project        {project_root}",
        f"state          {store.root}",
        f"roster         {len(roster)} members active ({', '.join(roster) or 'none'})",
        f"tasks          {len(tasks)} registered, {len(scheduled)} scheduled, "
        f"{len(trips)} breaker trips",
        chain_line(chain),
    ]
    return _emit(args, payload, "\n".join(lines))


def cmd_discuss(args: argparse.Namespace) -> int:
    """One-shot discussion. Outside OMP it fails; it never invents an opinion."""
    from theteam import run_discussion

    project_root = _project_root(args)
    return EXIT_OK if run_discussion(project_root, args.topic) else EXIT_ERROR


def cmd_loop(args: argparse.Namespace) -> int:
    """Schedule one registered task to run on an interval."""
    from theteam.tasks.repository import TaskRepository

    if args.interval <= 0:
        return _fail(args, "loop", f"--interval must be positive, got {args.interval}")

    repo = TaskRepository(_project_root(args))
    try:
        next_run = repo.schedule_task(args.task_id, args.interval)
    except KeyError:
        return _fail(args, "loop", f"Task not found: {args.task_id}")
    return _emit(args, {"task_id": args.task_id, "interval_minutes": args.interval,
                        "next_run": next_run},
                 f"{args.task_id} scheduled every {args.interval}m, "
                 f"next run {next_run}")

def cmd_tasks(args: argparse.Namespace) -> int:
    """Every task and its state. An empty list reports why it is empty."""
    from theteam.tasks.repository import TaskRepository

    payload = TaskRepository(_project_root(args)).list_tasks()
    lines = [
        f"{'order':>5}  {'id':<24} {'type':<12} {'pri':>3}  "
        f"{'next run':<30} breaker",
    ]
    for task in payload["tasks"]:
        # `never run` is not `closed`. The column prints what was measured,
        # and prints nothing measured as its own word (§3.3).
        breaker = task["breaker"] or "never run"
        lines.append(
            f"{task['order'] if task['order'] is not None else '-':>5}  "
            f"{task['id']:<24} {str(task['type'] or '-'):<12} "
            f"{task['priority']:>3}  "
            f"{(task['next_run'] or 'not scheduled'):<30} {breaker}"
        )
    lines.append(f"{payload['count']} tasks, {payload['yaml_count']} in YAML")
    return _emit(args, payload, "\n".join(lines))


def cmd_run(args: argparse.Namespace) -> int:
    """Execute everything currently due. Nothing due means nothing happens."""
    from theteam.tasks.executor import TaskExecutor
    from theteam.tasks.repository import TaskRepository

    project_root = _project_root(args)
    repo = TaskRepository(project_root)
    due = repo.due(only=args.only)
    # Breakers outlive the process: a task whose breaker tripped an hour ago
    # must still be tripped now, or the trip only survives as long as the run
    # that observed it. The repository owns the schedule (Layer 2), so it hands
    # the measured state to the executor (Layer 3) rather than the reverse.
    executor = TaskExecutor(project_root, breaker_states=repo.schedule()["last_run"])

    results = []
    for task in due:
        # Missing script is reported, never silently skipped as a success.
        missing = [p["script"] for p in task.get("phases", [])
                   if not os.path.exists(os.path.join(project_root, p["script"]))]
        if missing:
            detail = f"missing script: {', '.join(missing)}"
            repo.record_run(task["id"], "skipped", detail)
            results.append({"id": task["id"], "result": "skipped", "detail": detail})
            continue
        outcome = executor.execute_task(task)
        breaker = outcome["breaker"]
        consecutive = outcome["breaker_consecutive_failures"]
        if outcome.get("skipped"):
            # §3.2: the reason is the literal `breaker_open`, and it is
            # persisted so `theteam tasks` and `theteam history` still show it
            # in a later process.
            reason = outcome["skip_reason"]
            repo.record_run(task["id"], "skipped", reason, breaker=breaker,
                            consecutive_failures=consecutive)
            results.append({"id": task["id"], "result": "skipped", "detail": reason})
            continue
        ok = outcome["overall_success"]
        repo.record_run(task["id"], "ok" if ok else "failed",
                        "" if ok else f"returncode {outcome['phases'][-1].get('returncode')}",
                        breaker=breaker, consecutive_failures=consecutive)
        results.append({"id": task["id"], "result": "ok" if ok else "failed"})

    payload = {
        # `ran` counts what actually executed. A task with a missing script was
        # due but never ran, so counting it would report work that never happened.
        "ran": sum(1 for r in results if r["result"] in ("ok", "failed")),
        "skipped": sum(1 for r in results if r["result"] == "skipped"),
        "failures": sum(1 for r in results if r["result"] == "failed"),
        "results": results,
    }
    if not due:
        return _emit(args, payload, "nothing due")
    lines = [f"{r['id']}: {r['result']}" + (f" ({r['detail']})" if r.get("detail") else "")
             for r in results]
    lines.append(f"{payload['ran']} ran, {payload['skipped']} skipped, "
                 f"{payload['failures']} failed")
    return _emit(args, payload, "\n".join(lines))

def cmd_history(args: argparse.Namespace) -> int:
    """Per-task success rate, last run, last failure, consecutive failures (§7.1.7).

    Reads the two states S1 and S3 wrote: the schedule's `last_run` entry for
    breaker state, and the execution log for the run record. A task with no
    runs reports that, not a 0% success rate that reads like a measurement.
    """
    from theteam.tasks.repository import TaskRepository

    project_root = _project_root(args)
    repo = TaskRepository(project_root)
    schedule = repo.schedule()
    rows = []
    for task_id in [t["id"] for t in repo.all_tasks()]:
        last = schedule["last_run"].get(task_id, {})
        runs = _task_runs(project_root, task_id)
        failures = [r for r in runs if not r.get("overall_success")]
        rows.append({
            "id": task_id,
            "runs": len(runs),
            "successes": len(runs) - len(failures),
            "failures": len(failures),
            # None, not 0.0: with no runs there is no rate to report, and 0.0
            # is indistinguishable from a task that has never once passed.
            "success_rate": (round(100.0 * (len(runs) - len(failures)) / len(runs), 1)
                             if runs else None),
            "last_run": last.get("at"),
            "last_result": last.get("result"),
            "last_failure": failures[-1].get("timestamp") if failures else None,
            "breaker": last.get("breaker"),
            "consecutive_failures": last.get("breaker_consecutive_failures"),
        })
    if args.task:
        rows = [r for r in rows if r["id"] == args.task]
        if not rows:
            return _fail(args, "history", f"no task '{args.task}'")

    payload = {"tasks": rows, "count": len(rows)}
    if not rows:
        return _emit(args, payload, "no tasks")
    lines = [f"{'id':<24} {'runs':>4} {'rate':>6} {'consec':>6}  breaker"]
    for row in rows:
        rate = f"{row['success_rate']:.1f}%" if row["success_rate"] is not None else "-"
        lines.append(
            f"{row['id']:<24} {row['runs']:>4} {rate:>6} "
            f"{str(row['consecutive_failures'] if row['consecutive_failures'] is not None else '-'):>6}  "
            f"{row['breaker'] or 'never run'}"
        )
    return _emit(args, payload, "\n".join(lines))


def _task_runs(project_root: str, task_id: str) -> List[Dict]:
    """Every logged execution of one task, oldest first. Unparseable lines skipped."""
    path = StateStore(project_root).execution_log
    if not path.exists():
        return []
    runs = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("task_id") == task_id:
                runs.append(record)
    return runs


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


def cmd_task(args: argparse.Namespace) -> int:
    """Single-task operations. Every write reports what it did to what."""
    from theteam.tasks.repository import TaskRepository

    repo = TaskRepository(_project_root(args))
    action = args.task_command

    if action == "create":
        task_id = repo.create(_definition(args.path))
        return _emit(args, {"id": task_id, "created": True}, f"created {task_id}")

    if action == "edit":
        patch = _patch(args.patch)
        repo.update(args.task_id, patch)
        return _emit(args, {"id": patch.get("id", args.task_id), "patched": list(patch)},
                     f"edited {args.task_id}")

    if action == "delete":
        plan = _delete_plan(repo, args.task_id)
        if not args.yes:
            return _emit(args, plan, "would clean up:\n" + "\n".join(plan["will_remove"])
                         + "\nre-run with --yes to do it")
        repo.delete(args.task_id)
        return _emit(args, plan, f"deleted {args.task_id}")

    task = repo.get(args.task_id)
    if task is None:
        return _fail(args, "task show", f"no task '{args.task_id}'")
    return _emit(args, task, yaml.safe_dump(task, sort_keys=False).rstrip())


def _definition(path: Optional[str]) -> Dict[str, Any]:
    """A task definition from its YAML file. Named, never invented."""
    if not path:
        raise ValueError("--path is required")
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _patch(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        raise ValueError("--patch is required")
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _delete_plan(repo, task_id: str) -> Dict[str, Any]:
    """What a delete will touch, named before it does."""
    schedule = repo.schedule()
    will = [f"tasks/{repo._yaml[task_id]['source_file']}"] if task_id in repo._yaml else []
    if task_id in schedule["scheduled_tasks"]:
        will.append("schedule entry")
    if task_id in schedule["last_run"]:
        will.append("run history")
    return {"id": task_id, "will_remove": will}


# ======= parser =======

MILESTONE_OF = {
    "comment": "M5",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="theteam",
        description="A panel of expert reviewers that reads your real session, "
                    "plus your scheduled project tasks.",
    )
    parser.add_argument("--project-root", default=os.environ.get("THETEAM_PROJECT_ROOT"),
                        help="Project the command applies to. Defaults to $PWD.")
    # `--json` is accepted on either side of the subcommand. `SUPPRESS` keeps a
    # subparser copy from clobbering a value already parsed from the parent.
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="Machine-readable output.")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap", help="Generate a team for this project.")
    bootstrap.add_argument("path", nargs="?", help="Project root. Defaults to --project-root.")
    bootstrap.add_argument("--interactive", action="store_true", help="Ask before writing.")
    bootstrap.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="Machine-readable output.")
    bootstrap.set_defaults(func=cmd_bootstrap)

    status = sub.add_parser("status", help="Roster, state directory, task counts.")
    status.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="Machine-readable output.")
    status.set_defaults(func=cmd_status)

    discuss = sub.add_parser("discuss", help="One-shot team discussion, this turn only.")
    discuss.add_argument("topic")
    discuss.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="Machine-readable output.")
    discuss.set_defaults(func=cmd_discuss)

    serve = sub.add_parser("serve", help="Prometheus metrics endpoint.")
    serve.add_argument("--port", type=int,
                       default=int(os.environ.get("THETEAM_METRICS_PORT", "8000")))
    serve.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="Machine-readable output.")
    serve.set_defaults(func=cmd_serve)

    loop = sub.add_parser("loop", help="Schedule a registered task to run on an interval.")
    loop.add_argument("task_id")
    loop.add_argument("--interval", type=int, default=60,
                      help="Minutes between runs. Default 60.")
    loop.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="Machine-readable output.")
    loop.set_defaults(func=cmd_loop)


    tasks = sub.add_parser("tasks", help="List every task and its state.")
    tasks.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                       help="Machine-readable output.")
    tasks.set_defaults(func=cmd_tasks)

    run = sub.add_parser("run", help="Execute everything currently due.")
    run.add_argument("--only", help="Run one task id, ignoring the rest.")
    run.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                     help="Machine-readable output.")
    run.set_defaults(func=cmd_run)

    history = sub.add_parser("history", help="Success rate, last run, last failure.")
    history.add_argument("--task", help="One task id, ignoring the rest.")
    history.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                         help="Machine-readable output.")
    history.set_defaults(func=cmd_history)

    task = sub.add_parser("task", help="Create, edit, delete or show one task.")
    task_action = task.add_subparsers(dest="task_command", required=True)

    task_create = task_action.add_parser("create", help="Create a task from a YAML file.")
    task_create.add_argument("--path", required=True, help="YAML file holding the definition.")
    task_create.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                             help="Machine-readable output.")
    task_create.set_defaults(func=cmd_task)

    task_edit = task_action.add_parser("edit", help="Patch an existing task.")
    task_edit.add_argument("task_id")
    task_edit.add_argument("--patch", required=True, help="YAML file holding the patch.")
    task_edit.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                           help="Machine-readable output.")
    task_edit.set_defaults(func=cmd_task)

    task_delete = task_action.add_parser("delete", help="Delete a task and its references.")
    task_delete.add_argument("task_id")
    task_delete.add_argument("--yes", action="store_true", help="Actually delete.")
    task_delete.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                             help="Machine-readable output.")
    task_delete.set_defaults(func=cmd_task)

    task_show = task_action.add_parser("show", help="Show one task as stored.")
    task_show.add_argument("task_id")
    task_show.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                           help="Machine-readable output.")
    task_show.set_defaults(func=cmd_task)

    # Declared so the rest of the surface in ARCHITECTURE.md §2 is discoverable
    # from `--help`; each refuses until its milestone lands.
    for name, milestone in MILESTONE_OF.items():
        pending = sub.add_parser(name, add_help=False)
        pending.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="Machine-readable output.")
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
    except (KeyError, ValueError) as exc:
        # str(KeyError("x")) wraps the message in quotes ("'x'"). The user sees
        # the cause, not its repr. Same for ValueError if it leaks a repr.
        message = exc.args[0] if exc.args else str(exc)
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": message}, indent=2))
        else:
            print(f"theteam {args.command}: {message}", file=sys.stderr)
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
