"""Tests for AAL risk-factor validation and stochastic_rates bridge."""

import numpy as np
import pytest

from pk_alm.actus_asset_engine.risk_factors import (
    AALRiskFactorSet,
    coerce_aal_risk_factor_set,
    simulation_result_to_risk_factor_set,
)
from pk_alm.actus_asset_engine.scenarios.stochastic_rates_bridge import (
    build_stochastic_rates_risk_factor_set,
)
from stochastic_rates import SimulationResult


class _ReferenceIndexLike:
    marketObjectCode = "CHF_REFERENCE"

    def to_json(self):
        return {
            "marketObjectCode": self.marketObjectCode,
            "data": [{"time": "2026-01-01", "value": 0.01}],
        }


class _YieldCurveLike:
    marketObjectCode = "CHF_CURVE"

    def to_json(self):
        return {
            "marketObjectCode": self.marketObjectCode,
            "data": [{"tenor": "1Y", "rate": 0.01}],
        }


def test_risk_factor_set_accepts_reference_index_and_yield_curve_like_objects():
    reference = _ReferenceIndexLike()
    curve = _YieldCurveLike()

    result = AALRiskFactorSet((reference, curve))

    assert result.risk_factors == (reference, curve)
    assert result.to_aal_argument() == (reference, curve)


def test_risk_factor_set_rejects_invalid_objects():
    with pytest.raises(ValueError, match="marketObjectCode"):
        AALRiskFactorSet((object(),))


def test_coerce_risk_factor_set_accepts_none_and_lists():
    reference = _ReferenceIndexLike()

    assert coerce_aal_risk_factor_set(None).risk_factors == ()
    assert coerce_aal_risk_factor_set([reference]).risk_factors == (reference,)


def test_stochastic_rates_simulation_result_adapter_builds_reference_index():
    simulation = SimulationResult(
        times=np.array([0.0, 1 / 12, 2 / 12]),
        rates=np.array([[0.01], [0.011], [0.012]]),
    )

    result = simulation_result_to_risk_factor_set(
        simulation,
        base_date="2026-01-01",
        market_code="CHF_STOCHASTIC",
        path=0,
        freq="M",
    )

    assert isinstance(result, AALRiskFactorSet)
    risk_factor = result.risk_factors[0]
    assert risk_factor.marketObjectCode == "CHF_STOCHASTIC"
    payload = risk_factor.to_json()
    assert len(payload["data"]) == 3


def test_stochastic_rates_bridge_helper_returns_risk_factor_set():
    simulation = SimulationResult(
        times=np.array([0.0, 1.0]),
        rates=np.array([[0.01], [0.013]]),
    )

    result = build_stochastic_rates_risk_factor_set(
        simulation,
        base_date="2026-01-01",
        market_code="CHF_BRIDGE",
        freq="Y",
    )

    assert isinstance(result, AALRiskFactorSet)
    assert result.risk_factors[0].marketObjectCode == "CHF_BRIDGE"
