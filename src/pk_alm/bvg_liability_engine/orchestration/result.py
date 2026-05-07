"""Result container for the generic BVG engine.

Field names ``portfolio_states`` and ``cashflows`` are preserved so that
existing scenario and reporting code that reads from legacy result objects
keeps working when scenarios are migrated in Phase 6.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions.bvg_assumptions import BVGAssumptions
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.year_step import BVGYearStep
from pk_alm.cashflows.schema import validate_cashflow_dataframe


@dataclass(frozen=True)
class BVGEngineResult:
    """Frozen output of one BVG engine run."""

    assumptions: BVGAssumptions
    year_steps: tuple[BVGYearStep, ...]
    portfolio_states: tuple[BVGPortfolioState, ...]
    cashflows: pd.DataFrame

    def __post_init__(self) -> None:
        if not isinstance(self.assumptions, BVGAssumptions):
            raise TypeError(
                f"assumptions must be BVGAssumptions, got {type(self.assumptions).__name__}"
            )
        if not isinstance(self.year_steps, tuple):
            raise TypeError("year_steps must be a tuple")
        for i, ys in enumerate(self.year_steps):
            if not isinstance(ys, BVGYearStep):
                raise TypeError(
                    f"year_steps[{i}] must be BVGYearStep, got {type(ys).__name__}"
                )
        if not isinstance(self.portfolio_states, tuple):
            raise TypeError("portfolio_states must be a tuple")
        if len(self.portfolio_states) == 0:
            raise ValueError("portfolio_states must not be empty")
        for i, s in enumerate(self.portfolio_states):
            if not isinstance(s, BVGPortfolioState):
                raise TypeError(
                    f"portfolio_states[{i}] must be BVGPortfolioState, "
                    f"got {type(s).__name__}"
                )
        if not isinstance(self.cashflows, pd.DataFrame):
            raise TypeError("cashflows must be a pandas DataFrame")
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
