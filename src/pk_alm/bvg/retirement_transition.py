from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg.cohorts import RetiredCohort
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import CashflowRecord


# ---------------------------------------------------------------------------
# Validation helpers (local; same style as engine.py)
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


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetirementTransitionResult:
    """Frozen container holding the post-transition portfolio and KA cashflows."""

    portfolio_state: BVGPortfolioState
    cashflow_records: tuple[CashflowRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_state, BVGPortfolioState):
            raise TypeError(
                f"portfolio_state must be BVGPortfolioState, "
                f"got {type(self.portfolio_state).__name__}"
            )
        if not isinstance(self.cashflow_records, tuple):
            raise TypeError(
                f"cashflow_records must be a tuple, "
                f"got {type(self.cashflow_records).__name__}"
            )
        for i, r in enumerate(self.cashflow_records):
            if not isinstance(r, CashflowRecord):
                raise TypeError(
                    f"cashflow_records[{i}] must be CashflowRecord, "
                    f"got {type(r).__name__}"
                )

    @property
    def cashflow_count(self) -> int:
        return len(self.cashflow_records)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def apply_retirement_transitions_to_portfolio(
    portfolio: BVGPortfolioState,
    event_date: object,
    retirement_age: int = 65,
    capital_withdrawal_fraction: float = 0.35,
    conversion_rate: float = 0.068,
) -> RetirementTransitionResult:
    """Convert active cohorts at/above retirement_age into retired cohorts.

    Returns a new BVGPortfolioState plus one KA capital-withdrawal cashflow record
    per retiring cohort. Existing retired cohorts pass through untouched.
    Does not project the portfolio; only applies transitions to the input state.
    """
    if not isinstance(portfolio, BVGPortfolioState):
        raise TypeError(
            f"portfolio must be BVGPortfolioState, got {type(portfolio).__name__}"
        )

    retirement_age = _validate_non_bool_int(retirement_age, "retirement_age")
    if retirement_age < 0:
        raise ValueError(
            f"retirement_age must be >= 0, got {retirement_age}"
        )

    fraction = _validate_non_bool_real(
        capital_withdrawal_fraction, "capital_withdrawal_fraction"
    )
    if fraction < 0.0 or fraction > 1.0:
        raise ValueError(
            f"capital_withdrawal_fraction must be in [0.0, 1.0], got {fraction}"
        )

    conv_rate = _validate_non_bool_real(conversion_rate, "conversion_rate")
    if conv_rate < 0:
        raise ValueError(
            f"conversion_rate must be >= 0, got {conv_rate}"
        )

    ts = _normalize_event_date(event_date)

    remaining_active = []
    new_retired = []
    records: list[CashflowRecord] = []

    for cohort in portfolio.active_cohorts:
        if cohort.age < retirement_age:
            remaining_active.append(cohort)
            continue

        retirement_capital_pp = cohort.capital_active_per_person
        withdrawal_pp = retirement_capital_pp * fraction
        rente_pp = retirement_capital_pp * (1.0 - fraction)
        pension_pp = rente_pp * conv_rate

        new_retired.append(
            RetiredCohort(
                cohort_id=f"RET_FROM_{cohort.cohort_id}",
                age=cohort.age,
                count=cohort.count,
                annual_pension_per_person=pension_pp,
                capital_rente_per_person=rente_pp,
            )
        )
        records.append(
            CashflowRecord(
                contractId=cohort.cohort_id,
                time=ts,
                type="KA",
                payoff=-(cohort.count * withdrawal_pp),
                nominalValue=cohort.count * retirement_capital_pp,
                currency="CHF",
                source="BVG",
            )
        )

    new_portfolio = BVGPortfolioState(
        projection_year=portfolio.projection_year,
        active_cohorts=tuple(remaining_active),
        retired_cohorts=tuple(portfolio.retired_cohorts) + tuple(new_retired),
    )

    return RetirementTransitionResult(
        portfolio_state=new_portfolio,
        cashflow_records=tuple(records),
    )
