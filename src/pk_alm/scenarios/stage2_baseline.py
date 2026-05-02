"""Stage 2 Baseline Scenario (BAUPLAN, not yet implemented).

End-to-end Stage-2 demonstrator. Mirrors ``run_stage1_baseline`` but uses the
Stage-2 engine, adds two new CSV outputs (demographic_summary.csv,
cashflows_by_type.csv), and writes to ``outputs/stage2_baseline/``.

Implementation status:
    All public functions raise ``NotImplementedError("Stage 2 Bauplan:
    implementation deferred")`` until Sprint 10.

Architectural rule:
    The Stage-1 scenario ``run_stage1_baseline`` and its file
    ``stage1_baseline.py`` MUST NOT be modified. The Stage-2 scenario is
    parallel (ADR 010).

Output protection:
    - ``outputs/stage1_baseline/*`` is NEVER written by Stage 2.
    - ``outputs/stage2_baseline/*`` is the Stage-2 export root.
    - Both trees coexist.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pk_alm.adapters.aal_asset_portfolio import AssetSpec
from pk_alm.analytics.cashflows import (
    find_liquidity_inflection_year,
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.analytics.funding import (
    build_funding_ratio_trajectory,
    validate_funding_ratio_dataframe,
)
from pk_alm.analytics.funding_summary import (
    funding_summary_to_dataframe,
    summarize_funding_ratio,
    validate_funding_summary_dataframe,
)
from pk_alm.assets.deterministic import (
    build_deterministic_asset_trajectory,
    validate_asset_dataframe,
)
from pk_alm.bvg.engine_stage2 import Stage2EngineResult, run_bvg_engine_stage2
from pk_alm.bvg.entry_dynamics import EntryAssumptions
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.valuation import (
    validate_valuation_dataframe,
    value_portfolio_states,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe
from pk_alm.scenarios.result_summary import (
    build_scenario_result_summary,
    scenario_result_summary_to_dataframe,
    validate_scenario_result_dataframe,
)
from pk_alm.scenarios.stage1_baseline import build_default_stage1_portfolio
from pk_alm.scenarios.stage1_baseline import (
    ACTUS_ASSET_TRAJECTORY_FILENAME,
    ASSET_MODE_ACTUS,
    ASSET_MODE_DETERMINISTIC,
    AssetMode,
    _build_actus_mode_outputs,
    _resolve_output_dir,
    _validate_asset_mode,
)

STAGE2_OUTPUT_FILENAMES: tuple[str, ...] = (
    "cashflows.csv",
    "valuation_snapshots.csv",
    "annual_cashflows.csv",
    "asset_snapshots.csv",
    "funding_ratio_trajectory.csv",
    "funding_summary.csv",
    "scenario_summary.csv",
    "demographic_summary.csv",       # Stage-2 specific
    "cashflows_by_type.csv",         # Stage-2 specific
)

STAGE2_ACTUS_OUTPUT_FILENAMES: tuple[str, ...] = (
    *STAGE2_OUTPUT_FILENAMES,
    ACTUS_ASSET_TRAJECTORY_FILENAME,
)


@dataclass(frozen=True)
class Stage2BaselineResult:
    """Frozen result container for one Stage-2 baseline run.

    Attributes:
        scenario_id: Caller-supplied scenario identifier.
        engine_result: The underlying Stage2EngineResult.
        valuation_snapshots: Validated valuation snapshot DataFrame.
        annual_cashflows: Validated annual-cashflow DataFrame.
        asset_snapshots: Deterministic asset-roll-forward DataFrame.
        funding_ratio_trajectory: Funding-ratio path DataFrame.
        funding_summary: Compact funding summary DataFrame.
        scenario_summary: One-row scenario summary DataFrame.
        demographic_summary: NEW Stage-2 DataFrame: per-year entries,
            exits, retirements, turnover_residual, end-of-period counts.
        cashflows_by_type: NEW Stage-2 DataFrame: per-year totals split
            by event type (PR / RP / KA / EX / IN).
        output_dir: Directory where CSV files were written, or ``None`` if
            the scenario was run with ``output_dir=None``.
    """

    scenario_id: str
    engine_result: Stage2EngineResult
    cashflows: pd.DataFrame
    valuation_snapshots: pd.DataFrame
    annual_cashflows: pd.DataFrame
    asset_snapshots: pd.DataFrame
    funding_ratio_trajectory: pd.DataFrame
    funding_summary: pd.DataFrame
    scenario_summary: pd.DataFrame
    demographic_summary: pd.DataFrame
    cashflows_by_type: pd.DataFrame
    output_dir: Path | None
    actus_asset_trajectory: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        if not isinstance(self.engine_result, Stage2EngineResult):
            raise TypeError(
                "engine_result must be Stage2EngineResult, "
                f"got {type(self.engine_result).__name__}"
            )
        _validate_dataframe(self.cashflows, "cashflows")
        validate_cashflow_dataframe(self.cashflows)
        _validate_dataframe(self.valuation_snapshots, "valuation_snapshots")
        validate_valuation_dataframe(self.valuation_snapshots)
        _validate_dataframe(self.annual_cashflows, "annual_cashflows")
        validate_annual_cashflow_dataframe(self.annual_cashflows)
        _validate_dataframe(self.asset_snapshots, "asset_snapshots")
        validate_asset_dataframe(self.asset_snapshots)
        _validate_dataframe(
            self.funding_ratio_trajectory, "funding_ratio_trajectory"
        )
        validate_funding_ratio_dataframe(self.funding_ratio_trajectory)
        _validate_dataframe(self.funding_summary, "funding_summary")
        validate_funding_summary_dataframe(self.funding_summary)
        _validate_dataframe(self.scenario_summary, "scenario_summary")
        validate_scenario_result_dataframe(self.scenario_summary)
        _validate_demographic_summary(self.demographic_summary)
        _validate_cashflows_by_type(self.cashflows_by_type)
        if self.output_dir is not None and not isinstance(self.output_dir, Path):
            raise TypeError(
                f"output_dir must be Path or None, got {type(self.output_dir).__name__}"
            )
        if self.actus_asset_trajectory is not None and not isinstance(
            self.actus_asset_trajectory, pd.DataFrame
        ):
            raise TypeError("actus_asset_trajectory must be DataFrame or None")


def build_default_initial_portfolio_stage2():
    """Return the Stage-2 default starting portfolio.

    Stage 2 reuses the same default initial portfolio as Stage 1 to keep
    the demographic effect comparable. Sprint 10 will import the
    Stage-1 default builder rather than duplicate it.

    Returns:
        BVGPortfolioState with the same actives and retirees as
        ``stage1_baseline.build_default_initial_portfolio()``.

    Raises:
        NotImplementedError: Always, until Sprint 10.
    """
    return build_default_stage1_portfolio()


def run_stage2_baseline(
    scenario_id: str = "stage2_baseline",
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
    output_dir: str | Path | None = "outputs/stage2a_population",
) -> Stage2BaselineResult:
    """Run the Stage-2 baseline end-to-end with optional CSV export.

    Pipeline:

      1. Build default initial portfolio (or accept caller-provided one in a
         later overload).
      2. Run ``run_bvg_engine_stage2(...)`` for the Stage-2 cashflow stream.
      3. Run the Stage-1 valuation layer on the projected states (reused).
      4. Run the Stage-1 deterministic asset roll-forward (reused) using the
         Stage-2 net cashflow stream.
      5. Build Stage-2 demographic_summary and cashflows_by_type tables.
      6. Build the standard Stage-1-style scenario_summary.
      7. If ``output_dir is not None``: write all nine CSVs.

    Args:
        scenario_id: Non-empty string identifier.
        horizon_years: Non-negative integer.
        start_year: Calendar year for the first projection step.
        active_interest_rate / retired_interest_rate / technical_interest_rate:
            BVG interest rates (same Stage-1 semantics).
        contribution_multiplier: Stage-1 semantics. Default 1.4.
        valuation_terminal_age: Stage-1 semantics. Default 90.
        target_funding_ratio: Calibrates initial assets =
            initial liability * target_funding_ratio. Default 1.076.
        annual_asset_return: Deterministic annual return on assets.
            Default 0.0.
        salary_growth_rate: Stage-2 specific. Default 0.015.
        turnover_rate: Stage-2 specific. Default 0.02.
        entry_assumptions: Stage-2 specific. ``None`` → default.
        output_dir: Directory for CSV outputs, or ``None`` for in-memory
            only. Default ``"outputs/stage2_baseline"``.

    Returns:
        Stage2BaselineResult with all DataFrames and the resolved output_dir.

    Raises:
        TypeError / ValueError on invalid inputs.
        NotImplementedError: Always, until Sprint 10.

    Stage-1 protection:
        This function does not write to ``outputs/stage1_baseline/`` under
        any circumstances. The protection is enforced both by the explicit
        ``output_dir`` default AND by a Sprint-10 test that calls
        ``run_stage2_baseline(...)`` and asserts ``outputs/stage1_baseline/``
        is unchanged.
    """
    resolved_asset_mode = _validate_asset_mode(asset_mode)
    output_dir = _resolve_output_dir(
        asset_mode=resolved_asset_mode,
        output_dir=output_dir,
        deterministic_default="outputs/stage2a_population",
        actus_default="outputs/stage2a_actus",
    )
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ValueError("scenario_id must be a non-empty string")

    initial_state = build_default_initial_portfolio_stage2()
    if not isinstance(initial_state, BVGPortfolioState):
        raise TypeError("Stage-2 default portfolio must be BVGPortfolioState")

    engine_result = run_bvg_engine_stage2(
        initial_state=initial_state,
        horizon_years=horizon_years,
        active_interest_rate=active_interest_rate,
        retired_interest_rate=retired_interest_rate,
        salary_growth_rate=salary_growth_rate,
        turnover_rate=turnover_rate,
        entry_assumptions=entry_assumptions,
        contribution_multiplier=contribution_multiplier,
        start_year=start_year,
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
        }
        if actus_asset_trajectory is not None:
            outputs[ACTUS_ASSET_TRAJECTORY_FILENAME] = actus_asset_trajectory
        filenames = (
            STAGE2_ACTUS_OUTPUT_FILENAMES
            if resolved_asset_mode == ASSET_MODE_ACTUS
            else STAGE2_OUTPUT_FILENAMES
        )
        for filename in filenames:
            outputs[filename].to_csv(resolved_output_dir / filename, index=False)

    return Stage2BaselineResult(
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
        output_dir=resolved_output_dir,
        actus_asset_trajectory=actus_asset_trajectory,
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


def _build_demographic_summary(engine_result: Stage2EngineResult) -> pd.DataFrame:
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


def _validate_dataframe(df: object, name: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be pandas DataFrame, got {type(df).__name__}")


def _validate_demographic_summary(df: pd.DataFrame) -> bool:
    _validate_dataframe(df, "demographic_summary")
    if list(df.columns) != list(DEMOGRAPHIC_SUMMARY_COLUMNS):
        raise ValueError(
            "demographic_summary columns must be "
            f"{list(DEMOGRAPHIC_SUMMARY_COLUMNS)}, got {list(df.columns)}"
        )
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
        residual = float(row["turnover_residual"])
        if residual < 0:
            raise ValueError("turnover_residual must be >= 0")
    return True


def _validate_cashflows_by_type(df: pd.DataFrame) -> bool:
    _validate_dataframe(df, "cashflows_by_type")
    if list(df.columns) != list(CASHFLOWS_BY_TYPE_COLUMNS):
        raise ValueError(
            "cashflows_by_type columns must be "
            f"{list(CASHFLOWS_BY_TYPE_COLUMNS)}, got {list(df.columns)}"
        )
    for idx, row in df.iterrows():
        if isinstance(row["reporting_year"], bool) or int(row["reporting_year"]) != row["reporting_year"]:
            raise ValueError(f"row {idx}: reporting_year must be int")
        if not isinstance(row["type"], str) or not row["type"].strip():
            raise ValueError(f"row {idx}: type must be a non-empty string")
        float(row["total_payoff"])
    return True
