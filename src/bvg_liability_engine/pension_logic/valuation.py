"""Deterministic Stage-1 BVG liability valuation.

This module produces a simplified liability proxy:

    total_stage1_liability = total_capital_active + retiree_obligation_pv

It deliberately excludes technical provisions / technical reserves
(longevity, risk, fluctuation, additional reserves for pension losses).
Those belong to a later actuarial / funding-ratio layer.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg_liability_engine.pension_logic.formulas import calculate_pensionierungsverlust, calculate_retiree_pv
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState

VALUATION_COLUMNS = (
    "projection_year",
    "active_count_total",
    "retired_count_total",
    "member_count_total",
    "total_capital_active",
    "total_capital_rente",
    "retiree_obligation_pv",
    "pensionierungsverlust",
    "total_stage1_liability",
    "technical_interest_rate",
    "valuation_terminal_age",
    "currency",
)

_LIABILITY_TOLERANCE = 1e-5

_NON_NEGATIVE_INT_FIELDS = (
    "projection_year",
    "active_count_total",
    "retired_count_total",
    "member_count_total",
    "valuation_terminal_age",
)
_NON_NEGATIVE_REAL_FIELDS = (
    "total_capital_active",
    "total_capital_rente",
    "retiree_obligation_pv",
    "total_stage1_liability",
)


# ---------------------------------------------------------------------------
# Validation helpers (local; same style as the rest of the codebase)
# ---------------------------------------------------------------------------


def _validate_non_bool_int(
    value: object, name: str, *, min_value: int | None = None
) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def _validate_non_bool_real(
    value: object,
    name: str,
    *,
    min_value: float | None = None,
    allow_equal_min: bool = True,
) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    if min_value is not None:
        if allow_equal_min:
            if fval < min_value:
                raise ValueError(f"{name} must be >= {min_value}, got {fval}")
        else:
            if fval <= min_value:
                raise ValueError(f"{name} must be > {min_value}, got {fval}")
    return fval


def _validate_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BVGValuationSnapshot:
    """Frozen Stage-1 valuation snapshot for one BVGPortfolioState.

    `total_stage1_liability` is a simplified Stage-1 liability proxy and
    deliberately excludes technical reserves. It is NOT a full actuarial
    technical reserve.
    """

    projection_year: int
    active_count_total: int
    retired_count_total: int
    member_count_total: int
    total_capital_active: float
    total_capital_rente: float
    retiree_obligation_pv: float
    pensionierungsverlust: float
    total_stage1_liability: float
    technical_interest_rate: float
    valuation_terminal_age: int
    currency: str = "CHF"

    def __post_init__(self) -> None:
        for fname in _NON_NEGATIVE_INT_FIELDS:
            _validate_non_bool_int(getattr(self, fname), fname, min_value=0)
        for fname in _NON_NEGATIVE_REAL_FIELDS:
            _validate_non_bool_real(getattr(self, fname), fname, min_value=0.0)

        # pensionierungsverlust may be negative
        _validate_non_bool_real(self.pensionierungsverlust, "pensionierungsverlust")

        _validate_non_bool_real(
            self.technical_interest_rate,
            "technical_interest_rate",
            min_value=-1.0,
            allow_equal_min=False,
        )

        _validate_non_empty_string(self.currency, "currency")

        if (
            self.member_count_total
            != self.active_count_total + self.retired_count_total
        ):
            raise ValueError(
                "member_count_total must equal active_count_total + retired_count_total "
                f"({self.active_count_total} + {self.retired_count_total} != "
                f"{self.member_count_total})"
            )

        expected = self.total_capital_active + self.retiree_obligation_pv
        if not math.isclose(
            self.total_stage1_liability, expected, abs_tol=_LIABILITY_TOLERANCE
        ):
            raise ValueError(
                "total_stage1_liability must equal "
                "total_capital_active + retiree_obligation_pv "
                f"({self.total_capital_active} + {self.retiree_obligation_pv} = "
                f"{expected}, got {self.total_stage1_liability})"
            )

    def to_dict(self) -> dict[str, object]:
        return {col: getattr(self, col) for col in VALUATION_COLUMNS}


# ---------------------------------------------------------------------------
# Single-state valuation
# ---------------------------------------------------------------------------


def value_portfolio_state(
    portfolio: BVGPortfolioState,
    technical_interest_rate: float,
    valuation_terminal_age: int = 90,
    currency: str = "CHF",
) -> BVGValuationSnapshot:
    """Compute a Stage-1 liability snapshot for one portfolio state.

    Active liabilities = accumulated active savings capital.
    Retired liabilities = present value of future pension payments,
    discounted to the cohort's current age, capped at `valuation_terminal_age`.
    `pensionierungsverlust = retiree_obligation_pv - total_capital_rente`.
    """
    if not isinstance(portfolio, BVGPortfolioState):
        raise TypeError(
            f"portfolio must be BVGPortfolioState, got {type(portfolio).__name__}"
        )

    rate = _validate_non_bool_real(
        technical_interest_rate,
        "technical_interest_rate",
        min_value=-1.0,
        allow_equal_min=False,
    )
    terminal_age = _validate_non_bool_int(
        valuation_terminal_age, "valuation_terminal_age", min_value=0
    )
    cur = _validate_non_empty_string(currency, "currency")

    total_capital_active = portfolio.total_capital_active
    total_capital_rente = portfolio.total_capital_rente

    retiree_obligation_pv = 0.0
    for cohort in portfolio.retired_cohorts:
        remaining_years = max(0, terminal_age - cohort.age)
        if remaining_years == 0:
            continue
        pv_per_person = calculate_retiree_pv(
            cohort.annual_pension_per_person, remaining_years, rate
        )
        retiree_obligation_pv += cohort.count * pv_per_person

    pensionierungsverlust = calculate_pensionierungsverlust(
        retiree_obligation_pv, total_capital_rente
    )
    total_stage1_liability = total_capital_active + retiree_obligation_pv

    return BVGValuationSnapshot(
        projection_year=portfolio.projection_year,
        active_count_total=portfolio.active_count_total,
        retired_count_total=portfolio.retired_count_total,
        member_count_total=portfolio.member_count_total,
        total_capital_active=total_capital_active,
        total_capital_rente=total_capital_rente,
        retiree_obligation_pv=retiree_obligation_pv,
        pensionierungsverlust=pensionierungsverlust,
        total_stage1_liability=total_stage1_liability,
        technical_interest_rate=rate,
        valuation_terminal_age=terminal_age,
        currency=cur,
    )


# ---------------------------------------------------------------------------
# Snapshots → DataFrame
# ---------------------------------------------------------------------------


def valuation_snapshots_to_dataframe(snapshots: list | tuple) -> pd.DataFrame:
    if not isinstance(snapshots, (list, tuple)):
        raise TypeError(
            f"snapshots must be list or tuple, got {type(snapshots).__name__}"
        )
    for i, s in enumerate(snapshots):
        if not isinstance(s, BVGValuationSnapshot):
            raise TypeError(
                f"snapshots[{i}] must be BVGValuationSnapshot, "
                f"got {type(s).__name__}"
            )
    return pd.DataFrame(
        [s.to_dict() for s in snapshots], columns=list(VALUATION_COLUMNS)
    )


# ---------------------------------------------------------------------------
# DataFrame validation
# ---------------------------------------------------------------------------


def validate_valuation_dataframe(df: pd.DataFrame) -> bool:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"df must be a pandas DataFrame, got {type(df).__name__}"
        )

    missing = [c for c in VALUATION_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    if list(df.columns) != list(VALUATION_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(VALUATION_COLUMNS)}, "
            f"got {list(df.columns)}"
        )

    if df[list(VALUATION_COLUMNS)].isna().any().any():
        raise ValueError("required columns must not contain NaN/None/NaT/pd.NA")

    for idx, row in df.iterrows():
        prefix = f"row {idx}"

        for fname in _NON_NEGATIVE_INT_FIELDS:
            v = row[fname]
            if v < 0:
                raise ValueError(f"{prefix}: {fname} must be >= 0, got {v}")

        if (
            row["member_count_total"]
            != row["active_count_total"] + row["retired_count_total"]
        ):
            raise ValueError(
                f"{prefix}: member_count_total must equal "
                "active_count_total + retired_count_total"
            )

        for fname in _NON_NEGATIVE_REAL_FIELDS:
            v = row[fname]
            if v < 0:
                raise ValueError(f"{prefix}: {fname} must be >= 0, got {v}")

        if row["technical_interest_rate"] <= -1:
            raise ValueError(
                f"{prefix}: technical_interest_rate must be > -1, "
                f"got {row['technical_interest_rate']}"
            )

        cur = row["currency"]
        if not isinstance(cur, str) or not cur.strip():
            raise ValueError(f"{prefix}: currency must be a non-empty string")

        expected = row["total_capital_active"] + row["retiree_obligation_pv"]
        if not math.isclose(
            row["total_stage1_liability"], expected, abs_tol=_LIABILITY_TOLERANCE
        ):
            raise ValueError(
                f"{prefix}: total_stage1_liability must equal "
                f"total_capital_active + retiree_obligation_pv "
                f"(expected {expected}, got {row['total_stage1_liability']})"
            )

    return True


# ---------------------------------------------------------------------------
# Trajectory valuation
# ---------------------------------------------------------------------------


def value_portfolio_states(
    portfolio_states: list | tuple,
    technical_interest_rate: float,
    valuation_terminal_age: int = 90,
    currency: str = "CHF",
) -> pd.DataFrame:
    if not isinstance(portfolio_states, (list, tuple)):
        raise TypeError(
            f"portfolio_states must be list or tuple, "
            f"got {type(portfolio_states).__name__}"
        )
    for i, p in enumerate(portfolio_states):
        if not isinstance(p, BVGPortfolioState):
            raise TypeError(
                f"portfolio_states[{i}] must be BVGPortfolioState, "
                f"got {type(p).__name__}"
            )

    snapshots = [
        value_portfolio_state(
            p, technical_interest_rate, valuation_terminal_age, currency
        )
        for p in portfolio_states
    ]
    df = valuation_snapshots_to_dataframe(snapshots)
    validate_valuation_dataframe(df)
    return df
