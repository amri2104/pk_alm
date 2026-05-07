"""Small thesis-oriented BVG reporting table composers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions import BVGAssumptions
from pk_alm.bvg_liability_engine.orchestration import BVGEngineResult
from pk_alm.bvg_liability_engine.pension_logic.valuation_runoff import (
    value_portfolio_state_cashflow_runoff,
)
from pk_alm.bvg_liability_engine.reporting.assumption_report import (
    build_assumption_report,
)
from pk_alm.bvg_liability_engine.reporting.summary_trajectory import (
    build_summary_trajectory,
)
from pk_alm.bvg_liability_engine.reporting.validation_report import (
    build_validation_report,
)


def build_bvg_assumptions_table(assumptions: BVGAssumptions) -> pd.DataFrame:
    """Return the assumption table used in BVG thesis exhibits."""
    return build_assumption_report(assumptions)


def build_bvg_summary_trajectory_table(result: BVGEngineResult) -> pd.DataFrame:
    """Return the per-year BVG summary trajectory table."""
    return build_summary_trajectory(result)


def build_bvg_validation_table(result: BVGEngineResult) -> pd.DataFrame:
    """Return the BVG validation checklist table."""
    return build_validation_report(result)


def build_technical_vs_economic_liability_table(
    result: BVGEngineResult,
) -> pd.DataFrame:
    """Return technical/economic retiree-liability runoff PVs by state."""
    if not isinstance(result, BVGEngineResult):
        raise TypeError(
            f"result must be BVGEngineResult, got {type(result).__name__}"
        )
    rows: list[dict[str, object]] = []
    for projection_year, state in enumerate(result.portfolio_states):
        anchor_year = result.assumptions.start_year + projection_year
        runoff = value_portfolio_state_cashflow_runoff(
            state,
            result.assumptions,
            anchor_year=anchor_year,
        )
        rows.append(
            {
                "projection_year": projection_year,
                "calendar_year": anchor_year,
                "technical_pv": runoff.technical_pv,
                "economic_pv": runoff.economic_pv,
                "formula_pv": runoff.formula_pv,
                "economic_minus_technical_pv": (
                    runoff.economic_pv - runoff.technical_pv
                ),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "projection_year",
            "calendar_year",
            "technical_pv",
            "economic_pv",
            "formula_pv",
            "economic_minus_technical_pv",
        ],
    )


def build_bvg_scenario_comparison_table(
    scenarios: (
        Mapping[str, BVGEngineResult]
        | Sequence[tuple[str, BVGEngineResult]]
        | Sequence[object]
    ),
) -> pd.DataFrame:
    """Return one compact comparison row per BVG scenario result."""
    rows: list[dict[str, object]] = []
    for scenario_name, result in _iter_scenarios(scenarios):
        summary = build_summary_trajectory(result)
        validation = build_validation_report(result)
        final_state = result.final_state
        rows.append(
            {
                "scenario_name": scenario_name,
                "horizon_years": result.horizon_years,
                "final_active_count": final_state.active_count_total,
                "final_retired_count": final_state.retired_count_total,
                "final_total_capital": final_state.total_capital,
                "total_net_bvg_cashflow": float(
                    summary["net_bvg_cashflow"].sum()
                ),
                "validation_failures": int(
                    (validation["status"] == "fail").sum()
                ),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "scenario_name",
            "horizon_years",
            "final_active_count",
            "final_retired_count",
            "final_total_capital",
            "total_net_bvg_cashflow",
            "validation_failures",
        ],
    )


def _iter_scenarios(
    scenarios: (
        Mapping[str, BVGEngineResult]
        | Sequence[tuple[str, BVGEngineResult]]
        | Sequence[object]
    ),
) -> tuple[tuple[str, BVGEngineResult], ...]:
    if isinstance(scenarios, Mapping):
        items = tuple(scenarios.items())
    else:
        items = tuple(scenarios)

    resolved: list[tuple[str, BVGEngineResult]] = []
    for idx, item in enumerate(items):
        if isinstance(item, tuple) and len(item) == 2:
            name, result = item
        else:
            name = getattr(item, "scenario_name", getattr(item, "name", f"scenario_{idx}"))
            result = getattr(item, "engine_result", None)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("scenario names must be non-empty strings")
        if not isinstance(result, BVGEngineResult):
            raise TypeError(
                "scenario entries must contain BVGEngineResult values"
            )
        resolved.append((name, result))
    return tuple(resolved)


__all__ = [
    "build_bvg_assumptions_table",
    "build_bvg_scenario_comparison_table",
    "build_bvg_summary_trajectory_table",
    "build_bvg_validation_table",
    "build_technical_vs_economic_liability_table",
]
