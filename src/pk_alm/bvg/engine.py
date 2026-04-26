from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg.cashflow_generation import generate_bvg_cashflow_dataframe_for_state
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.portfolio_projection import project_portfolio_one_year
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BVGEngineResult:
    """Frozen container for one BVG engine run."""

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


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def run_bvg_engine(
    initial_state: BVGPortfolioState,
    horizon_years: int,
    active_interest_rate: float,
    retired_interest_rate: float,
    contribution_multiplier: float = 1.0,
    start_year: int = 2026,
) -> BVGEngineResult:
    """Project a BVG portfolio for `horizon_years` and emit one combined cashflow DataFrame.

    Timing convention: at each step, cashflows are generated from the *current* state
    (event date Dec 31 of that year), then the portfolio is projected one year forward.
    Therefore len(portfolio_states) == horizon_years + 1.
    """
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

    # Retirement transitions are not implemented in this sprint.
    max_active_age = max(
        (c.age for c in initial_state.active_cohorts), default=0
    )
    if max_active_age + horizon_years > 65:
        raise ValueError(
            "This projection would move at least one active cohort beyond age 65. "
            "Retirement transitions are not implemented in this engine sprint. "
            "Reduce horizon_years or implement retirement transition logic first."
        )

    states: list[BVGPortfolioState] = [initial_state]
    cashflow_frames: list[pd.DataFrame] = []
    current_state = initial_state

    for step in range(horizon_years):
        event_date = pd.Timestamp(f"{start_year + step}-12-31")
        df = generate_bvg_cashflow_dataframe_for_state(
            current_state, event_date, contribution_multiplier
        )
        cashflow_frames.append(df)
        current_state = project_portfolio_one_year(
            current_state, active_interest_rate, retired_interest_rate
        )
        states.append(current_state)

    if cashflow_frames:
        cashflows = pd.concat(cashflow_frames, ignore_index=True)
    else:
        cashflows = pd.DataFrame(columns=list(CASHFLOW_COLUMNS))

    validate_cashflow_dataframe(cashflows)

    return BVGEngineResult(portfolio_states=tuple(states), cashflows=cashflows)
