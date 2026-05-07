"""Unified BVG engine assumption container.

A single frozen dataclass capturing every input the generic engine needs
beyond the initial portfolio state. Replaces the per-stage positional
kwarg surface of the legacy engine variants.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass, field
from typing import Literal

from pk_alm.bvg_liability_engine.assumptions.mortality_assumptions import (
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.assumptions.rate_curves import (
    FlatRateCurve,
    RateCurve,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import (
    EntryPolicy,
    NoEntryPolicy,
)

CashflowFrequency = Literal["annual", "monthly"]
CashflowTiming = Literal["year_end"]


def _check_int(value: object, name: str, *, min_value: int | None = None) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def _check_real(value: object, name: str, *, min_value: float | None = None) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    if min_value is not None and fval < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {fval}")
    return fval


def _check_curve(value: object, name: str) -> RateCurve:
    if not isinstance(value, RateCurve):
        raise TypeError(
            f"{name} must implement RateCurve.value_at, got {type(value).__name__}"
        )
    return value


@dataclass(frozen=True)
class BVGAssumptions:
    """Frozen container of every assumption the BVG engine requires.

    Rate fields accept any :class:`RateCurve` implementation; pass
    :class:`FlatRateCurve` for constant inputs.
    """

    start_year: int = 2026
    horizon_years: int = 12
    retirement_age: int = 65
    valuation_terminal_age: int = 90

    active_crediting_rate: RateCurve = field(default_factory=lambda: FlatRateCurve(0.0125))
    technical_discount_rate: RateCurve = field(default_factory=lambda: FlatRateCurve(0.0176))
    economic_discount_rate: RateCurve = field(default_factory=lambda: FlatRateCurve(0.0100))
    salary_growth_rate: RateCurve = field(default_factory=lambda: FlatRateCurve(0.015))
    retired_interest_rate: RateCurve = field(default_factory=lambda: FlatRateCurve(0.0176))

    turnover_rate: float = 0.02
    conversion_rate: RateCurve = field(default_factory=lambda: FlatRateCurve(0.054))
    capital_withdrawal_fraction: float = 0.35
    contribution_multiplier: float = 1.4

    cashflow_frequency: CashflowFrequency = "annual"
    cashflow_timing: CashflowTiming = "year_end"

    mortality: MortalityAssumptions = field(default_factory=MortalityAssumptions)
    entry_policy: EntryPolicy = field(default_factory=NoEntryPolicy)

    def __post_init__(self) -> None:
        _check_int(self.start_year, "start_year")
        _check_int(self.horizon_years, "horizon_years", min_value=0)
        _check_int(self.retirement_age, "retirement_age", min_value=1)
        _check_int(self.valuation_terminal_age, "valuation_terminal_age", min_value=1)
        if self.valuation_terminal_age < self.retirement_age:
            raise ValueError(
                "valuation_terminal_age must be >= retirement_age, got "
                f"{self.valuation_terminal_age} < {self.retirement_age}"
            )

        _check_curve(self.active_crediting_rate, "active_crediting_rate")
        _check_curve(self.technical_discount_rate, "technical_discount_rate")
        _check_curve(self.economic_discount_rate, "economic_discount_rate")
        _check_curve(self.salary_growth_rate, "salary_growth_rate")
        _check_curve(self.retired_interest_rate, "retired_interest_rate")
        _check_curve(self.conversion_rate, "conversion_rate")

        turnover = _check_real(self.turnover_rate, "turnover_rate", min_value=0.0)
        if turnover > 1.0:
            raise ValueError(f"turnover_rate must be <= 1, got {turnover}")
        object.__setattr__(self, "turnover_rate", turnover)

        fraction = _check_real(
            self.capital_withdrawal_fraction,
            "capital_withdrawal_fraction",
            min_value=0.0,
        )
        if fraction > 1.0:
            raise ValueError(
                f"capital_withdrawal_fraction must be <= 1, got {fraction}"
            )
        object.__setattr__(self, "capital_withdrawal_fraction", fraction)

        multiplier = _check_real(
            self.contribution_multiplier,
            "contribution_multiplier",
            min_value=0.0,
        )
        object.__setattr__(self, "contribution_multiplier", multiplier)

        if self.cashflow_frequency not in ("annual", "monthly"):
            raise ValueError(
                f"cashflow_frequency must be 'annual' or 'monthly', got {self.cashflow_frequency!r}"
            )
        if self.cashflow_timing not in ("year_end",):
            raise ValueError(
                f"cashflow_timing must be 'year_end', got {self.cashflow_timing!r}"
            )

        if not isinstance(self.mortality, MortalityAssumptions):
            raise TypeError(
                "mortality must be MortalityAssumptions, got "
                f"{type(self.mortality).__name__}"
            )
        if not isinstance(self.entry_policy, EntryPolicy):
            raise TypeError(
                "entry_policy must implement EntryPolicy, got "
                f"{type(self.entry_policy).__name__}"
            )

    @property
    def periods_per_year(self) -> int:
        return 12 if self.cashflow_frequency == "monthly" else 1
