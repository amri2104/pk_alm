"""Stage-2C parity: generic engine == legacy stage-2C engine with time-varying rates.

The legacy engine consumes ``DynamicParameter`` (scalar | sequence) for
``active_interest_rate`` and ``conversion_rate``; the generic engine uses
:class:`StepRateCurve` for the same inputs. This test asserts both routes
produce identical cashflows and portfolio states.
"""

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
from pk_alm.bvg_liability_engine.orchestration.legacy.engine_stage2c import (
    run_bvg_engine_stage2c,
)
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


def test_stage2c_step_rates_match_legacy() -> None:
    initial = _portfolio()
    horizon = 12
    start_year = 2026
    active_seq = [0.0125, 0.0150, 0.0125, 0.0100, 0.0125]
    conv_seq = [0.068, 0.066, 0.064, 0.062, 0.060]
    entry = EntryAssumptions(entry_count_per_year=1)

    legacy = run_bvg_engine_stage2c(
        initial_state=initial,
        horizon_years=horizon,
        active_interest_rate=active_seq,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.015,
        turnover_rate=0.02,
        entry_assumptions=entry,
        contribution_multiplier=1.4,
        start_year=start_year,
        retirement_age=65,
        capital_withdrawal_fraction=0.35,
        conversion_rate=conv_seq,
    )

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

    pd.testing.assert_frame_equal(
        new.cashflows.reset_index(drop=True),
        legacy.cashflows.reset_index(drop=True),
        check_dtype=False,
    )
    assert len(new.portfolio_states) == len(legacy.portfolio_states)
    for i, (a, b) in enumerate(zip(new.portfolio_states, legacy.portfolio_states)):
        assert a == b, f"portfolio_states[{i}] differs"


def test_stage2c_scalar_rates_match_legacy() -> None:
    """Scalar DynamicParameter inputs become FlatRateCurve."""
    initial = _portfolio()
    horizon = 8
    start_year = 2026
    entry = EntryAssumptions(entry_count_per_year=1)
    legacy = run_bvg_engine_stage2c(
        initial_state=initial,
        horizon_years=horizon,
        active_interest_rate=0.0125,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.015,
        turnover_rate=0.02,
        entry_assumptions=entry,
        contribution_multiplier=1.4,
        start_year=start_year,
        conversion_rate=0.068,
    )
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
    pd.testing.assert_frame_equal(
        new.cashflows.reset_index(drop=True),
        legacy.cashflows.reset_index(drop=True),
        check_dtype=False,
    )
