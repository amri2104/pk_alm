import math

import pytest

from pk_alm.bvg.dynamic_parameters import expand_parameter, resolve_parameter


def test_scalar_resolves_to_identity_for_any_step() -> None:
    assert resolve_parameter(0.0176, 0, 3, "rate") == pytest.approx(0.0176)
    assert resolve_parameter(0.0176, 2, 3, "rate") == pytest.approx(0.0176)


def test_single_element_sequence_forward_fills() -> None:
    assert resolve_parameter((0.0176,), 0, 4, "rate") == pytest.approx(0.0176)
    assert resolve_parameter((0.0176,), 3, 4, "rate") == pytest.approx(0.0176)


def test_sequence_length_equal_to_horizon_uses_step_value() -> None:
    values = (0.01, 0.02, 0.03)
    assert resolve_parameter(values, 0, 3, "rate") == pytest.approx(0.01)
    assert resolve_parameter(values, 2, 3, "rate") == pytest.approx(0.03)


def test_short_sequence_forward_fills_last_value() -> None:
    values = (0.01, 0.02)
    assert resolve_parameter(values, 0, 5, "rate") == pytest.approx(0.01)
    assert resolve_parameter(values, 1, 5, "rate") == pytest.approx(0.02)
    assert resolve_parameter(values, 4, 5, "rate") == pytest.approx(0.02)


@pytest.mark.parametrize("bad_value", [True, math.nan, -0.01])
def test_bool_nan_and_negative_values_are_rejected(bad_value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        resolve_parameter(bad_value, 0, 1, "rate")
    with pytest.raises((TypeError, ValueError)):
        resolve_parameter((bad_value,), 0, 1, "rate")


@pytest.mark.parametrize("bad_value", [(), [], "", "0.01", b"0.01"])
def test_empty_and_non_numeric_sequences_are_rejected(bad_value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        resolve_parameter(bad_value, 0, 1, "rate")


def test_overlong_sequence_is_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_parameter((0.01, 0.02), 0, 1, "rate")


@pytest.mark.parametrize("bad_t", [-1, 2, True])
def test_invalid_step_is_rejected(bad_t: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        resolve_parameter(0.01, bad_t, 2, "rate")  # type: ignore[arg-type]


def test_expand_parameter_shape_and_forward_fill() -> None:
    assert expand_parameter((0.01, 0.02), 5, "rate") == pytest.approx(
        (0.01, 0.02, 0.02, 0.02, 0.02)
    )


def test_expand_parameter_zero_horizon_allows_valid_scalar_only() -> None:
    assert expand_parameter(0.01, 0, "rate") == ()
    with pytest.raises(ValueError):
        expand_parameter((0.01,), 0, "rate")
