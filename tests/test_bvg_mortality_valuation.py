import pytest

from pk_alm.bvg.cohorts import RetiredCohort
from pk_alm.bvg.mortality import EKF_0105, MORTALITY_MODE_EK0105, load_ek0105_table
from pk_alm.bvg.mortality_valuation import (
    mortality_weighted_retiree_pv_per_person,
    value_portfolio_state_stage2b,
)
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.valuation import value_portfolio_state


def test_mortality_weighted_pv_is_below_deterministic_terminal_age_pv() -> None:
    table = load_ek0105_table(EKF_0105)
    portfolio = BVGPortfolioState(
        retired_cohorts=(RetiredCohort("RET", 70, 5, 30_000.0, 450_000.0),)
    )
    deterministic = value_portfolio_state(
        portfolio,
        technical_interest_rate=0.0176,
        valuation_terminal_age=90,
    )
    mortality = value_portfolio_state_stage2b(
        portfolio,
        technical_interest_rate=0.0176,
        valuation_terminal_age=90,
        mortality_mode=MORTALITY_MODE_EK0105,
        mortality_table=table,
    )
    assert (
        mortality.mortality_weighted_retiree_obligation_pv
        <= deterministic.retiree_obligation_pv
    )
    assert mortality.retired_count_total == deterministic.retired_count_total


def test_pv_per_person_uses_annuity_due_first_payment() -> None:
    table = load_ek0105_table(EKF_0105)
    pv = mortality_weighted_retiree_pv_per_person(
        annual_pension=30_000.0,
        current_age=126,
        technical_interest_rate=0.0176,
        table=table,
    )
    assert pv == pytest.approx(30_000.0)
