"""Shared helpers for deterministic time-varying Stage-2C parameters."""

from __future__ import annotations

import math
import numbers
from collections.abc import Sequence


DynamicParameter = float | Sequence[float]


def resolve_parameter(
    value: DynamicParameter,
    t: int,
    horizon_years: int,
    name: str,
) -> float:
    """Resolve a scalar or sequence parameter for one projection step.

    ``t`` must be in ``[0, horizon_years - 1]``. Scalars are returned after
    validation. Sequences are forward-filled via
    ``values[min(t, len(values) - 1)]``.
    """
    step = _validate_non_bool_int(t, "t")
    horizon = _validate_non_bool_int(horizon_years, "horizon_years")
    parameter_name = _validate_name(name)
    if horizon < 0:
        raise ValueError(f"horizon_years must be >= 0, got {horizon}")
    if step < 0 or step >= horizon:
        raise ValueError(f"t must be in [0, {horizon - 1}], got {step}")

    if _is_sequence_parameter(value):
        values = _validate_parameter_sequence(value, horizon, parameter_name)
        return values[min(step, len(values) - 1)]
    return _validate_parameter_scalar(value, parameter_name)


def expand_parameter(
    value: DynamicParameter,
    horizon_years: int,
    name: str,
) -> tuple[float, ...]:
    """Return resolved values for ``t`` in ``[0, horizon_years - 1]``."""
    horizon = _validate_non_bool_int(horizon_years, "horizon_years")
    parameter_name = _validate_name(name)
    if horizon < 0:
        raise ValueError(f"horizon_years must be >= 0, got {horizon}")
    if horizon == 0:
        if _is_sequence_parameter(value):
            _validate_parameter_sequence(value, horizon, parameter_name)
        else:
            _validate_parameter_scalar(value, parameter_name)
        return ()
    return tuple(resolve_parameter(value, t, horizon, parameter_name) for t in range(horizon))


def _is_sequence_parameter(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _validate_parameter_sequence(
    value: Sequence[float],
    horizon_years: int,
    name: str,
) -> tuple[float, ...]:
    if len(value) == 0:
        raise ValueError(f"{name} sequence must contain at least one value")
    if len(value) > horizon_years:
        raise ValueError(
            f"{name} sequence length must be <= horizon_years "
            f"({horizon_years}), got {len(value)}"
        )
    return tuple(
        _validate_parameter_scalar(item, f"{name}[{i}]")
        for i, item in enumerate(value)
    )


def _validate_parameter_scalar(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    if fval < 0.0:
        raise ValueError(f"{name} must be >= 0, got {fval}")
    return fval


def _validate_non_bool_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


def _validate_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("name must be a non-empty string")
    return value
