import pytest
from pk_alm.bvg.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg.projection import (
    project_active_cohort_one_year,
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
