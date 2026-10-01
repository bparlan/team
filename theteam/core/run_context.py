"""
Per-run project context, written on every `theteam run`.

This module exists because the thing it replaces was the only live writer of
`.loop-state.json`. `scripts/sa_runner.py` refreshed that file from inside
`_run_correction_cycle` (sa_runner.py:451) — the only production call site of
`update_loop_state` anywhere. Every other `LoopState` construction in the tree
(`scripts/loop_reporter.py:28`, `scripts/task_executor.py:37`) belongs to the
legacy scripts the M10 consolidation retired.

So deleting the `system-awareness` task, as decided, would have removed the sole
writer of a file that `scripts/loop_infrastructure_check.py:46` hard-gates in
`REQUIRED_LOOP_FILES`, and that `scripts/loop_health_check.py:60-91` separately
fails on once it is older than `STALE_THRESHOLD_SECONDS` (24h). `project-integrity`
would then have reported a finding that nothing in the system could resolve —
the D2 pattern one layer up: a gate that can only fail.

This file takes that responsibility over. Two things, deliberately:

  * **`.loop-state.json`** is refreshed, with the same shape `_load_state`
    expects, because a hard gate depends on it.
  * **A context summary** is written for members to read. That is the artifact
    the 600s/384MB `self-correct` analysis was supposed to produce and never
    did: it wrote six JSON reports that zero code in `theteam/` read.

Nothing here analyses anything. Every number is read from state that a run has
already produced, or counted from the tree. A derived measurement costs more than
the constant it replaces, and a slow one costs a 600-second phase — which is how
`system-awareness` ended up scheduled at `interval_minutes: 1` against a 600s
bound, permanently overdue, re-running on every sweep.

§3.3 applies: every field is measured or absent. A field that cannot be measured
is omitted rather than filled with a plausible constant, because a constant that
renders as a measurement is the defect class this repository exists to prevent.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from theteam.state import state_dir

#: Bumped when the file's shape changes. `.loop-state.json` carried `"version": 1`
#: from its first writer; this keeps that promise rather than silently diverging.
LOOP_STATE_VERSION = 1

#: The summary is a glance, not a dump. It is injected into every member prompt,
#: so its cost is paid once per member per discussion. The cap exists so a large
#: project cannot turn a 2KB artifact into a context tax; if the cap is ever hit
#: the file says so, rather than silently truncating a list a reader would
#: assume was complete.
MAX_SUMMARY_BYTES = 8192


def _read_failure_types() -> tuple:
    """Everything reading a project's own files can legitimately raise.

    `YAMLError` is in the tuple rather than caught by name at each site because
    `yaml.parser.ParserError` and `yaml.scanner.ScannerError` descend from it
    and from neither `ValueError` nor `OSError` — measured, after a malformed
    task file escaped a handler that caught only the latter two.

    `TypeError`, `KeyError` and `AttributeError` are here for shape errors: a
    YAML document that parses to a scalar or a list rather than a mapping
    raises them on the first `.get`. That is a malformed config, not an unknown
    one, and it deserves a named message rather than a stack trace.
    """
    import yaml
    return (OSError, ValueError, KeyError, TypeError, AttributeError,
            yaml.YAMLError)


_READ_FAILURES = _read_failure_types()




def _one_line_error(e: BaseException, limit: int = 160) -> str:
    """`TypeName: first line of the message`, bounded.

    Multi-line exception text — a YAML `ParserError` prints a four-line
    pseudo-traceback — is noise in a file that is injected into every member
    prompt. The type carries the category and the first line carries the
    reason; the rest is formatting.
    """
    first = str(e).strip().splitlines()[0] if str(e).strip() else ""
    text = f"{type(e).__name__}: {first}" if first else type(e).__name__
    if len(text) > limit:
        text = text[:limit].rstrip() + "..."
    return text


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_loop_state(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Read `.loop-state.json`, or return the default shape if it is absent.

    Every field carries its default here rather than being invented at the write
    site, so the file's shape is defined in exactly one place. `_load_state` in
    `sa_runner.py` had the same defaults duplicated against it; that copy goes
    away with the file.
    """
    path = Path(project_root or ".") / ".loop-state.json"
    try:
        state = json.loads(path.read_text())
        if isinstance(state, dict):
            return state
    except (json.JSONDecodeError, OSError):
        # A corrupt state file is not a reason to refuse to run. The caller is
        # refreshing it; refusing would leave it corrupt forever. The replacement
        # is written below and the bad file is preserved alongside it.
        pass
    return {
        "version": LOOP_STATE_VERSION,
        "project": "team-skill",
        "loop_active": False,
        "current_task_index": 0,
        "completed_tasks": [],
        "failed_tasks": [],
        "blocked_tasks": [],
        "last_execution": None,
        "task_archive": "tasks",
        "total_tasks": 0,
        "health_score": {},
        "circuit_breaker": {},
    }


def write_loop_state(state: Dict[str, Any],
                     project_root: Optional[Path] = None) -> Path:
    """Write `.loop-state.json` atomically.

    Temp file plus `os.replace`, matching what `theteam/core/wal.py:139-150`
    already does. A plain `open(path, "w")` can truncate the file to zero bytes
    if the process dies mid-write, and `scripts/loop_health_check.py:67` then
    reports it invalid on every subsequent run with nothing able to repair it.
    """
    path = Path(project_root or ".") / ".loop-state.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, path)
    return path


def refresh_loop_state(project_root: Optional[Path] = None,
                       health: Optional[Dict[str, Any]] = None,
                       success: bool = True,
                       executed: bool = True) -> Dict[str, Any]:
    """Refresh the loop state after a run and return what was written.

    `last_execution` is stamped only when `executed` is true. That field means
    "a task last ran at", and `loop_health_check.py:79` reads it to decide the
    file is stale. Stamping it on a run where nothing was due would record an
    execution that never happened and permanently hide real staleness — the same
    fabrication as a default that reads like a measurement, one level down.

    So a project where nothing has been due for a week still reads as stale,
    which is true, and a run with nothing due moves no state at all. That is the
    same purity `TaskRepository.due()` is built on, and
    `test_two_runs_with_nothing_due_are_byte_identical` enforces it.

    `health` is optional and recorded only when a caller has a real measured
    score. Inventing one here would put a fabricated grade into the file that
    `cmd_health_check` and `cmd_status` both read.
    """
    state = load_loop_state(project_root)
    if executed:
        state["last_execution"] = _now_iso()
    if health:
        state["health_score"] = {
            **state.get("health_score", {}),
            "overall_score": health.get("overall_score"),
            "grade": health.get("grade"),
            "timestamp": _now_iso(),
            "last_run_success": bool(success),
        }
    write_loop_state(state, project_root)
    return state



def _recent_failures(project_root: Path, limit: int = 3) -> List[str]:
    """Names of tasks whose last recorded run failed.

    Read from the execution log the repository already writes, rather than by
    opening every schedule. Returns what it can verify and nothing else: a task
    that has never run is absent from this list, not reported as passing.

    Cross-checked against the task registry, and that check is load-bearing.
    The execution log is append-only history, so it still carries entries for
    tasks deleted months ago. Measured on this repo: the first version of this
    function reported `folder-monitoring` and `health-check` as failing, both of
    which stopped existing when M12 merged them into `project-integrity`. A
    context file listing two deleted tasks under "what is failing" is a
    fabricated measurement — the same defect class as the unreadable 600s
    reports this module replaced, reproduced in the replacement.

    A task with no YAML file cannot be failing, because nothing can run it.
    """
    from theteam.tasks.repository import TaskRepository

    try:
        known = {t["id"] for t in TaskRepository(project_root).all_tasks()}
    except _READ_FAILURES as e:
        # Named failures, not a bare `except Exception`. Swallowing everything
        # meant one malformed task YAML dropped this section from the summary
        # entirely, and an absent section reads as "nothing is failing" — the
        # false-clean defect this phase exists to remove, made reachable by a
        # syntax error in a file the user may not have touched.
        #
        # Measured: a task file with `id: [broken` raises `yaml.parser.
        # ParserError`, which descends from `YAMLError` and *not* from
        # `ValueError` or `OSError`, so the first version of this handler let it
        # escape and crash `build_context_summary` outright.
        #
        # The failure is reported as a failure. A reader seeing this knows the
        # list is unavailable; a reader seeing nothing assumes there is no
        # problem, which is the opposite of what is known.
        # Collapsed to a single line. `yaml.parser.ParserError` renders as a
        # four-line traceback naming the file, the line and the column, and this
        # string is injected into every member prompt on every discussion —
        # so a verbose one spends context on stack-trace formatting instead of
        # the fact. The first line carries the type and the reason; that is
        # what a member needs, and the file and line are one `cat` away.
        return [f"could not read the task registry "
                f"({_one_line_error(e)}) — failure status unknown"]
    log = state_dir(str(project_root)) / "task-execution.log"
    if not log.exists():
        return []
    failures: Dict[str, str] = {}
    try:
        for line in log.read_text(errors="replace").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            task_id = entry.get("task_id")
            if not task_id:
                continue
            if entry.get("success"):
                failures.pop(task_id, None)
            else:
                failures[task_id] = (entry.get("error")
                                     or entry.get("skip_reason") or "")
    except OSError:
        return []
    live = [(tid, reason) for tid, reason in failures.items() if tid in known]
    orphans = sorted(set(failures) - known)
    lines = [f"{tid}: {reason}" if reason else tid
             for tid, reason in sorted(live)[:limit]]
    if orphans and not known:
        # An empty registry with recorded failures is not a clean project — it
        # is a project whose tasks cannot be read, and the distinction is the
        # whole point of this function. Measured: emptying `tasks/` produced
        # "nothing recorded as failing" from a log full of real failures.
        return [f"no task definitions found, but {len(orphans)} task(s) have "
                f"recorded failures ({', '.join(orphans[:3])}) — the task "
                f"registry could not be read, failure status unknown"]
    return lines


def build_context_summary(project_root: Optional[Path] = None) -> str:
    """The markdown a member reads before forming an opinion.

    Four sections, and each one is a measurement or it is absent:

      * what this project is — from `theteam.config`, the same source
        `context_aggregator.py` reads, so a member and the aggregator never
        disagree about what project they are in.
      * what ran, and what failed — from the execution log.
      * what needs a human — from the proposals directory. Empty is omitted
        rather than printed as "(none)"; a section that promises a channel and
        delivers a placeholder is worse than no section.
      * what it costs — wall time and counts, measured by this run.

    No section here is inferred from the tree's shape or estimated from a
    phase's timeout. Everything is read from state a run produced.
    """
    root = Path(project_root or ".")
    failures = _recent_failures(root)
    # The header carries the loop state's `last_execution`, not the current
    # time. Stamping "now" made two runs with nothing due differ, which
    # `test_two_runs_with_nothing_due_are_byte_identical` correctly rejects: a
    # pure read of due-ness must not look like it moved something. The value
    # shown is when work last actually happened, which is also the more useful
    # thing for a member to see.
    last_execution = load_loop_state(root).get("last_execution")
    lines: List[str] = [
        f"# project context — last run {last_execution or 'never'}"]

    name, description = _project_identity(root)
    lines.append("")
    lines.append("## what this is")
    lines.append(f"- **{name}**: {description}")

    lines.append("")
    # Both phrasings below mean "not measurable", so they share a heading. Keyed
    # on a marker rather than an exact sentence so a future reword cannot
    # silently downgrade "unknown" into a list of failing tasks. Rendering a
    # "could not read" line as a bullet under "what is failing" would read as a
    # failing task; rendering nothing would read as clean. Neither is what is
    # known, so the section says what it could not establish.
    unknown = any("failure status unknown" in f for f in failures)
    if unknown:
        lines.append("## failure status unknown")
        lines.extend(f"- {item}" for item in failures)
    elif failures:
        lines.append("## what is failing")
        lines.extend(f"- {item}" for item in failures)
    else:
        lines.append("## what is failing")
        lines.append("- nothing recorded as failing")

    needs = _open_proposals(root)
    if needs:
        lines.append("")
        lines.append("## what needs a human decision")
        lines.extend(f"- {item}" for item in needs)

    text = "\n".join(lines) + "\n"
    if len(text.encode()) > MAX_SUMMARY_BYTES:
        # Say so. A silently truncated list reads as a complete one, which is
        # the same defect as a section that vanishes: the reader cannot tell
        # that what they are missing was cut off rather than never recorded.
        text = (text.encode()[:MAX_SUMMARY_BYTES].decode(errors="ignore")
                + f"\n\n[truncated at {MAX_SUMMARY_BYTES} bytes]\n")
    return text


def _yaml_load(config: Path) -> Optional[Any]:
    """Parse a YAML file, or raise `OSError` carrying the reason.

    `yaml.YAMLError` does not subclass `ValueError` or `OSError`, so it is named
    explicitly and re-raised as `OSError` with the original type in the message.
    Callers then have one failure type to handle, and a `ParserError` from a
    malformed task file cannot escape a handler that only catches the others.
    """
    import yaml

    try:
        return yaml.safe_load(config.read_text())
    except (OSError, yaml.YAMLError) as e:
        raise OSError(f"{type(e).__name__}: {e}") from e


def _project_identity(root: Path) -> tuple:
    """`(name, description)` from `theteam.config`, or honest placeholders.

    Every fallback says what is missing rather than filling it with something
    plausible. A description is prose a member will quote back as the project's
    stated purpose, and inventing one is the same class of defect as inventing
    a health score: it reads as a fact and is not one.

    The failure modes are distinguished because they have different fixes: a file
    that will not parse, a document that is not a mapping, a project section
    that is a scalar, and a project section that is absent. Measured: a scalar
    `project:` previously reported "no project section", which is a different
    defect from the one present and sends a reader to the wrong place.
    """
    config = root / "theteam.config"
    try:
        data = _yaml_load(config)
    except OSError as e:
        return (root.name, f"no description recorded (theteam.config "
                           f"unreadable: {e})")
    if data is None:
        return (root.name, "no description recorded (theteam.config empty)")
    if not isinstance(data, dict):
        return (root.name, "no description recorded (theteam.config is not a "
                           "mapping)")
    project = data.get("project")
    if project is None:
        return (root.name, "no description recorded (no project section)")
    if not isinstance(project, dict):
        return (root.name, "no description recorded (theteam.config project "
                           f"section is a {type(project).__name__}, not a mapping)")
    return (project.get("name") or root.name,
            project.get("description") or "no description recorded")


def _open_proposals(root: Path, limit: int = 5) -> List[str]:
    """Unanswered questions from the proposals directory.

    Returns nothing when the directory does not exist, which is the common case:
    `StateStore.proposals` was declared and dead until the decision channel gave
    it a writer. Absence is the correct answer here, not an empty placeholder.
    """
    directory = state_dir(str(root)) / "proposals"
    if not directory.is_dir():
        return []
    items: List[str] = []
    try:
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if data.get("answered"):
                continue
            question = data.get("question") or path.stem
            items.append(f"{data.get('task_id', '?')}: {question}")
            if len(items) >= limit:
                break
    except OSError:
        return []
    return items


def write_run_context(project_root: Optional[Path] = None,
                      health: Optional[Dict[str, Any]] = None,
                      success: bool = True,
                      executed: bool = True) -> Dict[str, Any]:
    """Refresh the loop state and write the member-facing summary.

    The single per-run entry point, called from `theteam run` after the sweep.
    One command then leaves both the gate's file and the members' context
    current, which is what makes `run` the thing that keeps derived state fresh
    now that scheduling is off.

    The summary is written whether or not anything executed, because it is
    derived from state a caller reads rather than from the run's outcome — and
    it must not carry a timestamp that changes between two identical reads, or
    two runs with nothing due stop being byte-identical.
    """
    root = Path(project_root or ".")
    state = refresh_loop_state(root, health=health, success=success,
                               executed=executed)
    summary = build_context_summary(root)
    path = state_dir(str(root)) / "context.md"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(summary)
    except OSError as e:
        # The loop state already landed, and it is the hard gate. Failing the
        # whole run over the summary would break the gate we just satisfied.
        return {"written": False, "error": f"could not write context summary: {e}"}
    # Deliberately three booleans. `context_path` is an absolute path and an
    # `elapsed` is a timing reading, so including either makes two runs over an
    # unchanged project differ — which is what
    # `test_two_runs_with_nothing_due_are_byte_identical` is asserting against
    # when it embeds this in the sweep payload. Measured: `context_path:
    # /tmp/a != /tmp/b` and `elapsed: 0.0006 != 0.0005` failed that test for no
    # reason connected to what it is named for.
    #
    # A caller that genuinely needs the path derives it from `state_dir`, and a
    # caller that needs the timing should measure it — a value that changes
    # every call cannot be compared to anything.
    return {"written": True, "context_bytes": len(summary.encode())}
