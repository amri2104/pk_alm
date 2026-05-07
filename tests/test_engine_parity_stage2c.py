"""Stage-2C canonical engine contract tests with time-varying rates."""

from __future__ import annotations

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    EntryAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
    StepRateCurve,
)
from pk_alm.bvg_liability_engine.assumptions.rate_curves import from_dynamic_parameter
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
                cohort_id="ACT_35",
                age=35,
                count=6,
                gross_salary_per_person=80_000.0,
                capital_active_per_person=90_000.0,
            ),
            ActiveCohort(
                cohort_id="ACT_60",
                age=60,
                count=2,
                gross_salary_per_person=110_000.0,
                capital_active_per_person=520_000.0,
            ),
        ),
        retired_cohorts=(
            RetiredCohort(
                cohort_id="RET_75",
                age=75,
                count=4,
                annual_pension_per_person=24_000.0,
                capital_rente_per_person=350_000.0,
            ),
        ),
    )


def test_stage2c_step_rates_drive_cashflows_and_states() -> None:
    initial = _portfolio()
    horizon = 12
    start_year = 2026
    active_seq = [0.0125, 0.0150, 0.0125, 0.0100, 0.0125]
    conv_seq = [0.068, 0.066, 0.064, 0.062, 0.060]
    entry = EntryAssumptions(entry_count_per_year=1)

    assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon,
        retirement_age=65,
        valuation_terminal_age=90,
        active_crediting_rate=from_dynamic_parameter(
            active_seq, start_year=start_year, horizon_years=horizon
        ),
        retired_interest_rate=FlatRateCurve(0.0176),
        technical_discount_rate=FlatRateCurve(0.0176),
        economic_discount_rate=FlatRateCurve(0.0176),
        salary_growth_rate=FlatRateCurve(0.015),
        conversion_rate=from_dynamic_parameter(
            conv_seq, start_year=start_year, horizon_years=horizon
        ),
        turnover_rate=0.02,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=1.4,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(entry),
    )
    new = run_bvg_engine(initial_state=initial, assumptions=assumptions)

    assert len(new.portfolio_states) == horizon + 1
    assert len(new.year_steps) == horizon
    assert tuple(ys.entry_count for ys in new.year_steps) == (1,) * horizon
    assert new.assumptions.active_crediting_rate.value_at(2027) == 0.0150
    assert new.assumptions.conversion_rate.value_at(2035) == 0.060


def test_stage2c_scalar_rates_match_equivalent_flat_curves() -> None:
    """Scalar inputs become flat curves."""
    initial = _portfolio()
    horizon = 8
    start_year = 2026
    entry = EntryAssumptions(entry_count_per_year=1)
    assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon,
        active_crediting_rate=FlatRateCurve(0.0125),
        retired_interest_rate=FlatRateCurve(0.0176),
        technical_discount_rate=FlatRateCurve(0.0176),
        economic_discount_rate=FlatRateCurve(0.0176),
        salary_growth_rate=FlatRateCurve(0.015),
        conversion_rate=FlatRateCurve(0.068),
        turnover_rate=0.02,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=1.4,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(entry),
    )
    new = run_bvg_engine(initial_state=initial, assumptions=assumptions)
    flat_assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon,
        active_crediting_rate=from_dynamic_parameter(
            0.0125,
            start_year=start_year,
            horizon_years=horizon,
        ),
        retired_interest_rate=FlatRateCurve(0.0176),
        technical_discount_rate=FlatRateCurve(0.0176),
        economic_discount_rate=FlatRateCurve(0.0176),
        salary_growth_rate=FlatRateCurve(0.015),
        conversion_rate=from_dynamic_parameter(
            0.068,
            start_year=start_year,
            horizon_years=horizon,
        ),
        turnover_rate=0.02,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=1.4,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(entry),
    )
    equivalent = run_bvg_engine(initial_state=initial, assumptions=flat_assumptions)
    pd.testing.assert_frame_equal(new.cashflows, equivalent.cashflows)
    assert new.portfolio_states == equivalent.portfolio_states
