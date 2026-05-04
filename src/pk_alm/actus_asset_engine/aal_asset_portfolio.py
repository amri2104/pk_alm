"""AAL/ACTUS asset portfolio specs and construction helpers.

Phase 2 asset modelling uses explicit spec classes for PAM bonds, STK
positions, and CSH cash positions. PAM, STK, and CSH contracts are sent to
the live AAL server. The engine records only server-emitted asset cashflows:
PAM emits IP/MD, STK currently emits TD but no DV on the tested public AAL
reference server, and CSH currently emits no temporal events.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import numbers
from types import ModuleType
from typing import Any, TypeAlias

from pk_alm.actus_asset_engine.aal_asset_boundary import (
    build_aal_cash_contract,
    build_aal_pam_contract,
    build_aal_portfolio,
    build_aal_stk_contract,
)


def _validate_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_currency(value: object, name: str = "currency") -> str:
    currency = _validate_non_empty_string(value, name)
    if len(currency) != 3 or not currency.isalpha() or currency.upper() != currency:
        raise ValueError(f"{name} must be a 3-letter uppercase ISO-4217 code")
    return currency


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


def _derive_stk_terminal_price(
    *,
    start_year: int,
    divestment_year: int,
    price_at_purchase: float,
    market_value_growth: float,
) -> float:
    years = divestment_year - start_year
    return price_at_purchase * ((1.0 + market_value_growth) ** years)


class AALAssetContractSpec:
    """Compatibility base class for Phase 2 asset specs.

    The concrete, instantiable specs are ``PAMSpec``, ``STKSpec``, and
    ``CSHSpec``. This base exists so untouched integration code that imports
    ``AALAssetContractSpec`` can continue to type-check and use
    ``isinstance(..., AALAssetContractSpec)`` until the engine refactor.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        if type(self) is AALAssetContractSpec:
            raise TypeError(
                "AALAssetContractSpec is a compatibility base; "
                "instantiate PAMSpec, STKSpec, or CSHSpec"
            )
        super().__init__()


@dataclass(frozen=True)
class PAMSpec(AALAssetContractSpec):
    """Specification for one PAM bond contract."""

    contract_id: str
    start_year: int
    maturity_year: int
    nominal_value: float
    coupon_rate: float
    coupon_cycle: str = "P1YL1"
    coupon_anchor_date: str | None = None
    currency: str = "CHF"

    @property
    def contract_type(self) -> str:
        return "PAM"

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
        coupon_cycle = _validate_non_empty_string(
            self.coupon_cycle, "coupon_cycle"
        )
        coupon_anchor_date = self.coupon_anchor_date
        if coupon_anchor_date is not None:
            coupon_anchor_date = _validate_non_empty_string(
                coupon_anchor_date, "coupon_anchor_date"
            )
        currency = _validate_currency(self.currency)

        object.__setattr__(self, "contract_id", contract_id)
        object.__setattr__(self, "start_year", start_year)
        object.__setattr__(self, "maturity_year", maturity_year)
        object.__setattr__(self, "nominal_value", nominal_value)
        object.__setattr__(self, "coupon_rate", coupon_rate)
        object.__setattr__(self, "coupon_cycle", coupon_cycle)
        object.__setattr__(self, "coupon_anchor_date", coupon_anchor_date)
        object.__setattr__(self, "currency", currency)


@dataclass(frozen=True)
class STKSpec(AALAssetContractSpec):
    """Specification for one STK position.

    ``dividend_yield`` declares dividend intent in the AAL Group 1 terms when
    positive. The tested public AAL reference server does not emit DV events,
    and the Python engine does not synthesize dividends.

    ``market_value_growth`` is used to derive ``price_at_termination`` for the
    ACTUS TD event and to value the open STK position in asset snapshots. It
    does not generate Python-side cashflow events.
    """

    contract_id: str
    start_year: int
    divestment_year: int
    quantity: float
    price_at_purchase: float
    price_at_termination: float
    currency: str = "CHF"
    dividend_yield: float = 0.0
    market_value_growth: float = 0.0

    @property
    def contract_type(self) -> str:
        return "STK"

    @property
    def nominal_value(self) -> float:
        return self.quantity * self.price_at_purchase

    def __post_init__(self) -> None:
        contract_id = _validate_non_empty_string(self.contract_id, "contract_id")
        start_year = _validate_non_bool_int(self.start_year, "start_year")
        divestment_year = _validate_non_bool_int(
            self.divestment_year, "divestment_year"
        )
        if divestment_year <= start_year:
            raise ValueError(
                "divestment_year must be > start_year "
                f"({divestment_year} <= {start_year})"
            )
        quantity = _validate_non_bool_real(
            self.quantity,
            "quantity",
            min_value=0.0,
            allow_equal_min=False,
        )
        price_at_purchase = _validate_non_bool_real(
            self.price_at_purchase,
            "price_at_purchase",
            min_value=0.0,
            allow_equal_min=False,
        )
        price_at_termination = _validate_non_bool_real(
            self.price_at_termination,
            "price_at_termination",
            min_value=0.0,
            allow_equal_min=False,
        )
        dividend_yield = _validate_non_bool_real(
            self.dividend_yield,
            "dividend_yield",
            min_value=0.0,
            allow_equal_min=True,
        )
        market_value_growth = _validate_non_bool_real(
            self.market_value_growth,
            "market_value_growth",
            min_value=-1.0,
            allow_equal_min=False,
        )
        currency = _validate_currency(self.currency)

        object.__setattr__(self, "contract_id", contract_id)
        object.__setattr__(self, "start_year", start_year)
        object.__setattr__(self, "divestment_year", divestment_year)
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "price_at_purchase", price_at_purchase)
        object.__setattr__(self, "price_at_termination", price_at_termination)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "dividend_yield", dividend_yield)
        object.__setattr__(self, "market_value_growth", market_value_growth)


@dataclass(frozen=True)
class CSHSpec(AALAssetContractSpec):
    """Specification for one CSH cash position.

    CSH is sent to the live AAL Portfolio for completeness. The tested public
    AAL reference server emits no temporal CSH events, and the Python engine
    does not synthesize cash interest.
    """

    contract_id: str
    start_year: int
    nominal_value: float
    currency: str = "CHF"

    @property
    def contract_type(self) -> str:
        return "CSH"

    def __post_init__(self) -> None:
        contract_id = _validate_non_empty_string(self.contract_id, "contract_id")
        start_year = _validate_non_bool_int(self.start_year, "start_year")
        nominal_value = _validate_non_bool_real(
            self.nominal_value,
            "nominal_value",
            min_value=0.0,
            allow_equal_min=False,
        )
        currency = _validate_currency(self.currency)

        object.__setattr__(self, "contract_id", contract_id)
        object.__setattr__(self, "start_year", start_year)
        object.__setattr__(self, "nominal_value", nominal_value)
        object.__setattr__(self, "currency", currency)


AssetSpec: TypeAlias = PAMSpec | STKSpec | CSHSpec


def _stk_spec_from_nominal(
    *,
    contract_id: str,
    start_year: int,
    divestment_year: int,
    nominal_value: float,
    dividend_yield: float,
    market_value_growth: float,
    price_at_purchase: float = 100.0,
    currency: str = "CHF",
) -> STKSpec:
    quantity = nominal_value / price_at_purchase
    price_at_termination = _derive_stk_terminal_price(
        start_year=start_year,
        divestment_year=divestment_year,
        price_at_purchase=price_at_purchase,
        market_value_growth=market_value_growth,
    )
    return STKSpec(
        contract_id=contract_id,
        start_year=start_year,
        divestment_year=divestment_year,
        quantity=quantity,
        price_at_purchase=price_at_purchase,
        price_at_termination=price_at_termination,
        currency=currency,
        dividend_yield=dividend_yield,
        market_value_growth=market_value_growth,
    )


DEFAULT_AAL_ASSET_CONTRACT_SPECS: tuple[AssetSpec, ...] = (
    PAMSpec(
        contract_id="AAL_PAM_BOND_2Y",
        start_year=2026,
        maturity_year=2028,
        nominal_value=310_000.0,
        coupon_rate=0.012,
    ),
    PAMSpec(
        contract_id="AAL_PAM_BOND_5Y",
        start_year=2026,
        maturity_year=2031,
        nominal_value=310_000.0,
        coupon_rate=0.014,
    ),
    PAMSpec(
        contract_id="AAL_PAM_BOND_7Y",
        start_year=2026,
        maturity_year=2033,
        nominal_value=310_000.0,
        coupon_rate=0.015,
    ),
    PAMSpec(
        contract_id="AAL_PAM_BOND_10Y",
        start_year=2026,
        maturity_year=2036,
        nominal_value=310_000.0,
        coupon_rate=0.017,
    ),
    PAMSpec(
        contract_id="AAL_PAM_BOND_15Y",
        start_year=2026,
        maturity_year=2041,
        nominal_value=310_000.0,
        coupon_rate=0.018,
    ),
    _stk_spec_from_nominal(
        contract_id="AAL_STK_EQUITY_PROXY",
        start_year=2026,
        divestment_year=2038,
        nominal_value=1_550_000.0,
        dividend_yield=0.025,
        market_value_growth=0.040,
    ),
    _stk_spec_from_nominal(
        contract_id="AAL_STK_REAL_ESTATE_PROXY",
        start_year=2026,
        divestment_year=2038,
        nominal_value=1_150_000.0,
        dividend_yield=0.035,
        market_value_growth=0.020,
    ),
    CSHSpec(
        contract_id="AAL_CSH_CASH",
        start_year=2026,
        nominal_value=250_000.0,
    ),
    _stk_spec_from_nominal(
        contract_id="AAL_STK_ALTERNATIVES_PROXY",
        start_year=2026,
        divestment_year=2038,
        nominal_value=500_000.0,
        dividend_yield=0.0,
        market_value_growth=0.030,
    ),
)


def get_default_aal_asset_contract_specs() -> tuple[AssetSpec, ...]:
    """Return the default Phase 2 pension-fund asset portfolio specs."""
    return DEFAULT_AAL_ASSET_CONTRACT_SPECS


def validate_aal_asset_contract_specs(
    specs: tuple[AssetSpec, ...] | list[AssetSpec],
) -> tuple[AssetSpec, ...]:
    """Validate portfolio-level constraints for AAL asset contract specs."""
    if not isinstance(specs, (list, tuple)):
        raise TypeError(f"specs must be list or tuple, got {type(specs).__name__}")
    if not specs:
        raise ValueError("specs must not be empty")

    validated: list[AssetSpec] = []
    for i, spec in enumerate(specs):
        if not isinstance(spec, (PAMSpec, STKSpec, CSHSpec)):
            raise TypeError(
                f"specs[{i}] must be PAMSpec, STKSpec, or CSHSpec, "
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
    specs: tuple[AssetSpec, ...] | list[AssetSpec] | None,
) -> tuple[AssetSpec, ...]:
    if specs is None:
        return validate_aal_asset_contract_specs(get_default_aal_asset_contract_specs())
    return validate_aal_asset_contract_specs(specs)


def build_aal_pam_contracts_from_specs(
    module: ModuleType | Any,
    specs: tuple[AssetSpec, ...] | list[AssetSpec] | None = None,
) -> tuple[object, ...]:
    """Construct AAL PAM contracts from the PAM subset of portfolio specs."""
    resolved = _resolve_specs(specs)
    return tuple(
        build_aal_pam_contract(
            module,
            contract_id=spec.contract_id,
            start_year=spec.start_year,
            maturity_year=spec.maturity_year,
            nominal_value=spec.nominal_value,
            coupon_rate=spec.coupon_rate,
            coupon_cycle=spec.coupon_cycle,
            coupon_anchor_date=spec.coupon_anchor_date,
            currency=spec.currency,
        )
        for spec in resolved
        if isinstance(spec, PAMSpec)
    )


def build_aal_stk_contracts_from_specs(
    module: ModuleType | Any,
    specs: tuple[AssetSpec, ...] | list[AssetSpec] | None = None,
) -> tuple[object, ...]:
    """Construct AAL STK contracts from the STK subset of portfolio specs."""
    resolved = _resolve_specs(specs)
    return tuple(
        build_aal_stk_contract(module, spec)
        for spec in resolved
        if isinstance(spec, STKSpec)
    )


def build_aal_cash_contracts_from_specs(
    module: ModuleType | Any,
    specs: tuple[AssetSpec, ...] | list[AssetSpec] | None = None,
) -> tuple[object, ...]:
    """Construct AAL CSH contracts from the CSH subset of portfolio specs."""
    resolved = _resolve_specs(specs)
    return tuple(
        build_aal_cash_contract(module, spec)
        for spec in resolved
        if isinstance(spec, CSHSpec)
    )


def build_aal_portfolio_from_specs(
    module: ModuleType | Any,
    specs: tuple[AssetSpec, ...] | list[AssetSpec] | None = None,
) -> object:
    """Construct an AAL Portfolio from PAM, STK, and CSH portfolio specs."""
    contracts = [
        *build_aal_pam_contracts_from_specs(module, specs),
        *build_aal_stk_contracts_from_specs(module, specs),
        *build_aal_cash_contracts_from_specs(module, specs),
    ]
    return build_aal_portfolio(module, contracts)
