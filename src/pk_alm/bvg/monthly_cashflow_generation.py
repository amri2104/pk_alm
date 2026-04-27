"""Standalone monthly BVG PR/RP cashflow generation.

This module provides a standalone monthly BVG PR/RP cashflow generator that
emits records in the canonical 7-column cashflow schema. It is intentionally
narrow:

- It uses the existing canonical cashflow schema and `source="BVG"`.
- It does not modify the deterministic annual Stage-1 baseline, the BVG
  engine, valuation snapshots, asset roll-forward, funding-ratio analytics,
  scenario summaries, or the seven default Stage-1 CSV outputs.
- It does not handle retirement transitions or KA capital-withdrawal events.
- It is intended for monthly liquidity timing analysis and for
  monthly-vs-annual reconciliation only.

The annual baseline remains the reference. Monthly PR/RP simulation is
standalone and not wired into ``run_stage1_baseline(...)``.
"""

from __future__ import annotations

import math
import numbers

import pandas as pd

from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import (
    CashflowRecord,
    cashflow_records_to_dataframe,
    validate_cashflow_dataframe,
)
from pk_alm.time_grid import build_time_grid

MONTHS_PER_YEAR = 12
MONTHLY_BVG_EVENT_TYPES = ("PR", "RP")


def _validate_reporting_year(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("reporting_year must not be bool")
    if not isinstance(value, numbers.Integral):
        raise TypeError(
            f"reporting_year must be int, got {type(value).__name__}"
        )
    result = int(value)
    if result < 0:
        raise ValueError(f"reporting_year must be >= 0, got {result}")
    return result


def _validate_contribution_multiplier(value: object) -> float:
    if isinstance(value, bool):
        raise TypeError("contribution_multiplier must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(
            f"contribution_multiplier must be numeric, got {type(value).__name__}"
        )
    fval = float(value)
    if math.isnan(fval):
        raise ValueError("contribution_multiplier must not be NaN")
    if fval < 0:
        raise ValueError(
            f"contribution_multiplier must be >= 0, got {fval}"
        )
    return fval


def generate_monthly_bvg_cashflow_records_for_state(
    portfolio: BVGPortfolioState,
    reporting_year: int,
    contribution_multiplier: float = 1.0,
) -> tuple[CashflowRecord, ...]:
    """Generate monthly BVG PR/RP cashflow records for one portfolio state.

    For each month-end of ``reporting_year``, emit one PR record per active
    cohort followed by one RP record per retired cohort, both in portfolio
    order. Monthly amounts are the corresponding annual cohort totals divided
    by 12, with PR records additionally scaled by ``contribution_multiplier``.

    Returns an empty tuple if the portfolio has no cohorts. Does not mutate
    the input portfolio or its cohorts.
    """
    if not isinstance(portfolio, BVGPortfolioState):
        raise TypeError(
            f"portfolio must be a BVGPortfolioState, got {type(portfolio).__name__}"
        )
    year = _validate_reporting_year(reporting_year)
    multiplier = _validate_contribution_multiplier(contribution_multiplier)

    steps = build_time_grid(
        start_year=year,
        horizon_years=1,
        frequency="MONTHLY",
    )

    records: list[CashflowRecord] = []
    for step in steps:
        month_end = step.event_date
        for cohort in portfolio.active_cohorts:
            records.append(
                CashflowRecord(
                    contractId=cohort.cohort_id,
                    time=month_end,
                    type="PR",
                    payoff=cohort.annual_age_credit_total
                    * multiplier
                    / MONTHS_PER_YEAR,
                    nominalValue=cohort.total_capital_active,
                    currency="CHF",
                    source="BVG",
                )
            )
        for cohort in portfolio.retired_cohorts:
            records.append(
                CashflowRecord(
                    contractId=cohort.cohort_id,
                    time=month_end,
                    type="RP",
                    payoff=-cohort.annual_pension_total / MONTHS_PER_YEAR,
                    nominalValue=cohort.total_capital_rente,
                    currency="CHF",
                    source="BVG",
                )
            )
    return tuple(records)


def generate_monthly_bvg_cashflow_dataframe_for_state(
    portfolio: BVGPortfolioState,
    reporting_year: int,
    contribution_multiplier: float = 1.0,
) -> pd.DataFrame:
    """Generate a schema-valid monthly BVG cashflow DataFrame for one state."""
    records = generate_monthly_bvg_cashflow_records_for_state(
        portfolio,
        reporting_year,
        contribution_multiplier,
    )
    df = cashflow_records_to_dataframe(records)
    validate_cashflow_dataframe(df)
    return df
