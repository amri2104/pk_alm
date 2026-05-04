"""Stage-2C valuation with time-varying technical interest rates."""

from __future__ import annotations

import pandas as pd

from pk_alm.bvg_liability_engine.actuarial_assumptions.dynamic_parameters import DynamicParameter, expand_parameter
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.valuation import (
    validate_valuation_dataframe,
    valuation_snapshots_to_dataframe,
    value_portfolio_state,
)


def value_portfolio_states_dynamic(
    portfolio_states: list | tuple,
    technical_interest_rate: DynamicParameter,
    valuation_terminal_age: int = 90,
    currency: str = "CHF",
) -> pd.DataFrame:
    """Value portfolio states with one resolved discount rate per snapshot.

    The returned DataFrame uses the same schema as
    :func:`pk_alm.bvg_liability_engine.pension_logic.valuation.value_portfolio_states`; the existing
    ``technical_interest_rate`` column contains the resolved per-row rate.
    """
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

    rates = expand_parameter(
        technical_interest_rate,
        len(portfolio_states),
        "technical_interest_rate",
    )
    snapshots = [
        value_portfolio_state(
            portfolio,
            rates[i],
            valuation_terminal_age,
            currency,
        )
        for i, portfolio in enumerate(portfolio_states)
    ]
    df = valuation_snapshots_to_dataframe(snapshots)
    validate_valuation_dataframe(df)
    return df
