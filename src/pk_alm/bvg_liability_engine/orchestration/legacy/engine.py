"""Stage-1 BVG engine adapter.

Thin wrapper that translates the legacy positional-kwarg surface into a
:class:`BVGAssumptions` and calls the generic
:func:`pk_alm.bvg_liability_engine.orchestration.generic_engine.run_bvg_engine`.
The return type :class:`BVGEngineResult` preserves the legacy two-field shape
(``portfolio_states``, ``cashflows``) so existing callers are unaffected.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions.bvg_assumptions import BVGAssumptions
from pk_alm.bvg_liability_engine.assumptions.mortality_assumptions import (
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.assumptions.rate_curves import FlatRateCurve
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.generic_engine import run_bvg_engine as _run_generic
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import NoEntryPolicy
from pk_alm.cashflows.schema import validate_cashflow_dataframe


def _validate_non_bool_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


def _validate_non_bool_real(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    return fval


@dataclass(frozen=True)
class BVGEngineResult:
    """Frozen container for one Stage-1 BVG engine run (legacy shape)."""

    portfolio_states: tuple[BVGPortfolioState, ...]
    cashflows: pd.DataFrame

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_states, tuple):
            raise TypeError(
                f"portfolio_states must be a tuple, got {type(self.portfolio_states).__name__}"
            )
        if len(self.portfolio_states) == 0:
            raise ValueError("portfolio_states must not be empty")
        for i, s in enumerate(self.portfolio_states):
            if not isinstance(s, BVGPortfolioState):
                raise TypeError(
                    f"portfolio_states[{i}] must be BVGPortfolioState, "
                    f"got {type(s).__name__}"
                )
        if not isinstance(self.cashflows, pd.DataFrame):
            raise TypeError(
                f"cashflows must be a pandas DataFrame, got {type(self.cashflows).__name__}"
            )
        validate_cashflow_dataframe(self.cashflows)

    @property
    def initial_state(self) -> BVGPortfolioState:
        return self.portfolio_states[0]

    @property
    def final_state(self) -> BVGPortfolioState:
        return self.portfolio_states[-1]

    @property
    def horizon_years(self) -> int:
        return len(self.portfolio_states) - 1

    @property
    def cashflow_count(self) -> int:
        return len(self.cashflows)


def run_bvg_engine(
    initial_state: BVGPortfolioState,
    horizon_years: int,
    active_interest_rate: float,
    retired_interest_rate: float,
    contribution_multiplier: float = 1.0,
    start_year: int = 2026,
    retirement_age: int = 65,
    capital_withdrawal_fraction: float = 0.35,
    conversion_rate: float = 0.068,
) -> BVGEngineResult:
    """Stage-1 entry point. Adapter over the generic engine."""
    if not isinstance(initial_state, BVGPortfolioState):
        raise TypeError(
            f"initial_state must be a BVGPortfolioState, got {type(initial_state).__name__}"
        )
    horizon_years = _validate_non_bool_int(horizon_years, "horizon_years")
    if horizon_years < 0:
        raise ValueError(f"horizon_years must be >= 0, got {horizon_years}")

    active_interest_rate = _validate_non_bool_real(
        active_interest_rate, "active_interest_rate"
    )
    if active_interest_rate <= -1:
        raise ValueError(
            f"active_interest_rate must be > -1, got {active_interest_rate}"
        )
    retired_interest_rate = _validate_non_bool_real(
        retired_interest_rate, "retired_interest_rate"
    )
    if retired_interest_rate <= -1:
        raise ValueError(
            f"retired_interest_rate must be > -1, got {retired_interest_rate}"
        )
    contribution_multiplier = _validate_non_bool_real(
        contribution_multiplier, "contribution_multiplier"
    )
    if contribution_multiplier < 0:
        raise ValueError(
            f"contribution_multiplier must be >= 0, got {contribution_multiplier}"
        )
    start_year = _validate_non_bool_int(start_year, "start_year")
    if start_year < 2000:
        raise ValueError(f"start_year must be >= 2000, got {start_year}")
    retirement_age = _validate_non_bool_int(retirement_age, "retirement_age")
    if retirement_age < 0:
        raise ValueError(f"retirement_age must be >= 0, got {retirement_age}")
    capital_withdrawal_fraction = _validate_non_bool_real(
        capital_withdrawal_fraction, "capital_withdrawal_fraction"
    )
    if capital_withdrawal_fraction < 0.0 or capital_withdrawal_fraction > 1.0:
        raise ValueError(
            f"capital_withdrawal_fraction must be in [0.0, 1.0], "
            f"got {capital_withdrawal_fraction}"
        )
    conversion_rate = _validate_non_bool_real(conversion_rate, "conversion_rate")
    if conversion_rate < 0:
        raise ValueError(f"conversion_rate must be >= 0, got {conversion_rate}")

    assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon_years,
        retirement_age=max(retirement_age, 1),
        valuation_terminal_age=max(retirement_age, 1) + 1,
        active_crediting_rate=FlatRateCurve(active_interest_rate),
        retired_interest_rate=FlatRateCurve(retired_interest_rate),
        technical_discount_rate=FlatRateCurve(retired_interest_rate),
        economic_discount_rate=FlatRateCurve(retired_interest_rate),
        salary_growth_rate=FlatRateCurve(0.0),
        conversion_rate=FlatRateCurve(conversion_rate),
        turnover_rate=0.0,
        capital_withdrawal_fraction=capital_withdrawal_fraction,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=NoEntryPolicy(),
    )
    new_result = _run_generic(initial_state=initial_state, assumptions=assumptions)
    return BVGEngineResult(
        portfolio_states=new_result.portfolio_states,
        cashflows=new_result.cashflows,
    )
