import pytest
from pk_alm.bvg.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.projection import (
    project_active_cohort_one_year,
    project_portfolio_one_year,
    project_retired_cohort_one_year,
)

RATE = 0.0176


# ---------------------------------------------------------------------------
# A. Active cohort standard projection
# ---------------------------------------------------------------------------


def test_active_projection_standard():
    cohort = ActiveCohort(
        cohort_id="ACT_40",
        age=40,
        count=10,
        gross_salary_per_person=85000,
        capital_active_per_person=120000,
    )
    projected = project_active_cohort_one_year(cohort, RATE)

    assert projected.cohort_id == "ACT_40"
    assert projected.age == 41
    assert projected.count == 10
    assert projected.gross_salary_per_person == pytest.approx(85000)
    # 120000 * 1.0176 + 5927.5 = 128039.5
    assert projected.capital_active_per_person == pytest.approx(128039.5)
    assert projected.total_capital_active == pytest.approx(1280395.0)


# ---------------------------------------------------------------------------
# B. Retired cohort standard projection
# ---------------------------------------------------------------------------


def test_retired_projection_standard():
    cohort = RetiredCohort(
        cohort_id="RET_70",
        age=70,
        count=5,
        annual_pension_per_person=30000,
        capital_rente_per_person=450000,
    )
    projected = project_retired_cohort_one_year(cohort, RATE)

    assert projected.cohort_id == "RET_70"
    assert projected.age == 71
    assert projected.count == 5
    assert projected.annual_pension_per_person == pytest.approx(30000)
    # (450000 - 30000) * 1.0176 = 427392.0
    assert projected.capital_rente_per_person == pytest.approx(427392.0)
    assert projected.total_capital_rente == pytest.approx(2136960.0)


# ---------------------------------------------------------------------------
# C. Immutability tests
# ---------------------------------------------------------------------------


def test_active_projection_does_not_mutate_input():
    cohort = ActiveCohort(
        cohort_id="ACT_40",
        age=40,
        count=10,
        gross_salary_per_person=85000,
        capital_active_per_person=120000,
    )
    projected = project_active_cohort_one_year(cohort, RATE)

    assert projected is not cohort
    assert cohort.age == 40
    assert cohort.capital_active_per_person == pytest.approx(120000)


def test_retired_projection_does_not_mutate_input():
    cohort = RetiredCohort(
        cohort_id="RET_70",
        age=70,
        count=5,
        annual_pension_per_person=30000,
        capital_rente_per_person=450000,
    )
    projected = project_retired_cohort_one_year(cohort, RATE)

    assert projected is not cohort
    assert cohort.age == 70
    assert cohort.capital_rente_per_person == pytest.approx(450000)


# ---------------------------------------------------------------------------
# D. Boundary tests
# ---------------------------------------------------------------------------


def test_active_projection_count_zero():
    cohort = ActiveCohort(
        cohort_id="ACT_ZERO",
        age=30,
        count=0,
        gross_salary_per_person=85000,
        capital_active_per_person=0,
    )
    projected = project_active_cohort_one_year(cohort, RATE)

    assert projected.age == 31
    assert projected.total_capital_active == pytest.approx(0.0)


def test_retired_projection_pension_exceeds_capital_capped_at_zero():
    cohort = RetiredCohort(
        cohort_id="RET_LOW",
        age=90,
        count=2,
        annual_pension_per_person=50000,
        capital_rente_per_person=10000,
    )
    projected = project_retired_cohort_one_year(cohort, RATE)

    # (10000 - 50000) * 1.0176 = -40704.0 -> capped at 0.0
    assert projected.capital_rente_per_person == pytest.approx(0.0)
    assert projected.total_capital_rente == pytest.approx(0.0)
    assert projected.age == 91


# ---------------------------------------------------------------------------
# E. Invalid input tests
# ---------------------------------------------------------------------------


def test_active_projection_rate_minus_one_raises():
    cohort = ActiveCohort(
        cohort_id="ACT_X",
        age=40,
        count=5,
        gross_salary_per_person=85000,
        capital_active_per_person=100000,
    )
    with pytest.raises(ValueError):
        project_active_cohort_one_year(cohort, -1.0)


def test_active_projection_rate_below_minus_one_raises():
    cohort = ActiveCohort(
        cohort_id="ACT_X",
        age=40,
        count=5,
        gross_salary_per_person=85000,
        capital_active_per_person=100000,
    )
    with pytest.raises(ValueError):
        project_active_cohort_one_year(cohort, -1.5)


def test_retired_projection_rate_minus_one_raises():
    cohort = RetiredCohort(
        cohort_id="RET_X",
        age=70,
        count=3,
        annual_pension_per_person=30000,
        capital_rente_per_person=400000,
    )
    with pytest.raises(ValueError):
        project_retired_cohort_one_year(cohort, -1.0)


def test_retired_projection_rate_below_minus_one_raises():
    cohort = RetiredCohort(
        cohort_id="RET_X",
        age=70,
        count=3,
        annual_pension_per_person=30000,
        capital_rente_per_person=400000,
    )
    with pytest.raises(ValueError):
        project_retired_cohort_one_year(cohort, -1.5)


# ---------------------------------------------------------------------------
# F. Portfolio projection
# ---------------------------------------------------------------------------


ACT_40 = ActiveCohort(
    cohort_id="ACT_40",
    age=40,
    count=10,
    gross_salary_per_person=85000,
    capital_active_per_person=120000,
)
ACT_55 = ActiveCohort(
    cohort_id="ACT_55",
    age=55,
    count=3,
    gross_salary_per_person=60000,
    capital_active_per_person=300000,
)
RET_70 = RetiredCohort(
    cohort_id="RET_70",
    age=70,
    count=5,
    annual_pension_per_person=30000,
    capital_rente_per_person=450000,
)

STANDARD_PORTFOLIO = BVGPortfolioState(
    projection_year=0,
    active_cohorts=(ACT_40, ACT_55),
    retired_cohorts=(RET_70,),
)


def test_standard_portfolio_projection_year():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.projection_year == 1


def test_standard_portfolio_projection_counts():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.active_count_total == 13
    assert p.retired_count_total == 5
    assert p.member_count_total == 18


def test_standard_portfolio_projection_active_cohort_ages():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.active_cohorts[0].age == 41
    assert p.active_cohorts[1].age == 56


def test_standard_portfolio_projection_retired_cohort_age():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.retired_cohorts[0].age == 71


def test_standard_portfolio_projection_act40_capital():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.active_cohorts[0].capital_active_per_person == pytest.approx(128039.5)
    assert p.active_cohorts[0].total_capital_active == pytest.approx(1_280_395.0)


def test_standard_portfolio_projection_act55_capital():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.active_cohorts[1].capital_active_per_person == pytest.approx(311449.5)
    assert p.active_cohorts[1].total_capital_active == pytest.approx(934348.5)


def test_standard_portfolio_projection_ret70_capital():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.retired_cohorts[0].capital_rente_per_person == pytest.approx(427392.0)
    assert p.retired_cohorts[0].total_capital_rente == pytest.approx(2_136_960.0)


def test_standard_portfolio_projection_totals():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.total_capital_active == pytest.approx(2_214_743.5)
    assert p.total_capital_rente == pytest.approx(2_136_960.0)
    assert p.total_capital == pytest.approx(4_351_703.5)


def test_standard_portfolio_projection_salary_and_pension_unchanged():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.annual_salary_total == pytest.approx(1_030_000.0)
    assert p.annual_pension_total == pytest.approx(150_000.0)


def test_standard_portfolio_projection_cohort_ids_preserved():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.cohort_ids == ("ACT_40", "ACT_55", "RET_70")


def test_portfolio_projection_returns_new_portfolio_object():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p is not STANDARD_PORTFOLIO


def test_portfolio_projection_returns_new_cohort_objects():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.active_cohorts[0] is not STANDARD_PORTFOLIO.active_cohorts[0]
    assert p.active_cohorts[1] is not STANDARD_PORTFOLIO.active_cohorts[1]
    assert p.retired_cohorts[0] is not STANDARD_PORTFOLIO.retired_cohorts[0]


def test_input_portfolio_year_unchanged():
    project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert STANDARD_PORTFOLIO.projection_year == 0


def test_input_active_cohort_ages_unchanged():
    project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert STANDARD_PORTFOLIO.active_cohorts[0].age == 40
    assert STANDARD_PORTFOLIO.active_cohorts[1].age == 55


def test_input_retired_cohort_age_unchanged():
    project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert STANDARD_PORTFOLIO.retired_cohorts[0].age == 70


def test_input_capital_values_unchanged():
    project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert STANDARD_PORTFOLIO.active_cohorts[0].capital_active_per_person == 120000
    assert STANDARD_PORTFOLIO.active_cohorts[1].capital_active_per_person == 300000
    assert STANDARD_PORTFOLIO.retired_cohorts[0].capital_rente_per_person == 450000


def test_empty_portfolio_projection_year():
    p = project_portfolio_one_year(BVGPortfolioState(), RATE, RATE)
    assert p.projection_year == 1


def test_empty_portfolio_all_zeros():
    p = project_portfolio_one_year(BVGPortfolioState(), RATE, RATE)
    assert p.active_count_total == 0
    assert p.retired_count_total == 0
    assert p.total_capital_active == pytest.approx(0.0)
    assert p.total_capital_rente == pytest.approx(0.0)
    assert p.total_capital == pytest.approx(0.0)


def test_empty_portfolio_cohort_ids():
    p = project_portfolio_one_year(BVGPortfolioState(), RATE, RATE)
    assert p.cohort_ids == ()


def test_different_rates_not_mixed():
    r_active = 0.02
    r_retired = 0.01

    portfolio = BVGPortfolioState(
        active_cohorts=(ACT_40,),
        retired_cohorts=(RET_70,),
    )
    p = project_portfolio_one_year(portfolio, r_active, r_retired)

    assert p.active_cohorts[0].capital_active_per_person == pytest.approx(128327.5)
    assert p.retired_cohorts[0].capital_rente_per_person == pytest.approx(424200.0)

    active_if_wrong_rate = 120000 * 1.01 + 5927.5
    assert p.active_cohorts[0].capital_active_per_person != pytest.approx(
        active_if_wrong_rate
    )


@pytest.mark.parametrize("bad_portfolio", [None, "not a portfolio", {"key": "val"}])
def test_invalid_portfolio_type_raises(bad_portfolio):
    with pytest.raises(TypeError):
        project_portfolio_one_year(bad_portfolio, RATE, RATE)


@pytest.mark.parametrize("bad_rate", [-1.0, -1.5, -2.0])
def test_invalid_active_rate_raises(bad_rate):
    with pytest.raises(ValueError):
        project_portfolio_one_year(STANDARD_PORTFOLIO, bad_rate, RATE)


@pytest.mark.parametrize("bad_rate", [-1.0, -1.5, -2.0])
def test_invalid_retiree_rate_raises(bad_rate):
    with pytest.raises(ValueError):
        project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, bad_rate)
