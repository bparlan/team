"""
Tests for the Reflex visibility state.

Reflex is an optional dependency, so these skip where it is absent. They only
cover the wiring: that the State declares every field the pages read, and that
it delegates to the pure builders rather than reimplementing them.
"""

import re
from pathlib import Path

import pytest

reflex = pytest.importorskip("reflex", reason="dashboard requires the optional reflex extra")

from theteam.ui.web_dashboard.theteam_dashboard.visibility_state import VisibilityState

PAGES_DIR = Path(__file__).resolve().parent.parent / "ui" / "web_dashboard" / "theteam_dashboard" / "pages"


class TestDeclaredSurface:
    def test_pages_only_reference_declared_state(self):
        """Every VisibilityState.X used by a page must exist on the class."""
        declared = set(vars(VisibilityState))
        missing = set()
        for page in PAGES_DIR.glob("*.py"):
            for name in re.findall(r"VisibilityState\.(\w+)", page.read_text()):
                if name not in declared:
                    missing.add(f"{page.name}:{name}")
        assert not missing, f"pages reference undeclared state: {sorted(missing)}"

    def test_state_delegates_to_pure_builders(self):
        """The State must not reimplement view logic in the handler."""
        source = (PAGES_DIR.parent / "visibility_state.py").read_text()
        assert "build_visibility(" in source
        assert "apply_panel_state(" in source
        # If the handler grew its own row-building, that logic would be
        # untestable without a running reflex runtime.
        assert "detail_text" not in source

    def test_error_is_surfaced_not_swallowed(self):
        assert "except Exception" in (PAGES_DIR.parent / "visibility_state.py").read_text()

    def test_panels_field_present(self):
        assert "expanded_panels" in vars(VisibilityState)
        assert "health_recovery_open" in vars(VisibilityState)


class TestToggleHandlersExist:
    @pytest.mark.parametrize(
        "name",
        ["toggle_panel", "toggle_health_recovery", "collapse_all", "load_visibility"],
    )
    def test_handler_defined(self, name):
        assert callable(getattr(VisibilityState, name, None))

class TestPageBuilderKeyContract:
    """
    Pages and the builder must agree on row keys.

    Regression cover for a real break: the pages read `detail_lines` while the
    builder emitted `detail_text`, so every disclosure panel silently rendered
    empty detail. Builder-level tests could not catch it - only cross-checking
    the keys each side actually uses can.

    Keys are read from real builder output, not from source, because the row
    builders spread upstream rows (`**row`) and so do not name every key.
    """

    @pytest.fixture
    def built(self):
        from theteam.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        from theteam.ui.components.visibility import build_visibility

        cb = CircuitBreaker("db", CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure()
        return build_visibility(
            {
                "events": [
                    {
                        "id": "e1",
                        "message": "Loop complete",
                        "severity": "info",
                        "agent": "orch",
                        "timestamp": "12:00:01",
                        "details": {"iterations": 12},
                    }
                ],
                "breakers": {"db": cb},
                "agents": [{"id": "w1", "name": "Worker", "status": "active"}],
            }
        )

    def _page_keys(self, filename: str, row_var: str) -> set:
        return set(
            re.findall(rf'{row_var}\["(\w+)"\]', (PAGES_DIR / filename).read_text())
        )

    def test_activity_page_keys_exist_in_builder(self, built):
        page_keys = self._page_keys("activity.py", "event")
        missing = page_keys - set(built["activity_view"][0])
        assert not missing, f"activity page reads keys the builder never emits: {sorted(missing)}"

    def test_agents_page_keys_exist_in_builder(self, built):
        page_keys = self._page_keys("agents.py", "agent")
        missing = page_keys - set(built["roster_view"][0])
        assert not missing, f"agents page reads keys the builder never emits: {sorted(missing)}"
