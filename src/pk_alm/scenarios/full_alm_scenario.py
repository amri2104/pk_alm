"""Full ALM scenario combining BVG liability and AAL/ACTUS asset cashflows.

This scenario glues the two engines:

- BVG Liability Engine via the canonical assumptions-driven engine.
- AAL Asset Engine via :func:`run_aal_asset_engine`.

It delegates all cross-engine aggregation to the canonical
``run_alm_analytics`` orchestrator. The default asset path is the required
live AAL strategic engine.

The scenario does not modify ``run_stage1_baseline(...)`` or the seven
default Stage-1 CSV outputs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.actus_asset_engine.contract_config import AALContractConfig
from pk_alm.alm_analytics_engine.analytics_input import ALMAnalyticsInput
from pk_alm.alm_analytics_engine.analytics_result import ALMAnalyticsResult
from pk_alm.alm_analytics_engine.cashflows import (
    find_liquidity_inflection_year,
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.alm_analytics_engine.funding import build_funding_ratio_trajectory
from pk_alm.alm_analytics_engine.funding_summary import (
    funding_summary_to_dataframe,
    summarize_funding_ratio,
)
from pk_alm.alm_analytics_engine.engine import run_alm_analytics
from pk_alm.actus_asset_engine.aal_engine import (
    AALAssetEngineResult,
    run_aal_asset_engine,
)
from pk_alm.actus_asset_engine.deterministic import build_deterministic_asset_trajectory
from pk_alm.actus_asset_engine.simulation_settings import AALSimulationSettings
from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.orchestration import run_bvg_engine
from pk_alm.bvg_liability_engine.pension_logic.valuation import value_portfolio_states
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import NoEntryPolicy
from pk_alm.cashflows.schema import validate_cashflow_dataframe
from pk_alm.scenarios.result_summary import (
    build_scenario_result_summary,
    scenario_result_summary_to_dataframe,
)
from pk_alm.scenarios.stage1_baseline import (
    Stage1BaselineResult,
    build_default_stage1_portfolio,
)


@dataclass(frozen=True)
class FullALMScenarioResult:
    """Result container for one Full ALM scenario run."""

    stage1_result: Stage1BaselineResult
    aal_asset_result: AALAssetEngineResult
    alm_analytics_result: ALMAnalyticsResult
    generation_mode: str = "aal"

    def __post_init__(self) -> None:
        if not isinstance(self.stage1_result, Stage1BaselineResult):
            raise TypeError(
                f"stage1_result must be Stage1BaselineResult, "
                f"got {type(self.stage1_result).__name__}"
            )
        if not isinstance(self.aal_asset_result, AALAssetEngineResult):
            raise TypeError(
                f"aal_asset_result must be AALAssetEngineResult, "
                f"got {type(self.aal_asset_result).__name__}"
            )
        if not isinstance(self.alm_analytics_result, ALMAnalyticsResult):
            raise TypeError(
                "alm_analytics_result must be ALMAnalyticsResult, got "
                f"{type(self.alm_analytics_result).__name__}"
            )
        if not self.asset_cashflows.empty and not (
            self.asset_cashflows["source"] == "ACTUS"
        ).all():
            raise ValueError('asset_cashflows source values must all be "ACTUS"')
        if self.generation_mode != "aal":
            raise ValueError('generation_mode is fixed to "aal"')
        if self.aal_asset_result.generation_mode != "aal":
            raise ValueError(
                'aal_asset_result.generation_mode must be fixed to "aal"'
            )

    @property
    def bvg_cashflows(self) -> pd.DataFrame:
        return self.alm_analytics_result.inputs.bvg_cashflows

    @property
    def asset_cashflows(self) -> pd.DataFrame:
        return self.alm_analytics_result.inputs.asset_cashflows

    @property
    def combined_cashflows(self) -> pd.DataFrame:
        return self.alm_analytics_result.combined_cashflows

    @property
    def annual_cashflows(self) -> pd.DataFrame:
        return self.alm_analytics_result.annual_cashflows

    @property
    def funding_ratio_trajectory(self) -> pd.DataFrame:
        return self.alm_analytics_result.funding_ratio_trajectory

    @property
    def funding_summary(self) -> pd.DataFrame:
        return self.alm_analytics_result.funding_summary

    @property
    def kpi_summary(self) -> pd.DataFrame:
        return self.alm_analytics_result.kpi_summary

    @property
    def analytics_result(self) -> ALMAnalyticsResult:
        return self.alm_analytics_result


def run_full_alm_scenario(
    *,
    scenario_id: str = "full_alm_scenario",
    horizon_years: int = 12,
    start_year: int = 2026,
    contribution_multiplier: float = 1.4,
    active_interest_rate: float = 0.0176,
    retired_interest_rate: float = 0.0176,
    technical_interest_rate: float = 0.0176,
    valuation_terminal_age: int = 90,
    target_funding_ratio: float = 1.076,
    annual_asset_return: float = 0.0,
    conversion_rate: float = 0.068,
    capital_withdrawal_fraction: float = 0.35,
    turnover_rate: float = 0.0,
    salary_growth_rate: float = 0.0,
    asset_contracts: tuple[AALContractConfig, ...] | list[AALContractConfig] | None = None,
) -> FullALMScenarioResult:
    """Run the BVG liability engine and the AAL Asset Engine and combine results.

    Asset-side ACTUS cashflows are generated through the required live AAL
    path. There is no fixture cashflow path.
    """
    initial_state = build_default_stage1_portfolio()
    assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon_years,
        retirement_age=65,
        valuation_terminal_age=valuation_terminal_age,
        active_crediting_rate=FlatRateCurve(active_interest_rate),
        retired_interest_rate=FlatRateCurve(retired_interest_rate),
        technical_discount_rate=FlatRateCurve(technical_interest_rate),
        economic_discount_rate=FlatRateCurve(technical_interest_rate),
        salary_growth_rate=FlatRateCurve(salary_growth_rate),
        conversion_rate=FlatRateCurve(conversion_rate),
        turnover_rate=turnover_rate,
        capital_withdrawal_fraction=capital_withdrawal_fraction,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=NoEntryPolicy(),
    )
    engine_result = run_bvg_engine(
        initial_state=initial_state,
        assumptions=assumptions,
    )
    validate_cashflow_dataframe(engine_result.cashflows)

    valuation_snapshots = value_portfolio_states(
        engine_result.portfolio_states,
        technical_interest_rate,
        valuation_terminal_age,
    )
    bvg_annual_cashflows = summarize_cashflows_by_year(engine_result.cashflows)
    validate_annual_cashflow_dataframe(bvg_annual_cashflows)
    asset_snapshots = build_deterministic_asset_trajectory(
        valuation_snapshots,
        bvg_annual_cashflows,
        target_funding_ratio=target_funding_ratio,
        annual_return_rate=annual_asset_return,
        start_year=start_year,
    )
    funding_ratio_trajectory = build_funding_ratio_trajectory(
        asset_snapshots,
        valuation_snapshots,
    )
    funding_summary_obj = summarize_funding_ratio(
        funding_ratio_trajectory,
        target_funding_ratio=target_funding_ratio,
    )
    funding_summary = funding_summary_to_dataframe(funding_summary_obj)
    inflection_structural = find_liquidity_inflection_year(
        bvg_annual_cashflows,
        use_structural=True,
    )
    inflection_net = find_liquidity_inflection_year(
        bvg_annual_cashflows,
        use_structural=False,
    )
    scenario_summary_obj = build_scenario_result_summary(
        scenario_id=scenario_id,
        valuation_snapshots=valuation_snapshots,
        annual_cashflows=bvg_annual_cashflows,
        asset_snapshots=asset_snapshots,
        funding_ratio_trajectory=funding_ratio_trajectory,
        funding_summary=funding_summary,
        liquidity_inflection_year_structural=inflection_structural,
        liquidity_inflection_year_net=inflection_net,
    )
    scenario_summary = scenario_result_summary_to_dataframe(scenario_summary_obj)
    stage1_result = Stage1BaselineResult(
        initial_state=initial_state,
        engine_result=engine_result,
        cashflows=engine_result.cashflows.copy(deep=True),
        valuation_snapshots=valuation_snapshots,
        annual_cashflows=bvg_annual_cashflows,
        asset_snapshots=asset_snapshots,
        funding_ratio_trajectory=funding_ratio_trajectory,
        funding_summary=funding_summary,
        scenario_summary=scenario_summary,
        liquidity_inflection_year_structural=inflection_structural,
        liquidity_inflection_year_net=inflection_net,
        output_paths={},
        actus_asset_trajectory=None,
    )

    aal_asset_result = run_aal_asset_engine(
        contracts=asset_contracts,
        settings=AALSimulationSettings(
            analysis_date=f"{start_year}-01-01T00:00:00",
            event_start_date=f"{start_year}-01-01T00:00:00",
            event_end_date=f"{start_year + horizon_years}-12-31T00:00:00",
            mode="validated",
            cashflow_cutoff_mode="from_status_date",
        ),
    )

    bvg_cashflows = stage1_result.engine_result.cashflows
    asset_cashflows = aal_asset_result.cashflows

    alm_analytics_result = run_alm_analytics(
        ALMAnalyticsInput(
            bvg_cashflows=bvg_cashflows,
            asset_cashflows=asset_cashflows,
            asset_snapshots=asset_snapshots,
            valuation_snapshots=valuation_snapshots,
            scenario_name=scenario_id,
            target_funding_ratio=target_funding_ratio,
            currency="CHF",
        )
    )

    return FullALMScenarioResult(
        stage1_result=stage1_result,
        aal_asset_result=aal_asset_result,
        alm_analytics_result=alm_analytics_result,
    )
