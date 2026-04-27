"""AAL asset boundary for pension fund asset modelling.

This module provides the boundary between the optional Awesome ACTUS Library
(AAL) and the project's canonical cashflow schema. It is intentionally narrow:

- It does NOT call PublicActusService or any network endpoint.
- It does NOT make AAL a hard dependency.
- It does NOT modify ``run_stage1_baseline(...)`` or the default Stage-1 outputs.
- When AAL is unavailable, an offline fallback using existing ACTUS-style
  fixtures and the actus_adapter delivers schema-valid ACTUS cashflows.

The design goal is to let a future user model the asset side with real AAL
PAM contracts and eventually combine those cashflows with BVG liability
cashflows through the shared CashflowRecord schema.

Production event generation (PublicActusService.generateEvents / network
calls) is NOT attempted here. Any future service-backed path must be an
explicit opt-in and is out of scope for this boundary sprint.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Any

import pandas as pd

from pk_alm.adapters.aal_probe import check_aal_availability, get_aal_module
from pk_alm.adapters.actus_fixtures import build_fixed_rate_bond_cashflow_dataframe
from pk_alm.cashflows.schema import validate_cashflow_dataframe

# ---------------------------------------------------------------------------
# Default PAM contract parameters
# (match the minimal terms proven in tests/test_aal_real_contract_smoke.py)
# ---------------------------------------------------------------------------

DEFAULT_PAM_CONTRACT_ID = "AAL_PAM_1"
DEFAULT_PAM_START_YEAR = 2026
DEFAULT_PAM_MATURITY_YEAR = 2028
DEFAULT_PAM_NOMINAL_VALUE = 100_000.0
DEFAULT_PAM_COUPON_RATE = 0.02
DEFAULT_PAM_CURRENCY = "CHF"


def _minimal_pam_terms(
    *,
    contract_id: str = DEFAULT_PAM_CONTRACT_ID,
    start_year: int = DEFAULT_PAM_START_YEAR,
    maturity_year: int = DEFAULT_PAM_MATURITY_YEAR,
    nominal_value: float = DEFAULT_PAM_NOMINAL_VALUE,
    coupon_rate: float = DEFAULT_PAM_COUPON_RATE,
    currency: str = DEFAULT_PAM_CURRENCY,
) -> dict[str, object]:
    """Return the minimal AAL PAM contract terms dict.

    The field names and types match the AAL 1.0.12 PAM constructor as
    documented in tests/test_aal_real_contract_smoke.py.
    """
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
    }


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


def _validate_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be bool, got {type(value).__name__}")
    return value


@dataclass(frozen=True)
class AALAssetBoundaryProbeResult:
    """Result of a non-network AAL asset boundary probe.

    Fields describe what was attempted and what succeeded. All flag fields
    are bool. ``service_generation_attempted`` is always False in this
    boundary module: network/service calls are never made by default.
    """

    aal_available: bool
    pam_constructed: bool
    portfolio_constructed: bool
    service_generation_attempted: bool
    fallback_used: bool

    def __post_init__(self) -> None:
        _validate_bool(self.aal_available, "aal_available")
        _validate_bool(self.pam_constructed, "pam_constructed")
        _validate_bool(self.portfolio_constructed, "portfolio_constructed")
        _validate_bool(
            self.service_generation_attempted,
            "service_generation_attempted",
        )
        _validate_bool(self.fallback_used, "fallback_used")

        if not self.aal_available:
            if self.pam_constructed:
                raise ValueError(
                    "pam_constructed must be False when aal_available is False"
                )
            if self.portfolio_constructed:
                raise ValueError(
                    "portfolio_constructed must be False when aal_available is False"
                )

        if self.service_generation_attempted:
            raise ValueError(
                "service_generation_attempted must be False: "
                "network/service calls are never made by this boundary module"
            )

    def to_dict(self) -> dict[str, bool]:
        """Return all fields in stable reporting order."""
        return {
            "aal_available": self.aal_available,
            "pam_constructed": self.pam_constructed,
            "portfolio_constructed": self.portfolio_constructed,
            "service_generation_attempted": self.service_generation_attempted,
            "fallback_used": self.fallback_used,
        }


# ---------------------------------------------------------------------------
# AAL construction helpers (optional — skip when AAL is absent)
# ---------------------------------------------------------------------------


def build_aal_pam_contract(
    module: ModuleType | Any,
    *,
    contract_id: str = DEFAULT_PAM_CONTRACT_ID,
    start_year: int = DEFAULT_PAM_START_YEAR,
    maturity_year: int = DEFAULT_PAM_MATURITY_YEAR,
    nominal_value: float = DEFAULT_PAM_NOMINAL_VALUE,
    coupon_rate: float = DEFAULT_PAM_COUPON_RATE,
    currency: str = DEFAULT_PAM_CURRENCY,
) -> object:
    """Construct a real AAL PAM contract using the provided AAL module.

    The caller is responsible for obtaining the module via ``get_aal_module()``
    from ``aal_probe``. This function does not import AAL itself.
    """
    terms = _minimal_pam_terms(
        contract_id=contract_id,
        start_year=start_year,
        maturity_year=maturity_year,
        nominal_value=nominal_value,
        coupon_rate=coupon_rate,
        currency=currency,
    )
    return module.PAM(**terms)


def build_aal_portfolio(
    module: ModuleType | Any,
    contracts: list[object],
) -> object:
    """Wrap a list of AAL contracts into a real AAL Portfolio object.

    The caller is responsible for obtaining the module via ``get_aal_module()``
    from ``aal_probe``. This function does not import AAL itself.
    """
    return module.Portfolio(contracts)


# ---------------------------------------------------------------------------
# Offline fallback cashflows
# ---------------------------------------------------------------------------


def get_aal_asset_boundary_fallback_cashflows(
    *,
    contract_id: str = DEFAULT_PAM_CONTRACT_ID,
    start_year: int = DEFAULT_PAM_START_YEAR,
    maturity_year: int = DEFAULT_PAM_MATURITY_YEAR,
    nominal_value: float = DEFAULT_PAM_NOMINAL_VALUE,
    annual_coupon_rate: float = DEFAULT_PAM_COUPON_RATE,
    currency: str = DEFAULT_PAM_CURRENCY,
    include_purchase_event: bool = False,
) -> pd.DataFrame:
    """Return schema-valid ACTUS cashflows without AAL or any network call.

    The fallback mirrors the default PAM parameters using the existing
    deterministic fixed-rate bond fixtures and actus_adapter. The returned
    DataFrame always passes ``validate_cashflow_dataframe`` and always has
    ``source == "ACTUS"`` on every row.

    This function works entirely offline and does not require AAL.
    """
    df = build_fixed_rate_bond_cashflow_dataframe(
        contract_id=contract_id,
        start_year=start_year,
        maturity_year=maturity_year,
        nominal_value=nominal_value,
        annual_coupon_rate=annual_coupon_rate,
        currency=currency,
        include_purchase_event=include_purchase_event,
    )
    validate_cashflow_dataframe(df)
    return df


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------


def probe_aal_asset_boundary() -> AALAssetBoundaryProbeResult:
    """Probe the AAL asset boundary without calling any network service.

    Checks whether AAL is available. If it is, attempts to construct a
    minimal PAM contract and wrap it in a Portfolio. Never calls
    PublicActusService or any remote endpoint.
    """
    availability = check_aal_availability()

    if not availability.is_available:
        return AALAssetBoundaryProbeResult(
            aal_available=False,
            pam_constructed=False,
            portfolio_constructed=False,
            service_generation_attempted=False,
            fallback_used=True,
        )

    module = get_aal_module()
    pam_constructed = False
    portfolio_constructed = False
    pam = None

    try:
        pam = build_aal_pam_contract(module)
        pam_constructed = True
    except Exception:
        pass

    if pam_constructed and pam is not None:
        try:
            build_aal_portfolio(module, [pam])
            portfolio_constructed = True
        except Exception:
            pass

    return AALAssetBoundaryProbeResult(
        aal_available=True,
        pam_constructed=pam_constructed,
        portfolio_constructed=portfolio_constructed,
        service_generation_attempted=False,
        fallback_used=False,
    )
