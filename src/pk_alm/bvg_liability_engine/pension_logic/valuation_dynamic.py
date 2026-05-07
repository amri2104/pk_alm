"""Stage-2C valuation with time-varying technical interest rates.

Accepts a scalar, a sequence (forward-filled), or a :class:`RateCurve`. The
input is materialized into one rate per snapshot and routed through the
canonical :func:`value_portfolio_state`.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions.rate_curves import (
    RateCurve,
    expand as expand_curve,
    from_dynamic_parameter,
)
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.valuation import (
    validate_valuation_dataframe,
    valuation_snapshots_to_dataframe,
    value_portfolio_state,
)


def _resolve_rates(
    technical_interest_rate: float | Sequence[float] | RateCurve,
    n_snapshots: int,
    *,
    start_year: int = 0,
) -> tuple[float, ...]:
    if n_snapshots <= 0:
        return ()
    if isinstance(technical_interest_rate, RateCurve):
        return expand_curve(
            technical_interest_rate,
            start_year=start_year,
            horizon_years=n_snapshots,
        )
    curve = from_dynamic_parameter(
        technical_interest_rate,
        start_year=start_year,
        horizon_years=n_snapshots,
    )
    return expand_curve(curve, start_year=start_year, horizon_years=n_snapshots)


def value_portfolio_states_dynamic(
    portfolio_states: list | tuple,
    technical_interest_rate: float | Sequence[float] | RateCurve,
    valuation_terminal_age: int = 90,
    currency: str = "CHF",
    *,
    start_year: int = 0,
) -> pd.DataFrame:
    """Value portfolio states with one resolved discount rate per snapshot."""
    if not isinstance(portfolio_states, (list, tuple)):
        raise TypeError(
            f"portfolio_states must be list or tuple, "
            f"got {type(portfolio_states).__name__}"
        )
    for i, portfolio in enumerate(portfolio_states):
        if not isinstance(portfolio, BVGPortfolioState):
            raise TypeError(
                f"portfolio_states[{i}] must be BVGPortfolioState, "
                f"got {type(portfolio).__name__}"
            )

    rates = _resolve_rates(
        technical_interest_rate, len(portfolio_states), start_year=start_year
    )
    snapshots = [
        value_portfolio_state(
            portfolio, rates[i], valuation_terminal_age, currency
        )
        for i, portfolio in enumerate(portfolio_states)
    ]
    df = valuation_snapshots_to_dataframe(snapshots)
    validate_valuation_dataframe(df)
    return df
