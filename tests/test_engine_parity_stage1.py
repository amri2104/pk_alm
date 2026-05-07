"""Stage-1 canonical engine contract tests.

Constructs :class:`BVGAssumptions` for the Stage-1 defaults: no turnover,
no salary growth, closed fund, mortality off, and flat rates.
"""

from __future__ import annotations

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import (
    ActiveCohort,
    RetiredCohort,
)
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.generic_engine import run_bvg_engine
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import NoEntryPolicy

RATE = 0.0176
ACTIVE_RATE = 0.0125
HORIZON = 12
START_YEAR = 2026


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


def _stage1_assumptions(*, contribution_multiplier: float = 1.0) -> BVGAssumptions:
    return BVGAssumptions(
        start_year=START_YEAR,
        horizon_years=HORIZON,
        retirement_age=65,
        valuation_terminal_age=90,
        active_crediting_rate=FlatRateCurve(ACTIVE_RATE),
        retired_interest_rate=FlatRateCurve(RATE),
        technical_discount_rate=FlatRateCurve(RATE),
        economic_discount_rate=FlatRateCurve(RATE),
        salary_growth_rate=FlatRateCurve(0.0),
        conversion_rate=FlatRateCurve(0.068),
        turnover_rate=0.0,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=NoEntryPolicy(),
    )


def test_stage1_config_produces_stable_cashflow_contract() -> None:
    initial = _portfolio()
    new = run_bvg_engine(
        initial_state=initial, assumptions=_stage1_assumptions()
    )
    assert new.horizon_years == HORIZON
    assert set(new.cashflows["type"]).issubset({"PR", "RP", "KA"})
    assert pd.to_datetime(new.cashflows["time"]).dt.year.min() == START_YEAR
    assert pd.to_datetime(new.cashflows["time"]).dt.year.max() == START_YEAR + HORIZON - 1


def test_stage1_config_portfolio_state_sequence_is_annual() -> None:
    initial = _portfolio()
    new = run_bvg_engine(
        initial_state=initial, assumptions=_stage1_assumptions()
    )
    assert len(new.portfolio_states) == HORIZON + 1
    assert tuple(state.projection_year for state in new.portfolio_states) == tuple(
        range(HORIZON + 1)
    )


def test_generic_engine_horizon_zero_returns_initial_only() -> None:
    initial = _portfolio()
    a = _stage1_assumptions()
    a = BVGAssumptions(
        start_year=a.start_year,
        horizon_years=0,
        retirement_age=a.retirement_age,
        valuation_terminal_age=a.valuation_terminal_age,
        active_crediting_rate=a.active_crediting_rate,
        retired_interest_rate=a.retired_interest_rate,
        technical_discount_rate=a.technical_discount_rate,
        economic_discount_rate=a.economic_discount_rate,
        salary_growth_rate=a.salary_growth_rate,
        conversion_rate=a.conversion_rate,
        turnover_rate=a.turnover_rate,
        capital_withdrawal_fraction=a.capital_withdrawal_fraction,
        contribution_multiplier=a.contribution_multiplier,
        mortality=a.mortality,
        entry_policy=a.entry_policy,
    )
    result = run_bvg_engine(initial_state=initial, assumptions=a)
    assert len(result.portfolio_states) == 1
    assert result.cashflows.empty
    assert result.year_steps == ()


def test_generic_engine_year_step_structure() -> None:
    initial = _portfolio()
    new = run_bvg_engine(initial_state=initial, assumptions=_stage1_assumptions())
    assert len(new.year_steps) == HORIZON
    first = new.year_steps[0]
    assert first.year == START_YEAR
    assert first.opening_state == initial
    assert first.closing_state == new.portfolio_states[1]
    # Stage-1 has no turnover or entries.
    assert first.exited_count == 0
    assert first.entry_count == 0
    assert first.turnover_cashflows.empty
    assert first.entry_cashflows.empty
    # Year cashflows = regular ⊕ retirement.
    expected = pd.concat(
        [first.regular_cashflows, first.retirement_cashflows], ignore_index=True
    )
    pd.testing.assert_frame_equal(
        first.year_cashflows.reset_index(drop=True),
        expected.reset_index(drop=True),
        check_dtype=False,
    )
