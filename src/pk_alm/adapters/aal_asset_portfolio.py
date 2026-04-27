"""Offline-safe AAL/ACTUS asset portfolio helpers.

This module represents a small pension-fund asset portfolio as multiple
PAM-like contract specifications. It can construct real AAL PAM contracts and
an AAL Portfolio when AAL is available, but it never calls PublicActusService
or any network endpoint. Offline cashflows are generated through the existing
ACTUS-style fixed-rate fixtures and the canonical CashflowRecord schema.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import numbers
from types import ModuleType
from typing import Any

import pandas as pd

from pk_alm.adapters.aal_asset_boundary import (
    build_aal_pam_contract,
    build_aal_portfolio,
)
from pk_alm.adapters.actus_fixtures import build_fixed_rate_bond_cashflow_dataframe
from pk_alm.cashflows.schema import validate_cashflow_dataframe


def _validate_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_non_bool_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return int(value)


def _validate_non_bool_real(
    value: object,
    name: str,
    *,
    min_value: float,
    allow_equal_min: bool,
) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    result = float(value)
    if math.isnan(result):
        raise ValueError(f"{name} must not be NaN")
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


@dataclass(frozen=True)
class AALAssetContractSpec:
    """Specification for one PAM-like pension-fund asset contract."""

    contract_id: str
    start_year: int
    maturity_year: int
    nominal_value: float
    coupon_rate: float
    currency: str = "CHF"
    include_purchase_event: bool = False

    def __post_init__(self) -> None:
        contract_id = _validate_non_empty_string(self.contract_id, "contract_id")
        start_year = _validate_non_bool_int(self.start_year, "start_year")
        maturity_year = _validate_non_bool_int(self.maturity_year, "maturity_year")
        if maturity_year <= start_year:
            raise ValueError(
                "maturity_year must be > start_year "
                f"({maturity_year} <= {start_year})"
            )
        nominal_value = _validate_non_bool_real(
            self.nominal_value,
            "nominal_value",
            min_value=0.0,
            allow_equal_min=False,
        )
        coupon_rate = _validate_non_bool_real(
            self.coupon_rate,
            "coupon_rate",
            min_value=0.0,
            allow_equal_min=True,
        )
        currency = _validate_non_empty_string(self.currency, "currency")
        include_purchase_event = _validate_bool(
            self.include_purchase_event,
            "include_purchase_event",
        )

        object.__setattr__(self, "contract_id", contract_id)
        object.__setattr__(self, "start_year", start_year)
        object.__setattr__(self, "maturity_year", maturity_year)
        object.__setattr__(self, "nominal_value", nominal_value)
        object.__setattr__(self, "coupon_rate", coupon_rate)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(
            self,
            "include_purchase_event",
            include_purchase_event,
        )


DEFAULT_AAL_ASSET_CONTRACT_SPECS: tuple[AALAssetContractSpec, ...] = (
    AALAssetContractSpec(
        contract_id="AAL_PAM_BOND_1",
        start_year=2026,
        maturity_year=2028,
        nominal_value=100_000.0,
        coupon_rate=0.020,
    ),
    AALAssetContractSpec(
        contract_id="AAL_PAM_BOND_2",
        start_year=2026,
        maturity_year=2030,
        nominal_value=150_000.0,
        coupon_rate=0.025,
    ),
    AALAssetContractSpec(
        contract_id="AAL_PAM_BOND_3",
        start_year=2027,
        maturity_year=2031,
        nominal_value=75_000.0,
        coupon_rate=0.015,
    ),
)


def get_default_aal_asset_contract_specs() -> tuple[AALAssetContractSpec, ...]:
    """Return the default manually inspectable mini asset portfolio."""
    return DEFAULT_AAL_ASSET_CONTRACT_SPECS


def validate_aal_asset_contract_specs(
    specs: tuple[AALAssetContractSpec, ...] | list[AALAssetContractSpec],
) -> tuple[AALAssetContractSpec, ...]:
    """Validate portfolio-level constraints for AAL asset contract specs."""
    if not isinstance(specs, (list, tuple)):
        raise TypeError(f"specs must be list or tuple, got {type(specs).__name__}")
    if not specs:
        raise ValueError("specs must not be empty")

    validated: list[AALAssetContractSpec] = []
    for i, spec in enumerate(specs):
        if not isinstance(spec, AALAssetContractSpec):
            raise TypeError(
                f"specs[{i}] must be AALAssetContractSpec, "
                f"got {type(spec).__name__}"
            )
        validated.append(spec)

    contract_ids = [spec.contract_id for spec in validated]
    duplicates = sorted({cid for cid in contract_ids if contract_ids.count(cid) > 1})
    if duplicates:
        raise ValueError(f"duplicate contract_id values: {duplicates}")

    currencies = {spec.currency for spec in validated}
    if len(currencies) != 1:
        raise ValueError(
            "mixed currencies are not supported for Stage-1 portfolio analytics"
        )

    return tuple(validated)


def _resolve_specs(
    specs: tuple[AALAssetContractSpec, ...] | list[AALAssetContractSpec] | None,
) -> tuple[AALAssetContractSpec, ...]:
    if specs is None:
        return validate_aal_asset_contract_specs(get_default_aal_asset_contract_specs())
    return validate_aal_asset_contract_specs(specs)


def build_aal_pam_contracts_from_specs(
    module: ModuleType | Any,
    specs: tuple[AALAssetContractSpec, ...] | list[AALAssetContractSpec] | None = None,
) -> tuple[object, ...]:
    """Construct real AAL PAM contracts from portfolio specs.

    This function only constructs AAL model objects. It does not generate
    events, call PublicActusService, or contact any network endpoint.
    """
    resolved = _resolve_specs(specs)
    return tuple(
        build_aal_pam_contract(
            module,
            contract_id=spec.contract_id,
            start_year=spec.start_year,
            maturity_year=spec.maturity_year,
            nominal_value=spec.nominal_value,
            coupon_rate=spec.coupon_rate,
            currency=spec.currency,
        )
        for spec in resolved
    )


def build_aal_portfolio_from_specs(
    module: ModuleType | Any,
    specs: tuple[AALAssetContractSpec, ...] | list[AALAssetContractSpec] | None = None,
) -> object:
    """Construct a real AAL Portfolio from portfolio specs."""
    contracts = list(build_aal_pam_contracts_from_specs(module, specs))
    return build_aal_portfolio(module, contracts)


def build_aal_asset_portfolio_fallback_cashflows(
    specs: tuple[AALAssetContractSpec, ...] | list[AALAssetContractSpec] | None = None,
) -> pd.DataFrame:
    """Return schema-valid ACTUS fallback cashflows for an asset portfolio."""
    resolved = _resolve_specs(specs)
    frames = [
        build_fixed_rate_bond_cashflow_dataframe(
            contract_id=spec.contract_id,
            start_year=spec.start_year,
            maturity_year=spec.maturity_year,
            nominal_value=spec.nominal_value,
            annual_coupon_rate=spec.coupon_rate,
            currency=spec.currency,
            include_purchase_event=spec.include_purchase_event,
        )
        for spec in resolved
    ]
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(
        ["time", "source", "contractId", "type"],
        ignore_index=True,
    )
    validate_cashflow_dataframe(df)
    if not (df["source"] == "ACTUS").all():
        raise ValueError('fallback cashflows source values must all be "ACTUS"')
    return df
