"""
theteam.ui.terminal - the trust surface, rendered in the terminal.

Stdlib only. `rich` is installed in this developer's pyenv transitively and
declared nowhere, so importing it at module scope would pass the suite here
and turn it red on every clean CI runner. A renderer that needs a rendering
library to print three tables has defeated its own purpose, so this module
imports nothing outside the standard library and the project's own view model.

**The boundary.** `state.py` -> the `*_payload` functions in `cli.py` -> here.
The renderer reads a payload and prints it. It never resolves a path, never
opens a file, never spawns a process, and never computes a value the payload
does not already carry. A second renderer that grows its own adapter breaks
this chain, which is how `task_stack_adapter.py` came to exist in M2.

`ui/components/visibility.py::build_visibility` is a **peer** view-model
builder, not a step in this chain. It builds activity/roster/metrics rows for
the reflex dashboard, which is not wired into the product; it has no
production caller. Adapting its output into a frame here would be the second
adapter the paragraph above forbids, so this renderer does not use it and
does not import it.

**The honesty rule (§3.3).** Every cell traces to a command output. A `None`
is not `0`, not `closed`, not `intact`, not `0%` - it is the word for "nothing
was measured yet", which is `-` for an unknown cell and `never run` for a
task that has not executed. In particular `circuit_visual(None)` returns
`UNKNOWN_VISUAL`, so every null is gated *before* it reaches the tokens.
"""

import shutil
import sys
import time
from typing import Any, Dict, List, Optional

from theteam.core.audit_chain import chain_line
from theteam.ui.components.design_tokens import Palette, circuit_visual

# Word for a cell nothing was measured for. `-` is not `0`.
UNMEASURED = "-"
NEVER_RUN = "never run"

# Seconds between frames when `--once` is not given. Named in `--help`.
DEFAULT_INTERVAL = 5.0


# ======= cells =======

def _cell(value: Any, fallback: str = UNMEASURED) -> str:
    """One cell. `None` is its own word, never a zero."""
    if value is None:
        return fallback
    if value == "":
        return fallback
    return str(value)


def _breaker_cell(state: Any) -> str:
    """
    Breaker state, or `never run`.

    Gated on `None` before the tokens are consulted: a task that has never
    run has no measured breaker, and `circuit_visual(None)` would report
    "Unknown" - a real-looking state nobody measured.
    """
    if state is None:
        return NEVER_RUN
    return f"{circuit_visual(state).icon} {state}"


def _rate_cell(rate: Any) -> str:
    """Success rate. No runs means no rate, and `0.0%` would read as a result."""
    if rate is None:
        return UNMEASURED
    return f"{float(rate):.1f}%"


# ======= colour =======

_ANSI = {key: f"\033[{code}m" for key, code in
         {"neutral": 90, "success": 32, "warning": 33, "danger": 31}.items()}


def _paint(text: str, color: str) -> str:
    """
    Colour a cell, only on a terminal.

    Colour goes to stdout and nothing else, so a redirected `watch` is clean
    text. The colours are the project's own `Palette`; no second palette.
    """
    if not sys.stdout.isatty():
        return text
    name = {
        Palette.success: "success",
        Palette.warning: "warning",
        Palette.danger: "danger",
        Palette.neutral: "neutral",
    }.get(color, "neutral")
    return f"{_ANSI[name]}{text}\033[0m"


# ======= frames =======

def _frame(view: str, width: int) -> List[str]:
    """The one header every frame shares."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return [f"theteam watch {view}  {stamp}", "─" * min(width, 78), ""]


def render_status(payload: Dict[str, Any]) -> str:
    """Roster, task counts, breaker trips, audit chain state."""
    roster = payload["roster"]
    tasks = payload["tasks"]
    lines = _frame("status", 78)

    lines.append(f"roster      {roster['active']} members active "
                 f"({', '.join(roster['members']) or 'none'})")
    lines.append(f"tasks       {tasks['registered']} registered, "
                 f"{tasks['scheduled']} scheduled")

    trips = tasks["breaker_trips"]
    if trips:
        lines.append(f"breakers    {len(trips)} tripped: {', '.join(trips)}")
        for task_id in trips:
            entry = payload["breakers"].get(task_id) or {}
            visual = circuit_visual(entry.get("state"))
            failures = entry.get("consecutive_failures")
            lines.append(
                f"  {_paint(visual.icon, visual.color)} {task_id:<24} "
                f"{_breaker_cell(entry.get('state'))}"
                f"{'  ' + _cell(failures) + ' consecutive failures' if failures else ''}"
            )
    else:
        # No trips, and none claimed: a project with no run task has no
        # measured breaker, which is not the same as a measured `closed`.
        lines.append("breakers    none tripped")

    # The audit row is rendered by the one function that already states it
    # honestly - absent, empty, intact, BROKEN - so a fourth spelling cannot
    # grow here.
    lines.append(chain_line(payload["audit_chain"]).replace("audit chain    ", "audit chain  "))
    return "\n".join(lines)


def render_tasks(payload: Dict[str, Any]) -> str:
    """id, order, next run, last result, breaker state."""
    lines = _frame("tasks", 78)
    lines.append(f"{'order':>5}  {'id':<24} {'next run':<26} {'last result':<12} breaker")

    if not payload["tasks"]:
        lines.append("")
        lines.append("no tasks registered")
        return "\n".join(lines)

    for task in payload["tasks"]:
        state = task.get("breaker")
        visual = circuit_visual(state) if state is not None else None
        breaker = _paint(_breaker_cell(state), visual.color if visual else Palette.neutral)
        last = _cell(task.get("last_result"))
        if last == UNMEASURED:
            last = NEVER_RUN
        lines.append(
            f"{_cell(task.get('order')):>5}  {task['id']:<24} "
            f"{_cell(task.get('next_run'), 'not scheduled'):<26} {last:<12} {breaker}"
        )
    lines.append("")
    lines.append(f"{payload['count']} tasks, {payload['yaml_count']} in YAML")
    return "\n".join(lines)


def render_history(payload: Dict[str, Any]) -> str:
    """success rate, last run, last failure, consecutive failures."""
    lines = _frame("history", 78)
    lines.append(f"{'id':<24} {'runs':>4} {'rate':>7} {'last run':<26} "
                 f"{'last failure':<26} {'consec':>6}  breaker")

    if not payload["tasks"]:
        lines.append("")
        lines.append("no tasks registered")
        return "\n".join(lines)

    for row in payload["tasks"]:
        state = row.get("breaker")
        visual = circuit_visual(state) if state is not None else None
        breaker = _paint(_breaker_cell(state), visual.color if visual else Palette.neutral)
        lines.append(
            f"{row['id']:<24} {row['runs']:>4} {_rate_cell(row.get('success_rate')):>7} "
            f"{_cell(row.get('last_run'), NEVER_RUN):<26} "
            f"{_cell(row.get('last_failure'), 'never'):<26} "
            f"{_cell(row.get('consecutive_failures')):>6}  {breaker}"
        )
    return "\n".join(lines)


# ======= views =======

# The three views and nothing else. A view registered here is the whole
# surface; there is no plugin hook, because there is no second consumer.
RENDERERS = {
    "status": render_status,
    "tasks": render_tasks,
    "history": render_history,
}

VIEWS = tuple(RENDERERS)


# ======= loop =======

def _clear() -> None:
    """Clear the screen and home the cursor, on a terminal only."""
    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[H")


def watch(project_root: str, view: str, once: bool = False,
          interval: float = DEFAULT_INTERVAL, stream: Optional[Any] = None) -> int:
    """
    Render `view` until interrupted, or exactly once.

    `frame` is read fresh every tick: a watch loop that renders a value it
    captured at start is showing a stale measurement, which is the one thing
    this surface must not do.
    """
    from theteam import cli

    out = stream if stream is not None else sys.stdout
    readers = {
        "status": lambda: cli.status_payload(project_root),
        "tasks": lambda: cli.tasks_payload(project_root),
        "history": lambda: cli.history_payload(project_root),
    }
    read = readers[view]

    while True:
        payload, lines = read()
        if payload is None:
            # The project is not bootstrapped, or the filter matched nothing.
            # Say the reason; do not render an empty frame that looks calm.
            _clear()
            print(f"theteam watch {view}: {lines if isinstance(lines, str) else lines[0]}",
                  file=out)
            return 1

        frame = RENDERERS[view](payload)
        _clear()
        out.write(frame + "\n\n")
        out.flush()
        if once:
            return 0
        time.sleep(max(interval, 0.1))


def terminal_width(default: int = 80) -> int:
    """Columns, for the header rule. Falls back to 80 with no terminal."""
    try:
        return shutil.get_terminal_size((default, 24)).columns
    except OSError:  # pragma: no cover - no terminal in CI
        return default
