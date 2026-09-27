"""
MetricsPanel - renders the Prometheus exposition from `core.metrics` as UI rows.

Pure-stdlib. Parses the registry's own text exposition rather than reaching into
its internals, so whatever `/metrics` serves is exactly what the panel shows.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

# name{label="v",...} 1.0   /   name 1.0
_SAMPLE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)"
    r"(?:\{(?P<labels>[^}]*)\})?"
    r"\s+(?P<value>\S+)\s*$"
)
_LABEL = re.compile(r'(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)="(?P<value>(?:[^"\\]|\\.)*)"')


def parse_exposition(text: str) -> List[Dict[str, Any]]:
    """
    Parse Prometheus text exposition into flat sample dicts.

    Comment lines, TYPE/HELP metadata and histogram bucket suffixes are handled
    so the caller gets only real samples. Never raises on malformed input - a
    bad line is skipped.
    """
    samples: List[Dict[str, Any]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _SAMPLE.match(line)
        if not match:
            continue
        value_text = match.group("value")
        try:
            value = float(value_text)
        except ValueError:
            # Non-numeric samples (e.g. `info{version="1.0"} 1`) are ignored.
            continue
        name = match.group("name")
        labels = {
            m.group("key"): m.group("value").replace('\\"', '"')
            for m in _LABEL.finditer(match.group("labels") or "")
        }
        samples.append(
            {
                "name": name,
                "labels": labels,
                "value": value,
                "is_histogram_bucket": name.endswith("_bucket"),
            }
        )
    return samples


def _fmt(value: float) -> str:
    """Compact human-readable rendering of a sample value."""
    # Magnitude scaling must come first: 2_500_000 is an integer, so testing
    # integrality up front would render it as "2500000" and never as "2.5M".
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


class MetricsPanel:
    """Turns registry exposition text into dashboard-ready rows."""

    def __init__(self, max_series: int = 40):
        self.max_series = max_series

    def samples(self, exposition: str) -> List[Dict[str, Any]]:
        """All parsed samples from the exposition text."""
        return parse_exposition(exposition)

    def counters(self, exposition: str) -> List[Dict[str, Any]]:
        """Non-bucket samples, one row per series, labelled rows only."""
        rows: List[Dict[str, Any]] = []
        for sample in self.samples(exposition):
            if sample["is_histogram_bucket"]:
                continue
            rows.append(
                {
                    "name": sample["name"],
                    "labels": sample["labels"],
                    "label": _label_suffix(sample["labels"]),
                    "value": sample["value"],
                    "display": _fmt(sample["value"]),
                }
            )
            if len(rows) >= self.max_series:
                break
        return rows

    def total(self, exposition: str, name: str) -> Optional[float]:
        """Sum one metric by name, or None when it is absent."""
        matches = [s["value"] for s in self.samples(exposition) if s["name"] == name]
        return sum(matches) if matches else None

    def histogram_quantiles(self, exposition: str, name: str) -> Dict[str, float]:
        """
        Estimate count/sum from a histogram's buckets.

        `name` is the histogram base (e.g. `request_duration_seconds`);
        returns {} when that histogram is not present.
        """
        buckets: List[Tuple[float, float]] = []
        total_sum = 0.0
        count = 0.0
        for sample in self.samples(exposition):
            if sample["name"] == f"{name}_bucket":
                le = sample["labels"].get("le")
                try:
                    buckets.append((float(le), sample["value"]))
                except (TypeError, ValueError):
                    continue
            elif sample["name"] == f"{name}_sum":
                total_sum = sample["value"]
            elif sample["name"] == f"{name}_count":
                count = sample["value"]
        if not buckets and count == 0.0:
            return {}
        buckets.sort()
        if count == 0.0 and buckets:
            count = buckets[-1][1]
        return {"count": count, "sum": total_sum, "buckets": len(buckets)}

    def summary(self, exposition: str) -> Dict[str, Any]:
        """Headline numbers for the metrics card."""
        return {
            "series": len(self.samples(exposition)),
            "request_count": self.total(exposition, "theteam_requests_total"),
            "error_count": self.total(exposition, "theteam_errors_total"),
            "health_score": self.total(exposition, "theteam_health_score"),
        }


def _label_suffix(labels: Dict[str, str]) -> str:
    """Render a label set as `k=v,k=v` for display, empty when unlabelled."""
    if not labels:

        return ""
    return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
