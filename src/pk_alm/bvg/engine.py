from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg.cashflow_generation import generate_bvg_cashflow_dataframe_for_state
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.projection import project_portfolio_one_year
from pk_alm.bvg.retirement_transition import (
    apply_retirement_transitions_to_portfolio,
)
from pk_alm.cashflows.schema import (
    CASHFLOW_COLUMNS,
    cashflow_records_to_dataframe,
    validate_cashflow_dataframe,
)


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
    retirement_age: int = 65,
    capital_withdrawal_fraction: float = 0.35,
    conversion_rate: float = 0.068,
) -> BVGEngineResult:
    """Project a BVG portfolio for `horizon_years` and emit one combined cashflow DataFrame.

    Per-step timing convention:
      1. Generate regular PR/RP cashflows from the current state (event date Dec 31).
      2. Project the portfolio one year forward (interest crediting + age + 1).
      3. Apply retirement transitions: any active cohort that has reached
         `retirement_age` is converted to a retired cohort and emits a KA
         capital-withdrawal record at the same year-end event date.

    Therefore len(portfolio_states) == horizon_years + 1, and a cohort that
    starts a year at age 64 receives one final regular contribution flow,
    is projected to age 65, then retires at year-end (KA), and only starts
    paying RP from the following year.
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

    states: list[BVGPortfolioState] = [initial_state]
    cashflow_frames: list[pd.DataFrame] = []
    current_state = initial_state

    for step in range(horizon_years):
        event_date = pd.Timestamp(f"{start_year + step}-12-31")

        # 1. Regular PR/RP cashflows from the current state.
        regular_df = generate_bvg_cashflow_dataframe_for_state(
            current_state, event_date, contribution_multiplier
        )

        # 2. Project one year forward.
        projected_state = project_portfolio_one_year(
            current_state, active_interest_rate, retired_interest_rate
        )

        # 3. Apply retirement transitions to the projected state.
        transition = apply_retirement_transitions_to_portfolio(
            projected_state,
            event_date,
            retirement_age=retirement_age,
            capital_withdrawal_fraction=capital_withdrawal_fraction,
            conversion_rate=conversion_rate,
        )
        transition_df = cashflow_records_to_dataframe(
            list(transition.cashflow_records)
        )

        # Combine for this year: regular rows first, KA rows after.
        year_df = pd.concat([regular_df, transition_df], ignore_index=True)
        validate_cashflow_dataframe(year_df)
        cashflow_frames.append(year_df)

        current_state = transition.portfolio_state
        states.append(current_state)

    if cashflow_frames:
        cashflows = pd.concat(cashflow_frames, ignore_index=True)
    else:
        cashflows = pd.DataFrame(columns=list(CASHFLOW_COLUMNS))

    validate_cashflow_dataframe(cashflows)

    return BVGEngineResult(portfolio_states=tuple(states), cashflows=cashflows)
