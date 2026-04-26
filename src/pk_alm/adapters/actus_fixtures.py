"""Deterministic ACTUS-style event fixtures for tests and examples.

This module provides manually checkable ACTUS-style event dictionaries for
the adapter boundary. It does not import or call AAL, does not depend on an
ACTUS service, and is not an asset engine.

The fixed-rate bond fixture assumes by default that the bond is already held
in the portfolio at ``start_year`` and therefore does not generate an initial
purchase cashflow. If ``include_purchase_event=True``, an initial ``IED``
purchase cashflow is generated from the pension fund investor perspective.
"""

from __future__ import annotations

import math
import numbers

import pandas as pd

from pk_alm.adapters.actus_adapter import actus_events_to_cashflow_dataframe


def _validate_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


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
    result = int(value)
    if min_value is not None and result < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {result}")
    return result


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
    result = float(value)
    if math.isnan(result):
        raise ValueError(f"{name} must not be NaN")
    if min_value is not None:
        if allow_equal_min:
            if result < min_value:
                raise ValueError(f"{name} must be >= {min_value}, got {result}")
        else:
            if result <= min_value:
                raise ValueError(f"{name} must be > {min_value}, got {result}")
    return result


def _validate_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be bool, got {type(value).__name__}")
    return value


def _bond_event(
    *,
    contract_id: str,
    event_date: str,
    event_type: str,
    payoff: float,
    nominal_value: float,
    currency: str,
) -> dict[str, object]:
    return {
        "contract_id": contract_id,
        "event_date": event_date,
        "event_type": event_type,
        "payoff": payoff,
        "nominal_value": nominal_value,
        "currency": currency,
    }


def build_fixed_rate_bond_events(
    *,
    contract_id: str,
    start_year: int,
    maturity_year: int,
    nominal_value: float,
    annual_coupon_rate: float,
    currency: str = "CHF",
    include_purchase_event: bool = False,
) -> tuple[dict, ...]:
    """Build deterministic ACTUS-style events for a fixed-rate bond.

    Payoffs are from the pension fund investor perspective: coupons and
    maturity redemption are positive inflows, while the optional initial
    purchase event is a negative outflow.
    """
    cid = _validate_non_empty_string(contract_id, "contract_id")
    start = _validate_non_bool_int(start_year, "start_year", min_value=0)
    maturity = _validate_non_bool_int(maturity_year, "maturity_year")
    if maturity <= start:
        raise ValueError(
            "maturity_year must be > start_year "
            f"({maturity} <= {start})"
        )

    nominal = _validate_non_bool_real(
        nominal_value,
        "nominal_value",
        min_value=0.0,
        allow_equal_min=False,
    )
    coupon_rate = _validate_non_bool_real(
        annual_coupon_rate,
        "annual_coupon_rate",
        min_value=0.0,
    )
    cur = _validate_non_empty_string(currency, "currency")
    include_purchase = _validate_bool(
        include_purchase_event,
        "include_purchase_event",
    )

    events: list[dict[str, object]] = []
    if include_purchase:
        events.append(
            _bond_event(
                contract_id=cid,
                event_date=f"{start}-01-01",
                event_type="IED",
                payoff=-nominal,
                nominal_value=nominal,
                currency=cur,
            )
        )

    coupon = nominal * coupon_rate
    for year in range(start + 1, maturity + 1):
        event_date = f"{year}-12-31"
        events.append(
            _bond_event(
                contract_id=cid,
                event_date=event_date,
                event_type="IP",
                payoff=coupon,
                nominal_value=nominal,
                currency=cur,
            )
        )
        if year == maturity:
            events.append(
                _bond_event(
                    contract_id=cid,
                    event_date=event_date,
                    event_type="MD",
                    payoff=nominal,
                    nominal_value=nominal,
                    currency=cur,
                )
            )

    return tuple(events)


def build_fixed_rate_bond_cashflow_dataframe(
    *,
    contract_id: str,
    start_year: int,
    maturity_year: int,
    nominal_value: float,
    annual_coupon_rate: float,
    currency: str = "CHF",
    include_purchase_event: bool = False,
) -> pd.DataFrame:
    """Build fixed-rate bond events and convert them through the ACTUS adapter."""
    events = build_fixed_rate_bond_events(
        contract_id=contract_id,
        start_year=start_year,
        maturity_year=maturity_year,
        nominal_value=nominal_value,
        annual_coupon_rate=annual_coupon_rate,
        currency=currency,
        include_purchase_event=include_purchase_event,
    )
    return actus_events_to_cashflow_dataframe(events)
