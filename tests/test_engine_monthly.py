"""Monthly cashflow-frequency sanity check.

In monthly mode the engine emits 12 sub-period rows per annual flow with
per-period payoff = annual / 12 and ``time`` set to the corresponding
month-end. State transitions remain annual. Aggregating monthly rows back
to annual must reproduce annual-mode cashflows up to floating-point noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    EntryAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import (
    ActiveCohort,
    RetiredCohort,
)
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.generic_engine import run_bvg_engine
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import (
    FixedEntryPolicy,
    NoEntryPolicy,
)


def _portfolio() -> BVGPortfolioState:
    return BVGPortfolioState(
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


def _base(*, frequency: str, entry: EntryAssumptions | None = None) -> BVGAssumptions:
    policy = FixedEntryPolicy(entry) if entry else NoEntryPolicy()
    return BVGAssumptions(
        start_year=2026,
        horizon_years=8,
        retirement_age=65,
        valuation_terminal_age=90,
        active_crediting_rate=FlatRateCurve(0.0125),
        retired_interest_rate=FlatRateCurve(0.0176),
        technical_discount_rate=FlatRateCurve(0.0176),
        economic_discount_rate=FlatRateCurve(0.0176),
        salary_growth_rate=FlatRateCurve(0.0),
        conversion_rate=FlatRateCurve(0.068),
        turnover_rate=0.0,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=1.0,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=policy,
        cashflow_frequency=frequency,  # type: ignore[arg-type]
    )


def _aggregate_monthly_to_annual(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["year"] = pd.to_datetime(df["time"]).dt.year
    grouped = (
        df.groupby(["year", "contractId", "type", "currency", "source"], as_index=False)
        .agg({"payoff": "sum", "nominalValue": "max"})
    )
    grouped["time"] = pd.to_datetime(
        grouped["year"].astype(str) + "-12-31"
    )
    grouped = grouped[
        ["contractId", "time", "type", "payoff", "nominalValue", "currency", "source"]
    ]
    return grouped.sort_values(["time", "contractId", "type"]).reset_index(drop=True)


def test_monthly_emits_twelve_rows_per_annual_flow() -> None:
    initial = _portfolio()
    monthly = run_bvg_engine(
        initial_state=initial, assumptions=_base(frequency="monthly")
    )
    annual = run_bvg_engine(
        initial_state=initial, assumptions=_base(frequency="annual")
    )
    assert len(monthly.cashflows) == 12 * len(annual.cashflows)


def test_monthly_aggregated_matches_annual() -> None:
    initial = _portfolio()
    monthly = run_bvg_engine(
        initial_state=initial, assumptions=_base(frequency="monthly")
    )
    annual = run_bvg_engine(
        initial_state=initial, assumptions=_base(frequency="annual")
    )
    aggregated = _aggregate_monthly_to_annual(monthly.cashflows)
    expected = annual.cashflows.copy()
    expected["time"] = pd.to_datetime(expected["time"])
    expected = expected.sort_values(["time", "contractId", "type"]).reset_index(drop=True)

    np.testing.assert_allclose(
        aggregated["payoff"].to_numpy(dtype=float),
        expected["payoff"].to_numpy(dtype=float),
        rtol=1e-9,
        atol=1e-9,
    )
    assert aggregated["contractId"].astype(str).tolist() == expected[
        "contractId"
    ].astype(str).tolist()
    assert aggregated["type"].astype(str).tolist() == expected["type"].astype(
        str
    ).tolist()


def test_monthly_state_transitions_remain_annual() -> None:
    initial = _portfolio()
    monthly = run_bvg_engine(
        initial_state=initial, assumptions=_base(frequency="monthly")
    )
    annual = run_bvg_engine(
        initial_state=initial, assumptions=_base(frequency="annual")
    )
    assert len(monthly.portfolio_states) == len(annual.portfolio_states)
    for ms, ans in zip(monthly.portfolio_states, annual.portfolio_states):
        assert ms == ans


def test_monthly_with_entries_aggregates_to_annual() -> None:
    initial = _portfolio()
    entry = EntryAssumptions(entry_count_per_year=1, entry_capital_per_person=10_000.0)
    monthly = run_bvg_engine(
        initial_state=initial,
        assumptions=_base(frequency="monthly", entry=entry),
    )
    annual = run_bvg_engine(
        initial_state=initial,
        assumptions=_base(frequency="annual", entry=entry),
    )
    aggregated = _aggregate_monthly_to_annual(monthly.cashflows)
    annual_sorted = annual.cashflows.sort_values(
        ["time", "contractId", "type"]
    ).reset_index(drop=True)
    np.testing.assert_allclose(
        aggregated["payoff"].to_numpy(dtype=float),
        annual_sorted["payoff"].to_numpy(dtype=float),
        rtol=1e-9,
        atol=1e-9,
    )
