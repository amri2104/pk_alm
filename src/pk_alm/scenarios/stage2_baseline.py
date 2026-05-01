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

from pk_alm.bvg.engine_stage2 import Stage2EngineResult
from pk_alm.bvg.entry_dynamics import EntryAssumptions

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
    valuation_snapshots: pd.DataFrame
    annual_cashflows: pd.DataFrame
    asset_snapshots: pd.DataFrame
    funding_ratio_trajectory: pd.DataFrame
    funding_summary: pd.DataFrame
    scenario_summary: pd.DataFrame
    demographic_summary: pd.DataFrame
    cashflows_by_type: pd.DataFrame
    output_dir: Path | None

    def __post_init__(self) -> None:
        # Validation rules (final, enforced in Sprint 10):
        # - scenario_id: non-empty non-whitespace string
        # - engine_result: Stage2EngineResult
        # - valuation_snapshots: validate_valuation_dataframe
        # - annual_cashflows: validate_annual_cashflow_dataframe
        # - asset_snapshots / funding_ratio_trajectory / funding_summary /
        #   scenario_summary: pandas DataFrames matching their respective
        #   contracts (mirrored from Stage 1)
        # - demographic_summary: schema defined in section "Demographic
        #   summary CSV" of docs/stage2_spec.md
        # - cashflows_by_type: schema with columns
        #   (reporting_year, type, total_payoff)
        # - output_dir: Path or None
        raise NotImplementedError(
            "Stage 2 Bauplan: Stage2BaselineResult validation deferred (Sprint 10)"
        )


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
    raise NotImplementedError(
        "Stage 2 Bauplan: build_default_initial_portfolio_stage2 deferred (Sprint 10)"
    )


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
    output_dir: str | Path | None = "outputs/stage2_baseline",
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
    raise NotImplementedError(
        "Stage 2 Bauplan: run_stage2_baseline implementation deferred (Sprint 10)"
    )
