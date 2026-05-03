import numpy as np
import pytest

from pk_alm.analytics.distributional import (
    compute_percentiles,
    compute_underfunding_probability,
    compute_var_es,
)


def test_compute_percentiles_known_values_axis_zero() -> None:
    values = np.array(
        [
            [1.0, 10.0],
            [2.0, 20.0],
            [3.0, 30.0],
            [4.0, 40.0],
            [5.0, 50.0],
        ]
    )
    result = compute_percentiles(values, axis=0)
    assert result["p50"] == pytest.approx([3.0, 30.0])
    assert result["p5"] == pytest.approx([1.2, 12.0])
    assert result["p95"] == pytest.approx([4.8, 48.0])


def test_compute_var_es_lower_tail_known_values() -> None:
    values = np.array([1.0, 2.0, 3.0, 4.0, 100.0])
    var, es = compute_var_es(values, alpha=0.2)
    assert var == pytest.approx(1.8)
    assert es == pytest.approx(1.0)


def test_all_same_values_are_stable() -> None:
    values = np.full((4, 3), 7.0)
    percentiles = compute_percentiles(values, axis=0)
    assert percentiles["p5"] == pytest.approx([7.0, 7.0, 7.0])
    var, es = compute_var_es(values[:, 0], alpha=0.05)
    assert var == pytest.approx(7.0)
    assert es == pytest.approx(7.0)


def test_single_value_var_es() -> None:
    var, es = compute_var_es(np.array([0.93]))
    assert var == pytest.approx(0.93)
    assert es == pytest.approx(0.93)


def test_underfunding_probability() -> None:
    paths = np.array(
        [
            [1.10, 1.05, 1.00],
            [1.10, 0.99, 1.02],
            [0.95, 1.02, 1.03],
            [1.01, 1.02, 1.03],
        ]
    )
    assert compute_underfunding_probability(paths) == pytest.approx(0.5)


@pytest.mark.parametrize("bad_values", [np.array([]), np.array([np.nan])])
def test_invalid_values_rejected(bad_values: np.ndarray) -> None:
    with pytest.raises(ValueError):
        compute_var_es(bad_values)
