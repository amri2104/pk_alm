"""ACTUS-native contract configuration for the AAL asset engine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import pandas as pd

_REQUIRED_TERMS = ("contractID", "contractRole", "currency", "statusDate")


def _validate_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_currency(value: object, name: str = "currency") -> str:
    currency = _validate_non_empty_string(value, name)
    if len(currency) != 3 or not currency.isalpha() or currency.upper() != currency:
        raise ValueError(f"{name} must be a 3-letter uppercase ISO-4217 code")
    return currency


def _parse_timestamp(value: object, name: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} could not be parsed as a timestamp") from exc
    if pd.isna(timestamp):
        raise ValueError(f"{name} must not be NaT/None/NaN")
    return timestamp


@dataclass(frozen=True)
class AALContractConfig:
    """ACTUS-native contract config passed to an AAL contract constructor.

    ``contract_type`` maps directly to an AAL class such as ``PAM``, ``STK``,
    or ``CSH``. ``terms`` are copied, validated, and later passed as
    ``module.<contract_type>(**terms)``.
    """

    contract_type: str
    terms: Mapping[str, object]
    label: str | None = None

    def __post_init__(self) -> None:
        contract_type = _validate_non_empty_string(
            self.contract_type, "contract_type"
        ).upper()
        if not isinstance(self.terms, Mapping):
            raise TypeError(
                f"terms must be a mapping, got {type(self.terms).__name__}"
            )
        terms = dict(self.terms)
        missing = [term for term in _REQUIRED_TERMS if term not in terms]
        if missing:
            raise ValueError(f"missing required ACTUS terms: {missing}")

        _validate_non_empty_string(terms["contractID"], "terms['contractID']")
        _validate_non_empty_string(terms["contractRole"], "terms['contractRole']")
        _validate_currency(terms["currency"], "terms['currency']")
        _parse_timestamp(terms["statusDate"], "terms['statusDate']")

        label = self.label
        if label is not None:
            label = _validate_non_empty_string(label, "label")

        object.__setattr__(self, "contract_type", contract_type)
        object.__setattr__(self, "terms", MappingProxyType(terms))
        object.__setattr__(self, "label", label)

    @property
    def contract_id(self) -> str:
        return str(self.terms["contractID"])

    @property
    def currency(self) -> str:
        return str(self.terms["currency"])

    @property
    def status_date(self) -> pd.Timestamp:
        return _parse_timestamp(self.terms["statusDate"], "terms['statusDate']")

    def term_timestamp(self, key: str) -> pd.Timestamp | None:
        value = self.terms.get(key)
        if value is None:
            return None
        return _parse_timestamp(value, f"terms[{key!r}]")


def validate_aal_contract_configs(
    contracts: tuple[AALContractConfig, ...] | list[AALContractConfig],
) -> tuple[AALContractConfig, ...]:
    """Validate portfolio-level constraints for ACTUS contract configs."""
    if not isinstance(contracts, (list, tuple)):
        raise TypeError(
            f"contracts must be list or tuple, got {type(contracts).__name__}"
        )
    if not contracts:
        raise ValueError("contracts must not be empty")

    validated: list[AALContractConfig] = []
    for i, contract in enumerate(contracts):
        if not isinstance(contract, AALContractConfig):
            raise TypeError(
                f"contracts[{i}] must be AALContractConfig, "
                f"got {type(contract).__name__}"
            )
        validated.append(contract)

    contract_ids = [contract.contract_id for contract in validated]
    duplicates = sorted(
        {cid for cid in contract_ids if contract_ids.count(cid) > 1}
    )
    if duplicates:
        raise ValueError(f"duplicate contractID values: {duplicates}")

    currencies = {contract.currency for contract in validated}
    if len(currencies) != 1:
        raise ValueError(
            "mixed currencies are not supported for ACTUS asset analytics"
        )

    return tuple(validated)


def build_aal_contract(module: Any, config: AALContractConfig) -> object:
    """Construct one AAL contract from an ACTUS-native config."""
    if not isinstance(config, AALContractConfig):
        raise TypeError(
            f"config must be AALContractConfig, got {type(config).__name__}"
        )
    try:
        contract_class = getattr(module, config.contract_type)
    except AttributeError as exc:
        raise ValueError(
            f"AAL module has no contract class {config.contract_type!r}"
        ) from exc
    return contract_class(**dict(config.terms))


def build_aal_contracts(
    module: Any,
    configs: tuple[AALContractConfig, ...] | list[AALContractConfig],
) -> tuple[object, ...]:
    resolved = validate_aal_contract_configs(configs)
    return tuple(build_aal_contract(module, config) for config in resolved)


def build_aal_portfolio_from_configs(
    module: Any,
    configs: tuple[AALContractConfig, ...] | list[AALContractConfig],
) -> object:
    """Construct a real AAL Portfolio from ACTUS-native configs."""
    return module.Portfolio(list(build_aal_contracts(module, configs)))
