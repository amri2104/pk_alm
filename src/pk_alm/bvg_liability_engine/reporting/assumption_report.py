"""Flatten :class:`BVGAssumptions` into a tabular parameter report."""

from __future__ import annotations

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions.bvg_assumptions import BVGAssumptions
from pk_alm.bvg_liability_engine.assumptions.rate_curves import (
    FlatRateCurve,
    RateCurve,
    StepRateCurve,
)


def _summarize_curve(curve: RateCurve) -> str:
    if isinstance(curve, FlatRateCurve):
        return f"flat {curve.rate:.6g}"
    if isinstance(curve, StepRateCurve):
        return "step " + ", ".join(
            f"{y}:{r:.6g}" for y, r in sorted(curve.rates.items())
        )
    return type(curve).__name__


def build_assumption_report(assumptions: BVGAssumptions) -> pd.DataFrame:
    """Return a parameter / value / unit / description table."""
    if not isinstance(assumptions, BVGAssumptions):
        raise TypeError(
            f"assumptions must be BVGAssumptions, got {type(assumptions).__name__}"
        )
    rows = [
        ("start_year", assumptions.start_year, "year", "First projection calendar year"),
        ("horizon_years", assumptions.horizon_years, "years", "Projection horizon"),
        ("retirement_age", assumptions.retirement_age, "years", "Retirement transition age"),
        (
            "valuation_terminal_age",
            assumptions.valuation_terminal_age,
            "years",
            "Cap age for run-off valuation",
        ),
        (
            "active_crediting_rate",
            _summarize_curve(assumptions.active_crediting_rate),
            "rate",
            "Annual crediting rate on active capital",
        ),
        (
            "retired_interest_rate",
            _summarize_curve(assumptions.retired_interest_rate),
            "rate",
            "Annual rate credited to retiree capital",
        ),
        (
            "technical_discount_rate",
            _summarize_curve(assumptions.technical_discount_rate),
            "rate",
            "Statutory technical discount rate",
        ),
        (
            "economic_discount_rate",
            _summarize_curve(assumptions.economic_discount_rate),
            "rate",
            "Economic / risk-free discount rate",
        ),
        (
            "salary_growth_rate",
            _summarize_curve(assumptions.salary_growth_rate),
            "rate",
            "Annual salary scaling on actives",
        ),
        (
            "conversion_rate",
            _summarize_curve(assumptions.conversion_rate),
            "rate",
            "Pension conversion rate at retirement",
        ),
        (
            "turnover_rate",
            assumptions.turnover_rate,
            "rate",
            "Annual fraction of actives leaving via Austritt",
        ),
        (
            "capital_withdrawal_fraction",
            assumptions.capital_withdrawal_fraction,
            "fraction",
            "Capital fraction taken as KA at retirement",
        ),
        (
            "contribution_multiplier",
            assumptions.contribution_multiplier,
            "multiplier",
            "Scale on age-credit-driven PR cashflows",
        ),
        (
            "cashflow_frequency",
            assumptions.cashflow_frequency,
            "label",
            "Cashflow emission frequency (annual or monthly)",
        ),
        (
            "cashflow_timing",
            assumptions.cashflow_timing,
            "label",
            "Within-year cashflow timing convention",
        ),
        (
            "mortality.mode",
            assumptions.mortality.mode,
            "label",
            "off | ek0105",
        ),
        (
            "mortality.table_id",
            assumptions.mortality.table_id,
            "label",
            "EK 0105 table identifier when active",
        ),
        (
            "entry_policy",
            type(assumptions.entry_policy).__name__,
            "label",
            "Entry policy class",
        ),
    ]
    return pd.DataFrame(
        rows, columns=["parameter", "value", "unit", "description"]
    )
