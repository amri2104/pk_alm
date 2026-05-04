"""Stage 2B mortality scenario wrapper.

Stage 2B is a prototype layer over Stage 2A. It uses EK 0105 only as a
simplified educational mortality input; BVG 2020 / VZ 2020 would be more
appropriate for real Swiss pension-fund valuation and are out of scope here.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pk_alm.actus_asset_engine.aal_asset_portfolio import AssetSpec
from pk_alm.alm_analytics_engine.cashflows import (
    find_liquidity_inflection_year,
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.alm_analytics_engine.funding import validate_funding_ratio_dataframe
from pk_alm.actus_asset_engine.deterministic import (
    DeterministicAssetSnapshot,
    asset_snapshots_to_dataframe,
    validate_asset_dataframe,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import EntryAssumptions
from pk_alm.bvg_liability_engine.actuarial_assumptions.mortality import (
    DEFAULT_EK0105_TABLE_ID,
    MORTALITY_MODE_EK0105,
    MORTALITY_MODE_OFF,
    MORTALITY_SOURCE_CAVEAT,
    SUPPORTED_EK0105_TABLE_IDS,
    MortalityTable,
    expected_pension_payment,
    load_ek0105_table,
    survival_factor,
)
from pk_alm.bvg_liability_engine.actuarial_assumptions.mortality_valuation import (
    validate_mortality_valuation_dataframe,
    value_portfolio_states_stage2b,
)
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe
from pk_alm.scenarios.stage2_baseline import (
    Stage2BaselineResult,
    run_stage2_baseline,
)
from pk_alm.scenarios.stage1_baseline import (
    ACTUS_ASSET_TRAJECTORY_FILENAME,
    ASSET_MODE_ACTUS,
    ASSET_MODE_DETERMINISTIC,
    AssetMode,
    _build_actus_mode_outputs,
    _resolve_output_dir,
    _validate_asset_mode,
)

STAGE2B_OUTPUT_FILENAMES: tuple[str, ...] = (
    "cashflows.csv",
    "mortality_valuation_snapshots.csv",
    "annual_cashflows.csv",
    "asset_snapshots.csv",
    "funding_ratio_trajectory.csv",
    "funding_summary.csv",
    "scenario_summary.csv",
    "demographic_summary.csv",
    "cashflows_by_type.csv",
    "survival_factors.csv",
    "mortality_assumptions.csv",
)

STAGE2B_ACTUS_OUTPUT_FILENAMES: tuple[str, ...] = (
    *STAGE2B_OUTPUT_FILENAMES,
    ACTUS_ASSET_TRAJECTORY_FILENAME,
)

STAGE2B_FUNDING_RATIO_COLUMNS = (
    "projection_year",
    "asset_value",
    "total_stage2b_liability",
    "funding_ratio",
    "funding_ratio_percent",
    "currency",
)

STAGE2B_SCENARIO_SUMMARY_COLUMNS = (
    "scenario_id",
    "mortality_mode",
    "mortality_table_id",
    "horizon_years",
    "start_year",
    "end_year",
    "initial_total_stage2b_liability",
    "final_total_stage2b_liability",
    "initial_asset_value",
    "final_asset_value",
    "initial_funding_ratio_percent",
    "final_funding_ratio_percent",
    "liquidity_inflection_year_structural",
    "liquidity_inflection_year_net",
    "currency",
    "source_caveat",
)


@dataclass(frozen=True)
class Stage2BMortalityResult:
    """Container for one Stage-2B mortality run."""

    scenario_id: str
    mortality_mode: str
    mortality_table_id: str
    stage2a_result: Stage2BaselineResult
    cashflows: pd.DataFrame
    mortality_valuation_snapshots: pd.DataFrame
    annual_cashflows: pd.DataFrame
    asset_snapshots: pd.DataFrame
    funding_ratio_trajectory: pd.DataFrame
    funding_summary: pd.DataFrame
    scenario_summary: pd.DataFrame
    demographic_summary: pd.DataFrame
    cashflows_by_type: pd.DataFrame
    survival_factors: pd.DataFrame
    mortality_assumptions: pd.DataFrame
    output_dir: Path | None
    actus_asset_trajectory: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        if self.mortality_mode not in (MORTALITY_MODE_OFF, MORTALITY_MODE_EK0105):
            raise ValueError("invalid mortality_mode")
        if not isinstance(self.stage2a_result, Stage2BaselineResult):
            raise TypeError("stage2a_result must be Stage2BaselineResult")
        validate_cashflow_dataframe(self.cashflows)
        validate_mortality_valuation_dataframe(self.mortality_valuation_snapshots)
        validate_annual_cashflow_dataframe(self.annual_cashflows)
        validate_asset_dataframe(self.asset_snapshots)
        if self.mortality_mode == MORTALITY_MODE_OFF:
            validate_funding_ratio_dataframe(self.funding_ratio_trajectory)
        else:
            _validate_stage2b_funding_ratio_dataframe(self.funding_ratio_trajectory)
        _validate_dataframe(self.funding_summary, "funding_summary")
        _validate_dataframe(self.scenario_summary, "scenario_summary")
        _validate_dataframe(self.demographic_summary, "demographic_summary")
        _validate_dataframe(self.cashflows_by_type, "cashflows_by_type")
        _validate_dataframe(self.survival_factors, "survival_factors")
        _validate_dataframe(self.mortality_assumptions, "mortality_assumptions")
        if self.output_dir is not None and not isinstance(self.output_dir, Path):
            raise TypeError("output_dir must be Path or None")
        if self.actus_asset_trajectory is not None and not isinstance(
            self.actus_asset_trajectory, pd.DataFrame
        ):
            raise TypeError("actus_asset_trajectory must be DataFrame or None")

    @property
    def portfolio_states(self):
        return self.stage2a_result.engine_result.portfolio_states


def run_stage2b_mortality(
    *,
    scenario_id: str = "stage2b_mortality",
    mortality_mode: str = MORTALITY_MODE_EK0105,
    mortality_table_id: str = DEFAULT_EK0105_TABLE_ID,
    horizon_years: int = 12,
    start_year: int = 2026,
    active_interest_rate: float = 0.0176,
    retired_interest_rate: float = 0.0176,
    technical_interest_rate: float = 0.0176,
    contribution_multiplier: float = 1.4,
    valuation_terminal_age: int = 90,
    target_funding_ratio: float = 1.076,
    annual_asset_return: float = 0.0,
    salary_growth_rate: float = 0.015,
    turnover_rate: float = 0.02,
    entry_assumptions: EntryAssumptions | None = None,
    asset_mode: AssetMode = ASSET_MODE_DETERMINISTIC,
    asset_specs: tuple[AssetSpec, ...] | list[AssetSpec] | None = None,
    output_dir: str | Path | None = "outputs/stage2b_mortality",
) -> Stage2BMortalityResult:
    """Run Stage 2B mortality over the Stage-2A population path.

    In ``asset_mode="actus"``, mortality still affects only liability-side
    RP cashflows and retiree PV. The live AAL asset portfolio is not
    mortality-weighted.
    """
    resolved_asset_mode = _validate_asset_mode(asset_mode)
    output_dir = _resolve_output_dir(
        asset_mode=resolved_asset_mode,
        output_dir=output_dir,
        deterministic_default="outputs/stage2b_mortality",
        actus_default="outputs/stage2b_actus",
    )
    if mortality_mode not in (MORTALITY_MODE_OFF, MORTALITY_MODE_EK0105):
        raise ValueError("mortality_mode must be 'off' or 'ek0105'")
    if mortality_table_id not in SUPPORTED_EK0105_TABLE_IDS:
        raise ValueError(
            f"mortality_table_id must be one of {SUPPORTED_EK0105_TABLE_IDS}"
        )

    stage2a = run_stage2_baseline(
        scenario_id="stage2_baseline_for_stage2b",
        horizon_years=horizon_years,
        start_year=start_year,
        active_interest_rate=active_interest_rate,
        retired_interest_rate=retired_interest_rate,
        technical_interest_rate=technical_interest_rate,
        contribution_multiplier=contribution_multiplier,
        valuation_terminal_age=valuation_terminal_age,
        target_funding_ratio=target_funding_ratio,
        annual_asset_return=annual_asset_return,
        salary_growth_rate=salary_growth_rate,
        turnover_rate=turnover_rate,
        entry_assumptions=entry_assumptions,
        asset_mode=resolved_asset_mode,
        asset_specs=asset_specs,
        output_dir=None,
    )

    mortality_table = (
        None if mortality_mode == MORTALITY_MODE_OFF else load_ek0105_table(mortality_table_id)
    )

    if mortality_mode == MORTALITY_MODE_OFF:
        cashflows = stage2a.engine_result.cashflows.copy(deep=True)
        annual_cashflows = stage2a.annual_cashflows.copy(deep=True)
        asset_snapshots = stage2a.asset_snapshots.copy(deep=True)
        funding_ratio_trajectory = stage2a.funding_ratio_trajectory.copy(deep=True)
        funding_summary = stage2a.funding_summary.copy(deep=True)
        cashflows_by_type = stage2a.cashflows_by_type.copy(deep=True)
        actus_asset_trajectory = (
            None
            if stage2a.actus_asset_trajectory is None
            else stage2a.actus_asset_trajectory.copy(deep=True)
        )
    else:
        liability_cashflows = _build_mortality_weighted_cashflows(
            stage2a, mortality_table, start_year
        )
        mortality_valuation_for_funding = value_portfolio_states_stage2b(
            stage2a.engine_result.portfolio_states,
            technical_interest_rate,
            valuation_terminal_age,
            mortality_mode,
            mortality_table,
        )
        if resolved_asset_mode == ASSET_MODE_DETERMINISTIC:
            cashflows = liability_cashflows
            annual_cashflows = summarize_cashflows_by_year(cashflows)
            asset_snapshots = _build_stage2b_asset_trajectory(
                annual_cashflows=annual_cashflows,
                valuation_snapshots=mortality_valuation_for_funding,
                initial_assets=float(
                    stage2a.asset_snapshots.iloc[0]["closing_asset_value"]
                ),
                annual_asset_return=annual_asset_return,
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
                valuation_snapshots=stage2a.valuation_snapshots,
                liability_cashflows=liability_cashflows,
                asset_specs=asset_specs,
                target_funding_ratio=target_funding_ratio,
                start_year=start_year,
                horizon_years=horizon_years,
                initial_liability=float(
                    mortality_valuation_for_funding.iloc[0][
                        "total_stage2b_liability"
                    ]
                ),
            )
        funding_ratio_trajectory = _build_stage2b_funding_ratio_trajectory(
            asset_snapshots, mortality_valuation_for_funding
        )
        funding_summary = _build_stage2b_funding_summary(
            funding_ratio_trajectory, target_funding_ratio
        )
        cashflows_by_type = _build_cashflows_by_type(cashflows)

    mortality_valuation_snapshots = value_portfolio_states_stage2b(
        stage2a.engine_result.portfolio_states,
        technical_interest_rate,
        valuation_terminal_age,
        mortality_mode,
        mortality_table,
    )
    survival_factors = _build_survival_factors(
        stage2a,
        mortality_table,
        mortality_mode,
    )
    mortality_assumptions = _build_mortality_assumptions(
        mortality_mode,
        "OFF" if mortality_table is None else mortality_table.table_id,
        None if mortality_table is None else mortality_table.max_age,
    )
    scenario_summary = _build_stage2b_scenario_summary(
        scenario_id=scenario_id,
        mortality_mode=mortality_mode,
        mortality_table_id="OFF" if mortality_table is None else mortality_table.table_id,
        annual_cashflows=annual_cashflows,
        asset_snapshots=asset_snapshots,
        funding_ratio_trajectory=funding_ratio_trajectory,
        mortality_valuation_snapshots=mortality_valuation_snapshots,
    )

    resolved_output_dir: Path | None = None
    if output_dir is not None:
        resolved_output_dir = Path(output_dir)
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        outputs = {
            "cashflows.csv": cashflows,
            "mortality_valuation_snapshots.csv": mortality_valuation_snapshots,
            "annual_cashflows.csv": annual_cashflows,
            "asset_snapshots.csv": asset_snapshots,
            "funding_ratio_trajectory.csv": funding_ratio_trajectory,
            "funding_summary.csv": funding_summary,
            "scenario_summary.csv": scenario_summary,
            "demographic_summary.csv": stage2a.demographic_summary,
            "cashflows_by_type.csv": cashflows_by_type,
            "survival_factors.csv": survival_factors,
            "mortality_assumptions.csv": mortality_assumptions,
        }
        if actus_asset_trajectory is not None:
            outputs[ACTUS_ASSET_TRAJECTORY_FILENAME] = actus_asset_trajectory
        filenames = (
            STAGE2B_ACTUS_OUTPUT_FILENAMES
            if resolved_asset_mode == ASSET_MODE_ACTUS
            else STAGE2B_OUTPUT_FILENAMES
        )
        for filename in filenames:
            outputs[filename].to_csv(resolved_output_dir / filename, index=False)

    return Stage2BMortalityResult(
        scenario_id=scenario_id,
        mortality_mode=mortality_mode,
        mortality_table_id="OFF" if mortality_table is None else mortality_table.table_id,
        stage2a_result=stage2a,
        cashflows=cashflows,
        mortality_valuation_snapshots=mortality_valuation_snapshots,
        annual_cashflows=annual_cashflows,
        asset_snapshots=asset_snapshots,
        funding_ratio_trajectory=funding_ratio_trajectory,
        funding_summary=funding_summary,
        scenario_summary=scenario_summary,
        demographic_summary=stage2a.demographic_summary.copy(deep=True),
        cashflows_by_type=cashflows_by_type,
        survival_factors=survival_factors,
        mortality_assumptions=mortality_assumptions,
        output_dir=resolved_output_dir,
        actus_asset_trajectory=actus_asset_trajectory,
    )


def _build_mortality_weighted_cashflows(
    stage2a: Stage2BaselineResult,
    mortality_table: MortalityTable,
    start_year: int,
) -> pd.DataFrame:
    cashflows = stage2a.engine_result.cashflows.copy(deep=True)
    origins = _retired_origins(stage2a)
    states = stage2a.engine_result.portfolio_states
    for idx, row in cashflows.iterrows():
        if row["type"] != "RP":
            continue
        step = int(pd.Timestamp(row["time"]).year) - start_year
        state = states[step]
        cohort = next(
            c for c in state.retired_cohorts if c.cohort_id == row["contractId"]
        )
        origin_year, origin_age = origins[cohort.cohort_id]
        survival = survival_factor(
            mortality_table,
            origin_age,
            max(0, step - origin_year),
        )
        cashflows.at[idx, "payoff"] = expected_pension_payment(
            count=cohort.count,
            annual_pension_per_person=cohort.annual_pension_per_person,
            survival_probability=survival,
        )
    cashflows = cashflows[list(CASHFLOW_COLUMNS)]
    validate_cashflow_dataframe(cashflows)
    return cashflows


def _retired_origins(stage2a: Stage2BaselineResult) -> dict[str, tuple[int, int]]:
    origins: dict[str, tuple[int, int]] = {}
    for projection_year, state in enumerate(stage2a.engine_result.portfolio_states):
        for cohort in state.retired_cohorts:
            origins.setdefault(cohort.cohort_id, (projection_year, cohort.age))
    return origins


def _build_survival_factors(
    stage2a: Stage2BaselineResult,
    mortality_table: MortalityTable | None,
    mortality_mode: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    origins = _retired_origins(stage2a)
    for projection_year, state in enumerate(stage2a.engine_result.portfolio_states):
        for cohort in state.retired_cohorts:
            origin_year, origin_age = origins[cohort.cohort_id]
            years_since_origin = max(0, projection_year - origin_year)
            survival = (
                1.0
                if mortality_table is None
                else survival_factor(mortality_table, origin_age, years_since_origin)
            )
            rows.append(
                {
                    "projection_year": projection_year,
                    "cohort_id": cohort.cohort_id,
                    "mortality_mode": mortality_mode,
                    "mortality_table_id": (
                        "OFF" if mortality_table is None else mortality_table.table_id
                    ),
                    "origin_projection_year": origin_year,
                    "origin_age": origin_age,
                    "current_age": cohort.age,
                    "years_since_origin": years_since_origin,
                    "survival_factor": survival,
                    "retired_count_state": cohort.count,
                    "expected_alive_count": cohort.count * survival,
                }
            )
    return pd.DataFrame(rows)


def _build_stage2b_asset_trajectory(
    *,
    valuation_snapshots: pd.DataFrame,
    annual_cashflows: pd.DataFrame,
    initial_assets: float,
    annual_asset_return: float,
    start_year: int,
    currency: str = "CHF",
) -> pd.DataFrame:
    assets = _validate_real(initial_assets, "initial_assets")
    return_rate = _validate_real(annual_asset_return, "annual_asset_return")
    if assets <= 0:
        raise ValueError("initial_assets must be > 0")
    if return_rate <= -1:
        raise ValueError("annual_asset_return must be > -1")
    snapshots = [
        DeterministicAssetSnapshot(
            projection_year=0,
            opening_asset_value=assets,
            investment_return=0.0,
            net_cashflow=0.0,
            closing_asset_value=assets,
            annual_return_rate=0.0,
            currency=currency,
        )
    ]
    previous = assets
    for i in range(1, len(valuation_snapshots)):
        reporting_year = start_year + i - 1
        matching = annual_cashflows.loc[
            annual_cashflows["reporting_year"] == reporting_year, "net_cashflow"
        ]
        if len(matching) != 1:
            raise ValueError(f"missing annual cashflow for {reporting_year}")
        investment_return = previous * return_rate
        net_cashflow = float(matching.iloc[0])
        closing = previous + investment_return + net_cashflow
        snapshots.append(
            DeterministicAssetSnapshot(
                projection_year=i,
                opening_asset_value=previous,
                investment_return=investment_return,
                net_cashflow=net_cashflow,
                closing_asset_value=closing,
                annual_return_rate=return_rate,
                currency=currency,
            )
        )
        previous = closing
    df = asset_snapshots_to_dataframe(snapshots)
    validate_asset_dataframe(df)
    return df


def _build_stage2b_funding_ratio_trajectory(
    asset_snapshots: pd.DataFrame,
    valuation_snapshots: pd.DataFrame,
    currency: str = "CHF",
) -> pd.DataFrame:
    rows = []
    for i in range(len(asset_snapshots)):
        assets = float(asset_snapshots.iloc[i]["closing_asset_value"])
        liability = float(valuation_snapshots.iloc[i]["total_stage2b_liability"])
        ratio = assets / liability
        rows.append(
            {
                "projection_year": int(asset_snapshots.iloc[i]["projection_year"]),
                "asset_value": assets,
                "total_stage2b_liability": liability,
                "funding_ratio": ratio,
                "funding_ratio_percent": ratio * 100.0,
                "currency": currency,
            }
        )
    df = pd.DataFrame(rows, columns=list(STAGE2B_FUNDING_RATIO_COLUMNS))
    _validate_stage2b_funding_ratio_dataframe(df)
    return df


def _build_stage2b_funding_summary(
    funding_ratio_trajectory: pd.DataFrame,
    target_funding_ratio: float,
) -> pd.DataFrame:
    percentages = list(funding_ratio_trajectory["funding_ratio_percent"])
    years = [int(y) for y in funding_ratio_trajectory["projection_year"]]
    min_idx = min(range(len(percentages)), key=lambda i: percentages[i])
    max_idx = max(range(len(percentages)), key=lambda i: percentages[i])
    target_percent = target_funding_ratio * 100.0
    return pd.DataFrame(
        [
            {
                "start_projection_year": years[0],
                "end_projection_year": years[-1],
                "initial_funding_ratio_percent": percentages[0],
                "final_funding_ratio_percent": percentages[-1],
                "minimum_funding_ratio_percent": percentages[min_idx],
                "minimum_funding_ratio_projection_year": years[min_idx],
                "maximum_funding_ratio_percent": percentages[max_idx],
                "maximum_funding_ratio_projection_year": years[max_idx],
                "target_funding_ratio_percent": target_percent,
                "years_below_100_percent": sum(p < 100.0 for p in percentages),
                "years_below_target_percent": sum(
                    p < target_percent for p in percentages
                ),
                "ever_underfunded": any(p < 100.0 for p in percentages),
                "final_underfunded": percentages[-1] < 100.0,
                "currency": "CHF",
            }
        ]
    )


def _build_stage2b_scenario_summary(
    *,
    scenario_id: str,
    mortality_mode: str,
    mortality_table_id: str,
    annual_cashflows: pd.DataFrame,
    asset_snapshots: pd.DataFrame,
    funding_ratio_trajectory: pd.DataFrame,
    mortality_valuation_snapshots: pd.DataFrame,
) -> pd.DataFrame:
    structural = find_liquidity_inflection_year(
        annual_cashflows, use_structural=True
    )
    net = find_liquidity_inflection_year(annual_cashflows, use_structural=False)
    return pd.DataFrame(
        [
            {
                "scenario_id": scenario_id,
                "mortality_mode": mortality_mode,
                "mortality_table_id": mortality_table_id,
                "horizon_years": len(mortality_valuation_snapshots) - 1,
                "start_year": (
                    0 if annual_cashflows.empty else int(annual_cashflows.iloc[0]["reporting_year"])
                ),
                "end_year": (
                    0 if annual_cashflows.empty else int(annual_cashflows.iloc[-1]["reporting_year"])
                ),
                "initial_total_stage2b_liability": float(
                    mortality_valuation_snapshots.iloc[0]["total_stage2b_liability"]
                ),
                "final_total_stage2b_liability": float(
                    mortality_valuation_snapshots.iloc[-1]["total_stage2b_liability"]
                ),
                "initial_asset_value": float(
                    asset_snapshots.iloc[0]["closing_asset_value"]
                ),
                "final_asset_value": float(
                    asset_snapshots.iloc[-1]["closing_asset_value"]
                ),
                "initial_funding_ratio_percent": float(
                    funding_ratio_trajectory.iloc[0]["funding_ratio_percent"]
                ),
                "final_funding_ratio_percent": float(
                    funding_ratio_trajectory.iloc[-1]["funding_ratio_percent"]
                ),
                "liquidity_inflection_year_structural": structural,
                "liquidity_inflection_year_net": net,
                "currency": "CHF",
                "source_caveat": MORTALITY_SOURCE_CAVEAT,
            }
        ],
        columns=list(STAGE2B_SCENARIO_SUMMARY_COLUMNS),
    )


def _build_cashflows_by_type(cashflows: pd.DataFrame) -> pd.DataFrame:
    if cashflows.empty:
        return pd.DataFrame(columns=["reporting_year", "type", "total_payoff"])
    work = cashflows.copy(deep=True)
    work["reporting_year"] = pd.to_datetime(work["time"]).dt.year.astype(int)
    return (
        work.groupby(["reporting_year", "type"], as_index=False)["payoff"]
        .sum()
        .rename(columns={"payoff": "total_payoff"})
    )[["reporting_year", "type", "total_payoff"]]


def _build_mortality_assumptions(
    mortality_mode: str,
    mortality_table_id: str,
    mortality_table_max_age: int | None,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "mortality_mode": mortality_mode,
                "mortality_table_id": mortality_table_id,
                "mortality_table_max_age": mortality_table_max_age,
                "source": "EK 0105 educational table",
                "source_caveat": MORTALITY_SOURCE_CAVEAT,
                "real_valuation_note": (
                    "BVG 2020 / VZ 2020 would be more appropriate for real "
                    "Swiss pension-fund valuation."
                ),
            }
        ]
    )


def _validate_stage2b_funding_ratio_dataframe(df: pd.DataFrame) -> bool:
    _validate_dataframe(df, "funding_ratio_trajectory")
    if list(df.columns) != list(STAGE2B_FUNDING_RATIO_COLUMNS):
        raise ValueError("invalid Stage-2B funding ratio columns")
    for _, row in df.iterrows():
        liability = float(row["total_stage2b_liability"])
        if liability <= 0:
            raise ValueError("total_stage2b_liability must be > 0")
        expected = float(row["asset_value"]) / liability
        if not math.isclose(float(row["funding_ratio"]), expected, abs_tol=1e-5):
            raise ValueError("funding ratio identity failed")
    return True


def _validate_dataframe(df: object, name: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be pandas DataFrame, got {type(df).__name__}")


def _validate_real(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    return fval
