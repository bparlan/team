"""Tests for UI design tokens and state-machine visual semantics."""

import pytest

from theteam.core.circuit_breaker import CircuitState
from theteam.ui.components.design_tokens import (
    AGENT_STATUSES,
    CIRCUIT_VISUALS,
    DesignTokens,
    Palette,
    Severity,
    agent_status_visual,
    circuit_visual,
    health_band,
)


class TestSeverity:
    def test_order_is_least_to_most_urgent(self):
        order = Severity.order()
        assert order.index(Severity.DEBUG) < order.index(Severity.INFO)
        assert order.index(Severity.INFO) < order.index(Severity.WARNING)
        assert order.index(Severity.WARNING) < order.index(Severity.ERROR)
        assert order.index(Severity.ERROR) < order.index(Severity.CRITICAL)

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("warning", Severity.WARNING),
            ("WARN", Severity.WARNING),
            ("  Error  ", Severity.ERROR),
            ("fatal", Severity.CRITICAL),
            ("crit", Severity.CRITICAL),
            ("ok", Severity.SUCCESS),
            ("trace", Severity.DEBUG),
        ],
    )
    def test_normalize_aliases(self, raw, expected):
        assert Severity.normalize(raw) == expected

    def test_normalize_passes_through_canonical(self):
        for level in Severity.order():
            assert Severity.normalize(level) == level

    def test_normalize_unknown_falls_back_to_info(self):
        # A malformed severity must not take down the stream reporting it.
        assert Severity.normalize("garbage") == Severity.INFO
        assert Severity.normalize(None) == Severity.INFO
        assert Severity.normalize(12345) == Severity.INFO

    def test_normalize_does_not_raise_on_objects(self):
        class Weird:
            def __str__(self):
                return "ERROR"

        assert Severity.normalize(Weird()) == Severity.ERROR


class TestCircuitVisual:
    def test_maps_real_circuit_state_enum(self):
        # Guards the contract the dashboard relies on: the UI reads the same
        # enum the breaker itself uses.
        assert circuit_visual(CircuitState.CLOSED).state == "closed"
        assert circuit_visual(CircuitState.OPEN).state == "open"
        assert circuit_visual(CircuitState.HALF_OPEN).state == "half_open"

    def test_open_is_the_bad_state(self):
        # The classic UI bug: rendering "open" as healthy. OPEN means the
        # breaker tripped and traffic is blocked, so it must be the danger
        # color, and CLOSED (traffic flowing) must be success.
        assert circuit_visual(CircuitState.OPEN).color == Palette.danger
        assert circuit_visual(CircuitState.CLOSED).color == Palette.success
        assert circuit_visual(CircuitState.HALF_OPEN).color == Palette.warning

    def test_state_colors_match_breaker_semantics(self):
        """
        Derive expected polarity from the breaker's own enum values.

        `CLOSED` is "requests allowed" (healthy) and `OPEN` is "requests
        blocked" (tripped). If either the enum or the tokens are ever
        redefined, this fails instead of silently inverting the UI.
        """
        allowed = CircuitState.CLOSED.value
        blocked = CircuitState.OPEN.value
        assert circuit_visual(allowed).color == Palette.success
        assert circuit_visual(blocked).color == Palette.danger
        # And they must actually differ, or severity coding is meaningless.
        assert circuit_visual(allowed).color != circuit_visual(blocked).color

    def test_every_state_has_distinct_icon_and_label(self):
        visuals = [circuit_visual(s) for s in CircuitState]
        assert len({v.icon for v in visuals}) == 3
        assert len({v.label for v in visuals}) == 3
        assert all(v.description for v in visuals)

    def test_all_three_states_are_keyed(self):
        assert set(CIRCUIT_VISUALS) == {"closed", "half_open", "open"}

    @pytest.mark.parametrize("junk", [None, "", "nonsense", 42])
    def test_unknown_state_degrades_safely(self, junk):
        visual = circuit_visual(junk)
        assert visual.state == "unknown"
        assert visual.label == "Unknown"
        assert visual.color == Palette.neutral

    def test_accepts_plain_string(self):
        assert circuit_visual("HALF_OPEN").state == "half_open"
        assert circuit_visual(" open ").state == "open"


class TestHealthBand:
    @pytest.mark.parametrize(
        "score,label",
        [
            (1.0, "Healthy"),
            (0.8, "Healthy"),
            (0.79, "Degraded"),
            (0.5, "Degraded"),
            (0.49, "Critical"),
            (0.0, "Critical"),
        ],
    )
    def test_bands(self, score, label):
        assert health_band(score).label == label

    def test_band_colors_are_ordered_by_severity(self):
        assert health_band(0.9).color == Palette.success
        assert health_band(0.6).color == Palette.warning
        assert health_band(0.1).color == Palette.danger

    @pytest.mark.parametrize("score", [-5.0, 42.0])
    def test_out_of_range_is_clamped(self, score):
        # Out-of-range must not produce a band-less visual.
        assert health_band(score).label in {"Healthy", "Degraded", "Critical"}

    def test_zero_is_critical_not_unknown(self):
        assert health_band(0.0).state == "critical"


class TestAgentStatusVisual:
    @pytest.mark.parametrize("status", AGENT_STATUSES)
    def test_known_statuses_have_visual(self, status):
        visual = agent_status_visual(status)
        assert visual.state == status
        assert visual.icon != "?"
        assert visual.color.startswith("#")

    def test_every_status_has_a_distinct_icon(self):
        # Icons must be separable even where colors are intentionally shared
        # (idle and offline both read as "not busy").
        icons = {agent_status_visual(s).icon for s in AGENT_STATUSES}
        assert len(icons) == len(AGENT_STATUSES)
        assert agent_status_visual("error").color == Palette.danger
        assert agent_status_visual("active").color == Palette.success

    def test_unknown_status_degrades(self):
        assert agent_status_visual("exploded").label == "Unknown"
        assert agent_status_visual("exploded").icon == "?"

    def test_missing_status_defaults_to_offline(self):
        assert agent_status_visual(None).state == "offline"
        assert agent_status_visual("").state == "offline"


class TestDesignTokens:
    def test_severity_color_covers_every_level(self):
        tokens = DesignTokens()
        for level in Severity.order():
            assert tokens.severity_color(level).startswith("#")

    def test_severity_colors_differ_per_level(self):
        tokens = DesignTokens()
        colors = {level: tokens.severity_color(level) for level in Severity.order()}
        # DEBUG and INFO must not collide, or severity coding is meaningless.
        assert colors[Severity.DEBUG] != colors[Severity.INFO]

    def test_severity_color_normalizes_first(self):
        tokens = DesignTokens()
        assert tokens.severity_color("WARN") == tokens.severity_color(Severity.WARNING)
        assert tokens.severity_color("junk") == tokens.severity_color(Severity.INFO)

    def test_all_tokens_is_flat_and_populated(self):
        tokens = DesignTokens().all_tokens()
        assert tokens
        assert "color.accent" in tokens
        assert tokens["severity.order"] == Severity.order()
        for key, value in tokens.items():
            if key.startswith("color."):
                assert isinstance(value, str) and value.startswith("#")
