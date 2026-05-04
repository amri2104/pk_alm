import pytest
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort


# ---------------------------------------------------------------------------
# A. ActiveCohort standard example
# ---------------------------------------------------------------------------


def test_active_cohort_standard():
    c = ActiveCohort(
        cohort_id="ACT_40",
        age=40,
        count=10,
        gross_salary_per_person=85000,
        capital_active_per_person=120000,
    )
    assert c.cohort_id == "ACT_40"
    assert c.coordinated_salary_per_person == pytest.approx(59275.0)
    assert c.age_credit_rate == pytest.approx(0.10)
    assert c.annual_age_credit_per_person == pytest.approx(5927.5)
    assert c.total_capital_active == pytest.approx(1200000.0)
    assert c.annual_salary_total == pytest.approx(850000.0)
    assert c.annual_age_credit_total == pytest.approx(59275.0)


# ---------------------------------------------------------------------------
# B. RetiredCohort standard example
# ---------------------------------------------------------------------------


def test_retired_cohort_standard():
    c = RetiredCohort(
        cohort_id="RET_70",
        age=70,
        count=5,
        annual_pension_per_person=30000,
        capital_rente_per_person=450000,
    )
    assert c.cohort_id == "RET_70"
    assert c.annual_pension_total == pytest.approx(150000.0)
    assert c.total_capital_rente == pytest.approx(2250000.0)


# ---------------------------------------------------------------------------
# C. Boundary tests
# ---------------------------------------------------------------------------


def test_active_cohort_count_zero():
    c = ActiveCohort(
        cohort_id="ACT_ZERO",
        age=40,
        count=0,
        gross_salary_per_person=85000,
        capital_active_per_person=120000,
    )
    assert c.total_capital_active == pytest.approx(0.0)
    assert c.annual_salary_total == pytest.approx(0.0)
    assert c.annual_age_credit_total == pytest.approx(0.0)


def test_retired_cohort_count_zero():
    c = RetiredCohort(
        cohort_id="RET_ZERO",
        age=70,
        count=0,
        annual_pension_per_person=30000,
        capital_rente_per_person=450000,
    )
    assert c.annual_pension_total == pytest.approx(0.0)
    assert c.total_capital_rente == pytest.approx(0.0)


def test_active_cohort_age_zero():
    c = ActiveCohort(
        cohort_id="ACT_INFANT",
        age=0,
        count=1,
        gross_salary_per_person=50000,
        capital_active_per_person=0,
    )
    assert c.age == 0
    assert c.age_credit_rate == pytest.approx(0.00)


def test_active_cohort_below_entry_threshold():
    c = ActiveCohort(
        cohort_id="ACT_LOW",
        age=30,
        count=3,
        gross_salary_per_person=10000,
        capital_active_per_person=5000,
    )
    assert c.coordinated_salary_per_person == pytest.approx(0.0)
    assert c.annual_age_credit_per_person == pytest.approx(0.0)


@pytest.mark.parametrize(
    "age, expected_rate",
    [
        (24, 0.00),
        (25, 0.07),
        (35, 0.10),
        (45, 0.15),
        (55, 0.18),
        (65, 0.00),
    ],
)
def test_active_cohort_age_credit_rate_boundaries(age, expected_rate):
    c = ActiveCohort(
        cohort_id=f"ACT_{age}",
        age=age,
        count=1,
        gross_salary_per_person=85000,
        capital_active_per_person=0,
    )
    assert c.age_credit_rate == pytest.approx(expected_rate)


# ---------------------------------------------------------------------------
# D. Invalid input tests — ActiveCohort
# ---------------------------------------------------------------------------


def test_active_cohort_empty_cohort_id():
    with pytest.raises(ValueError):
        ActiveCohort(
            cohort_id="",
            age=40,
            count=10,
            gross_salary_per_person=85000,
            capital_active_per_person=120000,
        )


def test_active_cohort_whitespace_cohort_id():
    with pytest.raises(ValueError):
        ActiveCohort(
            cohort_id="   ",
            age=40,
            count=10,
            gross_salary_per_person=85000,
            capital_active_per_person=120000,
        )


def test_active_cohort_negative_age():
    with pytest.raises(ValueError):
        ActiveCohort(
            cohort_id="ACT_X",
            age=-1,
            count=10,
            gross_salary_per_person=85000,
            capital_active_per_person=120000,
        )


def test_active_cohort_negative_count():
    with pytest.raises(ValueError):
        ActiveCohort(
            cohort_id="ACT_X",
            age=40,
            count=-1,
            gross_salary_per_person=85000,
            capital_active_per_person=120000,
        )


def test_active_cohort_negative_salary():
    with pytest.raises(ValueError):
        ActiveCohort(
            cohort_id="ACT_X",
            age=40,
            count=10,
            gross_salary_per_person=-1,
            capital_active_per_person=120000,
        )


def test_active_cohort_negative_capital():
    with pytest.raises(ValueError):
        ActiveCohort(
            cohort_id="ACT_X",
            age=40,
            count=10,
            gross_salary_per_person=85000,
            capital_active_per_person=-1,
        )


# ---------------------------------------------------------------------------
# D. Invalid input tests — RetiredCohort
# ---------------------------------------------------------------------------


def test_retired_cohort_empty_cohort_id():
    with pytest.raises(ValueError):
        RetiredCohort(
            cohort_id="",
            age=70,
            count=5,
            annual_pension_per_person=30000,
            capital_rente_per_person=450000,
        )


def test_retired_cohort_whitespace_cohort_id():
    with pytest.raises(ValueError):
        RetiredCohort(
            cohort_id="  ",
            age=70,
            count=5,
            annual_pension_per_person=30000,
            capital_rente_per_person=450000,
        )


def test_retired_cohort_negative_age():
    with pytest.raises(ValueError):
        RetiredCohort(
            cohort_id="RET_X",
            age=-1,
            count=5,
            annual_pension_per_person=30000,
            capital_rente_per_person=450000,
        )


def test_retired_cohort_negative_count():
    with pytest.raises(ValueError):
        RetiredCohort(
            cohort_id="RET_X",
            age=70,
            count=-1,
            annual_pension_per_person=30000,
            capital_rente_per_person=450000,
        )


def test_retired_cohort_negative_pension():
    with pytest.raises(ValueError):
        RetiredCohort(
            cohort_id="RET_X",
            age=70,
            count=5,
            annual_pension_per_person=-1,
            capital_rente_per_person=450000,
        )


def test_retired_cohort_negative_capital_rente():
    with pytest.raises(ValueError):
        RetiredCohort(
            cohort_id="RET_X",
            age=70,
            count=5,
            annual_pension_per_person=30000,
            capital_rente_per_person=-1,
        )
