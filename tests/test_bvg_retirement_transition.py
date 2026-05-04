import math

import pandas as pd
import pytest
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.retirement_transition import (
    RetirementTransitionResult,
    apply_retirement_transitions_to_portfolio,
)
from pk_alm.cashflows.schema import CashflowRecord

EVENT_DATE = "2026-12-31"
EVENT_TS = pd.Timestamp(EVENT_DATE)


# ---------------------------------------------------------------------------
# Standard retiring cohort
# ---------------------------------------------------------------------------


def _act_65() -> ActiveCohort:
    """Cohort already projected from 64 to 65; ready to retire at year-end."""
    return ActiveCohort(
        cohort_id="ACT_64",
        age=65,
        count=2,
        gross_salary_per_person=80000,
        capital_active_per_person=518569.5,
    )


# ---------------------------------------------------------------------------
# A. No retirement transition
# ---------------------------------------------------------------------------


def test_no_transition_for_young_cohort():
    a40 = ActiveCohort(
        cohort_id="ACT_40",
        age=40,
        count=10,
        gross_salary_per_person=85000,
        capital_active_per_person=120000,
    )
    portfolio = BVGPortfolioState(active_cohorts=(a40,))

    result = apply_retirement_transitions_to_portfolio(portfolio, EVENT_DATE)

    assert isinstance(result, RetirementTransitionResult)
    assert len(result.portfolio_state.active_cohorts) == 1
    assert len(result.portfolio_state.retired_cohorts) == 0
    assert result.cashflow_records == ()
    assert result.cashflow_count == 0


# ---------------------------------------------------------------------------
# B. Single retirement transition
# ---------------------------------------------------------------------------


def test_single_transition_portfolio_shape():
    portfolio = BVGPortfolioState(active_cohorts=(_act_65(),))
    result = apply_retirement_transitions_to_portfolio(portfolio, EVENT_DATE)

    assert len(result.portfolio_state.active_cohorts) == 0
    assert len(result.portfolio_state.retired_cohorts) == 1


def test_single_transition_new_retired_cohort_fields():
    portfolio = BVGPortfolioState(active_cohorts=(_act_65(),))
    result = apply_retirement_transitions_to_portfolio(portfolio, EVENT_DATE)

    rc = result.portfolio_state.retired_cohorts[0]
    assert rc.cohort_id == "RET_FROM_ACT_64"
    assert rc.age == 65
    assert rc.count == 2
    assert rc.annual_pension_per_person == pytest.approx(22920.7719)
    assert rc.capital_rente_per_person == pytest.approx(337070.175)
    assert rc.annual_pension_total == pytest.approx(45841.5438)
    assert rc.total_capital_rente == pytest.approx(674140.35)


def test_single_transition_ka_cashflow_record():
    portfolio = BVGPortfolioState(active_cohorts=(_act_65(),))
    result = apply_retirement_transitions_to_portfolio(portfolio, EVENT_DATE)

    assert len(result.cashflow_records) == 1
    rec = result.cashflow_records[0]
    assert isinstance(rec, CashflowRecord)
    assert rec.contractId == "ACT_64"
    assert rec.type == "KA"
    assert rec.payoff == pytest.approx(-362998.65)
    assert rec.payoff < 0
    assert rec.nominalValue == pytest.approx(2 * 518569.5)
    assert rec.currency == "CHF"
    assert rec.source == "BVG"
    assert rec.time == EVENT_TS


# ---------------------------------------------------------------------------
# C. Mixed portfolio
# ---------------------------------------------------------------------------


def test_mixed_portfolio_ordering_and_cashflows():
    a40 = ActiveCohort(
        cohort_id="ACT_40",
        age=40,
        count=10,
        gross_salary_per_person=85000,
        capital_active_per_person=120000,
    )
    a65 = _act_65()
    existing_ret = RetiredCohort(
        cohort_id="RET_70",
        age=70,
        count=5,
        annual_pension_per_person=30000,
        capital_rente_per_person=450000,
    )
    portfolio = BVGPortfolioState(
        active_cohorts=(a40, a65),
        retired_cohorts=(existing_ret,),
    )

    result = apply_retirement_transitions_to_portfolio(portfolio, EVENT_DATE)

    # active: only ACT_40 remains
    assert tuple(c.cohort_id for c in result.portfolio_state.active_cohorts) == (
        "ACT_40",
    )
    # retired: existing first, new last
    assert tuple(c.cohort_id for c in result.portfolio_state.retired_cohorts) == (
        "RET_70",
        "RET_FROM_ACT_64",
    )
    # only the retiring active emits a KA record
    assert len(result.cashflow_records) == 1
    assert result.cashflow_records[0].contractId == "ACT_64"


# ---------------------------------------------------------------------------
# D. Boundary
# ---------------------------------------------------------------------------


def _make_active_at_age(age: int, cohort_id: str = "ACT") -> ActiveCohort:
    return ActiveCohort(
        cohort_id=cohort_id,
        age=age,
        count=1,
        gross_salary_per_person=80000,
        capital_active_per_person=400000,
    )


def test_age_64_does_not_transition():
    portfolio = BVGPortfolioState(active_cohorts=(_make_active_at_age(64),))
    result = apply_retirement_transitions_to_portfolio(portfolio, EVENT_DATE)
    assert len(result.portfolio_state.active_cohorts) == 1
    assert len(result.portfolio_state.retired_cohorts) == 0


def test_age_65_transitions():
    portfolio = BVGPortfolioState(active_cohorts=(_make_active_at_age(65),))
    result = apply_retirement_transitions_to_portfolio(portfolio, EVENT_DATE)
    assert len(result.portfolio_state.active_cohorts) == 0
    assert len(result.portfolio_state.retired_cohorts) == 1


def test_age_66_transitions_if_still_active():
    portfolio = BVGPortfolioState(active_cohorts=(_make_active_at_age(66),))
    result = apply_retirement_transitions_to_portfolio(portfolio, EVENT_DATE)
    assert len(result.portfolio_state.active_cohorts) == 0
    assert len(result.portfolio_state.retired_cohorts) == 1


# ---------------------------------------------------------------------------
# E. Parameter behavior
# ---------------------------------------------------------------------------


def test_zero_capital_withdrawal_fraction():
    portfolio = BVGPortfolioState(active_cohorts=(_act_65(),))
    result = apply_retirement_transitions_to_portfolio(
        portfolio, EVENT_DATE, capital_withdrawal_fraction=0.0
    )
    rec = result.cashflow_records[0]
    assert rec.payoff == pytest.approx(0.0)
    rc = result.portfolio_state.retired_cohorts[0]
    assert rc.capital_rente_per_person == pytest.approx(518569.5)


def test_full_capital_withdrawal_fraction():
    portfolio = BVGPortfolioState(active_cohorts=(_act_65(),))
    result = apply_retirement_transitions_to_portfolio(
        portfolio, EVENT_DATE, capital_withdrawal_fraction=1.0
    )
    rc = result.portfolio_state.retired_cohorts[0]
    assert rc.capital_rente_per_person == pytest.approx(0.0)
    assert rc.annual_pension_per_person == pytest.approx(0.0)
    rec = result.cashflow_records[0]
    assert rec.payoff == pytest.approx(-2 * 518569.5)


def test_zero_conversion_rate():
    portfolio = BVGPortfolioState(active_cohorts=(_act_65(),))
    result = apply_retirement_transitions_to_portfolio(
        portfolio, EVENT_DATE, conversion_rate=0.0
    )
    rc = result.portfolio_state.retired_cohorts[0]
    assert rc.annual_pension_per_person == pytest.approx(0.0)
    # capital_rente still positive: 518569.5 * 0.65
    assert rc.capital_rente_per_person == pytest.approx(337070.175)


# ---------------------------------------------------------------------------
# F. Invalid inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, "x", {"k": 1}])
def test_invalid_portfolio_type_raises(bad):
    with pytest.raises(TypeError):
        apply_retirement_transitions_to_portfolio(bad, EVENT_DATE)


@pytest.mark.parametrize("bad", [True, 65.0, "65"])
def test_invalid_retirement_age_type_raises(bad):
    portfolio = BVGPortfolioState()
    with pytest.raises(TypeError):
        apply_retirement_transitions_to_portfolio(
            portfolio, EVENT_DATE, retirement_age=bad
        )


def test_negative_retirement_age_raises():
    portfolio = BVGPortfolioState()
    with pytest.raises(ValueError):
        apply_retirement_transitions_to_portfolio(
            portfolio, EVENT_DATE, retirement_age=-1
        )


@pytest.mark.parametrize("bad", [True, None, "x"])
def test_invalid_fraction_type_raises(bad):
    portfolio = BVGPortfolioState()
    with pytest.raises(TypeError):
        apply_retirement_transitions_to_portfolio(
            portfolio, EVENT_DATE, capital_withdrawal_fraction=bad
        )


@pytest.mark.parametrize("bad", [-0.01, 1.01, -1.0, 2.0])
def test_invalid_fraction_value_raises(bad):
    portfolio = BVGPortfolioState()
    with pytest.raises(ValueError):
        apply_retirement_transitions_to_portfolio(
            portfolio, EVENT_DATE, capital_withdrawal_fraction=bad
        )


def test_fraction_nan_raises():
    portfolio = BVGPortfolioState()
    with pytest.raises(ValueError):
        apply_retirement_transitions_to_portfolio(
            portfolio, EVENT_DATE, capital_withdrawal_fraction=math.nan
        )


@pytest.mark.parametrize("bad", [True, None, "x"])
def test_invalid_conversion_rate_type_raises(bad):
    portfolio = BVGPortfolioState()
    with pytest.raises(TypeError):
        apply_retirement_transitions_to_portfolio(
            portfolio, EVENT_DATE, conversion_rate=bad
        )


def test_negative_conversion_rate_raises():
    portfolio = BVGPortfolioState()
    with pytest.raises(ValueError):
        apply_retirement_transitions_to_portfolio(
            portfolio, EVENT_DATE, conversion_rate=-0.01
        )


def test_conversion_rate_nan_raises():
    portfolio = BVGPortfolioState()
    with pytest.raises(ValueError):
        apply_retirement_transitions_to_portfolio(
            portfolio, EVENT_DATE, conversion_rate=math.nan
        )


@pytest.mark.parametrize("bad", [None, "not-a-date"])
def test_invalid_event_date_raises(bad):
    portfolio = BVGPortfolioState()
    with pytest.raises(ValueError):
        apply_retirement_transitions_to_portfolio(portfolio, bad)


# ---------------------------------------------------------------------------
# G. Immutability
# ---------------------------------------------------------------------------


def test_no_mutation_of_input_portfolio_or_cohorts():
    a65 = _act_65()
    a40 = ActiveCohort(
        cohort_id="ACT_40",
        age=40,
        count=10,
        gross_salary_per_person=85000,
        capital_active_per_person=120000,
    )
    existing = RetiredCohort(
        cohort_id="RET_70",
        age=70,
        count=5,
        annual_pension_per_person=30000,
        capital_rente_per_person=450000,
    )
    portfolio = BVGPortfolioState(
        active_cohorts=(a40, a65),
        retired_cohorts=(existing,),
    )
    snap_active_ages = tuple(c.age for c in portfolio.active_cohorts)
    snap_active_caps = tuple(
        c.capital_active_per_person for c in portfolio.active_cohorts
    )
    snap_retired_ages = tuple(c.age for c in portfolio.retired_cohorts)
    snap_retired_caps = tuple(
        c.capital_rente_per_person for c in portfolio.retired_cohorts
    )

    result = apply_retirement_transitions_to_portfolio(portfolio, EVENT_DATE)

    assert tuple(c.age for c in portfolio.active_cohorts) == snap_active_ages
    assert (
        tuple(c.capital_active_per_person for c in portfolio.active_cohorts)
        == snap_active_caps
    )
    assert tuple(c.age for c in portfolio.retired_cohorts) == snap_retired_ages
    assert (
        tuple(c.capital_rente_per_person for c in portfolio.retired_cohorts)
        == snap_retired_caps
    )
    # And the result is a new object
    assert result.portfolio_state is not portfolio
