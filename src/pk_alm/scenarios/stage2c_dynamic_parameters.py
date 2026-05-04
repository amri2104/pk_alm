"""Stage 2C dynamic-parameter scenario.

Stage 2C is parallel to Stage 2A. It keeps the population layer unchanged and
adds deterministic time-varying paths for UWS, BVG minimum interest, and the
technical discount rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from pk_alm.actus_asset_engine.aal_asset_portfolio import AssetSpec
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
    build_deterministic_asset_trajectory,
    validate_asset_dataframe,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.actuarial_assumptions.dynamic_parameters import DynamicParameter, expand_parameter
from pk_alm.bvg_liability_engine.orchestration.engine_stage2c import Stage2CEngineResult, run_bvg_engine_stage2c
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import EntryAssumptions
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.valuation import validate_valuation_dataframe
from pk_alm.bvg_liability_engine.pension_logic.valuation_dynamic import value_portfolio_states_dynamic
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

STAGE2C_OUTPUT_FILENAMES: tuple[str, ...] = (
    "cashflows.csv",
    "valuation_snapshots.csv",
    "annual_cashflows.csv",
    "asset_snapshots.csv",
    "funding_ratio_trajectory.csv",
    "funding_summary.csv",
    "scenario_summary.csv",
    "demographic_summary.csv",
    "cashflows_by_type.csv",
    "parameter_trajectory.csv",
)

STAGE2C_ACTUS_OUTPUT_FILENAMES: tuple[str, ...] = (
    *STAGE2C_OUTPUT_FILENAMES,
    ACTUS_ASSET_TRAJECTORY_FILENAME,
)

DEMOGRAPHIC_SUMMARY_COLUMNS = (
    "projection_year",
    "entries",
    "exits",
    "retirements",
    "turnover_residual",
    "active_count_end",
    "retired_count_end",
)

CASHFLOWS_BY_TYPE_COLUMNS = (
    "reporting_year",
    "type",
    "total_payoff",
)

PARAMETER_TRAJECTORY_COLUMNS = (
    "projection_year",
    "conversion_rate",
    "active_interest_rate",
    "technical_interest_rate",
)


@dataclass(frozen=True)
class Stage2CResult:
    """Frozen result container for one Stage-2C dynamic-parameter run."""

    scenario_id: str
    engine_result: Stage2CEngineResult
    cashflows: pd.DataFrame
    valuation_snapshots: pd.DataFrame
    annual_cashflows: pd.DataFrame
    asset_snapshots: pd.DataFrame
    funding_ratio_trajectory: pd.DataFrame
    funding_summary: pd.DataFrame
    scenario_summary: pd.DataFrame
    demographic_summary: pd.DataFrame
    cashflows_by_type: pd.DataFrame
    parameter_trajectory: pd.DataFrame
    output_dir: Path | None
    actus_asset_trajectory: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        if not isinstance(self.engine_result, Stage2CEngineResult):
            raise TypeError("engine_result must be Stage2CEngineResult")
        validate_cashflow_dataframe(self.cashflows)
        validate_valuation_dataframe(self.valuation_snapshots)
        validate_annual_cashflow_dataframe(self.annual_cashflows)
        validate_asset_dataframe(self.asset_snapshots)
        validate_funding_ratio_dataframe(self.funding_ratio_trajectory)
        validate_funding_summary_dataframe(self.funding_summary)
        validate_scenario_result_dataframe(self.scenario_summary)
        _validate_demographic_summary(self.demographic_summary)
        _validate_cashflows_by_type(self.cashflows_by_type)
        _validate_parameter_trajectory(self.parameter_trajectory)
        if self.output_dir is not None and not isinstance(self.output_dir, Path):
            raise TypeError("output_dir must be Path or None")
        if self.actus_asset_trajectory is not None and not isinstance(
            self.actus_asset_trajectory, pd.DataFrame
        ):
            raise TypeError("actus_asset_trajectory must be DataFrame or None")


def build_default_initial_portfolio_stage2c() -> BVGPortfolioState:
    """Return the Stage-2C default portfolio, matching the Stage-1 demo."""
    return BVGPortfolioState(
        projection_year=0,
        active_cohorts=(
            ActiveCohort(
                cohort_id="ACT_40",
                age=40,
                count=10,
                gross_salary_per_person=85_000.0,
                capital_active_per_person=120_000.0,
            ),
            ActiveCohort(
                cohort_id="ACT_55",
                age=55,
                count=3,
                gross_salary_per_person=60_000.0,
                capital_active_per_person=300_000.0,
            ),
        ),
        retired_cohorts=(
            RetiredCohort(
                cohort_id="RET_70",
                age=70,
                count=5,
                annual_pension_per_person=30_000.0,
                capital_rente_per_person=450_000.0,
            ),
        ),
    )


def run_stage2c_dynamic_parameters(
    scenario_id: str = "stage2c_dynamic_parameters",
    horizon_years: int = 12,
    start_year: int = 2026,
    active_interest_rate: DynamicParameter = 0.0176,
    retired_interest_rate: float = 0.0176,
    technical_interest_rate: DynamicParameter = 0.0176,
    contribution_multiplier: float = 1.4,
    valuation_terminal_age: int = 90,
    target_funding_ratio: float = 1.076,
    annual_asset_return: float = 0.0,
    salary_growth_rate: float = 0.015,
    turnover_rate: float = 0.02,
    entry_assumptions: EntryAssumptions | None = None,
    conversion_rate: DynamicParameter = 0.068,
    asset_mode: AssetMode = ASSET_MODE_DETERMINISTIC,
    asset_specs: tuple[AssetSpec, ...] | list[AssetSpec] | None = None,
    output_dir: str | Path | None = "outputs/stage2c_dynamic_parameters",
) -> Stage2CResult:
    """Run the Stage-2C dynamic-parameter scenario end to end."""
    resolved_asset_mode = _validate_asset_mode(asset_mode)
    output_dir = _resolve_output_dir(
        asset_mode=resolved_asset_mode,
        output_dir=output_dir,
        deterministic_default="outputs/stage2c_dynamic_parameters",
        actus_default="outputs/stage2c_actus",
    )
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ValueError("scenario_id must be a non-empty string")

    initial_state = build_default_initial_portfolio_stage2c()
    engine_result = run_bvg_engine_stage2c(
        initial_state=initial_state,
        horizon_years=horizon_years,
        active_interest_rate=active_interest_rate,
        retired_interest_rate=retired_interest_rate,
        salary_growth_rate=salary_growth_rate,
        turnover_rate=turnover_rate,
        entry_assumptions=entry_assumptions,
        contribution_multiplier=contribution_multiplier,
        start_year=start_year,
        conversion_rate=conversion_rate,
    )
    validate_cashflow_dataframe(engine_result.cashflows)

    valuation_snapshots = value_portfolio_states_dynamic(
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
            asset_specs=asset_specs,
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

    demographic_summary = _build_demographic_summary(engine_result)
    cashflows_by_type = _build_cashflows_by_type(cashflows)
    parameter_trajectory = _build_parameter_trajectory(
        horizon_years=engine_result.horizon_years,
        conversion_rate=conversion_rate,
        active_interest_rate=active_interest_rate,
        technical_interest_rate=technical_interest_rate,
    )

    resolved_output_dir: Path | None = None
    if output_dir is not None:
        resolved_output_dir = Path(output_dir)
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        outputs = {
            "cashflows.csv": cashflows,
            "valuation_snapshots.csv": valuation_snapshots,
            "annual_cashflows.csv": annual_cashflows,
            "asset_snapshots.csv": asset_snapshots,
            "funding_ratio_trajectory.csv": funding_ratio_trajectory,
            "funding_summary.csv": funding_summary,
            "scenario_summary.csv": scenario_summary,
            "demographic_summary.csv": demographic_summary,
            "cashflows_by_type.csv": cashflows_by_type,
            "parameter_trajectory.csv": parameter_trajectory,
        }
        if actus_asset_trajectory is not None:
            outputs[ACTUS_ASSET_TRAJECTORY_FILENAME] = actus_asset_trajectory
        filenames = (
            STAGE2C_ACTUS_OUTPUT_FILENAMES
            if resolved_asset_mode == ASSET_MODE_ACTUS
            else STAGE2C_OUTPUT_FILENAMES
        )
        for filename in filenames:
            outputs[filename].to_csv(resolved_output_dir / filename, index=False)

    return Stage2CResult(
        scenario_id=scenario_id,
        engine_result=engine_result,
        cashflows=cashflows,
        valuation_snapshots=valuation_snapshots,
        annual_cashflows=annual_cashflows,
        asset_snapshots=asset_snapshots,
        funding_ratio_trajectory=funding_ratio_trajectory,
        funding_summary=funding_summary,
        scenario_summary=scenario_summary,
        demographic_summary=demographic_summary,
        cashflows_by_type=cashflows_by_type,
        parameter_trajectory=parameter_trajectory,
        output_dir=resolved_output_dir,
        actus_asset_trajectory=actus_asset_trajectory,
    )


def _build_parameter_trajectory(
    *,
    horizon_years: int,
    conversion_rate: DynamicParameter,
    active_interest_rate: DynamicParameter,
    technical_interest_rate: DynamicParameter,
) -> pd.DataFrame:
    snapshot_count = horizon_years + 1
    conversion = _expand_engine_parameter_for_snapshots(
        conversion_rate, horizon_years, "conversion_rate"
    )
    active = _expand_engine_parameter_for_snapshots(
        active_interest_rate, horizon_years, "active_interest_rate"
    )
    technical = expand_parameter(
        technical_interest_rate,
        snapshot_count,
        "technical_interest_rate",
    )
    df = pd.DataFrame(
        {
            "projection_year": list(range(snapshot_count)),
            "conversion_rate": conversion,
            "active_interest_rate": active,
            "technical_interest_rate": technical,
        },
        columns=list(PARAMETER_TRAJECTORY_COLUMNS),
    )
    _validate_parameter_trajectory(df)
    return df


def _expand_engine_parameter_for_snapshots(
    value: DynamicParameter,
    horizon_years: int,
    name: str,
) -> tuple[float, ...]:
    if horizon_years == 0:
        return expand_parameter(value, 1, name)
    engine_values = expand_parameter(value, horizon_years, name)
    return engine_values + (engine_values[-1],)


def _build_demographic_summary(engine_result: Stage2CEngineResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year_idx in range(engine_result.horizon_years):
        end_state = engine_result.portfolio_states[year_idx + 1]
        rows.append(
            {
                "projection_year": year_idx + 1,
                "entries": engine_result.per_year_entries[year_idx],
                "exits": engine_result.per_year_exits[year_idx],
                "retirements": engine_result.per_year_retirements[year_idx],
                "turnover_residual": (
                    engine_result.turnover_rounding_residual_count[year_idx]
                ),
                "active_count_end": end_state.active_count_total,
                "retired_count_end": end_state.retired_count_total,
            }
        )
    df = pd.DataFrame(rows, columns=list(DEMOGRAPHIC_SUMMARY_COLUMNS))
    _validate_demographic_summary(df)
    return df


def _build_cashflows_by_type(cashflows: pd.DataFrame) -> pd.DataFrame:
    validate_cashflow_dataframe(cashflows)
    if cashflows.empty:
        df = pd.DataFrame(columns=list(CASHFLOWS_BY_TYPE_COLUMNS))
    else:
        work = cashflows.copy(deep=True)
        work["reporting_year"] = pd.to_datetime(work["time"]).dt.year.astype(int)
        df = (
            work.groupby(["reporting_year", "type"], as_index=False)["payoff"]
            .sum()
            .rename(columns={"payoff": "total_payoff"})
        )
        df = df[list(CASHFLOWS_BY_TYPE_COLUMNS)]
    _validate_cashflows_by_type(df)
    return df


def _validate_asset_mode(asset_mode: object) -> AssetMode:
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
    if output_dir is not None:
        return output_dir
    return None


def _build_actus_mode_outputs(**kwargs):
    from pk_alm.scenarios.stage1_baseline import _build_actus_mode_outputs as build

    return build(**kwargs)


def _validate_dataframe(df: object, name: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be pandas DataFrame, got {type(df).__name__}")


def _validate_demographic_summary(df: pd.DataFrame) -> bool:
    _validate_dataframe(df, "demographic_summary")
    if list(df.columns) != list(DEMOGRAPHIC_SUMMARY_COLUMNS):
        raise ValueError("invalid demographic_summary columns")
    for idx, row in df.iterrows():
        for column in (
            "projection_year",
            "entries",
            "exits",
            "retirements",
            "active_count_end",
            "retired_count_end",
        ):
            value = row[column]
            if isinstance(value, bool) or int(value) != value or int(value) < 0:
                raise ValueError(f"row {idx}: {column} must be a non-negative int")
        if float(row["turnover_residual"]) < 0:
            raise ValueError("turnover_residual must be >= 0")
    return True


def _validate_cashflows_by_type(df: pd.DataFrame) -> bool:
    _validate_dataframe(df, "cashflows_by_type")
    if list(df.columns) != list(CASHFLOWS_BY_TYPE_COLUMNS):
        raise ValueError("invalid cashflows_by_type columns")
    for idx, row in df.iterrows():
        if isinstance(row["reporting_year"], bool) or int(row["reporting_year"]) != row["reporting_year"]:
            raise ValueError(f"row {idx}: reporting_year must be int")
        if not isinstance(row["type"], str) or not row["type"].strip():
            raise ValueError(f"row {idx}: type must be a non-empty string")
        float(row["total_payoff"])
    return True


def _validate_parameter_trajectory(df: pd.DataFrame) -> bool:
    _validate_dataframe(df, "parameter_trajectory")
    if list(df.columns) != list(PARAMETER_TRAJECTORY_COLUMNS):
        raise ValueError("invalid parameter_trajectory columns")
    expected_years = list(range(len(df)))
    actual_years = [int(value) for value in df["projection_year"]]
    if actual_years != expected_years:
        raise ValueError(
            f"projection_year must be {expected_years}, got {actual_years}"
        )
    for idx, row in df.iterrows():
        for column in (
            "conversion_rate",
            "active_interest_rate",
            "technical_interest_rate",
        ):
            value = float(row[column])
            if value < 0:
                raise ValueError(f"row {idx}: {column} must be >= 0")
    return True
