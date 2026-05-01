import pytest

from pk_alm.bvg.mortality import (
    EKF_0105,
    EKM_0105,
    MORTALITY_SOURCE_CAVEAT,
    expected_pension_payment,
    load_ek0105_table,
    survival_factor,
    survival_factors,
)


def test_load_supported_ek0105_tables() -> None:
    for table_id in (EKM_0105, EKF_0105):
        table = load_ek0105_table(table_id)
        assert table.table_id == table_id
        assert table.min_age == 0
        assert table.max_age == 127
        assert 0.0 <= table.qx(65) <= 1.0
        assert table.px(65) == pytest.approx(1.0 - table.qx(65))
        assert "BVG 2020 / VZ 2020" in table.source_caveat


def test_ek95_is_not_exposed() -> None:
    with pytest.raises(ValueError):
        load_ek0105_table("EKM 95")


def test_survival_factors_start_at_one_and_are_non_increasing() -> None:
    table = load_ek0105_table(EKF_0105)
    factors = survival_factors(table, start_age=65, horizon_years=20)
    assert factors[0] == pytest.approx(1.0)
    assert all(0.0 <= f <= 1.0 for f in factors)
    assert all(a >= b for a, b in zip(factors, factors[1:]))


def test_survival_factor_manual_product() -> None:
    table = load_ek0105_table(EKM_0105)
    expected = table.px(70) * table.px(71)
    assert survival_factor(table, 70, 2) == pytest.approx(expected)


def test_expected_pension_payment_is_negative_and_weighted() -> None:
    payoff = expected_pension_payment(
        count=5,
        annual_pension_per_person=30_000.0,
        survival_probability=0.8,
    )
    assert payoff == pytest.approx(-120_000.0)


def test_source_caveat_does_not_overclaim() -> None:
    assert "educational" in MORTALITY_SOURCE_CAVEAT
    assert "BVG 2020 / VZ 2020" in MORTALITY_SOURCE_CAVEAT
