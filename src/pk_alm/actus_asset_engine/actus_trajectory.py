"""Asset-side year-end trajectory for live AAL server cashflows.

The trajectory uses only real AAL/ACTUS server events as cashflows. STK market
values are still valued from the scenario assumption while open, but missing
STK dividends and CSH interest are not synthesized as cashflows.
"""

from __future__ import annotations

import math
import numbers

import pandas as pd

from pk_alm.actus_asset_engine.aal_asset_portfolio import (
    AssetSpec,
    CSHSpec,
    PAMSpec,
    STKSpec,
    validate_aal_asset_contract_specs,
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


def _pam_value(pam_specs: tuple[PAMSpec, ...], *, year: int) -> float:
    return float(
        sum(spec.nominal_value for spec in pam_specs if year < spec.maturity_year)
    )


def _stk_market_value(stk_specs: tuple[STKSpec, ...], *, year: int) -> float:
    total = 0.0
    for spec in stk_specs:
        if year < spec.start_year or year >= spec.divestment_year:
            continue
        elapsed_years = year - spec.start_year
        total += (
            spec.quantity
            * spec.price_at_purchase
            * ((1.0 + spec.market_value_growth) ** elapsed_years)
        )
    return float(total)


def compute_actus_asset_trajectory(
    specs: tuple[AssetSpec, ...] | list[AssetSpec],
    cashflows: pd.DataFrame,
    horizon_years: int,
    initial_cash: float = 0.0,
) -> pd.DataFrame:
    """Compute asset-side year-end snapshots from specs and asset cashflows.

    This helper is asset-side only. It does not include BVG net cashflows;
    scenario runners combine BVG and asset cashflows in a later layer.
    """
    resolved_specs = validate_aal_asset_contract_specs(specs)
    if not isinstance(cashflows, pd.DataFrame):
        raise TypeError(
            f"cashflows must be a pandas DataFrame, got {type(cashflows).__name__}"
        )
    validate_cashflow_dataframe(cashflows)
    horizon = _validate_non_bool_int(horizon_years, "horizon_years")
    cash_balance = _validate_non_bool_real(initial_cash, "initial_cash")

    pam_specs = tuple(spec for spec in resolved_specs if isinstance(spec, PAMSpec))
    stk_specs = tuple(spec for spec in resolved_specs if isinstance(spec, STKSpec))
    csh_specs = tuple(spec for spec in resolved_specs if isinstance(spec, CSHSpec))

    start_year = min(spec.start_year for spec in resolved_specs)
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
        pam_value = _pam_value(pam_specs, year=year)
        stk_market_value = _stk_market_value(stk_specs, year=year)
        csh_value = float(sum(spec.nominal_value for spec in csh_specs))
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
