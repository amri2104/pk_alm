import pytest
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState

# ---------------------------------------------------------------------------
# Fixtures
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


# ---------------------------------------------------------------------------
# A. Standard portfolio example
# ---------------------------------------------------------------------------


def test_portfolio_standard():
    p = BVGPortfolioState(
        projection_year=0,
        active_cohorts=(ACT_40, ACT_55),
        retired_cohorts=(RET_70,),
    )

    assert p.projection_year == 0
    assert p.active_count_total == 13
    assert p.retired_count_total == 5
    assert p.member_count_total == 18
    assert p.total_capital_active == pytest.approx(2_100_000.0)
    assert p.total_capital_rente == pytest.approx(2_250_000.0)
    assert p.total_capital == pytest.approx(4_350_000.0)
    assert p.annual_salary_total == pytest.approx(1_030_000.0)
    assert p.annual_age_credit_total == pytest.approx(77_783.5)
    assert p.annual_pension_total == pytest.approx(150_000.0)
    assert p.cohort_ids == ("ACT_40", "ACT_55", "RET_70")


def test_act55_cohort_properties():
    assert ACT_55.coordinated_salary_per_person == pytest.approx(34_275.0)
    assert ACT_55.age_credit_rate == pytest.approx(0.18)
    assert ACT_55.annual_age_credit_per_person == pytest.approx(6_169.5)
    assert ACT_55.total_capital_active == pytest.approx(900_000.0)
    assert ACT_55.annual_salary_total == pytest.approx(180_000.0)
    assert ACT_55.annual_age_credit_total == pytest.approx(18_508.5)


# ---------------------------------------------------------------------------
# B. Empty portfolio
# ---------------------------------------------------------------------------


def test_portfolio_empty():
    p = BVGPortfolioState()

    assert p.projection_year == 0
    assert p.active_count_total == 0
    assert p.retired_count_total == 0
    assert p.member_count_total == 0
    assert p.total_capital_active == pytest.approx(0.0)
    assert p.total_capital_rente == pytest.approx(0.0)
    assert p.total_capital == pytest.approx(0.0)
    assert p.annual_salary_total == pytest.approx(0.0)
    assert p.annual_age_credit_total == pytest.approx(0.0)
    assert p.annual_pension_total == pytest.approx(0.0)
    assert p.cohort_ids == ()


# ---------------------------------------------------------------------------
# C. List input is coerced to tuple
# ---------------------------------------------------------------------------


def test_list_input_coerced_to_tuple():
    p = BVGPortfolioState(
        active_cohorts=[ACT_40, ACT_55],
        retired_cohorts=[RET_70],
    )
    assert isinstance(p.active_cohorts, tuple)
    assert isinstance(p.retired_cohorts, tuple)


# ---------------------------------------------------------------------------
# D. Frozen immutability
# ---------------------------------------------------------------------------


def test_frozen_assignment_raises():
    p = BVGPortfolioState()
    with pytest.raises(Exception):
        p.projection_year = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# E. Invalid inputs — ValueError
# ---------------------------------------------------------------------------


def test_negative_projection_year_raises():
    with pytest.raises(ValueError):
        BVGPortfolioState(projection_year=-1)


def test_active_cohorts_none_raises():
    with pytest.raises(ValueError):
        BVGPortfolioState(active_cohorts=None)  # type: ignore[arg-type]


def test_retired_cohorts_none_raises():
    with pytest.raises(ValueError):
        BVGPortfolioState(retired_cohorts=None)  # type: ignore[arg-type]


def test_duplicate_id_within_active_raises():
    dup = ActiveCohort(
        cohort_id="ACT_40",
        age=35,
        count=2,
        gross_salary_per_person=70000,
        capital_active_per_person=50000,
    )
    with pytest.raises(ValueError, match="duplicate cohort_id"):
        BVGPortfolioState(active_cohorts=(ACT_40, dup))


def test_duplicate_id_within_retired_raises():
    dup = RetiredCohort(
        cohort_id="RET_70",
        age=75,
        count=1,
        annual_pension_per_person=20000,
        capital_rente_per_person=200000,
    )
    with pytest.raises(ValueError, match="duplicate cohort_id"):
        BVGPortfolioState(retired_cohorts=(RET_70, dup))


def test_duplicate_id_across_active_and_retired_raises():
    cross = RetiredCohort(
        cohort_id="ACT_40",  # same id as ACT_40
        age=70,
        count=2,
        annual_pension_per_person=25000,
        capital_rente_per_person=300000,
    )
    with pytest.raises(ValueError, match="duplicate cohort_id"):
        BVGPortfolioState(active_cohorts=(ACT_40,), retired_cohorts=(cross,))


# ---------------------------------------------------------------------------
# E. Invalid inputs — TypeError
# ---------------------------------------------------------------------------


def test_active_cohorts_contains_retired_raises():
    with pytest.raises(TypeError):
        BVGPortfolioState(active_cohorts=(RET_70,))  # type: ignore[arg-type]


def test_retired_cohorts_contains_active_raises():
    with pytest.raises(TypeError):
        BVGPortfolioState(retired_cohorts=(ACT_40,))  # type: ignore[arg-type]


def test_active_cohorts_contains_string_raises():
    with pytest.raises(TypeError):
        BVGPortfolioState(active_cohorts=("not_a_cohort",))  # type: ignore[arg-type]


def test_retired_cohorts_contains_dict_raises():
    with pytest.raises(TypeError):
        BVGPortfolioState(retired_cohorts=({"cohort_id": "X"},))  # type: ignore[arg-type]
