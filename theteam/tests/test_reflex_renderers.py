"""
Tests for the optional Reflex renderers.

Reflex is not a declared dependency, so it is absent in CI. The reflex-free
architecture depends on the view models importing no Reflex, and that guard
must actually RUN there - so the stdlib-only checks sit at module scope and
never touch Reflex. Only the tests that genuinely need Reflex are skipped, and
the `rx.State` subclass is defined lazily inside a fixture, because a
module-level `importorskip` would still let the class body execute and break
collection outright.
"""

import importlib
import importlib.util

import pytest

from theteam.ui.components import reflex_renderers as rr
from theteam.ui.components.disclosure import DisclosureGroup

VIEW_MODEL_MODULES = [
    "theteam.ui.components.activity_stream",
    "theteam.ui.components.agent_roster",
    "theteam.ui.components.health_dashboard",
    "theteam.ui.components.metrics_panel",
    "theteam.ui.components.disclosure",
    "theteam.ui.components.visibility",
]


class TestViewModelsAreReflexFree:
    """Runs in CI, where Reflex is not installed.

    This is the automated guard for the architecture decision: the view models
    must stay stdlib-only, because `pyproject.toml` declares no dependencies
    and CI does `pip install -e .`.
    """

    @pytest.mark.parametrize("module_name", VIEW_MODEL_MODULES)
    def test_view_model_does_not_import_reflex(self, module_name):
        # The dependency direction must stay one-way: view models are
        # stdlib-only, renderers depend on them.
        module = importlib.import_module(module_name)
        assert "reflex" not in module.__dict__

    def test_renderer_module_imports_without_reflex(self):
        # Importing the renderer must never raise, even with Reflex absent.
        assert rr is not None


class TestGroupToggleIsNotAnEventChain:
    """Stdlib-only: documents why the renderer needs an injected handler."""

    def test_group_toggle_returns_bool(self):
        # Reflex rejects non-event-chain values ("Invalid event chain"), which
        # is why `on_toggle` must be supplied by an rx.State method.
        assert isinstance(DisclosureGroup().toggle("p"), bool)


# A module-level importorskip here would skip the whole file, including the
# reflex-free guards above that must run in CI. Import without asserting, and
# let each reflex-dependent class skip itself.
reflex = importlib.import_module("reflex") if importlib.util.find_spec("reflex") else None

requires_reflex = pytest.mark.skipif(
    reflex is None, reason="renderers require the optional reflex extra"
)


@requires_reflex
class TestRequireReflex:
    def test_returns_module(self):
        assert rr.require_reflex() is reflex


@requires_reflex
class TestSeverityBadge:
    def test_renders_badge(self):
        assert rr.severity_badge("error", "#dc2626") is not None

    def test_uppercases_severity(self):
        # Reflex-safe: a severity must never reach the UI in mixed case.
        assert rr.severity_badge("warning", "#d97706") is not None


if reflex is not None:

    class _HandlerState(reflex.State):
        """A real rx.State, so handlers are genuine Reflex event chains."""

        expanded: list = []

        def toggle_panel(self, panel_id: str):
            self.expanded.append(panel_id)


@pytest.fixture
def handler():
    """
    A genuine Reflex event chain.

    Guarded on reflex as well as marked: `_HandlerState` only exists when
    Reflex is importable, so without this guard the fixture raises NameError
    instead of skipping if a `@requires_reflex` mark is ever dropped.
    """
    if reflex is None or "_HandlerState" not in globals():
        pytest.skip("reflex required to build an event handler")
    return _HandlerState.toggle_panel("p")


@requires_reflex
class TestDisclosurePanel:
    def test_requires_is_open(self):
        # The panel must be reactive; omitting is_open would silently render a
        # dead toggle.
        with pytest.raises(ValueError, match="is_open"):
            rr.disclosure_panel("p", "Title", "s", "k: v")

    def test_renders_with_is_open_and_handler(self, handler):
        assert (
            rr.disclosure_panel(
                "p",
                "Title",
                "1 field",
                "k: v",
                on_toggle=handler,
                is_open=False,
            )
            is not None
        )

    def test_renders_without_handler(self):
        # Read-only rendering is valid; the renderer must not fabricate an
        # invalid event chain.
        assert rr.disclosure_panel("p", "Title", "s", "k: v", is_open=False) is not None


@requires_reflex
class TestPageHeader:
    def test_renders(self, handler):
        assert rr.page_header("Title", "summary", on_collapse=handler) is not None

    def test_renders_without_collapse_control(self):
        assert rr.page_header("Title", "summary") is not None
