"""Full ALM scenario combining BVG liability and AAL/ACTUS asset cashflows.

This scenario glues the two engines:

- BVG Liability Engine via the canonical assumptions-driven engine.
- AAL Asset Engine via :func:`run_aal_asset_engine`.

It concatenates both cashflow streams in the canonical CashflowRecord schema
and recomputes annual cashflow analytics on the combined view. The default
asset path is the required live AAL strategic engine.

The scenario does not modify ``run_stage1_baseline(...)`` or the seven
default Stage-1 CSV outputs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.actus_asset_engine.contract_config import AALContractConfig
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

_COMBINED_SORT_COLUMNS = ("time", "source", "contractId", "type")


@dataclass(frozen=True)
class FullALMScenarioResult:
    """Result container for one Full ALM scenario run."""

    stage1_result: Stage1BaselineResult
    aal_asset_result: AALAssetEngineResult
    bvg_cashflows: pd.DataFrame
    asset_cashflows: pd.DataFrame
    combined_cashflows: pd.DataFrame
    annual_cashflows: pd.DataFrame
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

        for fname in ("bvg_cashflows", "asset_cashflows", "combined_cashflows"):
            value = getattr(self, fname)
            if not isinstance(value, pd.DataFrame):
                raise TypeError(
                    f"{fname} must be a pandas DataFrame, "
                    f"got {type(value).__name__}"
                )
            validate_cashflow_dataframe(value)

        if not self.asset_cashflows.empty and not (
            self.asset_cashflows["source"] == "ACTUS"
        ).all():
            raise ValueError('asset_cashflows source values must all be "ACTUS"')

        expected_rows = len(self.bvg_cashflows) + len(self.asset_cashflows)
        if len(self.combined_cashflows) != expected_rows:
            raise ValueError(
                "combined_cashflows must have exactly "
                "len(bvg_cashflows) + len(asset_cashflows) rows "
                f"({len(self.combined_cashflows)} != {expected_rows})"
            )

        if not isinstance(self.annual_cashflows, pd.DataFrame):
            raise TypeError(
                f"annual_cashflows must be a pandas DataFrame, "
                f"got {type(self.annual_cashflows).__name__}"
            )
        validate_annual_cashflow_dataframe(self.annual_cashflows)

        if self.generation_mode != "aal":
            raise ValueError('generation_mode is fixed to "aal"')
        if self.aal_asset_result.generation_mode != "aal":
            raise ValueError(
                'aal_asset_result.generation_mode must be fixed to "aal"'
            )


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
        salary_growth_rate=FlatRateCurve(0.0),
        conversion_rate=FlatRateCurve(0.068),
        turnover_rate=0.0,
        capital_withdrawal_fraction=0.35,
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

    combined_cashflows = pd.concat(
        [bvg_cashflows, asset_cashflows],
        ignore_index=True,
    )
    combined_cashflows = combined_cashflows.sort_values(
        list(_COMBINED_SORT_COLUMNS),
        ignore_index=True,
    )
    validate_cashflow_dataframe(combined_cashflows)

    annual_cashflows = summarize_cashflows_by_year(combined_cashflows)
    validate_annual_cashflow_dataframe(annual_cashflows)

    return FullALMScenarioResult(
        stage1_result=stage1_result,
        aal_asset_result=aal_asset_result,
        bvg_cashflows=bvg_cashflows,
        asset_cashflows=asset_cashflows,
        combined_cashflows=combined_cashflows,
        annual_cashflows=annual_cashflows,
    )
