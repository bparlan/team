#!/usr/bin/env python3
"""
`theteam serve`'s scheduler: the one place due work becomes executed work.

M10 deleted two competing schedulers. `UnifiedLoop` scheduled `UnifiedTask`
objects that nothing ever produced, and `routine-engine/` scheduled markdown
routines unrelated to the YAML tasks `theteam run` executes. This module is the
survivor, and it is thin on purpose: every decision about *what* is due and
*how* it runs already belongs to `RoutineRepository` and `RoutineExecutor` (Layer 2
and Layer 3). All this adds is a clock.

The counters it exposes are the ones `MetricsCollector.collect()` scrapes, and
it exposes them by attribute rather than by inheritance so the collector needs
no change and no second mapping of metric names to producers.

Layer 1 (§5.1 Control). It imports nothing above it: `run_due_tasks` is
injected by the caller precisely so this file does not import `theteam.cli`.
"""
import threading
import time
from typing import Any, Callable, Dict, List, Optional

#: Default seconds between scheduler sweeps. Matches the `watch` renderer so
#: the two surfaces a user watches side by side refresh on the same cadence.
DEFAULT_TICK_SECONDS = 60

#: A sweep never blocks the next one. A phase that outlives the interval is
#: reported by the executor's own timeout, not by stacking sweeps.
TICK_JOIN_SECONDS = 5.0


class RoutineScheduler:
    """Run due tasks on an interval and expose the counters metrics scrapes.

    Args:
        project_root: the project whose `routines/` directory is the schedule.
        run_due_tasks: callable `(project_root) -> payload`, injected so this
            module does not depend on the CLI. `theteam.cli.run_due_tasks` is
            the only implementation.
        tick_seconds: seconds between sweeps.
    """

    def __init__(
        self,
        project_root: str,
        run_due_tasks: Callable[[str], Dict[str, Any]],
        tick_seconds: float = DEFAULT_TICK_SECONDS,
    ) -> None:
        self.project_root = project_root
        self._run_due_tasks = run_due_tasks
        self.tick_seconds = float(tick_seconds)

        # Scraped by MetricsCollector.collect(), which reads these by name.
        self.metrics: Dict[str, float] = {
            "tasks_started": 0.0,
            "tasks_completed": 0.0,
            "tasks_failed": 0.0,
            "tasks_processed": 0.0,
        }
        self.dead_letter_queue: List[Dict[str, Any]] = []
        self.circuit_breaker = None
        self.health_monitor = None

        self._seen: Dict[str, bool] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ticks = 0
        self._last_error: Optional[str] = None
        self._built_at = time.time()

    # -- the shape MetricsCollector scrapes --------------------------------

    @property
    def tasks(self) -> Dict[str, Any]:
        """Active task map, for the `theteam_tasks_active` gauge.

        `collect()` measures `len(loop.tasks)`. A sweep runs each due task to
        completion or records it as failed, so at rest the honest value is the
        number of tasks this scheduler has executed at least once.
        """
        return dict(self._seen)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> bool:
        """Begin sweeping. Returns False when already running."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._monitoring_loop, daemon=True, name="RoutineScheduler")
            self._thread.start()
            return True

    def stop(self) -> None:
        """Stop sweeping and wait briefly for an in-flight sweep."""
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=TICK_JOIN_SECONDS)
        self._thread = None

    def _monitoring_loop(self) -> None:
        # Sweep once immediately: a `serve` that reported "nothing due" for a
        # full interval after starting would make a schedule look ignored.
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self.tick_seconds)

    # -- the sweep ---------------------------------------------------------

    def tick(self) -> Dict[str, Any]:
        """Run everything due, once. Returns the `run_due_tasks` payload.

        A sweep that raises is recorded and the scheduler keeps running: one
        unreadable task file must not take the endpoint down with it. The
        failure is named in `last_error`, never swallowed into a silent zero.
        """
        try:
            payload = self._run_due_tasks(self.project_root)
        except Exception as exc:
            with self._lock:
                self._ticks += 1
                self._last_error = f"{type(exc).__name__}: {exc}"
            return {"ran": 0, "skipped": 0, "failures": 0, "results": []}

        with self._lock:
            self._ticks += 1
            self._last_error = None
            ran = payload.get("ran", 0)
            failures = payload.get("failures", 0)
            skipped = payload.get("skipped", 0)
            self.metrics["tasks_started"] += float(ran)
            self.metrics["tasks_completed"] += float(ran - failures)
            self.metrics["tasks_failed"] += float(failures)
            self.metrics["tasks_processed"] += float(ran + skipped)
            results = payload.get("results", [])
            for result in results:
                self._seen[result.get("id", "")] = True
            # A task the breaker skipped is work that will not be retried on
            # this tick. Reporting it as a dead letter keeps the metric honest
            # about outstanding work rather than inventing a queue.
            self.dead_letter_queue = [
                r for r in results
                if r.get("result") == "skipped" and r.get("detail") == "breaker_open"
            ]
        return payload

    # -- introspection -----------------------------------------------------

    @property
    def ticks(self) -> int:
        """How many sweeps have completed."""
        return self._ticks

    @property
    def last_error(self) -> Optional[str]:
        """The last sweep failure, or None. Never a fabricated success."""
        return self._last_error

    def uptime_seconds(self) -> float:
        """Seconds since this scheduler was built."""
        return time.time() - self._built_at

    def get_status(self) -> Dict[str, Any]:
        """The scheduler's own state, for diagnostics and `theteam status`."""
        with self._lock:
            return {
                "running": self._thread is not None and self._thread.is_alive(),
                "ticks": self._ticks,
                "tick_seconds": self.tick_seconds,
                "tasks_active": len(self._seen),
                "tasks_started": self.metrics["tasks_started"],
                "tasks_completed": self.metrics["tasks_completed"],
                "tasks_failed": self.metrics["tasks_failed"],
                "dead_letter_queue": len(self.dead_letter_queue),
                "last_error": self._last_error,
            }