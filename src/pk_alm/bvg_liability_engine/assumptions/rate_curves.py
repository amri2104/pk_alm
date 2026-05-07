"""Rate-curve abstraction for BVG engine assumptions.

Replaces the legacy ``DynamicParameter`` (scalar | sequence) with explicit
curve types. Engine code calls ``curve.value_at(year, period)`` once per
projection step. ``period`` is the intra-year sub-step index (0 for annual
mode; 0..11 for monthly mode).
"""

from __future__ import annotations

import math
import numbers
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class RateCurve(Protocol):
    """A deterministic rate curve indexed by calendar year and intra-year period."""

    def value_at(self, year: int, period: int = 0) -> float:
        ...


def _validate_rate(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    return fval


def _validate_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


@dataclass(frozen=True)
class FlatRateCurve:
    """Constant rate across all years and periods."""

    rate: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "rate", _validate_rate(self.rate, "rate"))

    def value_at(self, year: int, period: int = 0) -> float:
        _validate_int(year, "year")
        _validate_int(period, "period")
        return self.rate


@dataclass(frozen=True)
class StepRateCurve:
    """Piecewise-constant rate by calendar year.

    ``rates`` maps a calendar year to a rate. Years before the first key use
    the first key's rate; years between keys forward-fill from the most
    recent key. Optionally ``period_rates`` overrides per-(year, period).
    """

    rates: Mapping[int, float]

    def __post_init__(self) -> None:
        if not isinstance(self.rates, Mapping):
            raise TypeError(
                f"rates must be a mapping, got {type(self.rates).__name__}"
            )
        if not self.rates:
            raise ValueError("rates must not be empty")
        clean: dict[int, float] = {}
        for k, v in self.rates.items():
            clean[_validate_int(k, "year key")] = _validate_rate(v, f"rate[{k}]")
        object.__setattr__(self, "rates", dict(sorted(clean.items())))

    def value_at(self, year: int, period: int = 0) -> float:
        _validate_int(year, "year")
        _validate_int(period, "period")
        keys = sorted(self.rates)
        if year <= keys[0]:
            return self.rates[keys[0]]
        last = keys[0]
        for k in keys:
            if k <= year:
                last = k
            else:
                break
        return self.rates[last]


@dataclass(frozen=True)
class CallableRateCurve:
    """Rate curve backed by an arbitrary ``(year, period) -> float`` callable."""

    fn: Callable[[int, int], float]

    def value_at(self, year: int, period: int = 0) -> float:
        _validate_int(year, "year")
        _validate_int(period, "period")
        return _validate_rate(self.fn(year, period), "callable rate")


def from_dynamic_parameter(
    value: float | Sequence[float],
    *,
    start_year: int,
    horizon_years: int,
) -> RateCurve:
    """Build a RateCurve from a legacy ``DynamicParameter``.

    Scalars become :class:`FlatRateCurve`. Sequences become a
    :class:`StepRateCurve` keyed by ``start_year + offset``; the last value is
    forward-filled by :class:`StepRateCurve` semantics.
    """
    _validate_int(start_year, "start_year")
    horizon = _validate_int(horizon_years, "horizon_years")
    if horizon < 0:
        raise ValueError(f"horizon_years must be >= 0, got {horizon}")

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) == 0:
            raise ValueError("rate sequence must not be empty")
        if len(value) > horizon:
            raise ValueError(
                f"rate sequence length ({len(value)}) must be <= horizon_years ({horizon})"
            )
        rates = {start_year + i: float(v) for i, v in enumerate(value)}
        return StepRateCurve(rates=rates)
    return FlatRateCurve(rate=float(value))


def expand(curve: RateCurve, *, start_year: int, horizon_years: int) -> tuple[float, ...]:
    """Materialize a curve over ``[start_year, start_year + horizon_years)``."""
    horizon = _validate_int(horizon_years, "horizon_years")
    if horizon < 0:
        raise ValueError(f"horizon_years must be >= 0, got {horizon}")
    return tuple(curve.value_at(start_year + t, 0) for t in range(horizon))
