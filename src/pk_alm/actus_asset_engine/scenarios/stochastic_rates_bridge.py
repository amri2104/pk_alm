"""Bridge stochastic_rates simulations into AAL risk-factor inputs."""

from __future__ import annotations

from typing import Any

from pk_alm.actus_asset_engine.risk_factors import (
    AALRiskFactorSet,
    simulation_result_to_risk_factor_set,
)


def build_stochastic_rates_risk_factor_set(
    simulation: Any,
    *,
    base_date: str,
    market_code: str = "STOCHASTIC_RATE_INDEX",
    path: int = 0,
    freq: str = "M",
) -> AALRiskFactorSet:
    """Map one stochastic_rates path to an ACTUS ReferenceIndex risk factor."""
    return simulation_result_to_risk_factor_set(
        simulation,
        base_date=base_date,
        market_code=market_code,
        path=path,
        freq=freq,
    )
