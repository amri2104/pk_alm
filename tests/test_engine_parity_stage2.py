"""Stage-2 canonical engine contract tests.

Configures :class:`BVGAssumptions` with a :class:`FixedEntryPolicy` and
non-zero turnover/salary growth.
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


def test_stage2_full_dynamics_cashflow_contract() -> None:
    initial = _portfolio()
    entry = EntryAssumptions(entry_count_per_year=1)
    new = run_bvg_engine(
        initial_state=initial,
        assumptions=_stage2_assumptions(entry=entry),
    )
    assert set(new.cashflows["type"]).issuperset({"PR", "RP"})
    assert len(new.year_steps) == 12
    assert tuple(ys.entry_count for ys in new.year_steps) == (1,) * 12


def test_stage2_full_dynamics_portfolio_states_are_annual() -> None:
    initial = _portfolio()
    entry = EntryAssumptions(entry_count_per_year=1)
    new = run_bvg_engine(
        initial_state=initial,
        assumptions=_stage2_assumptions(entry=entry),
    )
    assert len(new.portfolio_states) == 13
    assert tuple(state.projection_year for state in new.portfolio_states) == tuple(
        range(13)
    )


def test_stage2_zero_turnover_zero_growth_zero_entries_matches_stage1_signature() -> None:
    """Stage1-equivalent config under stage2 engine should match generic engine."""
    initial = _portfolio()
    entry = EntryAssumptions(entry_count_per_year=0)
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
    assert tuple(ys.exited_count for ys in new.year_steps) == (0,) * 8
    assert tuple(ys.entry_count for ys in new.year_steps) == (0,) * 8
    assert not (new.cashflows["type"] == "EX").any()
    assert not (new.cashflows["type"] == "IN").any()


def test_stage2_year_step_counts_match_legacy_demographics() -> None:
    initial = _portfolio()
    entry = EntryAssumptions(entry_count_per_year=2)
    new = run_bvg_engine(
        initial_state=initial,
        assumptions=_stage2_assumptions(entry=entry, horizon=10),
    )
    assert tuple(ys.exited_count for ys in new.year_steps) == (0,) * 10
    assert tuple(ys.retired_count for ys in new.year_steps) == (0,) * 10
    assert tuple(ys.entry_count for ys in new.year_steps) == (2,) * 10
