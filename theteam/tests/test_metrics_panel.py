"""Tests for the MetricsPanel, exercised against the real MetricsRegistry."""

import pytest

from theteam.core.metrics import MetricsRegistry
from theteam.ui.components.metrics_panel import MetricsPanel, parse_exposition


@pytest.fixture
def exposition():
    """A real registry rendered to Prometheus exposition text."""
    registry = MetricsRegistry()
    registry.describe("theteam_requests_total", "Requests")
    registry.inc("theteam_requests_total", {"route": "/health"}, 3)
    registry.inc("theteam_requests_total", {"route": "/metrics"}, 2)
    registry.describe("theteam_loop_iterations", "Iterations")
    registry.set_gauge("theteam_loop_iterations", 7)
    registry.describe("theteam_task_duration_seconds", "Duration")
    registry.observe("theteam_task_duration_seconds", 0.42)
    return registry.render()


@pytest.fixture
def panel():
    return MetricsPanel()


class TestParsing:
    def test_parses_labelled_sample(self):
        samples = parse_exposition('foo{bar="baz"} 1.5\n')
        assert samples[0]["name"] == "foo"
        assert samples[0]["labels"] == {"bar": "baz"}
        assert samples[0]["value"] == 1.5

    def test_parses_unlabelled_sample(self):
        assert parse_exposition("foo 3\n")[0]["value"] == 3.0

    def test_skips_help_and_type_metadata(self):
        assert parse_exposition("# HELP foo Help\n# TYPE foo gauge\nfoo 1\n") != []
        assert len(parse_exposition("# HELP foo Help\n# TYPE foo gauge\nfoo 1\n")) == 1

    def test_skips_blank_lines(self):
        assert len(parse_exposition("\n\nfoo 1\n\n")) == 1

    def test_ignores_non_numeric_samples(self):
        # `info{version="1"} 1` style builds are not numeric samples.
        assert parse_exposition('build_info{version="1.0"} abc\n') == []

    @pytest.mark.parametrize("junk", ["", "   ", "!!!", "no-value-here"])
    def test_malformed_lines_are_skipped_not_raised(self, junk):
        parse_exposition(junk + "\nfoo 1\n")

    def test_identifies_histogram_buckets(self):
        samples = parse_exposition('h_bucket{le="0.1"} 0\nh_count 1\n')
        assert samples[0]["is_histogram_bucket"] is True
        assert samples[1]["is_histogram_bucket"] is False

    def test_escaped_quote_in_label(self):
        samples = parse_exposition('foo{msg="a\\"b"} 1\n')
        assert samples[0]["labels"]["msg"] == 'a"b'

    def test_multiple_labels(self):
        samples = parse_exposition('foo{a="1",b="2"} 1\n')
        assert samples[0]["labels"] == {"a": "1", "b": "2"}


class TestCounterRows:
    def test_reads_real_registry_series(self, panel, exposition):
        rows = panel.counters(exposition)
        names = {r["name"] for r in rows}
        assert "theteam_requests_total" in names
        assert "theteam_loop_iterations" in names

    def test_label_set_rendered_in_row(self, panel, exposition):
        row = next(r for r in panel.counters(exposition) if r["name"] == "theteam_loop_iterations")
        assert row["label"] == ""
        labelled = [r for r in panel.counters(exposition) if r["name"] == "theteam_requests_total"]
        assert all("route=" in r["label"] for r in labelled)

    def test_values_are_display_formatted(self, panel, exposition):
        row = next(r for r in panel.counters(exposition) if r["name"] == "theteam_loop_iterations")
        assert row["value"] == 7.0
        assert row["display"] == "7"

    def test_buckets_excluded_from_counter_rows(self, panel, exposition):
        assert not any(r["name"].endswith("_bucket") for r in panel.counters(exposition))

    def test_max_series_caps_rows(self):
        panel = MetricsPanel(max_series=2)
        text = "\n".join(f"m{i} {i}" for i in range(10))
        assert len(panel.counters(text)) == 2

    def test_empty_exposition(self, panel):
        assert panel.counters("") == []


class TestTotals:
    def test_total_sums_across_labels(self, panel, exposition):
        # /health (3) + /metrics (2)
        assert panel.total(exposition, "theteam_requests_total") == 5.0

    def test_total_missing_metric_is_none(self, panel, exposition):
        assert panel.total(exposition, "nope_total") is None

    def test_summary_reports_series_count(self, panel, exposition):
        assert panel.summary(exposition)["series"] > 0

    def test_summary_absent_metrics_are_none(self, panel, exposition):
        summary = panel.summary(exposition)
        assert summary["error_count"] is None


class TestHistogram:
    def test_reads_count_and_sum_from_real_registry(self, panel, exposition):
        stats = panel.histogram_quantiles(exposition, "theteam_task_duration_seconds")
        assert stats["count"] == 1.0
        assert stats["sum"] == 0.42
        assert stats["buckets"] == 8

    def test_absent_histogram_is_empty(self, panel, exposition):
        assert panel.histogram_quantiles(exposition, "not_there_seconds") == {}

    def test_count_falls_back_to_top_bucket(self, panel):
        text = 'h_bucket{le="0.1"} 0\nh_bucket{le="+Inf"} 4\n'
        assert panel.histogram_quantiles(text, "h")["count"] == 4.0

    def test_non_numeric_le_is_skipped(self, panel):
        text = 'h_bucket{le="bad"} 1\nh_bucket{le="1.0"} 2\n'
        assert panel.histogram_quantiles(text, "h")["buckets"] == 1


class TestFormatting:
    @pytest.mark.parametrize(
        "value,expected",
        [(0.0, "0"), (7.0, "7"), (1500.0, "1.5k"), (2_500_000.0, "2.5M"), (0.25, "0.25")],
    )
    def test_display_formatting(self, panel, value, expected):
        from theteam.ui.components.metrics_panel import _fmt

        assert _fmt(value) == expected
