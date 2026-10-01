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
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from theteam.state import StateStore
from theteam.core.run_context import write_run_context

EXIT_OK = 0
EXIT_ERROR = 1


def _configure_logging() -> None:
    """The one place the product sets up logging.

    This used to be `logging.basicConfig(level=logging.INFO)` at module scope in
    25 modules, so importing theteam - which the CLI, the executor and the tests
    all do - attached a stderr handler to the *host's* root logger before the
    host had configured logging of its own. An OMP session or a test runner that
    had chosen WARNING inherited INFO output it never asked for.

    `force=False` is the default: if the host already configured the root
    logger, this leaves it alone. That is what makes it safe to call at all.
    """
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


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



# ======= manager (M9 Phase 2) =======

def _manager_config_path(project_root: str) -> str:
    """Where the roster lives. One path, named once."""
    return os.path.join(project_root, "theteam.config")


def _load_project_config(project_root: str):
    """The project's config, or `(None, reason)`. Never a default roster."""
    path = _manager_config_path(project_root)
    if not os.path.isfile(path):
        return None, f"no theteam.config at {path}; run 'theteam bootstrap' first"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle), None
    except (OSError, yaml.YAMLError) as e:
        return None, f"cannot read {path}: {e}"


def _write_project_config(project_root: str, config: Dict[str, Any]) -> Optional[str]:
    """Write a roster through the same validator bootstrap uses, or refuse.

    Returns an error string, or None on success. The write is validated
    *before* it reaches disk, because a config that fails validation is a
    config that breaks every later command — and §3.3 forbids leaving one.
    """
    from theteam.bin.theteam_config import validate_config

    is_valid, message = validate_config(config)
    if not is_valid:
        return f"refusing to write an invalid config: {message}"
    path = _manager_config_path(project_root)
    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(config, handle, default_flow_style=False, sort_keys=False)
    return None


def cmd_manager(args: argparse.Namespace) -> int:
    """`manager --topic | --status | --reset [--apply]`. Grows the roster.

    Three steps, and the middle one is the user: `--topic` **proposes**,
    `--apply` **persists**. A bare `--topic` writes nothing, because
    `--topic` also fires on every *uncovered project flag* — a plain
    `theteam manager --topic "anything"` would otherwise grow the user's
    committed config as a side effect of asking a question.

    The decision of *whether* to add a member is deterministic
    (`advisory.manager.detect_triggers`): this command proposes, reports the
    evidence, and persists on request. It decides nothing on its own, and it
    never asks a model to invent a member.
    """
    from theteam.advisory.manager import (
        CATALOG,
        detect_triggers,
        reasons_for,
        reset_roster,
    )

    project_root = _project_root(args)
    config, reason = _load_project_config(project_root)
    if config is None:
        return _fail(args, "manager", reason)

    from theteam import analyze_project_context
    context = analyze_project_context(project_root)
    roster = list(config.get("team") or [])

    if args.reset:
        fresh = reset_roster(project_root)
        error = _write_project_config(project_root, dict(config, team=fresh))
        if error:
            return _fail(args, "manager --reset", error)
        return _emit(args,
                     {"ok": True, "reset": True,
                      "team": [m["id"] for m in fresh]},
                     f"roster reset to {len(fresh)} member(s): "
                     f"{', '.join(m['id'] for m in fresh)}")

    if args.status:
        lines = []
        members = []
        unjustified = []
        for member in roster:
            why = reasons_for(member.get("id", ""), context, member=member)
            members.append({"id": member.get("id"),
                            "role": member.get("role"),
                            "enabled": member.get("enabled", True),
                            "reasons": why})
            lines.append(f"  {member.get('id')}: {'; '.join(why)}")
            if why and "no recorded reason" in why[0]:
                unjustified.append(member.get("id"))
        # A member on the roster with no evidence is reported, not hidden.
        payload = {"ok": True, "members": members,
                   "roster_size": len(roster),
                   "catalog_size": len(CATALOG),
                   "unjustified": unjustified}
        text = "\n".join(lines) or "  (no members on the roster)"
        if unjustified:
            text += f"\n  no recorded reason: {', '.join(unjustified)}"
        return _emit(args, payload, text)

    if not args.topic:
        return _fail(args, "manager",
                     "one of --topic, --status or --reset is required")

    detected = detect_triggers(args.topic, context, roster)
    proposal = detected["add"]

    if not proposal:
        return _emit(args,
            {"ok": True, "proposed": [], "applied": False,
             "considered": args.topic,
             "roster": [m.get("id") for m in roster]},
            f"roster already covers '{args.topic}' ({len(roster)} members)")

    additions = [{"id": c["member"],
                  "role": CATALOG[c["member"]].get("role"),
                  "reasons": c["reasons"]} for c in proposal]
    lines = [f"  + {a['id']}: {'; '.join(a['reasons'])}" for a in additions]
    proposed_roster = sorted({m.get("id") for m in roster}
                             | {a["id"] for a in additions})

    if not args.apply:
        # Proposal only. Nothing is written, so this is safe to run to see
        # what the manager thinks before deciding.
        return _emit(args,
            {"ok": True, "proposed": additions, "applied": False,
             "considered": args.topic, "roster": proposed_roster,
             "hint": "re-run with --apply to persist"},
            f"proposed {len(additions)} addition(s); nothing written yet\n"
            + "\n".join(lines)
            + "\nre-run with --apply to persist")

    by_id = {m.get("id"): m for m in roster}
    for addition in additions:
        member = dict(CATALOG[addition["id"]])
        member["enabled"] = True
        # The reason is recorded with the member, not re-derived later. A
        # topic-triggered addition cannot be re-justified from live project
        # context — the flag never fired — so a `--status` that re-derives
        # would report the member the manager just added as unjustified.
        # A recorded fact is a fact; a re-derivation is a guess.
        member["added_reason"] = addition["reasons"]
        member["added_for_topic"] = args.topic
        by_id[addition["id"]] = member
    new_roster = list(by_id.values())
    error = _write_project_config(project_root, dict(config, team=new_roster))
    if error:
        return _fail(args, "manager", error)

    return _emit(args,
        {"ok": True, "proposed": additions, "applied": True,
         "considered": args.topic,
         "roster": [m.get("id") for m in new_roster]},
        f"roster grew to {len(new_roster)} member(s)\n" + "\n".join(lines))


def status_payload(project_root: str):
    """The `status` view, as data: `(payload, lines)` on success,
    `(None, error_message)` when the project is not bootstrapped.

    Split out from `cmd_status` so the terminal renderer reads the same surface
    without emitting it. `status` keeps sole ownership of formatting and of the
    `--json` switch: a renderer that reprints the command output is breaking
    the agentic contract §2 promises.
    """
    from theteam.core.audit_chain import chain_line, read_chain_state
    from theteam.core.member import load_config

    store = StateStore(project_root)
    config, error = load_config(project_root)
    if config is None:
        return None, error

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
    return payload, lines


def cmd_status(args: argparse.Namespace) -> int:
    """The trust surface: roster, state, task counts, audit chain, breaker states."""
    payload, lines = status_payload(_project_root(args))
    if payload is None:
        return _fail(args, "status", f"{lines}. Run: theteam bootstrap "
                                    f"{_project_root(args)}")
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

def tasks_payload(project_root: str):
    """The `tasks` view as data: `(payload, lines)`, or `(None, error)`.

    The renderer reads the same rows `theteam tasks` prints. It is the same
    data, not a second source: §2 makes these commands the machine surface.
    """
    from theteam.tasks.repository import TaskRepository

    payload = TaskRepository(project_root).list_tasks()
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
    return payload, lines


def cmd_tasks(args: argparse.Namespace) -> int:
    """Every task and its state. An empty list reports why it is empty."""
    payload, lines = tasks_payload(_project_root(args))
    return _emit(args, payload, "\n".join(lines))


def _phase_problem(task, project_root):
    """Why this task cannot run, or `None` when it can.

    M9 Phase 4. Two rules, both named rather than inferred:

    1. A phase names **exactly one** runner: `script:` or `runner: llm`.
       Both is ambiguous — which one runs? Neither is dead weight that
       would otherwise read as "ran, did nothing".
    2. A `script:` phase's script must exist on disk, exactly as before.

    A `runner: llm` phase deliberately does **not** need a script: its
    instructions live in `prompt_file`, and a missing provider is a named
    failure from the runner, not a skip decided here.
    """
    for phase in task.get("phases", []) or []:
        if not isinstance(phase, dict):
            continue
        name = phase.get("name", "?")
        has_script = bool(phase.get("script"))
        has_runner = bool(phase.get("runner") == "llm")
        if has_script and has_runner:
            return f"phase '{name}' names both script and runner: llm"
        if not has_script and not has_runner:
            return f"phase '{name}' names no runner: needs script or runner: llm"
        if has_script and not os.path.exists(
                os.path.join(project_root, phase["script"])):
            return f"missing script: {phase['script']}"
    return None

def run_due_tasks(project_root: str, only: Optional[str] = None,
                  on_output=None) -> Dict[str, Any]:
    """
    Execute every due task and return the run payload.


    This is the product's one scheduler. `theteam run` calls it and emits the
    result; `theteam serve` calls it on an interval. It lives here rather than
    in `cmd_run` because a tick and a one-shot run must execute identical work
    — M10 deleted a second, parallel scheduler for exactly that reason.

    The payload is the same shape `cmd_run` returned before the extraction, and
    the rules are unchanged: a phase with no runner is skipped by name, a
    tripped breaker is skipped with the literal `breaker_open`, and a failure
    records the reason that actually explains it.
    """
    from theteam.tasks.executor import TaskExecutor
    from theteam.tasks.repository import TaskRepository

    repo = TaskRepository(project_root)
    due = repo.due(only=only)
    # Breakers outlive the process: a task whose breaker tripped an hour ago
    # must still be tripped now, or the trip only survives as long as the run
    # that observed it. The repository owns the schedule (Layer 2), so it hands
    # the measured state to the executor (Layer 3) rather than the reverse.
    # A schedule entry naming a task that no longer exists is never fired —
    # `due()` walks real tasks — so leaving it is not a correctness bug, it is
    # a lie in the file: `theteam tasks` and `theteam serve`'s payload both
    # report it as scheduled. Purged here because this is the one place every
    # sweep already passes through.
    purged = repo.purge_orphaned_schedules()
    # Runs beside the purge rather than only on the write path. `schedule_task`
    # refuses a too-short interval for a *new* entry, but `record_run` re-stamps
    # `next_run` from `interval_minutes` without validating it — so an entry that
    # predates the guard, or was hand-edited, is copied forward on every run and
    # never corrects itself. Measured: an entry at 1 minute against a 600s
    # bound, 36x overrun, `due()` true on every sweep forever.
    repaired = repo.repair_schedules()
    # Purge runs before the breaker states are read: `last_run` is kept, so
    # reading it after the purge sees the same history either way.
    executor = TaskExecutor(project_root, breaker_states=repo.schedule()["last_run"])

    sweep_started = time.monotonic()
    results = []
    for task in due:
        phase_started = time.monotonic()
        # Every phase must name exactly one runner, and the named thing must
        # exist. A phase with *neither* is refused here rather than passed to
        # the executor: `runner: llm` is a new kind, and a check that only
        # understood `script` would turn every llm phase into a
        # `missing script` skip — a silent-skip hole, the exact shape §3.3
        # forbids. M9 Phase 4.
        problem = _phase_problem(task, project_root)
        if problem:
            # Also a skip, and the same rule applies: `at` is not restamped and
            # the breaker reading is not invented. This branch used to call
            # `record_run` with no breaker arguments, which wrote `at = now` and
            # `breaker: null` — so a task that was genuinely open went from
            # "tripped at T, recovering" to "never measured" the first time it
            # was also misconfigured. Reproduced: a task seeded open 10 minutes
            # ago came back `breaker: null` after one skipped run, discarding the
            # five consecutive failures that had opened it.
            repo.record_skip(task["id"], problem)
            results.append({"id": task["id"], "result": "skipped", "detail": problem,
                            "elapsed": round(time.monotonic() - phase_started, 2)})
            continue
        outcome = executor.execute_task(task, on_output=on_output)
        breaker = outcome["breaker"]
        consecutive = outcome["breaker_consecutive_failures"]
        if outcome.get("skipped"):
            # §3.2: the reason is the literal `breaker_open`, and it is
            # persisted so `theteam tasks` and `theteam history` still show it
            # in a later process.
            #
            # `at` is deliberately NOT refreshed here. A skip is not a failure —
            # the code above says so and does not count it against the task — so
            # it must not restamp the moment the failures were recorded. It did:
            # `record_run` writes `at = now`, and the breaker anchors its recovery
            # window to `at`, so any retry faster than the 60s window re-stamped
            # it and re-anchored the countdown. A `while ! ok; do theteam run
            # --only <id>; done` loop, or a `serve --tick-seconds 30`, would have
            # kept an open breaker open forever. The window is anchored to the
            # failure that opened it and to nothing else.
            #
            # Only the reason and the breaker reading change, and both are what a
            # later process needs to explain why nothing ran.
            reason = outcome["skip_reason"]
            repo.record_skip(task["id"], reason, breaker=breaker,
                             consecutive_failures=consecutive)
            results.append({"id": task["id"], "result": "skipped", "detail": reason,
                            "elapsed": round(time.monotonic() - phase_started, 2)})
            continue
        ok = outcome["overall_success"]
        # A check that ran and reported findings is a success with something to
        # say, so it stays `ok` for the breaker and the exit code, and carries a
        # `findings` marker the human line renders. Rendering it as `failed`
        # would be the old defect in a new place; rendering it as a clean `ok`
        # with no marker would hide a monitor that has been reporting the same
        # thing for a week.
        has_findings = bool(outcome.get("has_findings"))
        # The reason a phase failed, whatever kind it was. `returncode` is
        # real for a script phase and absent for an `llm` one, so reading it
        # unconditionally recorded "returncode None" as the last failure —
        # a reason that explains nothing, on exactly the path §3.3 governs.
        detail = ""
        if not ok and outcome.get("phases"):
            failed = outcome["phases"][-1]
            detail = (failed.get("error")
                      or f"returncode {failed.get('returncode')}")
        elif has_findings:
            detail = "check reported findings"
        repo.record_run(task["id"], "ok" if ok else "failed", detail,
                        breaker=breaker, consecutive_failures=consecutive)
        result = {"id": task["id"], "result": "ok" if ok else "failed",
                  "elapsed": round(time.monotonic() - phase_started, 2)}
        if has_findings:
            result["findings"] = True
        if detail:
            result["detail"] = detail
        results.append(result)
    return {
        # `ran` counts what actually executed. A task with a missing script was
        # due but never ran, so counting it would report work that never happened.
        "ran": sum(1 for r in results if r["result"] in ("ok", "failed")),
        "skipped": sum(1 for r in results if r["result"] == "skipped"),
        "failures": sum(1 for r in results if r["result"] == "failed"),
        # Counted apart from `failures` because the two answer different
        # questions and collapsing them is what made a working monitor look
        # broken. A sweep reporting findings is not a red sweep — it is the
        # check working — but neither is it silently clean.
        "findings": sum(1 for r in results if r.get("findings")),
        # Measured, not estimated: how long the sweep actually took, and what
        # it purged. A caller that never learns either cannot tell "nothing was
        # due" from "everything was due and finished fast".
        "elapsed": round(time.monotonic() - sweep_started, 2),
        "purged_orphans": purged,
        "repaired_schedules": repaired,
        "results": results,
        # Every `theteam run` refreshes the state the project-integrity gate
        # reads and writes the context members are handed. This replaced the
        # only production writer of `.loop-state.json`, which lived inside
        # `sa_runner._run_correction_cycle` (sa_runner.py:451) — a 600s analysis
        # phase. With scheduling off, `run` is the only thing that executes, so
        # it is the only thing that can keep the gate honest: a file refreshed
        # only by a task nobody runs would eventually read as stale, and
        # `loop_health_check.py:79` would report a finding nothing could fix.
        # Only the booleans, never the paths or the timing. `run_due_tasks`
        # returns a payload a test can compare byte-for-byte across two runs
        # that did nothing — `test_two_runs_with_nothing_due_are_byte_identical`
        # enforces exactly that — and an absolute path or a fractional `elapsed`
        # makes two identical reads differ. Measured: including them failed that
        # test with `context_path: /tmp/... != /tmp/...` and `elapsed: 0.0006 !=
        # 0.0005`.
        #
        # The caller that wants the path or the timing can read them off disk or
        # time it itself; a payload that varies run to run cannot be compared,
        # and a payload nobody can compare cannot be asserted on.
        "context": write_run_context(project_root,
                                     success=not any(
                                         r["result"] == "failed"
                                         for r in results),
                                     executed=any(
                                         r["result"] in ("ok", "failed")
                                         for r in results)),
    }


def cmd_run(args: argparse.Namespace) -> int:
    """Execute everything currently due. Nothing due means nothing happens."""
    from theteam.tasks.repository import TaskRepository

    project_root = _project_root(args)
    # An id that matches no task is a named failure, not `nothing due`.
    # `theteam loop` already refuses an unknown id this way (ARCHITECTURE.md
    # §2: "An unknown task id is a named failure, not a silent no-op"), and
    # `run --only <typo>` reporting "nothing due" is the same lie: it reads
    # as "the scheduler had nothing for you" when the truth is "that task
    # does not exist". The check stays here because it is a *command* failure;
    # `run_due_tasks` is only told about ids that exist.
    if args.only and TaskRepository(project_root).get(args.only) is None:
        return _fail(args, "run --only", f"Task not found: {args.only}")

    if args.dry_run:
        return _dry_run(args, project_root, only=args.only)

    for task in TaskRepository(project_root).due(only=args.only):
        for phase in task.get("phases", []):
            bound = phase.get("timeout_seconds")
            if bound and not getattr(args, "json", False):
                print(f"  {task['id']}/{phase['name']}: up to {bound}s",
                      file=sys.stderr, flush=True)

    payload = run_due_tasks(project_root, only=args.only,
                            on_output=_live_reporter(args))
    if not payload["results"]:
        return _emit(args, payload, "nothing due")
    lines = [f"{r['id']}: {r['result']} ({r['elapsed']}s)"
             + (" (findings)" if r.get("findings") else "")
             + (f" ({r['detail']})" if r.get("detail") else "")
             for r in payload["results"]]
    # Findings are named rather than folded into either total. "0 failed" on a
    # sweep where a check reported a problem reads as a clean project, and the
    # point of the taxonomy is that those are two different facts — a check
    # working is not a check breaking, and neither is it nothing to say.
    lines.append(f"{payload['ran']} ran, {payload['skipped']} skipped, "
                 f"{payload['failures']} failed in {payload['elapsed']}s"
                 + (f", {payload['findings']} with findings"
                    if payload.get("findings") else ""))
    if payload["purged_orphans"]:
        lines.append(f"purged {len(payload['purged_orphans'])} schedule entries "
                     f"for tasks that no longer exist: "
                     f"{', '.join(payload['purged_orphans'])}")
    # Reported because a silent repair is a surprise: the operator's schedule
    # changes without them asking, and the next line says by how much.
    for repair in payload.get("repaired_schedules", []):
        lines.append(
            f"repaired schedule for {repair['task_id']}: interval "
            f"{repair['was_interval_minutes']}m -> "
            f"{repair['repaired_interval_minutes']}m, because the task can take "
            f"{repair['worst_case_seconds']}s and could never finish before it "
            f"was due again")
    # §2.1: a command that exists and failed returns 1. `theteam run` used to
    # return 0 with `failures: N` in the payload, so a shell could not tell a
    # red suite from a green one without parsing JSON. This is a behaviour
    # change for the pre-existing four tasks, and it is the documented one.
    _emit(args, payload, "\n".join(lines))
    return EXIT_ERROR if payload["failures"] else EXIT_OK


def _live_reporter(args):
    """A callback that shows each line as it arrives, or `None` when quiet.

    `None` for `--json`, because a machine reading one document cannot parse a
    progress stream mixed into it. That is the whole reason this is a
    callback: the caller decides whether a run is watched or captured.
    """
    if getattr(args, "json", False):
        return None

    def report(line: str) -> None:
        print(f"    {line.rstrip()}", file=sys.stderr, flush=True)

    return report


def _dry_run(args, project_root: str, only=None) -> int:
    """
    What would run, and for how long — without running it.

    The bound a task declares is the only duration figure that exists before
    it runs, so that is what is shown. It is an upper bound, not a prediction,
    and is labelled as one; a measured average would be a number nobody
    measured (§3.3).
    """
    from theteam.tasks.repository import TaskRepository

    repo = TaskRepository(project_root)
    due = repo.due(only=only)
    if not due:
        return _emit(args, {"dry_run": True, "tasks": []}, "nothing due")
    tasks = []
    for task in due:
        phases = [
            {
                "name": p.get("name", "?"),
                "runner": p.get("runner") or "script",
                "timeout_seconds": p.get("timeout_seconds", 300),
            }
            for p in task.get("phases", [])
        ]
        tasks.append({"id": task["id"], "phases": phases,
                      "worst_case_seconds": sum(p["timeout_seconds"] for p in phases)})
    lines = [f"{t['id']}: up to {t['worst_case_seconds']}s  —  "
             + ", ".join(f"{p['name']}({p['runner']},{p['timeout_seconds']}s)"
                         for p in t["phases"])
             for t in tasks]
    lines.append(f"{len(tasks)} task(s) would run; nothing was executed")
    return _emit(args, {"dry_run": True, "tasks": tasks}, "\n".join(lines))


def history_payload(project_root: str, task_id: Optional[str] = None):
    """The `history` view as data: `(payload, lines)`, or `(None, error)`.

    Same reads, same rows, one implementation - the renderer and the command
    cannot drift because there is only one place that computes a success rate.
    """
    from theteam.tasks.repository import TaskRepository

    repo = TaskRepository(project_root)
    schedule = repo.schedule()
    rows = []
    for tid in [t["id"] for t in repo.all_tasks()]:
        last = schedule["last_run"].get(tid, {})
        runs = _task_runs(project_root, tid)
        failures = [r for r in runs if not r.get("overall_success")]
        rows.append({
            "id": tid,
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
    if task_id:
        rows = [r for r in rows if r["id"] == task_id]
        if not rows:
            return None, f"no task '{task_id}'"

    payload = {"tasks": rows, "count": len(rows)}
    if not rows:
        return payload, ["no tasks"]
    lines = [f"{'id':<24} {'runs':>4} {'rate':>6} {'consec':>6}  breaker"]
    for row in rows:
        rate = f"{row['success_rate']:.1f}%" if row["success_rate"] is not None else "-"
        lines.append(
            f"{row['id']:<24} {row['runs']:>4} {rate:>6} "
            f"{str(row['consecutive_failures'] if row['consecutive_failures'] is not None else '-'):>6}  "
            f"{row['breaker'] or 'never run'}"
        )
    return payload, lines


def cmd_history(args: argparse.Namespace) -> int:
    """Per-task success rate, last run, last failure, consecutive failures (§7.1.7).

    Reads the two states S1 and S3 wrote: the schedule's `last_run` entry for
    breaker state, and the execution log for the run record. A task with no
    runs reports that, not a 0% success rate that reads like a measurement.
    """
    payload, lines = history_payload(_project_root(args), args.task)
    if payload is None:
        return _fail(args, "history", lines)
    return _emit(args, payload, "\n".join(lines))

def cmd_serve(args: argparse.Namespace) -> int:
    """The scheduler and the metrics endpoint, in one process.

    M10 changed what this command is. It used to construct a `UnifiedLoop` and
    bind metrics to it, which published a static snapshot of a scheduler whose
    only task producer (`integrated_orchestrator.py`) had no caller: every
    counter read `0.0` forever. It now sweeps the same due tasks `theteam run`
    executes, on an interval, so `/metrics` reports work that actually ran.

    The binding is duck-typed on purpose. `MetricsCollector.collect()` reads
    `.metrics`, `.tasks`, `.circuit_breaker` and `.health_monitor` off whatever
    it is given, so `TaskScheduler` satisfies it unchanged and the collector
    needs no second mapping of metric names to producers.
    """
    from theteam.core.metrics import MetricsCollector
    from theteam.tasks.scheduler import DEFAULT_TICK_SECONDS, TaskScheduler

    project_root = _project_root(args)
    scheduler = TaskScheduler(project_root, run_due_tasks,
                              tick_seconds=args.tick_seconds)
    collector = MetricsCollector(port=args.port)
    collector.bind(loop=scheduler)
    scheduler.start()
    if not collector.start_http_server():
        print("Metrics endpoint failed to start.", file=sys.stderr)
        scheduler.stop()
        return EXIT_ERROR
    print(f"theteam serving /metrics and /health on port {args.port} "
          f"(scheduler every {args.tick_seconds:g}s, default {DEFAULT_TICK_SECONDS:g})")
    try:
        import threading

        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        collector.stop()
        scheduler.stop()
    return EXIT_OK
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


def cmd_watch(args: argparse.Namespace) -> int:
    """The trust surface, in the terminal. `watch status|tasks|history`.

    Layer 0 dispatches and nothing else: the renderer owns the frame, and it
    reads the same payloads `status`, `tasks`, and `history` print. Those
    three commands are the machine surface (§2) and their output is
    unchanged - a TUI that improves them by rewriting them has broken the
    contract they exist to serve.

    `--monitor` turns on change detection over the same payloads. It is a flag
    on this command, not a new command, and it reads nothing `watch` did not
    already read: the transition is between two frames, so the data was on hand
    before this flag existed.
    """
    from theteam.ui.terminal import watch

    project_root = _project_root(args)
    monitoring = getattr(args, "monitor", False)

    # `--json` is honoured here as every other command honours it, so a
    # consumer can read the frame the renderer draws from a scripted run
    # instead of scraping a TUI. The payload is the SAME one `status`,
    # `tasks`, and `history` emit - read through the same `*_payload`
    # functions - so this branch cannot drift from the machine surface.
    # Without `--json` nothing below changes: the renderer still owns the
    # frame, and the three machine commands still print byte-identically.
    if getattr(args, "json", False):
        readers = {"status": status_payload, "tasks": tasks_payload,
                   "history": history_payload}
        payload, lines = readers[args.view](project_root)
        if payload is None:
            return _fail(args, "watch", lines if isinstance(lines, str) else lines[0])
        return _emit(args, payload, "\n".join(lines))

    if args.once:
        return watch(project_root, args.view, once=True, monitoring=monitoring)
    try:
        return watch(project_root, args.view, interval=args.interval,
                     monitoring=monitoring)
    except KeyboardInterrupt:
        # Ctrl-C is how a watch loop is meant to end. Returning the error
        # code would report a normal exit as a failure.
        return EXIT_OK



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

    serve = sub.add_parser(
        "serve", help="Run due tasks on an interval and publish /metrics.")
    serve.add_argument("--port", type=int,
                       default=int(os.environ.get("THETEAM_METRICS_PORT", "8000")))
    # Hoisted import: the parser needs the default at build time, and the
    # module it lives in is `theteam.tasks.scheduler`, which imports nothing
    # from this file — so this is not a cycle.
    from theteam.tasks.scheduler import DEFAULT_TICK_SECONDS
    serve.add_argument("--tick-seconds", type=float,
                       default=float(os.environ.get("THETEAM_TICK_SECONDS",
                                                    DEFAULT_TICK_SECONDS)),
                       help=f"Seconds between scheduler sweeps. Default "
                            f"{DEFAULT_TICK_SECONDS:g}.")
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
    run.add_argument("--dry-run", action="store_true",
                     help="Show what would run and its worst-case time; run nothing.")
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

    manager = sub.add_parser(
        "manager",
        help="Propose, apply, inspect or reset the roster for a topic.")
    manager.add_argument("--topic", help="The topic the roster should cover.")
    manager.add_argument("--status", action="store_true",
                         help="Why every member is on the roster.")
    manager.add_argument("--reset", action="store_true",
                         help="Restore the roster a fresh bootstrap would produce.")
    manager.add_argument("--apply", action="store_true",
                         help="Persist a --topic proposal. Without it, nothing "
                              "is written.")
    manager.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                         help="Machine-readable output.")
    manager.set_defaults(func=cmd_manager)

    watch = sub.add_parser("watch", help="Render status, tasks, or history in the terminal.")
    watch.add_argument("view", choices=("status", "tasks", "history"),
                       help="Which surface to render.")
    watch.add_argument("--once", action="store_true",
                       help="Render one frame and exit.")
    # Declared on the subparser as well as the parent, exactly like every other
    # command, so `theteam watch status --json` works. Before M7 this flag
    # existed only on the parent, which meant `watch` was the one command
    # whose `--json` had to precede the subcommand - an inconsistency, not a
    # documented exception. `SUPPRESS` keeps the subparser copy from clobbering
    # a value already parsed from the parent.
    watch.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                       help="Machine-readable output.")
    # The renderer owns the cadence; the parser only names it for `--help`.
    from theteam.ui.terminal import DEFAULT_INTERVAL
    watch.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                       help=f"Seconds between frames. Default {DEFAULT_INTERVAL:g}.")
    watch.add_argument("--monitor", action="store_true",
                       help="Show what changed since the previous frame, and name "
                            "state transitions (breaker opened, chain broken, task removed).")
    watch.set_defaults(func=cmd_watch)

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
    _configure_logging()
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
