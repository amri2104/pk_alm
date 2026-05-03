"""Pure distributional helpers for stochastic ALM outputs."""

from __future__ import annotations

import math
import numbers

import numpy as np


PERCENTILE_LEVELS = {
    "p5": 5.0,
    "p25": 25.0,
    "p50": 50.0,
    "p75": 75.0,
    "p95": 95.0,
}


def compute_percentiles(values: np.ndarray, axis: int) -> dict[str, np.ndarray]:
    """Return p5/p25/p50/p75/p95 percentiles along ``axis``."""
    arr = _validate_numeric_array(values, "values")
    if arr.size == 0:
        raise ValueError("values must not be empty")
    if isinstance(axis, bool) or not isinstance(axis, numbers.Integral):
        raise TypeError("axis must be int")
    axis_int = int(axis)
    if axis_int < -arr.ndim or axis_int >= arr.ndim:
        raise ValueError(f"axis out of bounds for {arr.ndim}D array: {axis_int}")
    return {
        name: np.percentile(arr, percentile, axis=axis_int)
        for name, percentile in PERCENTILE_LEVELS.items()
    }


def compute_var_es(values: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
    """Return lower-tail historical VaR and Expected Shortfall."""
    arr = _validate_numeric_array(values, "values").reshape(-1)
    if arr.size == 0:
        raise ValueError("values must not be empty")
    level = _validate_alpha(alpha)
    var = float(np.percentile(arr, level * 100.0))
    tail = arr[arr <= var]
    if tail.size == 0:
        tail = np.array([np.min(arr)])
    return var, float(np.mean(tail))


def compute_underfunding_probability(funding_ratio_paths: np.ndarray) -> float:
    """Return ``P(min funding ratio over a path < 1.0)`` for decimal ratios."""
    arr = _validate_numeric_array(funding_ratio_paths, "funding_ratio_paths")
    if arr.ndim != 2:
        raise ValueError("funding_ratio_paths must be 2D")
    if arr.shape[0] == 0 or arr.shape[1] == 0:
        raise ValueError("funding_ratio_paths must not be empty")
    underfunded = np.min(arr, axis=1) < 1.0
    return float(np.mean(underfunded))


def _validate_numeric_array(value: object, name: str) -> np.ndarray:
    if not isinstance(value, np.ndarray):
        raise TypeError(f"{name} must be numpy.ndarray, got {type(value).__name__}")
    try:
        arr = value.astype(float, copy=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must contain numeric values") from exc
    if np.isnan(arr).any():
        raise ValueError(f"{name} must not contain NaN")
    return arr


def _validate_alpha(value: object) -> float:
    if isinstance(value, bool):
        raise TypeError("alpha must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"alpha must be numeric, got {type(value).__name__}")
    alpha = float(value)
    if math.isnan(alpha):
        raise ValueError("alpha must not be NaN")
    if alpha <= 0.0 or alpha >= 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    return alpha
