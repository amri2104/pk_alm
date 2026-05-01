import math

import pytest

from pk_alm.bvg.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.salary_dynamics import (
    MAX_PERMITTED_SALARY_GROWTH_RATE,
    apply_salary_growth_to_active_cohort,
    apply_salary_growth_to_portfolio,
)


def _active() -> ActiveCohort:
    return ActiveCohort(
        cohort_id="ACT",
        age=40,
        count=10,
        gross_salary_per_person=60_000.0,
        capital_active_per_person=120_000.0,
    )


def _retired() -> RetiredCohort:
    return RetiredCohort(
        cohort_id="RET",
        age=70,
        count=5,
        annual_pension_per_person=30_000.0,
        capital_rente_per_person=450_000.0,
    )


def test_zero_growth_returns_equivalent_cohort() -> None:
    cohort = _active()
    assert apply_salary_growth_to_active_cohort(cohort, 0.0) == cohort


def test_positive_growth_scales_gross_salary_only() -> None:
    cohort = _active()
    grown = apply_salary_growth_to_active_cohort(cohort, 0.015)
    assert grown.gross_salary_per_person == pytest.approx(60_900.0)
    assert grown.cohort_id == cohort.cohort_id
    assert grown.age == cohort.age
    assert grown.count == cohort.count
    assert grown.capital_active_per_person == cohort.capital_active_per_person


def test_input_cohort_not_mutated() -> None:
    cohort = _active()
    apply_salary_growth_to_active_cohort(cohort, 0.02)
    assert cohort.gross_salary_per_person == 60_000.0


@pytest.mark.parametrize("bad_rate", [-0.01, MAX_PERMITTED_SALARY_GROWTH_RATE + 0.01])
def test_invalid_growth_rate_raises_value_error(bad_rate: float) -> None:
    with pytest.raises(ValueError):
        apply_salary_growth_to_active_cohort(_active(), bad_rate)


def test_nan_growth_rate_raises_value_error() -> None:
    with pytest.raises(ValueError):
        apply_salary_growth_to_active_cohort(_active(), math.nan)


def test_bool_growth_rate_raises_type_error() -> None:
    with pytest.raises(TypeError):
        apply_salary_growth_to_active_cohort(_active(), True)


def test_non_active_cohort_input_raises_type_error() -> None:
    with pytest.raises(TypeError):
        apply_salary_growth_to_active_cohort("not a cohort", 0.01)


def test_positive_growth_scales_all_active_cohorts_uniformly() -> None:
    portfolio = BVGPortfolioState(
        projection_year=3,
        active_cohorts=(
            _active(),
            ActiveCohort("ACT2", 55, 2, 80_000.0, 300_000.0),
        ),
        retired_cohorts=(_retired(),),
    )
    grown = apply_salary_growth_to_portfolio(portfolio, 0.01)
    assert grown.projection_year == 3
    assert grown.active_cohorts[0].gross_salary_per_person == pytest.approx(60_600.0)
    assert grown.active_cohorts[1].gross_salary_per_person == pytest.approx(80_800.0)
    assert grown.retired_cohorts == portfolio.retired_cohorts
    assert portfolio.active_cohorts[0].gross_salary_per_person == 60_000.0


def test_zero_growth_preserves_portfolio_state() -> None:
    portfolio = BVGPortfolioState(
        active_cohorts=(_active(),),
        retired_cohorts=(_retired(),),
    )
    assert apply_salary_growth_to_portfolio(portfolio, 0.0) == portfolio


def test_invalid_portfolio_input_raises_type_error() -> None:
    with pytest.raises(TypeError):
        apply_salary_growth_to_portfolio("not a portfolio", 0.0)
