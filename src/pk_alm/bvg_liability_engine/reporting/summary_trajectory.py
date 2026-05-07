"""Per-year aggregate summary from a :class:`BVGEngineResult`."""

from __future__ import annotations

import pandas as pd

from pk_alm.bvg_liability_engine.orchestration.result import BVGEngineResult
from pk_alm.cashflows.event_types import EX, IN, KA, PR, RP


_FLOW_COLUMNS = (
    ("annual_PR", PR),
    ("annual_RP", RP),
    ("annual_KA", KA),
    ("annual_EX", EX),
    ("annual_IN", IN),
)


def build_summary_trajectory(result: BVGEngineResult) -> pd.DataFrame:
    """Return one row per closing portfolio state with aggregate metrics."""
    if not isinstance(result, BVGEngineResult):
        raise TypeError(
            f"result must be BVGEngineResult, got {type(result).__name__}"
        )
    cashflows = result.cashflows.copy()
    if not cashflows.empty:
        cashflows["year"] = pd.to_datetime(cashflows["time"]).dt.year

    rows: list[dict[str, object]] = []
    for projection_year, state in enumerate(result.portfolio_states):
        calendar_year = result.assumptions.start_year + max(0, projection_year - 1)
        if projection_year == 0:
            calendar_year = result.assumptions.start_year - 1

        flows: dict[str, float] = {}
        if not cashflows.empty and projection_year > 0:
            year_mask = cashflows["year"] == result.assumptions.start_year + projection_year - 1
            year_df = cashflows[year_mask]
            for col, ev in _FLOW_COLUMNS:
                flows[col] = float(year_df.loc[year_df["type"] == ev, "payoff"].sum())
        else:
            for col, _ in _FLOW_COLUMNS:
                flows[col] = 0.0
        flows["net_bvg_cashflow"] = sum(flows.values())

        rows.append(
            {
                "projection_year": projection_year,
                "calendar_year": calendar_year,
                "active_count_total": state.active_count_total,
                "retired_count_total": state.retired_count_total,
                "member_count_total": state.member_count_total,
                "total_capital_active": state.total_capital_active,
                "total_capital_rente": state.total_capital_rente,
                "total_capital": state.total_capital,
                **flows,
            }
        )
    return pd.DataFrame(rows)
