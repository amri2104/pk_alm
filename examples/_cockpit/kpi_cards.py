"""Status-aware KPI cards for the cockpit."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Literal

Status = Literal["ok", "warn", "alert", "neutral"]


@dataclass(frozen=True)
class KpiSpec:
    label: str
    value_text: str
    sub_text: str = ""
    status: Status = "neutral"
    help_text: str = ""


def funding_ratio_status(percent: float | None) -> Status:
    """Status using BVG legal floor (100%) and Swiss sustainable range (>=110%)."""
    if percent is None:
        return "neutral"
    if percent >= 110.0:
        return "ok"
    if percent >= 100.0:
        return "neutral"
    if percent >= 90.0:
        return "warn"
    return "alert"


def liquidity_status(inflection_year: int | None, *, current_year: int = 0) -> Status:
    if inflection_year is None:
        return "ok"
    horizon = inflection_year - current_year if current_year else inflection_year
    if horizon > 10:
        return "warn"
    return "alert"


def underfunding_status(probability: float | None) -> Status:
    if probability is None:
        return "neutral"
    if probability < 0.05:
        return "ok"
    if probability < 0.15:
        return "warn"
    return "alert"


def cashflow_status(net: float | None) -> Status:
    if net is None:
        return "neutral"
    if net > 0:
        return "ok"
    if net == 0:
        return "neutral"
    return "warn"


def render_kpi_card(st: Any, spec: KpiSpec) -> None:
    label = html.escape(spec.label)
    value = html.escape(spec.value_text)
    sub = html.escape(spec.sub_text) if spec.sub_text else ""
    status = spec.status if spec.status in ("ok", "warn", "alert", "neutral") else "neutral"
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    card = (
        f'<div class="kpi-card {status}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f"{sub_html}"
        f"</div>"
    )
    st.markdown(card, unsafe_allow_html=True)
    if spec.help_text:
        with st.popover("ⓘ details"):
            st.write(spec.help_text)


def render_kpi_grid(st: Any, specs: list[KpiSpec], cols: int = 4) -> None:
    if not specs:
        return
    columns = st.columns(cols)
    for idx, spec in enumerate(specs):
        with columns[idx % cols]:
            render_kpi_card(st, spec)
