#!/usr/bin/env python3
"""
Prometheus metrics for theteam.

Phase 4 observability deliverable. Deliberately stdlib-only: `prometheus_client`
is not a runtime dependency, so the exposition format is produced directly and
served by `http.server`. That keeps the container image slim and means metrics
work identically in production and in tests.

Metric names are part of the contract with the Grafana dashboard and must not
change without updating `grafana/dashboards/theteam.json` and `prometheus.yml`.
"""

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Histogram buckets in seconds for task duration. Kept deliberately small.
DEFAULT_BUCKETS: Tuple[float, ...] = (0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)


def _escape(value: Any) -> str:
    """Escape a label value for the Prometheus text exposition format."""
    out = str(value)
    return out.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _render_labels(labels: Optional[Dict[str, Any]]) -> str:
    """Render a label set in exposition format, sorted for stable output."""
    if not labels:
        return ""
    parts = [f'{k}="{_escape(v)}"' for k, v in sorted(labels.items())]
    return "{" + ",".join(parts) + "}"


def _with_le(rendered_labels: str, bound: str) -> str:
    """Add an `le` bucket label to an already-rendered label set."""
    suffix = f'le="{bound}"'
    if rendered_labels:
        return "{" + rendered_labels[1:-1] + "," + suffix + "}"
    return "{" + suffix + "}"


def _bucket_label(bound: float) -> str:
    """Render a bucket bound the way Prometheus expects it."""
    return "+Inf" if bound == float("inf") else repr(bound)


class MetricsRegistry:
    """
    Thread-safe metric registry with Prometheus text exposition.

    Counters accumulate and reset on process restart; gauges hold the latest
    value; histograms accumulate per-bucket counts. Label sets form the series
    key, so repeated calls with equal labels accumulate rather than overwrite.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[Tuple[str, str], float] = {}
        self._gauges: Dict[Tuple[str, str], float] = {}
        # (name, labels) -> {"counts": {bound: n}, "sum": float, "count": int}
        self._histograms: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._help: Dict[str, str] = {}
        self._buckets: Tuple[float, ...] = DEFAULT_BUCKETS

    # -- recording ---------------------------------------------------------

    @staticmethod
    def _key(name: str, labels: Optional[Dict[str, Any]]) -> Tuple[str, str]:
        return (name, _render_labels(labels))

    def inc(self, name: str, labels: Optional[Dict[str, Any]] = None, value: float = 1) -> None:
        """Add `value` to a counter."""
        with self._lock:
            key = self._key(name, labels)
            self._counters[key] = self._counters.get(key, 0.0) + float(value)

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, Any]] = None) -> None:
        """Set a gauge to an absolute value."""
        with self._lock:
            self._gauges[self._key(name, labels)] = float(value)

    def set_counter(self, name: str, value: float, labels: Optional[Dict[str, Any]] = None) -> None:
        """Set a counter to an absolute value (used when restoring from persistence)."""
        with self._lock:
            self._counters[self._key(name, labels)] = float(value)

    def observe(self, name: str, value: float, labels: Optional[Dict[str, Any]] = None,
                buckets: Optional[Iterable[float]] = None) -> None:
        """Record an observation into a histogram."""
        value = float(value)
        bounds = tuple(buckets or self._buckets)
        with self._lock:
            key = self._key(name, labels)
            series = self._histograms.setdefault(key, {"counts": {}, "sum": 0.0, "count": 0})
            counts = series["counts"]
            # Every declared bucket is materialised even at zero so the
            # cumulative series stays well-formed for histogram_quantile().
            for bound in bounds:
                counts.setdefault(bound, 0)
                if value <= bound:
                    counts[bound] += 1
            counts.setdefault(float("inf"), 0)
            counts[float("inf")] += 1
            series["sum"] += value
            series["count"] += 1

    def describe(self, name: str, help_text: str) -> None:
        """Attach HELP text to a metric family."""
        with self._lock:
            self._help[name] = help_text

    # -- reading -----------------------------------------------------------

    def get(self, name: str, labels: Optional[Dict[str, Any]] = None) -> float:
        """Read a single series value. Returns 0.0 when the series is absent."""
        key = self._key(name, labels)
        with self._lock:
            if key in self._counters:
                return self._counters[key]
            return self._gauges.get(key, 0.0)

    def reset(self) -> None:
        """Drop all series. Used by tests to isolate state."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._help.clear()

    # -- exposition --------------------------------------------------------

    def render(self) -> str:
        """Render the registry in Prometheus text exposition format (v0.0.4)."""
        with self._lock:
            lines: List[str] = []
            emitted: set = set()

            for metric_type, series in (("counter", self._counters), ("gauge", self._gauges)):
                by_name: Dict[str, List[Tuple[str, float]]] = {}
                for (name, labels), value in series.items():
                    by_name.setdefault(name, []).append((labels, value))

                for name in sorted(by_name):
                    if name not in emitted:
                        help_text = self._help.get(name)
                        if help_text:
                            lines.append(f"# HELP {name} {help_text}")
                        lines.append(f"# TYPE {name} {metric_type}")
                        emitted.add(name)
                    for labels, value in sorted(by_name[name]):
                        lines.append(f"{name}{labels} {value!r}")

            hist_by_name: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
            for (name, labels), series in self._histograms.items():
                hist_by_name.setdefault(name, []).append((labels, series))

            for name in sorted(hist_by_name):
                if name not in emitted:
                    help_text = self._help.get(name)
                    if help_text:
                        lines.append(f"# HELP {name} {help_text}")
                    lines.append(f"# TYPE {name} histogram")
                    emitted.add(name)
                for labels, series in sorted(hist_by_name[name]):
                    counts = series["counts"]
                    for bound in sorted(counts):
                        lines.append(
                            f"{name}_bucket{_with_le(labels, _bucket_label(bound))} {counts[bound]}"
                        )
                    lines.append(f"{name}_sum{labels} {series['sum']!r}")
                    lines.append(f"{name}_count{labels} {series['count']}")

            lines.append("")
            return "\n".join(lines)


# Process-wide registry. The exporter and the components share this instance.
REGISTRY = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    """Return the process-wide metrics registry."""
    return REGISTRY


def breaker_state_value(breaker: Any) -> float:
    """Map a circuit breaker's state to a numeric gauge value (0/1/2, -1 unknown)."""
    from theteam.core.circuit_breaker import CircuitState

    state = getattr(getattr(breaker, "stats", None), "state", None)
    return {
        CircuitState.CLOSED: 0.0,
        CircuitState.HALF_OPEN: 1.0,
        CircuitState.OPEN: 2.0,
    }.get(state, -1.0)


def health_score(health: Any) -> Optional[float]:
    """
    Read the health score (0.0-1.0) from a HealthMonitor.

    Prefers `get_health_score()` and falls back to the `health_score` field of
    `get_health_status()`, so either HealthMonitor shape works.
    """
    score = getattr(health, "get_health_score", None)
    if callable(score):
        try:
            return float(score())
        except Exception as e:
            logger.debug(f"get_health_score() failed, falling back to status: {e}")
    status = getattr(health, "get_health_status", None)
    if callable(status):
        try:
            return float(status().get("health_score", 0.0))
        except Exception as e:
            logger.debug(f"get_health_status() failed: {e}")
    return None


class MetricsCollector:
    """
    Serves the registry over HTTP and binds it to the live component objects.

    The collector owns the mapping from metric name to the component attribute
    that produces it, so wiring stays in one place instead of being scattered
    across every component.
    """

    def __init__(self, registry: Optional[MetricsRegistry] = None, port: int = 8000) -> None:
        self.registry = registry or REGISTRY
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Any = None
        self._limiter: Any = None
        self._start_time = time.time()

    def bind(self, loop: Any = None, limiter: Any = None) -> None:
        """Attach the live scheduler and resource limiter to scrape.

        The parameter is still named `loop` because the scraping contract is
        duck-typed on attribute names, not on a type. M10 changed what is bound
        here from `UnifiedLoop` to `tasks.scheduler.TaskScheduler`; the
        attributes read below (`.metrics`, `.tasks`, `.circuit_breaker`,
        `.health_monitor`) are the whole interface.

        The name is kept rather than renamed because a Prometheus scrape is a
        wire contract with whatever already queries it, and renaming a local
        parameter buys nothing.
        """
        if loop is not None:
            self._loop = loop
        if limiter is not None:
            self._limiter = limiter

    # -- scrape ------------------------------------------------------------

    def collect(self) -> None:
        """Refresh every bound metric from the live components."""
        loop = self._loop
        if loop is not None:
            try:
                metrics = getattr(loop, "metrics", {}) or {}
                for name in ("tasks_started", "tasks_completed", "tasks_failed", "tasks_processed"):
                    if name in metrics:
                        self.registry.set_counter(f"theteam_{name}", float(metrics[name]))
                self.registry.set_gauge(
                    "theteam_tasks_active", float(len(getattr(loop, "tasks", {}) or {}))
                )
                self.registry.set_gauge(
                    "theteam_dead_letter_queue",
                    float(len(getattr(loop, "dead_letter_queue", []) or [])),
                )

                breaker = getattr(loop, "circuit_breaker", None)
                if breaker is not None:
                    self.registry.set_gauge(
                        "theteam_circuit_breaker_state", breaker_state_value(breaker)
                    )

                health = getattr(loop, "health_monitor", None)
                if health is not None:
                    score = health_score(health)
                    if score is not None:
                        self.registry.set_gauge("theteam_health_score", score)
            except Exception as e:
                logger.debug(f"loop metrics unavailable: {e}")

        limiter = self._limiter
        if limiter is not None:
            try:
                report = limiter.get_usage_report()
                for resource_type, stats in (report.get("resource_breakdown") or {}).items():
                    self.registry.set_gauge(
                        "theteam_resource_utilization_percent",
                        float(stats.get("average_utilization", 0.0)),
                        {"resource": resource_type},
                    )
            except Exception as e:
                logger.debug(f"resource metrics unavailable: {e}")

        self.registry.set_gauge("theteam_uptime_seconds", time.time() - self._start_time)

    def health(self) -> Dict[str, Any]:
        """Build the health payload served at /health."""
        payload: Dict[str, Any] = {"status": "healthy"}

        loop = self._loop
        if loop is not None:
            breaker = getattr(loop, "circuit_breaker", None)
            is_open = getattr(breaker, "is_open", None)
            if callable(is_open) and is_open():
                payload["status"] = "unhealthy"
                payload["circuit_breaker"] = "open"

            health = getattr(loop, "health_monitor", None)
            if health is not None:
                score = health_score(health)
                if score is not None:
                    payload["health_score"] = score
                    # HealthMonitor scores 0.0-1.0; below 0.5 is critical.
                    if score < 0.5 and payload["status"] == "healthy":
                        payload["status"] = "unhealthy"

        return payload

    # -- lifecycle ---------------------------------------------------------

    def start_http_server(self, port: Optional[int] = None) -> bool:
        """
        Start the /metrics and /health HTTP server.

        Returns True on success, False if the port is unavailable - a busy port
        must not stop the orchestrator from running.
        """
        if self._server is not None:
            return True
        self.port = port or self.port
        collector = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server API
                if self.path.startswith("/metrics"):
                    collector.collect()
                    body = collector.registry.render().encode("utf-8")
                    content_type = "text/plain; version=0.0.4; charset=utf-8"
                    status = 200
                elif self.path.startswith("/health"):
                    body = json.dumps(collector.health()).encode("utf-8")
                    content_type = "application/json"
                    status = 200
                else:
                    body = b"not found"
                    content_type = "text/plain"
                    status = 404

                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt: str, *args: Any) -> None:
                # Route the access log into the project logger, not stderr.
                logger.debug("metrics http: " + fmt, *args)

        try:
            self._server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        except OSError as e:
            logger.error(f"Metrics server could not bind port {self.port}: {e}")
            self._server = None
            return False

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="MetricsHTTP",
        )
        self._thread.start()
        logger.info(f"Metrics server listening on :{self.port}/metrics and /health")
        return True

    def stop(self) -> None:
        """Shut the HTTP server down. Safe to call when never started."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self._thread = None
