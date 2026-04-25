import pytest
from pk_alm.bvg.formulas import (
    MAX_COORDINATED_SALARY,
    MIN_COORDINATED_SALARY,
    calculate_age_credit,
    calculate_annuity_due,
    calculate_annuity_immediate,
    calculate_coordinated_salary,
    calculate_pensionierungsverlust,
    calculate_retiree_pv,
    get_age_credit_rate,
)


# ---------------------------------------------------------------------------
# calculate_coordinated_salary
# ---------------------------------------------------------------------------


def test_coordinated_salary_spec_example():
    assert calculate_coordinated_salary(85000) == 59275.0


def test_coordinated_salary_below_entry_threshold():
    assert calculate_coordinated_salary(10000) == 0.0


def test_coordinated_salary_just_below_entry_threshold():
    # 22049 < ENTRY_THRESHOLD → not insured
    assert calculate_coordinated_salary(22049.0) == 0.0


def test_coordinated_salary_at_entry_threshold():
    # 22050 >= ENTRY_THRESHOLD; min salary applies even though 22050 - 25725 < 0
    assert calculate_coordinated_salary(22050.0) == MIN_COORDINATED_SALARY


def test_coordinated_salary_very_high_salary():
    assert calculate_coordinated_salary(200000) == MAX_COORDINATED_SALARY


def test_coordinated_salary_invalid():
    with pytest.raises(ValueError):
        calculate_coordinated_salary(-1)


# ---------------------------------------------------------------------------
# get_age_credit_rate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "age, expected",
    [
        (24, 0.00),
        (25, 0.07),
        (34, 0.07),
        (35, 0.10),
        (44, 0.10),
        (45, 0.15),
        (54, 0.15),
        (55, 0.18),
        (64, 0.18),
        (65, 0.00),
        (70, 0.00),
    ],
)
def test_age_credit_rate_brackets(age, expected):
    assert get_age_credit_rate(age) == expected


def test_age_credit_rate_spec_example():
    assert get_age_credit_rate(40) == 0.10


def test_age_credit_rate_invalid():
    with pytest.raises(ValueError):
        get_age_credit_rate(-1)


# ---------------------------------------------------------------------------
# calculate_age_credit
# ---------------------------------------------------------------------------


def test_age_credit_spec_example():
    assert calculate_age_credit(59275, 40) == pytest.approx(5927.5)


def test_age_credit_invalid_salary():
    with pytest.raises(ValueError):
        calculate_age_credit(-1, 40)


def test_age_credit_invalid_age():
    with pytest.raises(ValueError):
        calculate_age_credit(1000, -1)


# ---------------------------------------------------------------------------
# calculate_annuity_immediate
# ---------------------------------------------------------------------------


def test_annuity_immediate_zero_rate():
    assert calculate_annuity_immediate(10, 0.0) == 10.0


def test_annuity_immediate_positive_rate():
    result = calculate_annuity_immediate(25, 0.0176)
    # annuity_due / (1+r) = 20.438381859657717 / 1.0176 ≈ 20.08489
    assert result == pytest.approx(20.08488783378313, rel=1e-8)


def test_annuity_immediate_invalid_n_zero():
    with pytest.raises(ValueError):
        calculate_annuity_immediate(0, 0.05)


def test_annuity_immediate_invalid_n_negative():
    with pytest.raises(ValueError):
        calculate_annuity_immediate(-1, 0.05)


def test_annuity_immediate_invalid_rate_at_minus_one():
    with pytest.raises(ValueError):
        calculate_annuity_immediate(10, -1.0)


def test_annuity_immediate_invalid_rate_below_minus_one():
    with pytest.raises(ValueError):
        calculate_annuity_immediate(10, -2.0)


# ---------------------------------------------------------------------------
# calculate_annuity_due
# ---------------------------------------------------------------------------


def test_annuity_due_spec_example():
    result = calculate_annuity_due(25, 0.0176)
    assert result == pytest.approx(20.4383818597, rel=1e-8)


def test_annuity_due_zero_rate():
    # With zero rate annuity-due == annuity-immediate == n
    assert calculate_annuity_due(10, 0.0) == 10.0


def test_annuity_due_invalid_n():
    with pytest.raises(ValueError):
        calculate_annuity_due(0, 0.05)


def test_annuity_due_invalid_rate():
    with pytest.raises(ValueError):
        calculate_annuity_due(10, -1.5)


# ---------------------------------------------------------------------------
# calculate_retiree_pv
# ---------------------------------------------------------------------------


def test_retiree_pv_spec_example():
    result = calculate_retiree_pv(5000, 25, 0.0176)
    assert result == pytest.approx(102191.909298, rel=1e-8)


def test_retiree_pv_invalid_pension():
    with pytest.raises(ValueError):
        calculate_retiree_pv(-1, 25, 0.0176)


def test_retiree_pv_invalid_n():
    with pytest.raises(ValueError):
        calculate_retiree_pv(5000, 0, 0.0176)


def test_retiree_pv_invalid_rate():
    with pytest.raises(ValueError):
        calculate_retiree_pv(5000, 25, -1.5)


# ---------------------------------------------------------------------------
# calculate_pensionierungsverlust
# ---------------------------------------------------------------------------


def test_pensionierungsverlust_spec_example():
    result = calculate_pensionierungsverlust(102191.909298, 85000)
    assert result == pytest.approx(17191.909298, abs=1e-4)


def test_pensionierungsverlust_zero_loss():
    assert calculate_pensionierungsverlust(100000, 100000) == pytest.approx(0.0)


def test_pensionierungsverlust_negative():
    # Retiree PV < capital: fund gains (negative loss)
    assert calculate_pensionierungsverlust(80000, 100000) == pytest.approx(-20000.0)
