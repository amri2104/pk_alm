"""Default ACTUS-native asset portfolio configs for AAL modelling."""

from __future__ import annotations

import math

from pk_alm.actus_asset_engine.contract_config import (
    AALContractConfig,
    build_aal_contract,
    build_aal_contracts,
    build_aal_portfolio_from_configs,
    validate_aal_contract_configs,
)


def _iso(year: int, month: int = 1, day: int = 1) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}T00:00:00"


def _validate_year(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


def _validate_positive_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    result = float(value)
    if math.isnan(result) or result <= 0.0:
        raise ValueError(f"{name} must be > 0")
    return result


def _validate_non_negative_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    result = float(value)
    if math.isnan(result) or result < 0.0:
        raise ValueError(f"{name} must be >= 0")
    return result


def make_pam_contract_config(
    *,
    contract_id: str,
    start_year: int,
    maturity_year: int,
    nominal_value: float,
    coupon_rate: float,
    coupon_cycle: str = "P1YL1",
    coupon_anchor_date: str | None = None,
    currency: str = "CHF",
    label: str | None = None,
) -> AALContractConfig:
    """Build an ACTUS PAM config for a fixed-rate bond."""
    start = _validate_year(start_year, "start_year")
    maturity = _validate_year(maturity_year, "maturity_year")
    if maturity <= start:
        raise ValueError("maturity_year must be > start_year")
    nominal = _validate_positive_number(nominal_value, "nominal_value")
    coupon = _validate_non_negative_number(coupon_rate, "coupon_rate")
    anchor = coupon_anchor_date or _iso(start + 1)
    return AALContractConfig(
        contract_type="PAM",
        label=label,
        terms={
            "contractDealDate": _iso(start),
            "contractID": contract_id,
            "contractRole": "RPA",
            "counterpartyID": "COUNTERPARTY_1",
            "creatorID": "PK_ALM",
            "currency": currency,
            "dayCountConvention": "30E360",
            "initialExchangeDate": _iso(start),
            "maturityDate": _iso(maturity, 12, 31),
            "nominalInterestRate": coupon,
            "notionalPrincipal": nominal,
            "statusDate": _iso(start),
            "cycleAnchorDateOfInterestPayment": anchor,
            "cycleOfInterestPayment": coupon_cycle,
        },
    )


def make_stk_contract_config(
    *,
    contract_id: str,
    start_year: int,
    divestment_year: int,
    quantity: float,
    price_at_purchase: float,
    price_at_termination: float,
    dividend_yield: float = 0.0,
    currency: str = "CHF",
    label: str | None = None,
) -> AALContractConfig:
    """Build an ACTUS STK config for a listed-equity-style proxy."""
    start = _validate_year(start_year, "start_year")
    divestment = _validate_year(divestment_year, "divestment_year")
    if divestment <= start:
        raise ValueError("divestment_year must be > start_year")
    quantity = _validate_positive_number(quantity, "quantity")
    purchase_price = _validate_positive_number(
        price_at_purchase, "price_at_purchase"
    )
    termination_price = _validate_positive_number(
        price_at_termination, "price_at_termination"
    )
    dividend = _validate_non_negative_number(dividend_yield, "dividend_yield")
    nominal = quantity * purchase_price
    terms: dict[str, object] = {
        "contractDealDate": _iso(start),
        "contractID": contract_id,
        "contractRole": "RPA",
        "counterpartyID": "COUNTERPARTY_1",
        "creatorID": "PK_ALM",
        "currency": currency,
        "notionalPrincipal": nominal,
        "priceAtPurchaseDate": purchase_price,
        "purchaseDate": _iso(start),
        "quantity": quantity,
        "statusDate": _iso(start),
        "terminationDate": _iso(divestment, 12, 31),
        "priceAtTerminationDate": termination_price,
    }
    if dividend > 0.0:
        terms.update(
            {
                "cycleOfDividend": "P1YL1",
                "cycleAnchorDateOfDividend": _iso(start + 1),
                "nextDividendPaymentAmount": dividend * nominal,
            }
        )
    return AALContractConfig(
        contract_type="STK",
        terms=terms,
        label=label,
    )


def make_stk_contract_config_from_nominal(
    *,
    contract_id: str,
    start_year: int,
    divestment_year: int,
    nominal_value: float,
    dividend_yield: float,
    market_value_growth: float,
    price_at_purchase: float = 100.0,
    currency: str = "CHF",
    label: str | None = None,
) -> AALContractConfig:
    nominal = _validate_positive_number(nominal_value, "nominal_value")
    purchase_price = _validate_positive_number(
        price_at_purchase, "price_at_purchase"
    )
    if isinstance(market_value_growth, bool) or not isinstance(
        market_value_growth, (int, float)
    ):
        raise TypeError("market_value_growth must be numeric")
    growth = float(market_value_growth)
    if math.isnan(growth) or growth <= -1.0:
        raise ValueError("market_value_growth must be > -1")
    years = _validate_year(divestment_year, "divestment_year") - _validate_year(
        start_year, "start_year"
    )
    return make_stk_contract_config(
        contract_id=contract_id,
        start_year=start_year,
        divestment_year=divestment_year,
        quantity=nominal / purchase_price,
        price_at_purchase=purchase_price,
        price_at_termination=purchase_price * ((1.0 + growth) ** years),
        dividend_yield=dividend_yield,
        currency=currency,
        label=label,
    )


def make_csh_contract_config(
    *,
    contract_id: str,
    start_year: int,
    nominal_value: float,
    currency: str = "CHF",
    label: str | None = None,
) -> AALContractConfig:
    """Build an ACTUS CSH config for a cash position."""
    start = _validate_year(start_year, "start_year")
    nominal = _validate_positive_number(nominal_value, "nominal_value")
    return AALContractConfig(
        contract_type="CSH",
        label=label,
        terms={
            "contractID": contract_id,
            "contractRole": "RPA",
            "creatorID": "PK_ALM",
            "currency": currency,
            "notionalPrincipal": nominal,
            "statusDate": _iso(start),
        },
    )


DEFAULT_AAL_ASSET_CONTRACT_CONFIGS: tuple[AALContractConfig, ...] = (
    make_pam_contract_config(
        contract_id="AAL_PAM_BOND_2Y",
        start_year=2026,
        maturity_year=2028,
        nominal_value=310_000.0,
        coupon_rate=0.012,
        label="BVG bond bucket 2Y",
    ),
    make_pam_contract_config(
        contract_id="AAL_PAM_BOND_5Y",
        start_year=2026,
        maturity_year=2031,
        nominal_value=310_000.0,
        coupon_rate=0.014,
        label="BVG bond bucket 5Y",
    ),
    make_pam_contract_config(
        contract_id="AAL_PAM_BOND_7Y",
        start_year=2026,
        maturity_year=2033,
        nominal_value=310_000.0,
        coupon_rate=0.015,
        label="BVG bond bucket 7Y",
    ),
    make_pam_contract_config(
        contract_id="AAL_PAM_BOND_10Y",
        start_year=2026,
        maturity_year=2036,
        nominal_value=310_000.0,
        coupon_rate=0.017,
        label="BVG bond bucket 10Y",
    ),
    make_pam_contract_config(
        contract_id="AAL_PAM_BOND_15Y",
        start_year=2026,
        maturity_year=2041,
        nominal_value=310_000.0,
        coupon_rate=0.018,
        label="BVG bond bucket 15Y",
    ),
    make_stk_contract_config_from_nominal(
        contract_id="AAL_STK_EQUITY_PROXY",
        start_year=2026,
        divestment_year=2038,
        nominal_value=1_550_000.0,
        dividend_yield=0.025,
        market_value_growth=0.040,
        label="Equity proxy",
    ),
    make_stk_contract_config_from_nominal(
        contract_id="AAL_STK_REAL_ESTATE_PROXY",
        start_year=2026,
        divestment_year=2038,
        nominal_value=1_150_000.0,
        dividend_yield=0.035,
        market_value_growth=0.020,
        label="Real estate proxy",
    ),
    make_csh_contract_config(
        contract_id="AAL_CSH_CASH",
        start_year=2026,
        nominal_value=250_000.0,
        label="Cash",
    ),
    make_stk_contract_config_from_nominal(
        contract_id="AAL_STK_ALTERNATIVES_PROXY",
        start_year=2026,
        divestment_year=2038,
        nominal_value=500_000.0,
        dividend_yield=0.0,
        market_value_growth=0.030,
        label="Alternatives proxy",
    ),
)


def get_default_aal_asset_contract_configs() -> tuple[AALContractConfig, ...]:
    """Return the default ACTUS-native pension-fund asset portfolio."""
    return DEFAULT_AAL_ASSET_CONTRACT_CONFIGS


__all__ = [
    "AALContractConfig",
    "DEFAULT_AAL_ASSET_CONTRACT_CONFIGS",
    "build_aal_contract",
    "build_aal_contracts",
    "build_aal_portfolio_from_configs",
    "get_default_aal_asset_contract_configs",
    "make_csh_contract_config",
    "make_pam_contract_config",
    "make_stk_contract_config",
    "make_stk_contract_config_from_nominal",
    "validate_aal_contract_configs",
]
