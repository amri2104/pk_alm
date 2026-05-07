"""Per-year structured output of the generic BVG engine."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import validate_cashflow_dataframe


@dataclass(frozen=True)
class BVGYearStep:
    """Detailed snapshot of one projection year.

    State fields capture the portfolio at every meaningful intermediate
    step. Cashflow fields capture the records produced at each stage. The
    union of all stage-level cashflow frames equals ``year_cashflows`` (in
    the canonical concat order: regular → turnover → retirement → entry).
    """

    year: int

    opening_state: BVGPortfolioState
    post_regular_cashflow_state: BVGPortfolioState
    post_turnover_state: BVGPortfolioState
    post_projection_state: BVGPortfolioState
    post_salary_growth_state: BVGPortfolioState
    post_retirement_state: BVGPortfolioState
    closing_state: BVGPortfolioState

    regular_cashflows: pd.DataFrame
    turnover_cashflows: pd.DataFrame
    retirement_cashflows: pd.DataFrame
    entry_cashflows: pd.DataFrame
    year_cashflows: pd.DataFrame

    exited_count: int
    retired_count: int
    entry_count: int

    def __post_init__(self) -> None:
        for name, df in (
            ("regular_cashflows", self.regular_cashflows),
            ("turnover_cashflows", self.turnover_cashflows),
            ("retirement_cashflows", self.retirement_cashflows),
            ("entry_cashflows", self.entry_cashflows),
            ("year_cashflows", self.year_cashflows),
        ):
            if not isinstance(df, pd.DataFrame):
                raise TypeError(
                    f"{name} must be a pandas DataFrame, got {type(df).__name__}"
                )
            validate_cashflow_dataframe(df)
        for name, state in (
            ("opening_state", self.opening_state),
            ("post_regular_cashflow_state", self.post_regular_cashflow_state),
            ("post_turnover_state", self.post_turnover_state),
            ("post_projection_state", self.post_projection_state),
            ("post_salary_growth_state", self.post_salary_growth_state),
            ("post_retirement_state", self.post_retirement_state),
            ("closing_state", self.closing_state),
        ):
            if not isinstance(state, BVGPortfolioState):
                raise TypeError(
                    f"{name} must be BVGPortfolioState, got {type(state).__name__}"
                )
        for name, n in (
            ("exited_count", self.exited_count),
            ("retired_count", self.retired_count),
            ("entry_count", self.entry_count),
        ):
            if isinstance(n, bool) or not isinstance(n, int):
                raise TypeError(f"{name} must be int")
            if n < 0:
                raise ValueError(f"{name} must be >= 0, got {n}")
