"""Cashflow-runoff valuation cross-check for BVG liabilities.

Two complementary lenses on the retiree liability:

- **Formula PV** — closed-form annuity PV using
  :func:`pk_alm.bvg_liability_engine.pension_logic.formulas.calculate_retiree_pv`,
  capped at ``valuation_terminal_age``. Mortality-blind.
- **Cashflow-runoff PV** — project the portfolio without further entries
  out to ``valuation_terminal_age``, generate the run-off ``RP`` cashflows,
  then discount them back at ``technical`` and ``economic`` rates.

When mortality is off both lenses must agree to numerical precision. When
mortality is active, the cashflow-runoff PV is bounded above by the
certain-annuity formula PV.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions.bvg_assumptions import BVGAssumptions
from pk_alm.bvg_liability_engine.assumptions.rate_curves import RateCurve
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.formulas import calculate_retiree_pv
from pk_alm.bvg_liability_engine.pension_logic.projection import project_portfolio_one_year


@dataclass(frozen=True)
class RunoffValuation:
    """Runoff valuation result for one anchor year."""

    anchor_year: int
    technical_pv: float
    economic_pv: float
    formula_pv: float
    runoff_cashflows: pd.DataFrame


def project_runoff_cashflows_for_valuation(
    state: BVGPortfolioState,
    assumptions: BVGAssumptions,
    *,
    anchor_year: int,
) -> pd.DataFrame:
    """Project a state forward with no entries until ``valuation_terminal_age``.

    Returns the implied ``RP`` cashflows: per (relative-year-offset, cohort)
    expected pension payment computed from the projected retiree counts.
    """
    if not isinstance(state, BVGPortfolioState):
        raise TypeError("state must be BVGPortfolioState")
    if not isinstance(assumptions, BVGAssumptions):
        raise TypeError("assumptions must be BVGAssumptions")

    retired_rate = float(assumptions.retired_interest_rate.value_at(anchor_year))
    active_rate = float(assumptions.active_crediting_rate.value_at(anchor_year))

    rows: list[dict[str, object]] = []
    current = state
    relevant_ages = [c.age for c in current.retired_cohorts]
    if current.active_cohorts:
        relevant_ages.extend(c.age for c in current.active_cohorts)
    if not relevant_ages:
        horizon = 0
    else:
        horizon = max(
            0, assumptions.valuation_terminal_age - min(relevant_ages)
        )

    for offset in range(horizon):
        year = anchor_year + offset
        for cohort in current.retired_cohorts:
            if cohort.age >= assumptions.valuation_terminal_age:
                continue
            payoff = cohort.count * cohort.annual_pension_per_person
            if payoff <= 0:
                continue
            rows.append(
                {
                    "anchor_year": anchor_year,
                    "offset_years": offset,
                    "calendar_year": year,
                    "cohort_id": cohort.cohort_id,
                    "cohort_age": cohort.age,
                    "annual_payment": payoff,
                }
            )
        current = project_portfolio_one_year(current, active_rate, retired_rate)

    return pd.DataFrame(
        rows,
        columns=[
            "anchor_year",
            "offset_years",
            "calendar_year",
            "cohort_id",
            "cohort_age",
            "annual_payment",
        ],
    )


def discount_cashflows(
    df: pd.DataFrame,
    *,
    rate_curve: RateCurve,
    anchor_year: int,
    payment_column: str = "annual_payment",
) -> float:
    """Discount per-year cashflows in ``df`` back to ``anchor_year``.

    The discount factor for offset ``k`` is
    ``prod_{j=0..k-1} 1 / (1 + rate_curve.value_at(anchor_year + j))``.
    """
    if df.empty:
        return 0.0
    max_offset = int(df["offset_years"].max())
    # Annuity-due: payment at offset 0 occurs at the anchor date itself
    # (factor 1.0); payment at offset k is discounted by k years.
    factors: list[float] = [1.0]
    accum = 1.0
    for j in range(max_offset):
        rate = float(rate_curve.value_at(anchor_year + j))
        accum = accum / (1.0 + rate)
        factors.append(accum)
    pv = 0.0
    for _, row in df.iterrows():
        offset = int(row["offset_years"])
        pv += float(row[payment_column]) * factors[offset]
    return pv


def value_portfolio_state_formula(
    state: BVGPortfolioState,
    *,
    technical_rate: float,
    valuation_terminal_age: int,
) -> float:
    """Closed-form retiree PV at the given technical rate."""
    pv = 0.0
    for cohort in state.retired_cohorts:
        remaining = max(0, valuation_terminal_age - cohort.age)
        if remaining == 0:
            continue
        pv += cohort.count * calculate_retiree_pv(
            cohort.annual_pension_per_person, remaining, technical_rate
        )
    return pv


def value_portfolio_state_cashflow_runoff(
    state: BVGPortfolioState,
    assumptions: BVGAssumptions,
    *,
    anchor_year: int,
) -> RunoffValuation:
    """Compute formula, technical-runoff and economic-runoff PVs side-by-side."""
    cashflows = project_runoff_cashflows_for_valuation(
        state, assumptions, anchor_year=anchor_year
    )
    technical_pv = discount_cashflows(
        cashflows,
        rate_curve=assumptions.technical_discount_rate,
        anchor_year=anchor_year,
    )
    economic_pv = discount_cashflows(
        cashflows,
        rate_curve=assumptions.economic_discount_rate,
        anchor_year=anchor_year,
    )
    formula_pv = value_portfolio_state_formula(
        state,
        technical_rate=float(assumptions.technical_discount_rate.value_at(anchor_year)),
        valuation_terminal_age=assumptions.valuation_terminal_age,
    )
    return RunoffValuation(
        anchor_year=anchor_year,
        technical_pv=technical_pv,
        economic_pv=economic_pv,
        formula_pv=formula_pv,
        runoff_cashflows=cashflows,
    )


def compare_formula_vs_cashflow_pv(
    runoff: RunoffValuation, *, mortality_active: bool, abs_tol: float = 1e-3
) -> bool:
    """Return True if the runoff/formula relation holds for the given mode.

    - When mortality is off, formula PV must equal technical-runoff PV up to
      ``abs_tol`` (both compute the same certain-annuity sum at the
      technical-rate curve evaluated at the anchor year).
    - When mortality is active, the runoff PV is bounded above by the formula
      PV (deaths reduce expected payments).
    """
    if mortality_active:
        return runoff.technical_pv <= runoff.formula_pv + abs_tol
    return abs(runoff.technical_pv - runoff.formula_pv) <= abs_tol
