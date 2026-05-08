"""AAL object-construction boundary for ACTUS-native contract configs."""

from __future__ import annotations

from typing import Any

from pk_alm.actus_asset_engine.contract_config import (
    AALContractConfig,
    build_aal_contract,
    build_aal_contracts,
    build_aal_portfolio_from_configs,
)


def build_aal_portfolio(module: Any, contracts: list[object]) -> object:
    """Wrap already constructed AAL contracts into a real AAL Portfolio."""
    return module.Portfolio(contracts)


__all__ = [
    "AALContractConfig",
    "build_aal_contract",
    "build_aal_contracts",
    "build_aal_portfolio",
    "build_aal_portfolio_from_configs",
]
