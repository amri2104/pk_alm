"""Canonical base-case BVG scenario helper."""

from __future__ import annotations

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration import run_bvg_engine
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import NoEntryPolicy
from pk_alm.bvg_liability_engine.reporting import (
    build_summary_trajectory,
    build_validation_report,
)
from pk_alm.bvg_liability_engine.scenarios.bvg_scenario_result import (
    BVGScenarioResult,
)
from pk_alm.scenarios.stage1_baseline import build_default_stage1_portfolio


def build_bvg_base_case_assumptions(
    *,
    start_year: int = 2026,
    horizon_years: int = 12,
    active_interest_rate: float = 0.0176,
    retired_interest_rate: float = 0.0176,
    technical_interest_rate: float = 0.0176,
    economic_interest_rate: float | None = None,
    contribution_multiplier: float = 1.4,
    conversion_rate: float = 0.068,
    retirement_age: int = 65,
    valuation_terminal_age: int = 90,
) -> BVGAssumptions:
    """Build the small deterministic base-case assumption set."""
    economic_rate = (
        technical_interest_rate
        if economic_interest_rate is None
        else economic_interest_rate
    )
    return BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon_years,
        retirement_age=retirement_age,
        valuation_terminal_age=valuation_terminal_age,
        active_crediting_rate=FlatRateCurve(active_interest_rate),
        retired_interest_rate=FlatRateCurve(retired_interest_rate),
        technical_discount_rate=FlatRateCurve(technical_interest_rate),
        economic_discount_rate=FlatRateCurve(economic_rate),
        salary_growth_rate=FlatRateCurve(0.0),
        conversion_rate=FlatRateCurve(conversion_rate),
        turnover_rate=0.0,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=NoEntryPolicy(),
    )


def run_bvg_base_case(
    *,
    scenario_name: str = "bvg_base_case",
    initial_state: BVGPortfolioState | None = None,
    assumptions: BVGAssumptions | None = None,
    include_reports: bool = True,
) -> BVGScenarioResult:
    """Run a canonical base BVG scenario through ``run_bvg_engine``."""
    resolved_state = (
        build_default_stage1_portfolio()
        if initial_state is None
        else initial_state
    )
    resolved_assumptions = (
        build_bvg_base_case_assumptions()
        if assumptions is None
        else assumptions
    )
    engine_result = run_bvg_engine(
        initial_state=resolved_state,
        assumptions=resolved_assumptions,
    )
    summary = build_summary_trajectory(engine_result) if include_reports else None
    validation = build_validation_report(engine_result) if include_reports else None
    return BVGScenarioResult(
        scenario_name=scenario_name,
        assumptions=resolved_assumptions,
        engine_result=engine_result,
        summary=summary,
        validation=validation,
    )


__all__ = ["build_bvg_base_case_assumptions", "run_bvg_base_case"]
