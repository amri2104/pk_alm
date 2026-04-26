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

import pandas as pd

from pk_alm.analytics.cashflows import (
    find_liquidity_inflection_year,
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.analytics.funding import (
    build_funding_ratio_trajectory,
    validate_funding_ratio_dataframe,
)
from pk_alm.assets.deterministic import (
    build_deterministic_asset_trajectory,
    validate_asset_dataframe,
)
from pk_alm.bvg.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg.engine import BVGEngineResult, run_bvg_engine
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.valuation import (
    validate_valuation_dataframe,
    value_portfolio_states,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage1BaselineResult:
    """Frozen container for one Stage-1 baseline scenario run."""

    initial_state: BVGPortfolioState
    engine_result: BVGEngineResult
    valuation_snapshots: pd.DataFrame
    annual_cashflows: pd.DataFrame
    asset_snapshots: pd.DataFrame
    funding_ratio_trajectory: pd.DataFrame
    liquidity_inflection_year_structural: int | None
    liquidity_inflection_year_net: int | None
    output_paths: dict[str, Path]

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


def run_stage1_baseline(
    *,
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
    output_dir: str | Path | None = None,
) -> Stage1BaselineResult:
    """Run the Stage-1 baseline scenario end-to-end and optionally export CSVs."""
    initial_state = build_default_stage1_portfolio()

    engine_result = run_bvg_engine(
        initial_state=initial_state,
        horizon_years=horizon_years,
        active_interest_rate=active_interest_rate,
        retired_interest_rate=retired_interest_rate,
        contribution_multiplier=contribution_multiplier,
        start_year=start_year,
        retirement_age=retirement_age,
        capital_withdrawal_fraction=capital_withdrawal_fraction,
        conversion_rate=conversion_rate,
    )
    validate_cashflow_dataframe(engine_result.cashflows)

    valuation_snapshots = value_portfolio_states(
        engine_result.portfolio_states,
        technical_interest_rate,
        valuation_terminal_age,
    )
    validate_valuation_dataframe(valuation_snapshots)

    annual_cashflows = summarize_cashflows_by_year(engine_result.cashflows)
    validate_annual_cashflow_dataframe(annual_cashflows)

    asset_snapshots = build_deterministic_asset_trajectory(
        valuation_snapshots,
        annual_cashflows,
        target_funding_ratio=target_funding_ratio,
        annual_return_rate=annual_asset_return,
        start_year=start_year,
    )
    validate_asset_dataframe(asset_snapshots)

    funding_ratio_trajectory = build_funding_ratio_trajectory(
        asset_snapshots,
        valuation_snapshots,
    )
    validate_funding_ratio_dataframe(funding_ratio_trajectory)

    inflection_structural = find_liquidity_inflection_year(
        annual_cashflows, use_structural=True
    )
    inflection_net = find_liquidity_inflection_year(
        annual_cashflows, use_structural=False
    )

    output_paths: dict[str, Path] = {}
    if output_dir is not None:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        cashflows_path = out_path / "cashflows.csv"
        valuation_path = out_path / "valuation_snapshots.csv"
        annual_path = out_path / "annual_cashflows.csv"
        asset_path = out_path / "asset_snapshots.csv"
        funding_path = out_path / "funding_ratio_trajectory.csv"

        engine_result.cashflows.to_csv(cashflows_path, index=False)
        valuation_snapshots.to_csv(valuation_path, index=False)
        annual_cashflows.to_csv(annual_path, index=False)
        asset_snapshots.to_csv(asset_path, index=False)
        funding_ratio_trajectory.to_csv(funding_path, index=False)

        output_paths = {
            "cashflows": cashflows_path,
            "valuation_snapshots": valuation_path,
            "annual_cashflows": annual_path,
            "asset_snapshots": asset_path,
            "funding_ratio_trajectory": funding_path,
        }

    return Stage1BaselineResult(
        initial_state=initial_state,
        engine_result=engine_result,
        valuation_snapshots=valuation_snapshots,
        annual_cashflows=annual_cashflows,
        asset_snapshots=asset_snapshots,
        funding_ratio_trajectory=funding_ratio_trajectory,
        liquidity_inflection_year_structural=inflection_structural,
        liquidity_inflection_year_net=inflection_net,
        output_paths=output_paths,
    )
