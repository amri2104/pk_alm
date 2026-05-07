from __future__ import annotations

import math
import numbers

import pandas as pd

from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.cashflows.event_types import PR, RP
from pk_alm.cashflows.schema import (
    CashflowRecord,
    cashflow_records_to_dataframe,
    validate_cashflow_dataframe,
)


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


def _normalize_event_date(event_date: object) -> pd.Timestamp:
    if event_date is None:
        raise ValueError("event_date must not be None")
    try:
        ts = pd.Timestamp(event_date)
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"event_date could not be converted to pd.Timestamp: {event_date!r}"
        ) from e
    if pd.isna(ts):
        raise ValueError(
            f"event_date could not be converted to pd.Timestamp: {event_date!r}"
        )
    return ts


def generate_bvg_cashflow_records_for_state(
    portfolio: BVGPortfolioState,
    event_date: object,
    contribution_multiplier: float = 1.0,
) -> tuple[CashflowRecord, ...]:
    """Convert one BVGPortfolioState snapshot into shared-schema CashflowRecords.

    Active cohorts emit a "PR" inflow scaled by contribution_multiplier.
    Retired cohorts emit an "RP" outflow equal to the cohort's pension total.
    Order: actives first, retirees second, each in portfolio order.
    """
    if not isinstance(portfolio, BVGPortfolioState):
        raise TypeError(
            f"portfolio must be a BVGPortfolioState, got {type(portfolio).__name__}"
        )

    multiplier = _validate_contribution_multiplier(contribution_multiplier)
    ts = _normalize_event_date(event_date)

    records: list[CashflowRecord] = []
    for cohort in portfolio.active_cohorts:
        records.append(
            CashflowRecord(
                contractId=cohort.cohort_id,
                time=ts,
                type=PR,
                payoff=cohort.annual_age_credit_total * multiplier,
                nominalValue=cohort.total_capital_active,
                currency="CHF",
                source="BVG",
            )
        )
    for cohort in portfolio.retired_cohorts:
        records.append(
            CashflowRecord(
                contractId=cohort.cohort_id,
                time=ts,
                type=RP,
                payoff=-cohort.annual_pension_total,
                nominalValue=cohort.total_capital_rente,
                currency="CHF",
                source="BVG",
            )
        )
    return tuple(records)


def generate_bvg_cashflow_dataframe_for_state(
    portfolio: BVGPortfolioState,
    event_date: object,
    contribution_multiplier: float = 1.0,
) -> pd.DataFrame:
    """Generate a schema-valid cashflow DataFrame for one portfolio state."""
    records = generate_bvg_cashflow_records_for_state(
        portfolio, event_date, contribution_multiplier
    )
    df = cashflow_records_to_dataframe(records)
    validate_cashflow_dataframe(df)
    return df
