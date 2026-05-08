"""Stage-1 baseline scenario: deterministic end-to-end demo.

Wires together the BVG engine, liability valuation, and annual cashflow
analytics over a small deterministic test/demo portfolio. Optionally exports
CSV outputs to a directory.

This is an integration scenario, not a calibrated pension fund. It introduces
no new financial mathematics.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from pk_alm.actus_asset_engine.contract_config import AALContractConfig
from pk_alm.alm_analytics_engine.cashflows import (
    find_liquidity_inflection_year,
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.alm_analytics_engine.funding import (
    build_funding_ratio_trajectory,
    validate_funding_ratio_dataframe,
)
from pk_alm.alm_analytics_engine.funding_summary import (
    funding_summary_to_dataframe,
    summarize_funding_ratio,
    validate_funding_summary_dataframe,
)
from pk_alm.actus_asset_engine.deterministic import (
    DeterministicAssetSnapshot,
    asset_snapshots_to_dataframe,
    build_deterministic_asset_trajectory,
    validate_asset_dataframe,
)
from pk_alm.actus_asset_engine.aal_engine import run_aal_asset_engine
from pk_alm.actus_asset_engine.actus_trajectory import compute_actus_asset_trajectory
from pk_alm.actus_asset_engine.simulation_settings import AALSimulationSettings
from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration import BVGEngineResult, run_bvg_engine
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import NoEntryPolicy
from pk_alm.bvg_liability_engine.pension_logic.valuation import (
    validate_valuation_dataframe,
    value_portfolio_states,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe
from pk_alm.scenarios.result_summary import (
    build_scenario_result_summary,
    scenario_result_summary_to_dataframe,
    validate_scenario_result_dataframe,
)

AssetMode = Literal["deterministic", "actus"]
ASSET_MODE_DETERMINISTIC = "deterministic"
ASSET_MODE_ACTUS = "actus"
ACTUS_ASSET_TRAJECTORY_FILENAME = "actus_asset_trajectory.csv"
_CASHFLOW_SORT_COLUMNS = ["time", "source", "contractId", "type"]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage1BaselineResult:
    """Frozen container for one Stage-1 baseline scenario run."""

    initial_state: BVGPortfolioState
    engine_result: BVGEngineResult
    cashflows: pd.DataFrame
    valuation_snapshots: pd.DataFrame
    annual_cashflows: pd.DataFrame
    asset_snapshots: pd.DataFrame
    funding_ratio_trajectory: pd.DataFrame
    funding_summary: pd.DataFrame
    scenario_summary: pd.DataFrame
    liquidity_inflection_year_structural: int | None
    liquidity_inflection_year_net: int | None
    output_paths: dict[str, Path]
    actus_asset_trajectory: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.initial_state, BVGPortfolioState):
            raise TypeError(
                f"initial_state must be BVGPortfolioState, "
                f"got {type(self.initial_state).__name__}"
            )
        if not isinstance(self.engine_result, BVGEngineResult):
            raise TypeError(
                f"engine_result must be BVGEngineResult, "
                f"got {type(self.engine_result).__name__}"
            )
        if not isinstance(self.cashflows, pd.DataFrame):
            raise TypeError(
                f"cashflows must be a pandas DataFrame, "
                f"got {type(self.cashflows).__name__}"
            )
        validate_cashflow_dataframe(self.cashflows)
        if not isinstance(self.valuation_snapshots, pd.DataFrame):
            raise TypeError(
                f"valuation_snapshots must be a pandas DataFrame, "
                f"got {type(self.valuation_snapshots).__name__}"
            )
        validate_valuation_dataframe(self.valuation_snapshots)

        if not isinstance(self.annual_cashflows, pd.DataFrame):
            raise TypeError(
                f"annual_cashflows must be a pandas DataFrame, "
                f"got {type(self.annual_cashflows).__name__}"
            )
        validate_annual_cashflow_dataframe(self.annual_cashflows)

        if not isinstance(self.asset_snapshots, pd.DataFrame):
            raise TypeError(
                f"asset_snapshots must be a pandas DataFrame, "
                f"got {type(self.asset_snapshots).__name__}"
            )
        validate_asset_dataframe(self.asset_snapshots)

        if not isinstance(self.funding_ratio_trajectory, pd.DataFrame):
            raise TypeError(
                f"funding_ratio_trajectory must be a pandas DataFrame, "
                f"got {type(self.funding_ratio_trajectory).__name__}"
            )
        validate_funding_ratio_dataframe(self.funding_ratio_trajectory)

        if not isinstance(self.funding_summary, pd.DataFrame):
            raise TypeError(
                f"funding_summary must be a pandas DataFrame, "
                f"got {type(self.funding_summary).__name__}"
            )
        validate_funding_summary_dataframe(self.funding_summary)

        if not isinstance(self.scenario_summary, pd.DataFrame):
            raise TypeError(
                f"scenario_summary must be a pandas DataFrame, "
                f"got {type(self.scenario_summary).__name__}"
            )
        validate_scenario_result_dataframe(self.scenario_summary)

        # bool is a subclass of int → reject before the int check.
        for fname in (
            "liquidity_inflection_year_structural",
            "liquidity_inflection_year_net",
        ):
            value = getattr(self, fname)
            if isinstance(value, bool):
                raise TypeError(f"{fname} must not be bool")
            if value is not None and not isinstance(value, int):
                raise TypeError(
                    f"{fname} must be int or None, got {type(value).__name__}"
                )

        if not isinstance(self.output_paths, dict):
            raise TypeError(
                f"output_paths must be a dict, "
                f"got {type(self.output_paths).__name__}"
            )
        for k, v in self.output_paths.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"output_paths keys must be str, got {type(k).__name__}"
                )
            if not k.strip():
                raise ValueError("output_paths keys must be non-empty strings")
            if not isinstance(v, Path):
                raise TypeError(
                    f"output_paths[{k!r}] must be Path, got {type(v).__name__}"
                )
        if self.actus_asset_trajectory is not None and not isinstance(
            self.actus_asset_trajectory, pd.DataFrame
        ):
            raise TypeError("actus_asset_trajectory must be DataFrame or None")


# ---------------------------------------------------------------------------
# Default portfolio
# ---------------------------------------------------------------------------


def build_default_stage1_portfolio() -> BVGPortfolioState:
    """Construct the deterministic Stage-1 demo portfolio.

    This is intentionally small and manually inspectable; it is a test/demo
    portfolio, not a calibration to any real pension fund.
    """
    act_40 = ActiveCohort(
        cohort_id="ACT_40",
        age=40,
        count=10,
        gross_salary_per_person=85000,
        capital_active_per_person=120000,
    )
    act_55 = ActiveCohort(
        cohort_id="ACT_55",
        age=55,
        count=3,
        gross_salary_per_person=60000,
        capital_active_per_person=300000,
    )
    ret_70 = RetiredCohort(
        cohort_id="RET_70",
        age=70,
        count=5,
        annual_pension_per_person=30000,
        capital_rente_per_person=450000,
    )
    return BVGPortfolioState(
        projection_year=0,
        active_cohorts=(act_40, act_55),
        retired_cohorts=(ret_70,),
    )


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------


def _validate_asset_mode(asset_mode: str) -> AssetMode:
    if asset_mode not in (ASSET_MODE_DETERMINISTIC, ASSET_MODE_ACTUS):
        raise ValueError("asset_mode must be 'deterministic' or 'actus'")
    return asset_mode  # type: ignore[return-value]


def _resolve_output_dir(
    *,
    asset_mode: AssetMode,
    output_dir: str | Path | None,
    deterministic_default: str,
    actus_default: str,
) -> str | Path | None:
    if output_dir is None:
        return None
    if (
        asset_mode == ASSET_MODE_ACTUS
        and str(output_dir) == deterministic_default
    ):
        return actus_default
    return output_dir


def _filter_cashflows_to_projection_window(
    cashflows: pd.DataFrame,
    *,
    start_year: int,
    horizon_years: int,
) -> pd.DataFrame:
    if cashflows.empty:
        return cashflows.copy(deep=True)
    end_year = start_year + horizon_years - 1
    years = pd.to_datetime(cashflows["time"]).dt.year.astype(int)
    filtered = cashflows.loc[
        (years >= start_year) & (years <= end_year)
    ].copy(deep=True)
    return filtered.reset_index(drop=True)


def _combine_cashflows(
    liability_cashflows: pd.DataFrame,
    asset_cashflows: pd.DataFrame,
    *,
    start_year: int,
    horizon_years: int,
) -> pd.DataFrame:
    filtered_asset_cashflows = _filter_cashflows_to_projection_window(
        asset_cashflows,
        start_year=start_year,
        horizon_years=horizon_years,
    )
    combined = pd.concat(
        [liability_cashflows, filtered_asset_cashflows],
        ignore_index=True,
    )
    if not combined.empty:
        combined = combined.sort_values(_CASHFLOW_SORT_COLUMNS, ignore_index=True)
    validate_cashflow_dataframe(combined)
    return combined


def _liability_net_cashflow_by_projection_year(
    liability_cashflows: pd.DataFrame,
    *,
    start_year: int,
    horizon_years: int,
) -> dict[int, float]:
    if horizon_years == 0:
        return {}
    annual_liability = summarize_cashflows_by_year(liability_cashflows)
    return {
        projection_year: float(
            annual_liability.loc[
                annual_liability["reporting_year"] == start_year + projection_year - 1,
                "net_cashflow",
            ].sum()
        )
        for projection_year in range(1, horizon_years + 1)
    }


def _asset_snapshots_from_actus_trajectory(
    actus_asset_trajectory: pd.DataFrame,
    liability_cashflows: pd.DataFrame,
    *,
    start_year: int,
    horizon_years: int,
    currency: str = "CHF",
) -> pd.DataFrame:
    liability_net = _liability_net_cashflow_by_projection_year(
        liability_cashflows,
        start_year=start_year,
        horizon_years=horizon_years,
    )
    bvg_cumulative = 0.0
    closing_values: list[float] = []
    for projection_year in range(horizon_years + 1):
        if projection_year > 0:
            bvg_cumulative += liability_net.get(projection_year, 0.0)
        base_closing = float(
            actus_asset_trajectory.iloc[projection_year]["closing_asset_value"]
        )
        closing_values.append(base_closing + bvg_cumulative)

    snapshots = [
        DeterministicAssetSnapshot(
            projection_year=0,
            opening_asset_value=closing_values[0],
            investment_return=0.0,
            net_cashflow=0.0,
            closing_asset_value=closing_values[0],
            annual_return_rate=0.0,
            currency=currency,
        )
    ]
    for projection_year in range(1, horizon_years + 1):
        opening = closing_values[projection_year - 1]
        closing = closing_values[projection_year]
        snapshots.append(
            DeterministicAssetSnapshot(
                projection_year=projection_year,
                opening_asset_value=opening,
                investment_return=0.0,
                net_cashflow=closing - opening,
                closing_asset_value=closing,
                annual_return_rate=0.0,
                currency=currency,
            )
        )
    df = asset_snapshots_to_dataframe(snapshots)
    validate_asset_dataframe(df)
    return df


def _build_actus_mode_outputs(
    *,
    valuation_snapshots: pd.DataFrame,
    liability_cashflows: pd.DataFrame,
    asset_contracts: tuple[AALContractConfig, ...] | list[AALContractConfig] | None,
    target_funding_ratio: float,
    start_year: int,
    horizon_years: int,
    initial_liability: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    asset_settings = AALSimulationSettings(
        analysis_date=f"{start_year}-01-01T00:00:00",
        event_start_date=f"{start_year}-01-01T00:00:00",
        event_end_date=f"{start_year + horizon_years}-12-31T00:00:00",
        mode="validated",
        cashflow_cutoff_mode="from_status_date",
    )
    asset_result = run_aal_asset_engine(
        contracts=asset_contracts,
        settings=asset_settings,
    )
    liability_for_calibration = (
        float(valuation_snapshots.iloc[0]["total_stage1_liability"])
        if initial_liability is None
        else float(initial_liability)
    )
    target_assets = liability_for_calibration * target_funding_ratio
    zero_cash_trajectory = compute_actus_asset_trajectory(
        asset_result.contracts,
        asset_result.cashflows,
        horizon_years,
        initial_cash=0.0,
    )
    initial_cash = target_assets - float(
        zero_cash_trajectory.iloc[0]["closing_asset_value"]
    )
    actus_asset_trajectory = compute_actus_asset_trajectory(
        asset_result.contracts,
        asset_result.cashflows,
        horizon_years,
        initial_cash=initial_cash,
    )
    combined_cashflows = _combine_cashflows(
        liability_cashflows,
        asset_result.cashflows,
        start_year=start_year,
        horizon_years=horizon_years,
    )
    annual_cashflows = summarize_cashflows_by_year(combined_cashflows)
    validate_annual_cashflow_dataframe(annual_cashflows)
    asset_snapshots = _asset_snapshots_from_actus_trajectory(
        actus_asset_trajectory,
        liability_cashflows,
        start_year=start_year,
        horizon_years=horizon_years,
    )
    return (
        combined_cashflows,
        annual_cashflows,
        asset_snapshots,
        actus_asset_trajectory,
    )


def run_stage1_baseline(
    *,
    scenario_id: str = "stage1_baseline",
    horizon_years: int = 12,
    start_year: int = 2026,
    active_interest_rate: float = 0.0176,
    retired_interest_rate: float = 0.0176,
    technical_interest_rate: float = 0.0176,
    contribution_multiplier: float = 1.4,
    retirement_age: int = 65,
    capital_withdrawal_fraction: float = 0.35,
    conversion_rate: float = 0.068,
    valuation_terminal_age: int = 90,
    target_funding_ratio: float = 1.076,
    annual_asset_return: float = 0.0,
    asset_mode: AssetMode = ASSET_MODE_DETERMINISTIC,
    asset_contracts: tuple[AALContractConfig, ...] | list[AALContractConfig] | None = None,
    output_dir: str | Path | None = "outputs/stage1_baseline",
) -> Stage1BaselineResult:
    """Run the Stage-1 baseline scenario end-to-end and optionally export CSVs."""
    resolved_asset_mode = _validate_asset_mode(asset_mode)
    output_dir = _resolve_output_dir(
        asset_mode=resolved_asset_mode,
        output_dir=output_dir,
        deterministic_default="outputs/stage1_baseline",
        actus_default="outputs/stage1_actus",
    )
    initial_state = build_default_stage1_portfolio()

    assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon_years,
        retirement_age=retirement_age,
        valuation_terminal_age=valuation_terminal_age,
        active_crediting_rate=FlatRateCurve(active_interest_rate),
        retired_interest_rate=FlatRateCurve(retired_interest_rate),
        technical_discount_rate=FlatRateCurve(technical_interest_rate),
        economic_discount_rate=FlatRateCurve(technical_interest_rate),
        salary_growth_rate=FlatRateCurve(0.0),
        conversion_rate=FlatRateCurve(conversion_rate),
        turnover_rate=0.0,
        capital_withdrawal_fraction=capital_withdrawal_fraction,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=NoEntryPolicy(),
    )
    engine_result = run_bvg_engine(
        initial_state=initial_state, assumptions=assumptions
    )
    validate_cashflow_dataframe(engine_result.cashflows)

    valuation_snapshots = value_portfolio_states(
        engine_result.portfolio_states,
        technical_interest_rate,
        valuation_terminal_age,
    )
    validate_valuation_dataframe(valuation_snapshots)

    if resolved_asset_mode == ASSET_MODE_DETERMINISTIC:
        cashflows = engine_result.cashflows.copy(deep=True)
        annual_cashflows = summarize_cashflows_by_year(cashflows)
        validate_annual_cashflow_dataframe(annual_cashflows)
        asset_snapshots = build_deterministic_asset_trajectory(
            valuation_snapshots,
            annual_cashflows,
            target_funding_ratio=target_funding_ratio,
            annual_return_rate=annual_asset_return,
            start_year=start_year,
        )
        actus_asset_trajectory = None
    else:
        (
            cashflows,
            annual_cashflows,
            asset_snapshots,
            actus_asset_trajectory,
        ) = _build_actus_mode_outputs(
            valuation_snapshots=valuation_snapshots,
            liability_cashflows=engine_result.cashflows,
            asset_contracts=asset_contracts,
            target_funding_ratio=target_funding_ratio,
            start_year=start_year,
            horizon_years=horizon_years,
        )
    validate_asset_dataframe(asset_snapshots)

    funding_ratio_trajectory = build_funding_ratio_trajectory(
        asset_snapshots,
        valuation_snapshots,
    )
    validate_funding_ratio_dataframe(funding_ratio_trajectory)

    funding_summary_obj = summarize_funding_ratio(
        funding_ratio_trajectory,
        target_funding_ratio=target_funding_ratio,
    )
    funding_summary = funding_summary_to_dataframe(funding_summary_obj)
    validate_funding_summary_dataframe(funding_summary)

    inflection_structural = find_liquidity_inflection_year(
        annual_cashflows, use_structural=True
    )
    inflection_net = find_liquidity_inflection_year(
        annual_cashflows, use_structural=False
    )

    scenario_summary_obj = build_scenario_result_summary(
        scenario_id=scenario_id,
        valuation_snapshots=valuation_snapshots,
        annual_cashflows=annual_cashflows,
        asset_snapshots=asset_snapshots,
        funding_ratio_trajectory=funding_ratio_trajectory,
        funding_summary=funding_summary,
        liquidity_inflection_year_structural=inflection_structural,
        liquidity_inflection_year_net=inflection_net,
    )
    scenario_summary = scenario_result_summary_to_dataframe(scenario_summary_obj)
    validate_scenario_result_dataframe(scenario_summary)

    output_paths: dict[str, Path] = {}
    if output_dir is not None:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        cashflows_path = out_path / "cashflows.csv"
        valuation_path = out_path / "valuation_snapshots.csv"
        annual_path = out_path / "annual_cashflows.csv"
        asset_path = out_path / "asset_snapshots.csv"
        funding_path = out_path / "funding_ratio_trajectory.csv"
        funding_summary_path = out_path / "funding_summary.csv"
        scenario_summary_path = out_path / "scenario_summary.csv"

        engine_result.cashflows.to_csv(cashflows_path, index=False)
        if resolved_asset_mode == ASSET_MODE_ACTUS:
            cashflows.to_csv(cashflows_path, index=False)
        valuation_snapshots.to_csv(valuation_path, index=False)
        annual_cashflows.to_csv(annual_path, index=False)
        asset_snapshots.to_csv(asset_path, index=False)
        funding_ratio_trajectory.to_csv(funding_path, index=False)
        funding_summary.to_csv(funding_summary_path, index=False)
        scenario_summary.to_csv(scenario_summary_path, index=False)

        output_paths = {
            "cashflows": cashflows_path,
            "valuation_snapshots": valuation_path,
            "annual_cashflows": annual_path,
            "asset_snapshots": asset_path,
            "funding_ratio_trajectory": funding_path,
            "funding_summary": funding_summary_path,
            "scenario_summary": scenario_summary_path,
        }
        if actus_asset_trajectory is not None:
            actus_path = out_path / ACTUS_ASSET_TRAJECTORY_FILENAME
            actus_asset_trajectory.to_csv(actus_path, index=False)
            output_paths["actus_asset_trajectory"] = actus_path

    return Stage1BaselineResult(
        initial_state=initial_state,
        engine_result=engine_result,
        cashflows=cashflows,
        valuation_snapshots=valuation_snapshots,
        annual_cashflows=annual_cashflows,
        asset_snapshots=asset_snapshots,
        funding_ratio_trajectory=funding_ratio_trajectory,
        funding_summary=funding_summary,
        scenario_summary=scenario_summary,
        liquidity_inflection_year_structural=inflection_structural,
        liquidity_inflection_year_net=inflection_net,
        output_paths=output_paths,
        actus_asset_trajectory=actus_asset_trajectory,
    )
