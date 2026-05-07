import math

import pytest

from pk_alm.bvg_liability_engine.assumptions.rate_curves import (
    FlatRateCurve,
    StepRateCurve,
    expand,
    from_dynamic_parameter,
)


def test_scalar_builds_flat_curve() -> None:
    curve = from_dynamic_parameter(0.0176, start_year=2026, horizon_years=3)
    assert isinstance(curve, FlatRateCurve)
    assert curve.value_at(2026) == pytest.approx(0.0176)
    assert curve.value_at(2028) == pytest.approx(0.0176)


def test_single_element_sequence_forward_fills() -> None:
    curve = from_dynamic_parameter((0.0176,), start_year=2026, horizon_years=4)
    assert isinstance(curve, StepRateCurve)
    assert curve.value_at(2026) == pytest.approx(0.0176)
    assert curve.value_at(2029) == pytest.approx(0.0176)


def test_sequence_length_equal_to_horizon_uses_step_value() -> None:
    curve = from_dynamic_parameter((0.01, 0.02, 0.03), start_year=2026, horizon_years=3)
    assert curve.value_at(2026) == pytest.approx(0.01)
    assert curve.value_at(2028) == pytest.approx(0.03)


def test_short_sequence_forward_fills_last_value() -> None:
    curve = from_dynamic_parameter((0.01, 0.02), start_year=2026, horizon_years=5)
    assert curve.value_at(2026) == pytest.approx(0.01)
    assert curve.value_at(2027) == pytest.approx(0.02)
    assert curve.value_at(2030) == pytest.approx(0.02)


@pytest.mark.parametrize("bad_value", [True, math.nan])
def test_bool_and_nan_values_are_rejected(bad_value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        from_dynamic_parameter(bad_value, start_year=2026, horizon_years=1)
    with pytest.raises((TypeError, ValueError)):
        from_dynamic_parameter((bad_value,), start_year=2026, horizon_years=1)


@pytest.mark.parametrize("bad_value", [(), [], "", "0.01", b"0.01"])
def test_empty_and_non_numeric_sequences_are_rejected(bad_value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        from_dynamic_parameter(bad_value, start_year=2026, horizon_years=1)


def test_overlong_sequence_is_rejected() -> None:
    with pytest.raises(ValueError):
        from_dynamic_parameter((0.01, 0.02), start_year=2026, horizon_years=1)


def test_expand_shape_and_forward_fill() -> None:
    curve = from_dynamic_parameter((0.01, 0.02), start_year=2026, horizon_years=5)
    assert expand(curve, start_year=2026, horizon_years=5) == pytest.approx(
        (0.01, 0.02, 0.02, 0.02, 0.02)
    )


def test_expand_zero_horizon_allows_valid_curve() -> None:
    curve = from_dynamic_parameter(0.01, start_year=2026, horizon_years=0)
    assert expand(curve, start_year=2026, horizon_years=0) == ()
