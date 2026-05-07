"""Canonical BVG scenario result container."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg_liability_engine.assumptions import BVGAssumptions
from pk_alm.bvg_liability_engine.orchestration import BVGEngineResult


@dataclass(frozen=True)
class BVGScenarioResult:
    """Frozen output bundle for one named BVG scenario."""

    scenario_name: str
    assumptions: BVGAssumptions
    engine_result: BVGEngineResult
    summary: pd.DataFrame | None = None
    validation: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_name, str) or not self.scenario_name.strip():
            raise ValueError("scenario_name must be a non-empty string")
        if not isinstance(self.assumptions, BVGAssumptions):
            raise TypeError("assumptions must be BVGAssumptions")
        if not isinstance(self.engine_result, BVGEngineResult):
            raise TypeError("engine_result must be BVGEngineResult")
        if self.summary is not None and not isinstance(self.summary, pd.DataFrame):
            raise TypeError("summary must be DataFrame or None")
        if self.validation is not None and not isinstance(
            self.validation,
            pd.DataFrame,
        ):
            raise TypeError("validation must be DataFrame or None")


__all__ = ["BVGScenarioResult"]
