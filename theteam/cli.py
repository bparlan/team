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
from pathlib import Path
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


# ======= comment (M5) =======

# ARCHITECTURE.md §2: `comment on` takes --max-members, default 3, hard cap 4.
# The cap is the ceiling on how many members the commentary layer may call in
# one tick. Exceeding it is a bug in the caller, and clamping silently would
# hide that bug behind a command that looks like it worked, so the request is
# refused with a named reason instead.
COMMENT_MAX_MEMBERS = 4
COMMENT_MAX_MEMBERS_DEFAULT = 3


def _now_iso() -> str:
    """UTC timestamp for the on-marker.

    UTC, not local: the controller compares this against its own clock to
    report the marker's age, and a timezone that changes under a moving user
    would make that age wrong.
    """
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _comment_state_path(store: StateStore) -> Path:
    """The one path the commentary state lives at.

    Three call sites need it - status, the read-modify-write in `on`/`off`, and
    the future controller - and a filename spelled out three times is three
    chances to end up reading different files.
    """
    return store.root / "commentary.json"


def _comment_status_payload(store: StateStore) -> Dict[str, Any]:
    """The `status` view: whether commentary is on, and what it last did.

    `on` is the presence of the on-marker, nothing else. The marker is the same
    file the commentary controller checks, so the two cannot disagree about
    whether the team is meant to be speaking.
    """
    on_marker = store.root / "commentary.on"
    state = store.read_json(_comment_state_path(store))
    return {
        "on": on_marker.exists(),
        "marker": str(on_marker) if on_marker.exists() else None,
        "max_members": state.get("max_members", COMMENT_MAX_MEMBERS_DEFAULT),
        "last_digest": state.get("last_digest"),
        "last_opinion": state.get("last_opinion"),
        "tick_count": state.get("tick_count", 0),
    }


def _comment_read_state(store: StateStore) -> Dict[str, Any]:
    """The commentary state document, or an empty one before the first write.

    The controller owns the fields it produces (last digest, last opinion, tick
    count); `on`/`off` own only `on` and `max_members`. Both read through here,
    so neither has to know the file name.
    """
    return store.read_json(_comment_state_path(store))


def _comment_write_state(store: StateStore, state: Dict[str, Any]) -> None:
    """Write the commentary state document.

    One file at the state root, one writer path, so `comment status` and the
    controller read the same document. A malformed file raises out of
    `read_json` rather than resetting to defaults: a state file that cannot be
    parsed is evidence, and overwriting it would destroy the evidence.
    """
    with open(_comment_state_path(store), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True, default=str)


def cmd_comment(args: argparse.Namespace) -> int:
    """Continuous in-context commentary: `comment on|off|status`.

    `on` writes the on-marker and records the member budget. `off` removes it
    and writes the stop sentinel the controller reads on its next tick.
    `status` reports what is currently true. All three support `--json`.
    """
    action = getattr(args, "comment_action", None)
    if action is None:
        # A bare `theteam comment`. argparse's own exit here would be 2; the
        # surface contract names 1 for a usage mistake, and every other command
        # in this file returns 1, so the command reports it itself.
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "command": "comment",
                              "reason": "missing subcommand: on|off|status"},
                             indent=2))
        else:
            print("theteam comment: missing subcommand: on|off|status",
                  file=sys.stderr)
        return EXIT_ERROR

    # The cap is checked before anything is created, so a refused request
    # leaves no state behind at all.
    if action == "on" and args.max_members > COMMENT_MAX_MEMBERS:
        return _fail(args, "comment on",
                     f"--max-members {args.max_members} exceeds the cap of "
                     f"{COMMENT_MAX_MEMBERS}")

    store = StateStore(_project_root(args))
    store.ensure()
    state = _comment_read_state(store)

    if action == "on":
        marker = store.root / "commentary.on"
        marker.write_text(
            json.dumps({"max_members": args.max_members,
                        "started_at": _now_iso()}),
            encoding="utf-8",
        )
        # `off` writes the stop sentinel, so `on` has to remove it. Without
        # this the sentinel outranks the on-marker in every tick and `off` is
        # permanent: the user turns commentary back on and every tick still
        # reports `stopped`.
        if store.commentary_stop.exists():
            store.commentary_stop.unlink()
        _comment_write_state(store, dict(state, on=True,
                                         max_members=args.max_members))
        return _emit(args, {"ok": True, "on": True,
                            "max_members": args.max_members,
                            "marker": str(marker)},
                     f"commentary on (max {args.max_members} members)")

    if action == "off":
        marker = store.root / "commentary.on"
        if marker.exists():
            marker.unlink()
        # The sentinel is written, not just the marker removed: a controller
        # mid-tick must still see the stop and report `spoke: false,
        # reason: "stopped"` rather than reading the marker's absence.
        store.commentary_stop.write_text("stop\n", encoding="utf-8")
        _comment_write_state(store, dict(state, on=False))
        return _emit(args, {"ok": True, "on": False,
                            "sentinel": str(store.commentary_stop)},
                     "commentary off")

    payload = _comment_status_payload(store)
    return _emit(args, payload, f"commentary {'on' if payload['on'] else 'off'}")


# ======= parser =======

MILESTONE_OF = {
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

    comment = sub.add_parser("comment", help="Continuous in-context commentary.")
    # `required=False` so a bare `theteam comment` reaches `cmd_comment`
    # rather than argparse exiting 2. The command then prints its own usage
    # error and returns 1, which is the exit code §2 promises for a usage
    # mistake. argparse's default of 2 would also be honest, but it is not
    # the one the surface contract names.
    comment_action = comment.add_subparsers(dest="comment_action", required=False)

    comment_on = comment_action.add_parser("on", help="Start commentary for the session.")
    comment_on.add_argument("--max-members", type=int, default=COMMENT_MAX_MEMBERS_DEFAULT,
                            help=f"Members the commentary layer may call per tick. "
                                 f"Default {COMMENT_MAX_MEMBERS_DEFAULT}, hard cap "
                                 f"{COMMENT_MAX_MEMBERS}. Above the cap is refused, not clamped.")
    comment_on.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                            help="Machine-readable output.")
    comment_on.set_defaults(func=cmd_comment)

    comment_off = comment_action.add_parser("off", help="Stop commentary. Takes effect next tick.")
    comment_off.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                             help="Machine-readable output.")
    comment_off.set_defaults(func=cmd_comment)

    comment_status = comment_action.add_parser("status", help="Is commentary on, and what did it last do?")
    comment_status.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                                help="Machine-readable output.")
    comment_status.set_defaults(func=cmd_comment)

    # The bare `comment` still needs a handler, and it is the one that reports
    # the missing subcommand. Without this default argparse has no `func` and
    # the command dies on an AttributeError instead of a usage error.
    comment.set_defaults(func=cmd_comment)

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
