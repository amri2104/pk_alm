"""Monthly-vs-annual BVG cashflow reconciliation.

This module reconciles the standalone monthly BVG PR/RP cashflow generator
against the deterministic annual BVG cashflow generator. It is intentionally
narrow:

- It is not a new valuation model, asset model, or funding-ratio model.
- It is not wired into the deterministic annual Stage-1 baseline and does
  not change ``run_stage1_baseline(...)``, the BVG engine, valuation
  snapshots, asset roll-forward, funding-ratio analytics, scenario
  summaries, or the seven default Stage-1 CSV outputs.
- Its only purpose is to prove that distributing PR and RP across calendar
  month-ends preserves the corresponding annual totals up to a small
  numerical tolerance.

KA capital-withdrawal events and any other non-PR/RP event types are
silently ignored by the reconciliation: only PR and RP totals are
compared.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg.cashflow_generation import (
    generate_bvg_cashflow_dataframe_for_state,
)
from pk_alm.bvg.monthly_cashflow_generation import (
    generate_monthly_bvg_cashflow_dataframe_for_state,
)
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import validate_cashflow_dataframe

RECONCILIATION_EVENT_TYPES = ("PR", "RP")
MONTHLY_RECONCILIATION_COLUMNS = (
    "reporting_year",
    "type",
    "annual_payoff",
    "monthly_payoff",
    "difference",
    "abs_difference",
    "is_close",
)
RECONCILIATION_TOLERANCE = 1e-5


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


def _validate_real_amount(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    return fval


@dataclass(frozen=True)
class MonthlyReconciliationRow:
    """One reconciliation row comparing monthly vs annual payoff totals."""

    reporting_year: int
    type: str
    annual_payoff: float
    monthly_payoff: float
    difference: float
    abs_difference: float
    is_close: bool

    def __post_init__(self) -> None:
        year = _validate_reporting_year(self.reporting_year)

        if not isinstance(self.type, str) or not self.type.strip():
            raise ValueError("type must be a non-empty string")
        if self.type not in RECONCILIATION_EVENT_TYPES:
            raise ValueError(
                f"type must be one of {RECONCILIATION_EVENT_TYPES}, "
                f"got {self.type!r}"
            )

        annual = _validate_real_amount(self.annual_payoff, "annual_payoff")
        monthly = _validate_real_amount(self.monthly_payoff, "monthly_payoff")
        difference = _validate_real_amount(self.difference, "difference")
        abs_difference = _validate_real_amount(
            self.abs_difference, "abs_difference"
        )

        if abs_difference < 0:
            raise ValueError(
                f"abs_difference must be >= 0, got {abs_difference}"
            )

        if not isinstance(self.is_close, bool):
            raise TypeError("is_close must be bool")

        expected_difference = monthly - annual
        if not math.isclose(
            difference,
            expected_difference,
            abs_tol=RECONCILIATION_TOLERANCE,
        ):
            raise ValueError(
                "difference must equal monthly_payoff - annual_payoff "
                f"(expected {expected_difference}, got {difference})"
            )

        expected_abs = abs(difference)
        if not math.isclose(
            abs_difference,
            expected_abs,
            abs_tol=RECONCILIATION_TOLERANCE,
        ):
            raise ValueError(
                "abs_difference must equal abs(difference) "
                f"(expected {expected_abs}, got {abs_difference})"
            )

        expected_is_close = math.isclose(
            monthly,
            annual,
            abs_tol=RECONCILIATION_TOLERANCE,
        )
        if self.is_close != expected_is_close:
            raise ValueError(
                "is_close must equal math.isclose(monthly_payoff, "
                "annual_payoff, abs_tol=RECONCILIATION_TOLERANCE) "
                f"(expected {expected_is_close}, got {self.is_close})"
            )

        object.__setattr__(self, "reporting_year", year)
        object.__setattr__(self, "annual_payoff", annual)
        object.__setattr__(self, "monthly_payoff", monthly)
        object.__setattr__(self, "difference", difference)
        object.__setattr__(self, "abs_difference", abs_difference)

    def to_dict(self) -> dict[str, object]:
        """Return row fields keyed in MONTHLY_RECONCILIATION_COLUMNS order."""
        return {
            column: getattr(self, column)
            for column in MONTHLY_RECONCILIATION_COLUMNS
        }


def _build_reconciliation_row(
    reporting_year: int,
    event_type: str,
    annual_payoff: float,
    monthly_payoff: float,
) -> MonthlyReconciliationRow:
    difference = monthly_payoff - annual_payoff
    is_close = math.isclose(
        monthly_payoff,
        annual_payoff,
        abs_tol=RECONCILIATION_TOLERANCE,
    )
    return MonthlyReconciliationRow(
        reporting_year=reporting_year,
        type=event_type,
        annual_payoff=annual_payoff,
        monthly_payoff=monthly_payoff,
        difference=difference,
        abs_difference=abs(difference),
        is_close=is_close,
    )


def _sum_payoff_by_type(df: pd.DataFrame, event_type: str) -> float:
    """Sum ``payoff`` for rows where ``type == event_type`` in a cashflow DF."""
    validate_cashflow_dataframe(df)
    if df.empty:
        return 0.0
    mask = df["type"] == event_type
    if not mask.any():
        return 0.0
    return float(df.loc[mask, "payoff"].sum())


def reconcile_monthly_bvg_cashflows_to_annual(
    annual_cashflows: pd.DataFrame,
    monthly_cashflows: pd.DataFrame,
    reporting_year: int,
) -> pd.DataFrame:
    """Reconcile monthly vs annual BVG cashflow totals for PR and RP.

    Both inputs must be schema-valid cashflow DataFrames. KA and any other
    non-PR/RP event types are silently ignored. The reconciliation always
    emits one row for PR and one row for RP, in that order.
    """
    if not isinstance(annual_cashflows, pd.DataFrame):
        raise TypeError(
            "annual_cashflows must be a pandas DataFrame, "
            f"got {type(annual_cashflows).__name__}"
        )
    if not isinstance(monthly_cashflows, pd.DataFrame):
        raise TypeError(
            "monthly_cashflows must be a pandas DataFrame, "
            f"got {type(monthly_cashflows).__name__}"
        )
    validate_cashflow_dataframe(annual_cashflows)
    validate_cashflow_dataframe(monthly_cashflows)
    year = _validate_reporting_year(reporting_year)

    rows = []
    for event_type in RECONCILIATION_EVENT_TYPES:
        annual_payoff = _sum_payoff_by_type(annual_cashflows, event_type)
        monthly_payoff = _sum_payoff_by_type(monthly_cashflows, event_type)
        rows.append(
            _build_reconciliation_row(
                reporting_year=year,
                event_type=event_type,
                annual_payoff=annual_payoff,
                monthly_payoff=monthly_payoff,
            )
        )

    df = pd.DataFrame(
        [row.to_dict() for row in rows],
        columns=list(MONTHLY_RECONCILIATION_COLUMNS),
    )
    validate_monthly_reconciliation_dataframe(df)
    return df


def build_monthly_bvg_reconciliation_for_state(
    portfolio: BVGPortfolioState,
    reporting_year: int,
    contribution_multiplier: float = 1.0,
) -> pd.DataFrame:
    """Build the annual and monthly BVG cashflows for a state and reconcile."""
    if not isinstance(portfolio, BVGPortfolioState):
        raise TypeError(
            f"portfolio must be a BVGPortfolioState, got {type(portfolio).__name__}"
        )
    year = _validate_reporting_year(reporting_year)

    annual_df = generate_bvg_cashflow_dataframe_for_state(
        portfolio,
        f"{year}-12-31",
        contribution_multiplier,
    )
    monthly_df = generate_monthly_bvg_cashflow_dataframe_for_state(
        portfolio,
        year,
        contribution_multiplier,
    )
    return reconcile_monthly_bvg_cashflows_to_annual(
        annual_df,
        monthly_df,
        year,
    )


def validate_monthly_reconciliation_dataframe(df: pd.DataFrame) -> bool:
    """Validate a monthly reconciliation DataFrame.

    Checks the canonical column set in order, rejects missing values and
    duplicate ``(reporting_year, type)`` pairs, requires the type column to
    contain only ``RECONCILIATION_EVENT_TYPES``, and re-runs the row-level
    identity validation by reconstructing each row as a
    ``MonthlyReconciliationRow``.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"df must be a pandas DataFrame, got {type(df).__name__}"
        )

    missing = [
        column
        for column in MONTHLY_RECONCILIATION_COLUMNS
        if column not in df.columns
    ]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if list(df.columns) != list(MONTHLY_RECONCILIATION_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(MONTHLY_RECONCILIATION_COLUMNS)}, "
            f"got {list(df.columns)}"
        )

    if df.empty:
        return True

    if df[list(MONTHLY_RECONCILIATION_COLUMNS)].isna().any().any():
        raise ValueError("required columns must not contain missing values")

    seen_keys: set[tuple[int, str]] = set()
    for idx, row in df.iterrows():
        prefix = f"row {idx}"

        type_value = row["type"]
        if not isinstance(type_value, str) or not type_value.strip():
            raise ValueError(f"{prefix}: type must be a non-empty string")
        if type_value not in RECONCILIATION_EVENT_TYPES:
            raise ValueError(
                f"{prefix}: type must be one of {RECONCILIATION_EVENT_TYPES}, "
                f"got {type_value!r}"
            )

        is_close_value = bool(row["is_close"])

        reconciled = MonthlyReconciliationRow(
            reporting_year=int(row["reporting_year"]),
            type=type_value,
            annual_payoff=float(row["annual_payoff"]),
            monthly_payoff=float(row["monthly_payoff"]),
            difference=float(row["difference"]),
            abs_difference=float(row["abs_difference"]),
            is_close=is_close_value,
        )

        key = (reconciled.reporting_year, reconciled.type)
        if key in seen_keys:
            raise ValueError(
                f"{prefix}: duplicate (reporting_year, type) pair {key}"
            )
        seen_keys.add(key)

    return True
