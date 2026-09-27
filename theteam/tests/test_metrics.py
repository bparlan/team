#!/usr/bin/env python3
"""
Regression tests for theteam.core.metrics.

Defends the observable contracts callers depend on:
  * counter accumulation, gauge overwrite, histogram observation
  * Prometheus CUMULATIVE histogram buckets (+Inf == observation count)
  * text exposition format: HELP/TYPE lines, sorted+escaped label sets
  * breaker_state_value / health_score mapping (and the unknown-input sentinel)
  * MetricsCollector degrades gracefully when the port is busy
"""

import os
import socket
import sys
from types import SimpleNamespace

import re

import pytest


from theteam.core import metrics as metrics_mod
from theteam.core.circuit_breaker import CircuitState
from theteam.core.metrics import (
    MetricsCollector,
    MetricsRegistry,
    breaker_state_value,
    health_score,
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def parse_samples(rendered):
    """Parse exposition text into {full_series_name: float value}."""
    samples = {}
    for line in rendered.splitlines():
        if not line or line.startswith("#"):
            continue
        series, _, value = line.rpartition(" ")
        samples[series] = float(value)
    return samples


_BUCKET_RE = re.compile(
    r'^(?P<series>[A-Za-z_:][A-Za-z0-9_:]*)_bucket\{(?P<labels>.*)le="(?P<le>[^"]*)"\} (?P<value>\S+)$'
)


def bucket_values(rendered, series):
    """Return [(le_label, value)] for every bucket series of `series`, in order."""
    out = []
    for line in rendered.splitlines():
        match = _BUCKET_RE.match(line)
        if match and match.group("series") == series:
            out.append((match.group("le"), float(match.group("value"))))
    return out


# --------------------------------------------------------------------------
# counter / gauge / histogram recording
# --------------------------------------------------------------------------


def test_counter_accumulates_across_calls_and_label_order():
    """inc() is cumulative: repeated calls sum, and label dict order is irrelevant."""
    reg = MetricsRegistry()
    reg.inc("tasks_total")
    reg.inc("tasks_total", value=4)
    reg.inc("tasks_total", {"a": "1", "b": "2"}, 2)
    reg.inc("tasks_total", {"b": "2", "a": "1"}, 3)


# --------------------------------------------------------------------------
# counter / gauge / histogram recording
# --------------------------------------------------------------------------

    assert reg.get("tasks_total") == 5.0
    # Distinct label sets are distinct series; order must not fork them.
    assert reg.get("tasks_total", {"a": "1", "b": "2"}) == 5.0
    assert reg.get("tasks_total", {"a": "1"}) == 0.0


def test_gauge_overwrites_instead_of_accumulating():
    """A gauge holds the latest value; a second set must replace, not add."""
    reg = MetricsRegistry()
    reg.set_gauge("queue_depth", 3)
    reg.set_gauge("queue_depth", 7)
    reg.set_gauge("queue_depth", 0)

    assert reg.get("queue_depth") == 0.0
    assert parse_samples(reg.render())["queue_depth"] == 0.0


def test_histogram_buckets_are_cumulative_and_inf_equals_count():
    """
    Prometheus histogram buckets are CUMULATIVE: each `le` counts every
    observation <= that bound, counts never decrease as `le` grows, and the
    `+Inf` bucket equals the total number of observations.
    """
    reg = MetricsRegistry()
    for value in (0.05, 0.4, 0.9, 3.0, 7.0, 100.0):
        reg.observe("latency", value, {"k": "v"}, buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0))

    rendered = reg.render()
    buckets = bucket_values(rendered, "latency")
    counts = [count for _, count in buckets]

    assert [le for le, _ in buckets][-1] == "+Inf"
    assert all(a <= b for a, b in zip(counts, counts[1:])), f"non-monotonic buckets: {buckets}"
    assert buckets[-1][1] == 6.0, "the +Inf bucket must equal the observation count"
    assert parse_samples(rendered)['latency_count{k="v"}'] == 6.0
    assert parse_samples(rendered)['latency_sum{k="v"}'] == pytest.approx(111.35)
    # Boundary is inclusive: 0.05 <= 0.1 and 0.4 <= 0.5.
    assert counts[0] == 1.0
    assert counts[1] == 2.0


def test_histogram_stays_cumulative_across_multiple_observations():
    """A second observation must add to every qualifying bucket, not reset it."""
    reg = MetricsRegistry()
    reg.observe("latency", 0.2, buckets=(1.0, 2.0))
    reg.observe("latency", 1.5, buckets=(1.0, 2.0))

    buckets = bucket_values(reg.render(), "latency")
    assert buckets == [("1.0", 1.0), ("2.0", 2.0), ("+Inf", 2.0)]


def test_histogram_materialises_every_declared_bucket_at_zero():
    """Zero-count buckets must still be emitted or histogram_quantile() breaks."""
    reg = MetricsRegistry()
    reg.observe("latency", 100.0, buckets=(0.1, 1.0, 10.0))

    assert [le for le, _ in bucket_values(reg.render(), "latency")] == [
        "0.1",
        "1.0",
        "10.0",
        "+Inf",
    ]


# --------------------------------------------------------------------------
# render() / exposition format
# --------------------------------------------------------------------------

def test_render_emits_help_and_type_lines_per_metric_family():
    reg = MetricsRegistry()
    reg.describe("tasks_total", "Total tasks processed.")
    reg.inc("tasks_total", value=1)
    reg.set_gauge("queue_depth", 2)
    reg.observe("latency", 0.5)

    lines = reg.render().splitlines()
    assert "# HELP tasks_total Total tasks processed." in lines
    assert "# TYPE tasks_total counter" in lines
    assert "# TYPE queue_depth gauge" in lines
    assert "# TYPE latency histogram" in lines
    # Each family declares its TYPE exactly once even with many series.
    assert lines.count("# TYPE tasks_total counter") == 1


def test_render_sorts_label_sets_deterministically():
    reg = MetricsRegistry()
    reg.inc("m", {"zeta": "1", "alpha": "2", "mid": "3"})

    line = next(l for l in reg.render().splitlines() if l.startswith("m{"))
    assert line == 'm{alpha="2",mid="3",zeta="1"} 1.0'


def test_render_escapes_quotes_backslashes_and_newlines_in_labels():
    """Raw control/quote characters would corrupt the exposition stream."""
    reg = MetricsRegistry()
    reg.inc("m", {"path": 'C:\\tmp\\"q"\nnext'})

    rendered = reg.render()
    line = next(l for l in rendered.splitlines() if l.startswith("m{"))
    assert line == 'm{path="C:\\\\tmp\\\\\\"q\\"\\nnext"} 1.0'
    # The value never spans a physical line break.
    assert len(rendered.splitlines()) == 2  # TYPE line + one sample


def test_render_histogram_bucket_labels_are_prometheus_canonical():
    reg = MetricsRegistry()
    reg.observe("h", 0.05, buckets=(0.1, 1.0))

    rendered = reg.render()
    assert 'h_bucket{le="0.1"} 1' in rendered
    assert 'h_bucket{le="+Inf"} 1' in rendered
    assert "le=inf" not in rendered


def test_render_ends_with_a_trailing_newline():
    """Prometheus parsers expect the document to be newline-terminated."""
    reg = MetricsRegistry()
    reg.inc("m")

    assert reg.render().endswith("\n")


# --------------------------------------------------------------------------
# breaker_state_value()
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "state, expected",
    [
        (CircuitState.CLOSED, 0.0),
        (CircuitState.HALF_OPEN, 1.0),
        (CircuitState.OPEN, 2.0),
    ],
)
def test_breaker_state_value_maps_each_state_to_its_gauge_value(state, expected):
    breaker = SimpleNamespace(stats=SimpleNamespace(state=state))

    assert breaker_state_value(breaker) == expected


def test_breaker_state_value_reads_the_stats_attribute():
    """A breaker reporting OPEN through is_open() must expose 2.0 on the gauge."""
    breaker = SimpleNamespace(
        stats=SimpleNamespace(state=CircuitState.OPEN),
        is_open=lambda: True,
    )

    assert breaker_state_value(breaker) == 2.0


@pytest.mark.parametrize(
    "breaker",
    [
        None,
        SimpleNamespace(),
        SimpleNamespace(stats=None),
        SimpleNamespace(stats=SimpleNamespace(state="melted")),
    ],
)
def test_breaker_state_value_is_minus_one_for_unknown_state(breaker):
    """Unknown state must be a sentinel, never a crash or a wrong bucket."""
    assert breaker_state_value(breaker) == -1.0


# --------------------------------------------------------------------------
# health_score()
# --------------------------------------------------------------------------

def test_health_score_prefers_get_health_score():
    monitor = SimpleNamespace(
        get_health_score=lambda: 0.75,
        get_health_status=lambda: {"health_score": 0.1},
    )

    assert health_score(monitor) == 0.75


def test_health_score_falls_back_to_status_dict():
    """HealthMonitor in this repo only exposes get_health_status()."""
    monitor = SimpleNamespace(get_health_status=lambda: {"health_score": 0.42})

    assert health_score(monitor) == 0.42


def test_health_score_survives_a_raising_health_score_reader():
    monitor = SimpleNamespace(
        get_health_score=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        get_health_status=lambda: {"health_score": 0.6},
    )

    assert health_score(monitor) == 0.6


def test_health_score_is_none_when_no_reader_exists():
    assert health_score(None) is None
    assert health_score(SimpleNamespace()) is None


# --------------------------------------------------------------------------
# MetricsCollector.collect()
# --------------------------------------------------------------------------

def _collector_with_fakes(**overrides):
    loop_kwargs = dict(
        metrics={"tasks_started": 3, "tasks_completed": 2, "tasks_failed": 1},
        tasks={"a": 1, "b": 2},
        dead_letter_queue=["x", "y"],
        circuit_breaker=SimpleNamespace(
            stats=SimpleNamespace(state=CircuitState.OPEN), is_open=lambda: True
        ),
        health_monitor=SimpleNamespace(get_health_score=lambda: 0.3),
    )
    loop_kwargs.update(overrides)
    limiter = SimpleNamespace(
        get_usage_report=lambda: {
            "resource_breakdown": {"cpu": {"average_utilization": 42.5}}
        }
    )
    reg = MetricsRegistry()
    collector = MetricsCollector(registry=reg)
    collector.bind(SimpleNamespace(**loop_kwargs), limiter)
    return collector, reg


def test_collect_publishes_loop_and_limiter_metrics():
    collector, reg = _collector_with_fakes()
    collector.collect()

    samples = parse_samples(reg.render())
    assert samples["theteam_tasks_started"] == 3.0
    assert samples["theteam_tasks_completed"] == 2.0
    assert samples["theteam_tasks_failed"] == 1.0
    assert samples["theteam_tasks_active"] == 2.0
    assert samples["theteam_dead_letter_queue"] == 2.0
    assert samples["theteam_circuit_breaker_state"] == 2.0
    assert samples["theteam_health_score"] == 0.3
    assert samples['theteam_resource_utilization_percent{resource="cpu"}'] == 42.5


def test_collect_is_idempotent_across_scrape_cycles():
    """Counters are absolute: a second scrape must not double them."""
    collector, reg = _collector_with_fakes()
    collector.collect()
    collector.collect()

    assert reg.get("theteam_tasks_started") == 3.0


def test_collect_degrades_when_the_loop_explodes():
    """A broken component must not take the exporter down with it."""
    class ExplodingLoop:
        @property
        def metrics(self):
            raise RuntimeError("loop metrics unavailable")

        tasks = {}
        dead_letter_queue = []

    collector, reg = _collector_with_fakes()
    collector._loop = ExplodingLoop()

    collector.collect()

    assert "theteam_uptime_seconds" in parse_samples(reg.render())


def test_health_payload_flags_an_open_breaker():
    collector, _ = _collector_with_fakes()
    payload = collector.health()

    assert payload["status"] == "unhealthy"
    assert payload["circuit_breaker"] == "open"
    assert payload["health_score"] == 0.3


def test_health_payload_is_healthy_with_a_closed_breaker_and_good_score():
    collector, _ = _collector_with_fakes(
        circuit_breaker=SimpleNamespace(
            stats=SimpleNamespace(state=CircuitState.CLOSED), is_open=lambda: False
        ),
        health_monitor=SimpleNamespace(get_health_score=lambda: 0.9),
    )

    assert collector.health()["status"] == "healthy"


def test_health_payload_marks_low_score_unhealthy():
    collector, _ = _collector_with_fakes(
        circuit_breaker=SimpleNamespace(
            stats=SimpleNamespace(state=CircuitState.CLOSED), is_open=lambda: False
        ),
        health_monitor=SimpleNamespace(get_health_score=lambda: 0.49),
    )

    assert collector.health()["status"] == "unhealthy"


# --------------------------------------------------------------------------
# MetricsCollector.start_http_server()
# --------------------------------------------------------------------------

def test_start_http_server_returns_false_on_a_busy_port():
    """A busy port must degrade gracefully; container startup depends on it."""
    blocker = socket.socket()
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        blocker.bind(("0.0.0.0", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]

        collector = MetricsCollector(port=port)
        try:
            assert collector.start_http_server() is False
            assert collector._server is None
        finally:
            collector.stop()
    finally:
        blocker.close()


def test_start_http_server_is_idempotent_and_binds_the_requested_port(monkeypatch):
    """A second start must not rebind, and an explicit port must win."""
    created = []

    class FakeServer:
        def __init__(self, address, handler):
            self.address = address
            created.append(address)

        def serve_forever(self):
            return None

        def shutdown(self):
            self.closed = True

        def server_close(self):
            self.closed = True
    monkeypatch.setattr(metrics_mod, "ThreadingHTTPServer", FakeServer)

    collector = MetricsCollector(port=1)
    assert collector.start_http_server(port=9999) is True
    assert created == [("0.0.0.0", 9999)]

    collector.start_http_server(port=8888)
    assert created == [("0.0.0.0", 9999)], "already-started collector must not rebind"
    assert collector.port == 9999

    collector.stop()
    assert collector._server is None
