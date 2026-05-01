"""Mortality-weighted retiree valuation for Stage 2B.

This module is a prototype valuation layer. It uses EK 0105 as simplified
educational mortality input only; BVG 2020 / VZ 2020 would be more appropriate
for real Swiss pension-fund valuation and are intentionally out of scope.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg.formulas import calculate_retiree_pv
from pk_alm.bvg.mortality import (
    MORTALITY_MODE_EK0105,
    MORTALITY_MODE_OFF,
    MORTALITY_SOURCE_CAVEAT,
    MortalityTable,
    survival_factor,
)
from pk_alm.bvg.portfolio import BVGPortfolioState

MORTALITY_VALUATION_COLUMNS = (
    "projection_year",
    "active_count_total",
    "retired_count_total",
    "member_count_total",
    "total_capital_active",
    "total_capital_rente",
    "deterministic_retiree_obligation_pv",
    "mortality_weighted_retiree_obligation_pv",
    "pensionierungsverlust",
    "total_stage2b_liability",
    "technical_interest_rate",
    "valuation_terminal_age",
    "mortality_mode",
    "mortality_table_id",
    "mortality_table_max_age",
    "currency",
    "source_caveat",
)


@dataclass(frozen=True)
class MortalityValuationSnapshot:
    """One Stage-2B liability snapshot."""

    projection_year: int
    active_count_total: int
    retired_count_total: int
    member_count_total: int
    total_capital_active: float
    total_capital_rente: float
    deterministic_retiree_obligation_pv: float
    mortality_weighted_retiree_obligation_pv: float
    pensionierungsverlust: float
    total_stage2b_liability: float
    technical_interest_rate: float
    valuation_terminal_age: int
    mortality_mode: str
    mortality_table_id: str
    mortality_table_max_age: int
    currency: str = "CHF"
    source_caveat: str = MORTALITY_SOURCE_CAVEAT

    def __post_init__(self) -> None:
        for name in (
            "projection_year",
            "active_count_total",
            "retired_count_total",
            "member_count_total",
            "valuation_terminal_age",
            "mortality_table_max_age",
        ):
            _validate_non_bool_int(getattr(self, name), name, min_value=0)
        for name in (
            "total_capital_active",
            "total_capital_rente",
            "deterministic_retiree_obligation_pv",
            "mortality_weighted_retiree_obligation_pv",
            "total_stage2b_liability",
        ):
            _validate_non_bool_real(getattr(self, name), name, min_value=0.0)
        _validate_non_bool_real(self.pensionierungsverlust, "pensionierungsverlust")
        _validate_non_bool_real(
            self.technical_interest_rate,
            "technical_interest_rate",
            min_value=-1.0,
            allow_equal_min=False,
        )
        if self.member_count_total != self.active_count_total + self.retired_count_total:
            raise ValueError("member_count_total must equal active + retired")
        expected = (
            self.total_capital_active
            + self.mortality_weighted_retiree_obligation_pv
        )
        if not math.isclose(self.total_stage2b_liability, expected, abs_tol=1e-5):
            raise ValueError("total_stage2b_liability identity failed")
        if self.mortality_mode not in (MORTALITY_MODE_OFF, MORTALITY_MODE_EK0105):
            raise ValueError("invalid mortality_mode")
        for name in ("mortality_table_id", "currency", "source_caveat"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")

    def to_dict(self) -> dict[str, object]:
        return {col: getattr(self, col) for col in MORTALITY_VALUATION_COLUMNS}


def mortality_weighted_retiree_pv_per_person(
    annual_pension: float,
    current_age: int,
    technical_interest_rate: float,
    table: MortalityTable,
    terminal_age: int | None = None,
) -> float:
    """Return mortality-weighted annuity-due PV for one retired person."""
    pension = _validate_non_bool_real(annual_pension, "annual_pension", min_value=0.0)
    age = _validate_non_bool_int(current_age, "current_age", min_value=0)
    rate = _validate_non_bool_real(
        technical_interest_rate,
        "technical_interest_rate",
        min_value=-1.0,
        allow_equal_min=False,
    )
    if not isinstance(table, MortalityTable):
        raise TypeError(f"table must be MortalityTable, got {type(table).__name__}")
    if age > table.max_age:
        return 0.0
    terminal = table.max_age if terminal_age is None else min(
        _validate_non_bool_int(terminal_age, "terminal_age", min_value=0),
        table.max_age,
    )
    if age >= terminal:
        return 0.0

    pv = 0.0
    max_terms = terminal - age
    for t in range(max_terms):
        pv += pension * survival_factor(table, age, t) / ((1.0 + rate) ** t)
    return pv


def value_portfolio_state_stage2b(
    portfolio: BVGPortfolioState,
    technical_interest_rate: float,
    valuation_terminal_age: int,
    mortality_mode: str,
    mortality_table: MortalityTable | None,
    currency: str = "CHF",
) -> MortalityValuationSnapshot:
    """Compute one Stage-2B valuation snapshot."""
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
    if mortality_mode not in (MORTALITY_MODE_OFF, MORTALITY_MODE_EK0105):
        raise ValueError("invalid mortality_mode")
    if mortality_mode == MORTALITY_MODE_EK0105 and not isinstance(
        mortality_table, MortalityTable
    ):
        raise TypeError("mortality_table must be MortalityTable in ek0105 mode")

    deterministic_pv = 0.0
    mortality_pv = 0.0
    for cohort in portfolio.retired_cohorts:
        remaining_years = max(0, terminal_age - cohort.age)
        if remaining_years > 0:
            deterministic_pv += cohort.count * calculate_retiree_pv(
                cohort.annual_pension_per_person,
                remaining_years,
                rate,
            )
        if mortality_mode == MORTALITY_MODE_OFF:
            mortality_pv = deterministic_pv
        else:
            mortality_pv += cohort.count * mortality_weighted_retiree_pv_per_person(
                cohort.annual_pension_per_person,
                cohort.age,
                rate,
                mortality_table,  # type: ignore[arg-type]
                terminal_age=terminal_age,
            )

    total_capital_active = portfolio.total_capital_active
    total_stage2b_liability = total_capital_active + mortality_pv
    pensionierungsverlust = mortality_pv - portfolio.total_capital_rente

    return MortalityValuationSnapshot(
        projection_year=portfolio.projection_year,
        active_count_total=portfolio.active_count_total,
        retired_count_total=portfolio.retired_count_total,
        member_count_total=portfolio.member_count_total,
        total_capital_active=total_capital_active,
        total_capital_rente=portfolio.total_capital_rente,
        deterministic_retiree_obligation_pv=deterministic_pv,
        mortality_weighted_retiree_obligation_pv=mortality_pv,
        pensionierungsverlust=pensionierungsverlust,
        total_stage2b_liability=total_stage2b_liability,
        technical_interest_rate=rate,
        valuation_terminal_age=terminal_age,
        mortality_mode=mortality_mode,
        mortality_table_id=(
            "OFF" if mortality_table is None else mortality_table.table_id
        ),
        mortality_table_max_age=(
            terminal_age if mortality_table is None else mortality_table.max_age
        ),
        currency=currency,
    )


def value_portfolio_states_stage2b(
    portfolio_states: list | tuple,
    technical_interest_rate: float,
    valuation_terminal_age: int,
    mortality_mode: str,
    mortality_table: MortalityTable | None,
    currency: str = "CHF",
) -> pd.DataFrame:
    snapshots = [
        value_portfolio_state_stage2b(
            state,
            technical_interest_rate,
            valuation_terminal_age,
            mortality_mode,
            mortality_table,
            currency,
        )
        for state in portfolio_states
    ]
    df = pd.DataFrame(
        [snapshot.to_dict() for snapshot in snapshots],
        columns=list(MORTALITY_VALUATION_COLUMNS),
    )
    validate_mortality_valuation_dataframe(df)
    return df


def validate_mortality_valuation_dataframe(df: pd.DataFrame) -> bool:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"df must be pandas DataFrame, got {type(df).__name__}")
    if list(df.columns) != list(MORTALITY_VALUATION_COLUMNS):
        raise ValueError("invalid mortality valuation columns")
    for _, row in df.iterrows():
        MortalityValuationSnapshot(**{col: row[col] for col in MORTALITY_VALUATION_COLUMNS})
    return True


def _validate_non_bool_int(
    value: object,
    name: str,
    *,
    min_value: int | None = None,
) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    ivalue = int(value)
    if min_value is not None and ivalue < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {ivalue}")
    return ivalue


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
        if allow_equal_min and fval < min_value:
            raise ValueError(f"{name} must be >= {min_value}, got {fval}")
        if not allow_equal_min and fval <= min_value:
            raise ValueError(f"{name} must be > {min_value}, got {fval}")
    return fval
