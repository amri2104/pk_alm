"""Cashflow-runoff valuation cross-checks."""

from __future__ import annotations

import math

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.domain_models.cohorts import RetiredCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.valuation_runoff import (
    compare_formula_vs_cashflow_pv,
    project_runoff_cashflows_for_valuation,
    value_portfolio_state_cashflow_runoff,
    value_portfolio_state_formula,
)


def _retiree_state() -> BVGPortfolioState:
    return BVGPortfolioState(
        active_cohorts=(),
        retired_cohorts=(
            RetiredCohort(
                cohort_id="RET_70",
                age=70,
                count=5,
                annual_pension_per_person=30_000.0,
                capital_rente_per_person=450_000.0,
            ),
            RetiredCohort(
                cohort_id="RET_75",
                age=75,
                count=3,
                annual_pension_per_person=22_000.0,
                capital_rente_per_person=200_000.0,
            ),
        ),
    )


def _assumptions(
    *,
    technical: float = 0.02,
    economic: float = 0.005,
    terminal: int = 90,
    mortality_mode: str = "off",
) -> BVGAssumptions:
    return BVGAssumptions(
        start_year=2026,
        horizon_years=4,
        retirement_age=65,
        valuation_terminal_age=terminal,
        active_crediting_rate=FlatRateCurve(0.0125),
        retired_interest_rate=FlatRateCurve(technical),
        technical_discount_rate=FlatRateCurve(technical),
        economic_discount_rate=FlatRateCurve(economic),
        salary_growth_rate=FlatRateCurve(0.0),
        conversion_rate=FlatRateCurve(0.068),
        turnover_rate=0.0,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=1.0,
        mortality=MortalityAssumptions(mode=mortality_mode),  # type: ignore[arg-type]
    )


def test_runoff_cashflows_have_one_row_per_year_per_cohort_below_terminal() -> None:
    state = _retiree_state()
    a = _assumptions(terminal=80)
    df = project_runoff_cashflows_for_valuation(state, a, anchor_year=2026)
    # min age = 70, terminal = 80 → 10 offsets total.
    # RET_70 pays for ages 70..79 (10 rows). RET_75 pays for ages 75..79 (5 rows).
    assert len(df) == 15
    assert sorted(df["offset_years"].unique()) == list(range(10))
    counts = df.groupby("cohort_id").size().to_dict()
    assert counts == {"RET_70": 10, "RET_75": 5}


def test_runoff_pv_matches_formula_when_mortality_off() -> None:
    state = _retiree_state()
    a = _assumptions(technical=0.02)
    runoff = value_portfolio_state_cashflow_runoff(state, a, anchor_year=2026)
    assert math.isclose(runoff.technical_pv, runoff.formula_pv, abs_tol=1e-3)
    assert compare_formula_vs_cashflow_pv(runoff, mortality_active=False)


def test_runoff_economic_pv_higher_when_economic_rate_lower() -> None:
    state = _retiree_state()
    a = _assumptions(technical=0.02, economic=0.005)
    runoff = value_portfolio_state_cashflow_runoff(state, a, anchor_year=2026)
    assert runoff.economic_pv > runoff.technical_pv


def test_value_portfolio_state_formula_matches_inline_calculation() -> None:
    state = _retiree_state()
    pv = value_portfolio_state_formula(
        state, technical_rate=0.0, valuation_terminal_age=80
    )
    # Zero rate: PV is just remaining_years * count * pension
    expected = 5 * 30_000.0 * 10 + 3 * 22_000.0 * 5
    assert math.isclose(pv, expected, abs_tol=1e-6)


def test_compare_formula_vs_cashflow_pv_relation_holds() -> None:
    state = _retiree_state()
    a = _assumptions()
    runoff = value_portfolio_state_cashflow_runoff(state, a, anchor_year=2026)
    # mortality off: equality (within tolerance)
    assert compare_formula_vs_cashflow_pv(runoff, mortality_active=False)
    # mortality "active" — runoff_pv <= formula_pv (bound is loose since the
    # current engine runoff does not actually decrement counts; the bound is
    # technically equal and so still <=).
    assert compare_formula_vs_cashflow_pv(runoff, mortality_active=True)
