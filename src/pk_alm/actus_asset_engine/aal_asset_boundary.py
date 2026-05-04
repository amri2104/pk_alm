"""AAL asset construction helpers for pension fund asset modelling.

AAL is a required dependency for asset-side ACTUS work. This module only
builds real AAL contract and portfolio objects; event generation is handled by
the AAL Asset Engine through ``PublicActusService.generateEvents``.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

DEFAULT_PAM_CONTRACT_ID = "AAL_PAM_1"
DEFAULT_PAM_START_YEAR = 2026
DEFAULT_PAM_MATURITY_YEAR = 2028
DEFAULT_PAM_NOMINAL_VALUE = 100_000.0
DEFAULT_PAM_COUPON_RATE = 0.02
DEFAULT_PAM_CURRENCY = "CHF"
DEFAULT_PAM_COUPON_CYCLE = "P1YL1"


def _minimal_pam_terms(
    *,
    contract_id: str = DEFAULT_PAM_CONTRACT_ID,
    start_year: int = DEFAULT_PAM_START_YEAR,
    maturity_year: int = DEFAULT_PAM_MATURITY_YEAR,
    nominal_value: float = DEFAULT_PAM_NOMINAL_VALUE,
    coupon_rate: float = DEFAULT_PAM_COUPON_RATE,
    currency: str = DEFAULT_PAM_CURRENCY,
    coupon_cycle: str = DEFAULT_PAM_COUPON_CYCLE,
    coupon_anchor_date: str | None = None,
) -> dict[str, object]:
    """Return the minimal AAL PAM contract terms dict."""
    resolved_coupon_anchor = (
        coupon_anchor_date
        if coupon_anchor_date is not None
        else f"{start_year + 1}-01-01T00:00:00"
    )
    return {
        "contractDealDate": f"{start_year}-01-01T00:00:00",
        "contractID": contract_id,
        "contractRole": "RPA",
        "counterpartyID": "COUNTERPARTY_1",
        "creatorID": "PK_ALM",
        "currency": currency,
        "dayCountConvention": "30E360",
        "initialExchangeDate": f"{start_year}-01-01T00:00:00",
        "maturityDate": f"{maturity_year}-12-31T00:00:00",
        "nominalInterestRate": coupon_rate,
        "notionalPrincipal": nominal_value,
        "statusDate": f"{start_year}-01-01T00:00:00",
        "cycleAnchorDateOfInterestPayment": resolved_coupon_anchor,
        "cycleOfInterestPayment": coupon_cycle,
    }


def build_aal_pam_contract(
    module: ModuleType | Any,
    *,
    contract_id: str = DEFAULT_PAM_CONTRACT_ID,
    start_year: int = DEFAULT_PAM_START_YEAR,
    maturity_year: int = DEFAULT_PAM_MATURITY_YEAR,
    nominal_value: float = DEFAULT_PAM_NOMINAL_VALUE,
    coupon_rate: float = DEFAULT_PAM_COUPON_RATE,
    coupon_cycle: str = DEFAULT_PAM_COUPON_CYCLE,
    coupon_anchor_date: str | None = None,
    currency: str = DEFAULT_PAM_CURRENCY,
) -> object:
    """Construct a real AAL PAM contract using the provided AAL module."""
    terms = _minimal_pam_terms(
        contract_id=contract_id,
        start_year=start_year,
        maturity_year=maturity_year,
        nominal_value=nominal_value,
        coupon_rate=coupon_rate,
        coupon_cycle=coupon_cycle,
        coupon_anchor_date=coupon_anchor_date,
        currency=currency,
    )
    return module.PAM(**terms)


def build_aal_stk_contract(module: ModuleType | Any, spec: object) -> object:
    """Construct a real AAL STK contract from an STKSpec-like object."""
    terms: dict[str, object] = {
        "contractDealDate": f"{spec.start_year}-01-01T00:00:00",
        "contractID": spec.contract_id,
        "contractRole": "RPA",
        "counterpartyID": "COUNTERPARTY_1",
        "creatorID": "PK_ALM",
        "currency": spec.currency,
        "notionalPrincipal": spec.quantity * spec.price_at_purchase,
        "priceAtPurchaseDate": spec.price_at_purchase,
        "purchaseDate": f"{spec.start_year}-01-01T00:00:00",
        "quantity": spec.quantity,
        "statusDate": f"{spec.start_year}-01-01T00:00:00",
        "terminationDate": f"{spec.divestment_year}-12-31T00:00:00",
        "priceAtTerminationDate": spec.price_at_termination,
    }
    if spec.dividend_yield > 0:
        terms.update(
            {
                "cycleOfDividend": "P1YL1",
                "cycleAnchorDateOfDividend": (
                    f"{spec.start_year + 1}-01-01T00:00:00"
                ),
                "nextDividendPaymentAmount": (
                    spec.dividend_yield * spec.nominal_value
                ),
            }
        )
    return module.STK(**terms)


def build_aal_cash_contract(module: ModuleType | Any, spec: object) -> object:
    """Construct a real AAL CSH contract from a CSHSpec-like object."""
    terms = {
        "contractID": spec.contract_id,
        "contractRole": "RPA",
        "creatorID": "PK_ALM",
        "currency": spec.currency,
        "notionalPrincipal": spec.nominal_value,
        "statusDate": f"{spec.start_year}-01-01T00:00:00",
    }
    return module.CSH(**terms)


def build_aal_portfolio(
    module: ModuleType | Any,
    contracts: list[object],
) -> object:
    """Wrap AAL contracts into a real AAL Portfolio object."""
    return module.Portfolio(contracts)
