"""Stage-2 BVG engine adapter over the generic engine.

Translates Stage-2 positional kwargs into a :class:`BVGAssumptions` and
calls the generic engine. Returns a :class:`Stage2EngineResult` rebuilt
from the generic engine's :class:`BVGYearStep` sequence.
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
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import (
    EntryAssumptions,
    get_default_entry_assumptions,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import (
    FixedEntryPolicy,
)
from pk_alm.bvg_liability_engine.population_dynamics.salary_dynamics import (
    MAX_PERMITTED_SALARY_GROWTH_RATE,
)
from pk_alm.bvg_liability_engine.population_dynamics.turnover import (
    MAX_PERMITTED_TURNOVER_RATE,
    apply_turnover_to_portfolio,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe


@dataclass(frozen=True)
class Stage2EngineResult:
    """Frozen container for one Stage-2 BVG engine run (legacy shape)."""

    portfolio_states: tuple[BVGPortfolioState, ...]
    cashflows: pd.DataFrame
    turnover_rounding_residual_count: tuple[float, ...]
    per_year_entries: tuple[int, ...]
    per_year_exits: tuple[int, ...]
    per_year_retirements: tuple[int, ...]
    salary_growth_rate: float
    turnover_rate: float
    entry_assumptions: EntryAssumptions

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_states, tuple):
            raise TypeError("portfolio_states must be tuple")
        if len(self.portfolio_states) == 0:
            raise ValueError("portfolio_states must not be empty")
        for i, state in enumerate(self.portfolio_states):
            if not isinstance(state, BVGPortfolioState):
                raise TypeError(
                    f"portfolio_states[{i}] must be BVGPortfolioState, "
                    f"got {type(state).__name__}"
                )
        if not isinstance(self.cashflows, pd.DataFrame):
            raise TypeError("cashflows must be a pandas DataFrame")
        validate_cashflow_dataframe(self.cashflows)
        if not self.cashflows.empty and set(self.cashflows["source"]) != {"BVG"}:
            raise ValueError("cashflows source must be BVG")
        if not isinstance(self.entry_assumptions, EntryAssumptions):
            raise TypeError(
                "entry_assumptions must be EntryAssumptions, "
                f"got {type(self.entry_assumptions).__name__}"
            )

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

    @property
    def total_entries(self) -> int:
        return sum(self.per_year_entries)

    @property
    def total_exits(self) -> int:
        return sum(self.per_year_exits)

    @property
    def total_retirements(self) -> int:
        return sum(self.per_year_retirements)


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


def _turnover_residual(state: BVGPortfolioState, rate: float, event_date: pd.Timestamp) -> float:
    """Recompute the per-year residual count from turnover for legacy reporting."""
    return apply_turnover_to_portfolio(state, rate, event_date).rounding_residual_count


def run_bvg_engine_stage2(
    initial_state: BVGPortfolioState,
    horizon_years: int,
    active_interest_rate: float,
    retired_interest_rate: float,
    salary_growth_rate: float = 0.015,
    turnover_rate: float = 0.02,
    entry_assumptions: EntryAssumptions | None = None,
    contribution_multiplier: float = 1.4,
    start_year: int = 2026,
    retirement_age: int = 65,
    capital_withdrawal_fraction: float = 0.35,
    conversion_rate: float = 0.068,
) -> Stage2EngineResult:
    """Stage-2 entry point. Adapter over the generic engine."""
    if not isinstance(initial_state, BVGPortfolioState):
        raise TypeError(
            f"initial_state must be BVGPortfolioState, got {type(initial_state).__name__}"
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
    salary_growth_rate = _validate_non_bool_real(
        salary_growth_rate, "salary_growth_rate"
    )
    if salary_growth_rate < 0.0 or salary_growth_rate > MAX_PERMITTED_SALARY_GROWTH_RATE:
        raise ValueError(
            "salary_growth_rate must be in "
            f"[0.0, {MAX_PERMITTED_SALARY_GROWTH_RATE}], got {salary_growth_rate}"
        )
    turnover_rate = _validate_non_bool_real(turnover_rate, "turnover_rate")
    if turnover_rate < 0.0 or turnover_rate > MAX_PERMITTED_TURNOVER_RATE:
        raise ValueError(
            "turnover_rate must be in "
            f"[0.0, {MAX_PERMITTED_TURNOVER_RATE}], got {turnover_rate}"
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
            "capital_withdrawal_fraction must be in [0.0, 1.0], "
            f"got {capital_withdrawal_fraction}"
        )
    conversion_rate = _validate_non_bool_real(conversion_rate, "conversion_rate")
    if conversion_rate < 0:
        raise ValueError(f"conversion_rate must be >= 0, got {conversion_rate}")

    if entry_assumptions is None:
        entry = get_default_entry_assumptions()
    elif isinstance(entry_assumptions, EntryAssumptions):
        entry = entry_assumptions
    else:
        raise TypeError(
            "entry_assumptions must be EntryAssumptions or None, "
            f"got {type(entry_assumptions).__name__}"
        )
    if entry.entry_age >= retirement_age:
        raise ValueError(
            "entry_assumptions.entry_age must be < retirement_age "
            f"({entry.entry_age} >= {retirement_age})"
        )

    assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon_years,
        retirement_age=max(retirement_age, 1),
        valuation_terminal_age=max(retirement_age, 1) + 1,
        active_crediting_rate=FlatRateCurve(active_interest_rate),
        retired_interest_rate=FlatRateCurve(retired_interest_rate),
        technical_discount_rate=FlatRateCurve(retired_interest_rate),
        economic_discount_rate=FlatRateCurve(retired_interest_rate),
        salary_growth_rate=FlatRateCurve(salary_growth_rate),
        conversion_rate=FlatRateCurve(conversion_rate),
        turnover_rate=turnover_rate,
        capital_withdrawal_fraction=capital_withdrawal_fraction,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(entry),
    )
    new_result = _run_generic(initial_state=initial_state, assumptions=assumptions)

    residuals = tuple(
        _turnover_residual(
            ys.opening_state, turnover_rate, pd.Timestamp(f"{ys.year}-12-31")
        )
        for ys in new_result.year_steps
    )

    per_year_entries = tuple(ys.entry_count for ys in new_result.year_steps)
    per_year_exits = tuple(ys.exited_count for ys in new_result.year_steps)
    per_year_retirements = tuple(ys.retired_count for ys in new_result.year_steps)

    return Stage2EngineResult(
        portfolio_states=new_result.portfolio_states,
        cashflows=new_result.cashflows,
        turnover_rounding_residual_count=residuals,
        per_year_entries=per_year_entries,
        per_year_exits=per_year_exits,
        per_year_retirements=per_year_retirements,
        salary_growth_rate=salary_growth_rate,
        turnover_rate=turnover_rate,
        entry_assumptions=entry,
    )
