"""Risk-factor input layer for the ACTUS/AAL asset engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_KNOWN_AAL_RISK_FACTOR_CLASSES = {"ReferenceIndex", "YieldCurve"}


def _market_object_code(risk_factor: object) -> str:
    code = getattr(risk_factor, "marketObjectCode", None)
    if not isinstance(code, str) or not code.strip():
        raise ValueError(
            "AAL risk factors must expose a non-empty marketObjectCode"
        )
    return code


def _validate_risk_factor(risk_factor: object) -> object:
    _market_object_code(risk_factor)
    class_name = type(risk_factor).__name__
    has_json = callable(getattr(risk_factor, "to_json", None))
    if not has_json and class_name not in _KNOWN_AAL_RISK_FACTOR_CLASSES:
        raise TypeError(
            "AAL risk factors must be ReferenceIndex/YieldCurve-like objects "
            "or expose to_json()"
        )
    return risk_factor


@dataclass(frozen=True)
class AALRiskFactorSet:
    """Tuple wrapper for AAL risk factors sent to PublicActusService."""

    risk_factors: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.risk_factors, tuple):
            raise TypeError(
                "risk_factors must be a tuple; use coerce_aal_risk_factor_set "
                "for lists"
            )
        object.__setattr__(
            self,
            "risk_factors",
            tuple(_validate_risk_factor(rf) for rf in self.risk_factors),
        )

    def to_aal_argument(self) -> tuple[object, ...] | None:
        return self.risk_factors or None


def coerce_aal_risk_factor_set(
    risk_factors: AALRiskFactorSet | tuple[object, ...] | list[object] | None,
) -> AALRiskFactorSet:
    if risk_factors is None:
        return AALRiskFactorSet()
    if isinstance(risk_factors, AALRiskFactorSet):
        return risk_factors
    if isinstance(risk_factors, (list, tuple)):
        return AALRiskFactorSet(tuple(risk_factors))
    raise TypeError(
        "risk_factors must be AALRiskFactorSet, list, tuple, or None, "
        f"got {type(risk_factors).__name__}"
    )


def simulation_result_to_reference_index(
    simulation: Any,
    *,
    base_date: str,
    market_code: str,
    path: int = 0,
    freq: str = "M",
) -> object:
    """Adapt a stochastic_rates SimulationResult to an AAL ReferenceIndex."""
    from stochastic_rates.integration import simulation_to_reference_index

    return simulation_to_reference_index(
        simulation,
        base_date=base_date,
        market_code=market_code,
        path=path,
        freq=freq,
    )


def simulation_result_to_risk_factor_set(
    simulation: Any,
    *,
    base_date: str,
    market_code: str,
    path: int = 0,
    freq: str = "M",
) -> AALRiskFactorSet:
    return AALRiskFactorSet(
        (
            simulation_result_to_reference_index(
                simulation,
                base_date=base_date,
                market_code=market_code,
                path=path,
                freq=freq,
            ),
        )
    )
