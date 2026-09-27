"""
Reflex renderers shared by the dashboard pages.

Reflex is an OPTIONAL dependency: it is not declared in `pyproject.toml`
(keeping the core package installable without a web stack), so every renderer
here raises a clear error if Reflex is absent instead of failing at import time
and taking the whole package down.

The view models in this package never import Reflex. These renderers import the
view models, never the reverse.

Scope: only the pieces the pages actually compose with. The page modules own
their own layout, so this module holds the shared primitives - a severity pill
and the collapsible panel used by the activity, roster, and health views.
"""

from typing import Any, Optional

try:  # pragma: no cover - exercised only where Reflex is installed
    import reflex as rx
except ImportError as exc:  # pragma: no cover
    rx = None
    _REFLEX_IMPORT_ERROR = exc
else:
    _REFLEX_IMPORT_ERROR = None


def require_reflex():
    """Return the Reflex module, or raise a helpful error."""
    if rx is None:
        raise RuntimeError(
            "Reflex is required to render the web dashboard. "
            "Install it with `pip install reflex`. The view models in "
            "theteam.ui.components work without it."
        ) from _REFLEX_IMPORT_ERROR
    return rx


def severity_badge(severity: str, color: str) -> Any:
    """Render a severity pill from design tokens."""
    reflex = require_reflex()
    return reflex.badge(
        str(severity).upper(),
        color=color,
        variant="solid",
        radius="full",
        size="1",
    )


def disclosure_panel(
    panel_id: str,
    title: str,
    summary: str = "",
    detail_text: str = "",
    on_toggle: Optional[Any] = None,
    is_open: Optional[Any] = None,
) -> Any:
    """
    Render one collapsible panel (progressive disclosure).

    The caller supplies all three reactive inputs, because none can be derived
    at compile time from the plain stdlib DisclosureGroup:

    * `is_open` - a boolean Var taken from a precomputed row, so the panel
      re-renders when toggled.
    * `on_toggle` - an EventHandler owned by an `rx.State`. `group.toggle()`
      returns a bool, which reflex rejects as an invalid event chain.
    * `detail_text` - pre-rendered, pre-joined text. Reflex cannot `foreach`
      over an untyped nested Var, so the state layer formats the lines.
    """
    reflex = require_reflex()

    if is_open is None:
        raise ValueError(
            "disclosure_panel requires is_open (a reactive Var) so the panel "
            "re-renders when toggled"
        )

    def _icon(open_: Any) -> Any:
        """Chevron reflecting the panel's open state."""
        return reflex.cond(open_, "▼", "▶")

    def _body(open_: Any) -> Any:
        """Mount the detail block only while the panel is open."""
        rows = reflex.text(
            detail_text, size="1", color_scheme="gray", white_space="pre-line"
        )
        return reflex.cond(open_, rows, reflex.fragment())

    trigger = (
        reflex.button(
            _icon(is_open),
            on_click=on_toggle,
            variant="ghost",
            size="1",
        )
        if on_toggle is not None
        else reflex.text(_icon(is_open))
    )
    return reflex.vstack(
        trigger,
        reflex.text(title, weight="bold", size="2"),
        reflex.text(summary, size="1", color_scheme="gray"),
        _body(is_open),
        spacing="1",
        align="start",
        width="100%",
    )


def page_header(heading: str, summary: str, on_collapse: Optional[Any] = None) -> Any:
    """
    Page header with an optional "collapse all" control.

    Shared by the activity and roster pages so the control is not duplicated.
    """
    reflex = require_reflex()
    return reflex.hstack(
        reflex.heading(heading, size="6"),
        reflex.badge(summary, color_scheme="blue", variant="soft"),
        reflex.button(
            "Collapse all",
            on_click=on_collapse,
            size="1",
            variant="ghost",
        )
        if on_collapse is not None
        else reflex.fragment(),
        justify="between",
        width="100%",
        padding="4",
    )
