import pytest
from pk_alm.bvg.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.portfolio_projection import project_portfolio_one_year

RATE = 0.0176

# ---------------------------------------------------------------------------
# Shared cohorts
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


# ---------------------------------------------------------------------------
# A. Standard portfolio projection
# ---------------------------------------------------------------------------


def test_standard_projection_year():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.projection_year == 1


def test_standard_projection_counts():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.active_count_total == 13
    assert p.retired_count_total == 5
    assert p.member_count_total == 18


def test_standard_projection_active_cohort_ages():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.active_cohorts[0].age == 41
    assert p.active_cohorts[1].age == 56


def test_standard_projection_retired_cohort_age():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.retired_cohorts[0].age == 71


def test_standard_projection_act40_capital():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    # 120000 * 1.0176 + 5927.5 = 128039.5
    assert p.active_cohorts[0].capital_active_per_person == pytest.approx(128039.5)
    assert p.active_cohorts[0].total_capital_active == pytest.approx(1_280_395.0)


def test_standard_projection_act55_capital():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    # 300000 * 1.0176 + 6169.5 = 311449.5
    assert p.active_cohorts[1].capital_active_per_person == pytest.approx(311449.5)
    assert p.active_cohorts[1].total_capital_active == pytest.approx(934348.5)


def test_standard_projection_ret70_capital():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    # (450000 - 30000) * 1.0176 = 427392.0
    assert p.retired_cohorts[0].capital_rente_per_person == pytest.approx(427392.0)
    assert p.retired_cohorts[0].total_capital_rente == pytest.approx(2_136_960.0)


def test_standard_projection_totals():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.total_capital_active == pytest.approx(2_214_743.5)
    assert p.total_capital_rente == pytest.approx(2_136_960.0)
    assert p.total_capital == pytest.approx(4_351_703.5)


def test_standard_projection_salary_and_pension_unchanged():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    # salary and pension per person do not change in a one-year projection
    assert p.annual_salary_total == pytest.approx(1_030_000.0)
    assert p.annual_pension_total == pytest.approx(150_000.0)


def test_standard_projection_cohort_ids_preserved():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p.cohort_ids == ("ACT_40", "ACT_55", "RET_70")


# ---------------------------------------------------------------------------
# B. Immutability
# ---------------------------------------------------------------------------


def test_projection_returns_new_portfolio_object():
    p = project_portfolio_one_year(STANDARD_PORTFOLIO, RATE, RATE)
    assert p is not STANDARD_PORTFOLIO


def test_projection_returns_new_cohort_objects():
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


# ---------------------------------------------------------------------------
# C. Empty portfolio
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# D. Different rates
# ---------------------------------------------------------------------------


def test_different_rates_not_mixed():
    r_active = 0.02
    r_retired = 0.01

    portfolio = BVGPortfolioState(
        active_cohorts=(ACT_40,),
        retired_cohorts=(RET_70,),
    )
    p = project_portfolio_one_year(portfolio, r_active, r_retired)

    # ACT_40 must use 0.02: 120000 * 1.02 + 5927.5 = 128327.5
    assert p.active_cohorts[0].capital_active_per_person == pytest.approx(128327.5)

    # RET_70 must use 0.01: (450000 - 30000) * 1.01 = 424200.0
    assert p.retired_cohorts[0].capital_rente_per_person == pytest.approx(424200.0)

    # Sanity: the active value must not equal what 0.01 would produce
    active_if_wrong_rate = 120000 * 1.01 + 5927.5
    assert p.active_cohorts[0].capital_active_per_person != pytest.approx(
        active_if_wrong_rate
    )


# ---------------------------------------------------------------------------
# E. Invalid inputs
# ---------------------------------------------------------------------------


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
