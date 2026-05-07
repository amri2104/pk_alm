"""Monte-Carlo runner over an array of pre-generated active-rate paths.

Replaces the legacy stage-2D engine. The runner builds a fresh
:class:`BVGAssumptions` per realization (substituting the path's active
crediting curve) and calls :func:`run_bvg_engine`. Callers supply a
``rate_paths_active`` array of shape ``(n_paths, horizon_years)``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from pk_alm.bvg_liability_engine.assumptions.bvg_assumptions import BVGAssumptions
from pk_alm.bvg_liability_engine.assumptions.rate_curves import StepRateCurve
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.generic_engine import run_bvg_engine
from pk_alm.bvg_liability_engine.orchestration.result import BVGEngineResult


@dataclass(frozen=True)
class BVGStochasticResult:
    """One Monte-Carlo run over ``n_paths`` active-rate scenarios."""

    n_paths: int
    horizon_years: int
    path_results: tuple[BVGEngineResult, ...]
    rate_paths_active: np.ndarray
    model_active: str

    def __post_init__(self) -> None:
        if not isinstance(self.path_results, tuple):
            raise TypeError("path_results must be a tuple")
        if len(self.path_results) != self.n_paths:
            raise ValueError(
                f"path_results length must equal n_paths ({self.n_paths})"
            )
        if not isinstance(self.rate_paths_active, np.ndarray):
            raise TypeError("rate_paths_active must be a numpy array")
        if self.rate_paths_active.shape != (self.n_paths, self.horizon_years):
            raise ValueError(
                "rate_paths_active shape must be "
                f"({self.n_paths}, {self.horizon_years}), got {self.rate_paths_active.shape}"
            )

    def cashflow_paths(self) -> tuple[np.ndarray, ...]:
        return tuple(r.cashflows["payoff"].to_numpy() for r in self.path_results)


def run_stochastic_bvg_engine(
    *,
    initial_state: BVGPortfolioState,
    assumptions: BVGAssumptions,
    rate_paths_active: np.ndarray,
    model_active: str = "pre_generated",
) -> BVGStochasticResult:
    """Run :func:`run_bvg_engine` once per row of ``rate_paths_active``.

    Each row becomes the engine's ``active_crediting_rate`` curve via
    :class:`StepRateCurve` keyed on calendar year ``[start_year, ...,
    start_year + horizon_years - 1]``. All other assumption fields are
    held constant across realizations.
    """
    if not isinstance(rate_paths_active, np.ndarray):
        raise TypeError("rate_paths_active must be a numpy array")
    if rate_paths_active.ndim != 2:
        raise ValueError("rate_paths_active must be 2D (n_paths, horizon_years)")
    n_paths, horizon = rate_paths_active.shape
    if horizon != assumptions.horizon_years:
        raise ValueError(
            f"rate_paths_active horizon ({horizon}) must match "
            f"assumptions.horizon_years ({assumptions.horizon_years})"
        )
    if n_paths <= 0:
        raise ValueError(f"n_paths must be > 0, got {n_paths}")

    results: list[BVGEngineResult] = []
    for path in rate_paths_active:
        rates = {
            assumptions.start_year + t: float(path[t])
            for t in range(horizon)
        }
        path_curve = StepRateCurve(rates=rates) if rates else assumptions.active_crediting_rate
        path_assumptions = replace(assumptions, active_crediting_rate=path_curve)
        results.append(
            run_bvg_engine(initial_state=initial_state, assumptions=path_assumptions)
        )

    return BVGStochasticResult(
        n_paths=n_paths,
        horizon_years=horizon,
        path_results=tuple(results),
        rate_paths_active=rate_paths_active,
        model_active=model_active,
    )
