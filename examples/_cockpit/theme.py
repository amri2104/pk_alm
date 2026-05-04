"""Cockpit theme constants and Plotly template."""

from __future__ import annotations

from typing import Any

BG = "#0F1B2D"
PANEL = "#152238"
FG = "#E6EDF3"
MUTED = "#9DA9B8"
TEAL = "#26C6A8"
CORAL = "#E5484D"
AMBER = "#F4B740"
GOLD = "#D4AF37"
GRID = "#2A3A52"

STATUS_COLORS = {
    "ok": TEAL,
    "warn": AMBER,
    "alert": CORAL,
    "neutral": MUTED,
}

FR_RED = 90.0
FR_AMBER = 100.0
FR_GREEN = 110.0
FR_TARGET_DEFAULT = 107.6

FONT_FAMILY = (
    '"Inter", "SF Pro Display", -apple-system, BlinkMacSystemFont, '
    '"Segoe UI", "Helvetica Neue", Arial, sans-serif'
)

SOURCE_COLORS = {
    "BVG": CORAL,
    "ACTUS": TEAL,
    "MANUAL": AMBER,
    "ASSUMPTION": AMBER,
}

_TEMPLATE_NAME = "cockpit"
_template_registered = False


def cockpit_template() -> Any:
    """Return the Plotly cockpit template, registering it lazily."""
    import plotly.graph_objects as go
    import plotly.io as pio

    global _template_registered
    if _template_registered and _TEMPLATE_NAME in pio.templates:
        return pio.templates[_TEMPLATE_NAME]

    template = go.layout.Template()
    template.layout = go.Layout(
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(family=FONT_FAMILY, color=FG, size=13),
        title=dict(font=dict(color=FG, size=16)),
        xaxis=dict(
            gridcolor=GRID,
            zerolinecolor=GRID,
            linecolor=GRID,
            tickfont=dict(color=MUTED),
            title=dict(font=dict(color=MUTED, size=11)),
        ),
        yaxis=dict(
            gridcolor=GRID,
            zerolinecolor=GRID,
            linecolor=GRID,
            tickfont=dict(color=MUTED),
            title=dict(font=dict(color=MUTED, size=11)),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor=GRID,
            font=dict(color=FG),
        ),
        colorway=[TEAL, GOLD, AMBER, CORAL, "#7AA2F7", "#BB9AF7", MUTED],
        hoverlabel=dict(
            bgcolor=BG,
            bordercolor=GOLD,
            font=dict(color=FG, family=FONT_FAMILY),
        ),
        margin=dict(l=48, r=24, t=48, b=40),
    )
    pio.templates[_TEMPLATE_NAME] = template
    _template_registered = True
    return template
