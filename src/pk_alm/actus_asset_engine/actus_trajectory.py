"""Asset-side year-end trajectory for ACTUS-native AAL contract configs."""

from __future__ import annotations

import math
import numbers

import pandas as pd

from pk_alm.actus_asset_engine.contract_config import (
    AALContractConfig,
    validate_aal_contract_configs,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe

ACTUS_ASSET_TRAJECTORY_COLUMNS = (
    "year",
    "cash_balance",
    "pam_value",
    "stk_market_value",
    "csh_value",
    "coupon_income",
    "realized_maturity_or_td",
    "closing_asset_value",
)


def _validate_non_bool_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be >= 0, got {result}")
    return result


def _validate_non_bool_real(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    result = float(value)
    if math.isnan(result):
        raise ValueError(f"{name} must not be NaN")
    return result


def _term_float(config: AALContractConfig, key: str, default: float = 0.0) -> float:
    value = config.terms.get(key, default)
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return default
    result = float(value)
    return default if math.isnan(result) else result


def _term_year(config: AALContractConfig, key: str, default: int) -> int:
    timestamp = config.term_timestamp(key)
    if timestamp is None:
        return default
    return int(timestamp.year)


def _cashflow_total(
    cashflows: pd.DataFrame,
    *,
    year: int,
    event_types: set[str],
    source: str | None = None,
) -> float:
    if cashflows.empty:
        return 0.0
    mask = pd.to_datetime(cashflows["time"]).dt.year.eq(year)
    mask &= cashflows["type"].isin(event_types)
    if source is not None:
        mask &= cashflows["source"].eq(source)
    return float(cashflows.loc[mask, "payoff"].sum())


def _pam_value(contracts: tuple[AALContractConfig, ...], *, year: int) -> float:
    total = 0.0
    for config in contracts:
        if config.contract_type != "PAM":
            continue
        maturity_year = _term_year(config, "maturityDate", default=year)
        if year < maturity_year:
            total += _term_float(config, "notionalPrincipal")
    return float(total)


def _stk_market_value(
    contracts: tuple[AALContractConfig, ...],
    *,
    year: int,
) -> float:
    total = 0.0
    for config in contracts:
        if config.contract_type != "STK":
            continue
        purchase_year = _term_year(
            config,
            "purchaseDate",
            default=int(config.status_date.year),
        )
        termination_year = _term_year(config, "terminationDate", default=year)
        if year < purchase_year or year >= termination_year:
            continue
        quantity = _term_float(config, "quantity")
        purchase_price = _term_float(config, "priceAtPurchaseDate")
        termination_price = _term_float(
            config,
            "priceAtTerminationDate",
            default=purchase_price,
        )
        years_total = max(termination_year - purchase_year, 1)
        elapsed_years = max(year - purchase_year, 0)
        growth = (termination_price / purchase_price) ** (
            elapsed_years / years_total
        )
        total += quantity * purchase_price * growth
    return float(total)


def _csh_value(contracts: tuple[AALContractConfig, ...]) -> float:
    return float(
        sum(
            _term_float(config, "notionalPrincipal")
            for config in contracts
            if config.contract_type == "CSH"
        )
    )


def compute_actus_asset_trajectory(
    contracts: tuple[AALContractConfig, ...] | list[AALContractConfig],
    cashflows: pd.DataFrame,
    horizon_years: int,
    initial_cash: float = 0.0,
) -> pd.DataFrame:
    """Compute year-end asset snapshots from ACTUS configs and cashflows."""
    resolved_contracts = validate_aal_contract_configs(contracts)
    if not isinstance(cashflows, pd.DataFrame):
        raise TypeError(
            f"cashflows must be a pandas DataFrame, got {type(cashflows).__name__}"
        )
    validate_cashflow_dataframe(cashflows)
    horizon = _validate_non_bool_int(horizon_years, "horizon_years")
    cash_balance = _validate_non_bool_real(initial_cash, "initial_cash")

    start_year = min(int(config.status_date.year) for config in resolved_contracts)
    rows: list[dict[str, float | int]] = []
    for year in range(start_year, start_year + horizon + 1):
        year_payoff = _cashflow_total(
            cashflows,
            year=year,
            event_types=set(cashflows["type"].unique()) if not cashflows.empty else set(),
        )
        cash_balance += year_payoff

        coupon_income = _cashflow_total(
            cashflows,
            year=year,
            event_types={"IP"},
            source="ACTUS",
        )
        realized_maturity_or_td = _cashflow_total(
            cashflows,
            year=year,
            event_types={"MD", "TD"},
        )
        pam_value = _pam_value(resolved_contracts, year=year)
        stk_market_value = _stk_market_value(resolved_contracts, year=year)
        csh_value = _csh_value(resolved_contracts)
        closing_asset_value = (
            cash_balance + pam_value + stk_market_value + csh_value
        )
        rows.append(
            {
                "year": year,
                "cash_balance": cash_balance,
                "pam_value": pam_value,
                "stk_market_value": stk_market_value,
                "csh_value": csh_value,
                "coupon_income": coupon_income,
                "realized_maturity_or_td": realized_maturity_or_td,
                "closing_asset_value": closing_asset_value,
            }
        )

    return pd.DataFrame(rows, columns=list(ACTUS_ASSET_TRAJECTORY_COLUMNS))
