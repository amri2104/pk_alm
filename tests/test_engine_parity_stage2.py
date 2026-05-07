"""Stage-2 parity: generic engine == legacy stage-2 engine.

Configures :class:`BVGAssumptions` with a :class:`FixedEntryPolicy` and
non-zero turnover/salary-growth, then asserts cashflow + portfolio-state
equality with the legacy stage-2 engine.
"""

from __future__ import annotations

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
from pk_alm.bvg_liability_engine.orchestration.legacy.engine_stage2 import (
    run_bvg_engine_stage2,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import (
    FixedEntryPolicy,
)


def _portfolio() -> BVGPortfolioState:
    return BVGPortfolioState(
        active_cohorts=(
            ActiveCohort(
                cohort_id="ACT_30",
                age=30,
                count=8,
                gross_salary_per_person=70_000.0,
                capital_active_per_person=50_000.0,
            ),
            ActiveCohort(
                cohort_id="ACT_50",
                age=50,
                count=4,
                gross_salary_per_person=95_000.0,
                capital_active_per_person=400_000.0,
            ),
        ),
        retired_cohorts=(
            RetiredCohort(
                cohort_id="RET_72",
                age=72,
                count=6,
                annual_pension_per_person=28_000.0,
                capital_rente_per_person=420_000.0,
            ),
        ),
    )


def _stage2_assumptions(
    *,
    entry: EntryAssumptions,
    salary_growth: float = 0.015,
    turnover: float = 0.02,
    contribution_multiplier: float = 1.4,
    horizon: int = 12,
) -> BVGAssumptions:
    return BVGAssumptions(
        start_year=2026,
        horizon_years=horizon,
        retirement_age=65,
        valuation_terminal_age=90,
        active_crediting_rate=FlatRateCurve(0.0125),
        retired_interest_rate=FlatRateCurve(0.0176),
        technical_discount_rate=FlatRateCurve(0.0176),
        economic_discount_rate=FlatRateCurve(0.0176),
        salary_growth_rate=FlatRateCurve(salary_growth),
        conversion_rate=FlatRateCurve(0.068),
        turnover_rate=turnover,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(entry),
    )


def test_stage2_full_dynamics_cashflows_match_legacy() -> None:
    initial = _portfolio()
    entry = EntryAssumptions(entry_count_per_year=1)
    legacy = run_bvg_engine_stage2(
        initial_state=initial,
        horizon_years=12,
        active_interest_rate=0.0125,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.015,
        turnover_rate=0.02,
        entry_assumptions=entry,
        contribution_multiplier=1.4,
        start_year=2026,
        retirement_age=65,
        capital_withdrawal_fraction=0.35,
        conversion_rate=0.068,
    )
    new = run_bvg_engine(
        initial_state=initial,
        assumptions=_stage2_assumptions(entry=entry),
    )
    pd.testing.assert_frame_equal(
        new.cashflows.reset_index(drop=True),
        legacy.cashflows.reset_index(drop=True),
        check_dtype=False,
    )


def test_stage2_full_dynamics_portfolio_states_match_legacy() -> None:
    initial = _portfolio()
    entry = EntryAssumptions(entry_count_per_year=1)
    legacy = run_bvg_engine_stage2(
        initial_state=initial,
        horizon_years=12,
        active_interest_rate=0.0125,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.015,
        turnover_rate=0.02,
        entry_assumptions=entry,
        contribution_multiplier=1.4,
        start_year=2026,
        retirement_age=65,
        capital_withdrawal_fraction=0.35,
        conversion_rate=0.068,
    )
    new = run_bvg_engine(
        initial_state=initial,
        assumptions=_stage2_assumptions(entry=entry),
    )
    assert len(new.portfolio_states) == len(legacy.portfolio_states)
    for i, (a, b) in enumerate(zip(new.portfolio_states, legacy.portfolio_states)):
        assert a == b, f"portfolio_states[{i}] differs"


def test_stage2_zero_turnover_zero_growth_zero_entries_matches_stage1_signature() -> None:
    """Stage1-equivalent config under stage2 engine should match generic engine."""
    initial = _portfolio()
    entry = EntryAssumptions(entry_count_per_year=0)
    legacy = run_bvg_engine_stage2(
        initial_state=initial,
        horizon_years=8,
        active_interest_rate=0.0125,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=entry,
        contribution_multiplier=1.0,
        start_year=2026,
    )
    new = run_bvg_engine(
        initial_state=initial,
        assumptions=_stage2_assumptions(
            entry=entry,
            salary_growth=0.0,
            turnover=0.0,
            contribution_multiplier=1.0,
            horizon=8,
        ),
    )
    pd.testing.assert_frame_equal(
        new.cashflows.reset_index(drop=True),
        legacy.cashflows.reset_index(drop=True),
        check_dtype=False,
    )


def test_stage2_year_step_counts_match_legacy_demographics() -> None:
    initial = _portfolio()
    entry = EntryAssumptions(entry_count_per_year=2)
    legacy = run_bvg_engine_stage2(
        initial_state=initial,
        horizon_years=10,
        active_interest_rate=0.0125,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.015,
        turnover_rate=0.02,
        entry_assumptions=entry,
    )
    new = run_bvg_engine(
        initial_state=initial,
        assumptions=_stage2_assumptions(entry=entry, horizon=10),
    )
    assert tuple(ys.exited_count for ys in new.year_steps) == legacy.per_year_exits
    assert (
        tuple(ys.retired_count for ys in new.year_steps) == legacy.per_year_retirements
    )
    assert tuple(ys.entry_count for ys in new.year_steps) == legacy.per_year_entries
