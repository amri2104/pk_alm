"""Stage-2D Monte-Carlo BVG engine adapter.

Wraps :func:`pk_alm.bvg_liability_engine.orchestration.stochastic_runner.run_stochastic_bvg_engine`
behind the legacy ``run_bvg_engine_stage2d`` signature and rebuilds
:class:`Stage2DEngineResult` / :class:`Stage2DPathResult` from the new
generic engine results.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pk_alm.bvg_liability_engine.assumptions.bvg_assumptions import BVGAssumptions
from pk_alm.bvg_liability_engine.assumptions.mortality_assumptions import (
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.assumptions.rate_curves import FlatRateCurve
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.stochastic_runner import (
    run_stochastic_bvg_engine,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import (
    EntryAssumptions,
    get_default_entry_assumptions,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import (
    FixedEntryPolicy,
)
from pk_alm.bvg_liability_engine.population_dynamics.salary_dynamics import (
    MAX_PERMITTED_SALARY_GROWTH_RATE,
)
from pk_alm.bvg_liability_engine.population_dynamics.turnover import (
    MAX_PERMITTED_TURNOVER_RATE,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe


@dataclass(frozen=True)
class Stage2DPathResult:
    """Per-path stochastic engine result (legacy shape)."""

    path_index: int
    cashflows: pd.DataFrame
    portfolio_states: tuple[BVGPortfolioState, ...]
    active_rate_path: tuple[float, ...]

    def __post_init__(self) -> None:
        if isinstance(self.path_index, bool) or not isinstance(self.path_index, int):
            raise TypeError("path_index must be int")
        if self.path_index < 0:
            raise ValueError(f"path_index must be >= 0, got {self.path_index}")
        validate_cashflow_dataframe(self.cashflows)
        if not isinstance(self.portfolio_states, tuple):
            raise TypeError("portfolio_states must be tuple")
        if len(self.portfolio_states) == 0:
            raise ValueError("portfolio_states must not be empty")
        for i, state in enumerate(self.portfolio_states):
            if not isinstance(state, BVGPortfolioState):
                raise TypeError(
                    f"portfolio_states[{i}] must be BVGPortfolioState, "
                    f"got {type(state).__name__}"
                )
        if not isinstance(self.active_rate_path, tuple):
            raise TypeError("active_rate_path must be tuple")
        if len(self.active_rate_path) != len(self.portfolio_states) - 1:
            raise ValueError(
                "active_rate_path length must equal horizon "
                f"({len(self.portfolio_states) - 1}), got {len(self.active_rate_path)}"
            )


@dataclass(frozen=True)
class Stage2DEngineResult:
    """Stochastic engine result (legacy shape)."""

    n_paths: int
    horizon_years: int
    path_results: tuple[Stage2DPathResult, ...]
    rate_paths_active: np.ndarray
    model_active: str

    def __post_init__(self) -> None:
        if isinstance(self.n_paths, bool) or not isinstance(self.n_paths, int):
            raise TypeError("n_paths must be int")
        if isinstance(self.horizon_years, bool) or not isinstance(
            self.horizon_years, int
        ):
            raise TypeError("horizon_years must be int")
        if self.n_paths <= 0:
            raise ValueError(f"n_paths must be > 0, got {self.n_paths}")
        if self.horizon_years < 0:
            raise ValueError(f"horizon_years must be >= 0, got {self.horizon_years}")
        if not isinstance(self.path_results, tuple):
            raise TypeError("path_results must be tuple")
        if len(self.path_results) != self.n_paths:
            raise ValueError(
                f"path_results length must be {self.n_paths}, got {len(self.path_results)}"
            )
        for i, result in enumerate(self.path_results):
            if not isinstance(result, Stage2DPathResult):
                raise TypeError(
                    f"path_results[{i}] must be Stage2DPathResult, "
                    f"got {type(result).__name__}"
                )
            if result.path_index != i:
                raise ValueError(f"path_results[{i}].path_index must be {i}")
        if not isinstance(self.rate_paths_active, np.ndarray):
            raise TypeError("rate_paths_active must be numpy.ndarray")
        if self.rate_paths_active.shape != (self.n_paths, self.horizon_years):
            raise ValueError(
                "rate_paths_active shape must be "
                f"({self.n_paths}, {self.horizon_years}), got {self.rate_paths_active.shape}"
            )
        if not isinstance(self.model_active, str) or not self.model_active.strip():
            raise ValueError("model_active must be a non-empty string")


def _validate_non_bool_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return int(value)


def _validate_non_bool_real(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    return fval


def _validate_rate_paths_active(
    value: object,
    horizon_years: int,
    *,
    name: str,
    allow_zero_paths: bool,
) -> np.ndarray:
    if not isinstance(value, np.ndarray):
        raise TypeError(f"{name} must be numpy.ndarray, got {type(value).__name__}")
    try:
        arr = value.astype(float, copy=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must contain numeric values") from exc
    if arr.ndim != 2:
        raise ValueError(f"{name} must be 2D")
    if arr.shape[1] != horizon_years:
        raise ValueError(
            f"{name} shape must be (n_paths, {horizon_years}), got {arr.shape}"
        )
    if arr.shape[0] == 0 and not allow_zero_paths:
        raise ValueError(f"{name} must contain at least one path")
    if np.isnan(arr).any():
        raise ValueError(f"{name} must not contain NaN")
    if np.any(arr <= -1.0):
        raise ValueError(f"{name} rates must be > -1")
    return arr


def run_bvg_engine_stage2d(
    initial_state: BVGPortfolioState,
    horizon_years: int,
    rate_paths_active: np.ndarray,
    retired_interest_rate: float,
    salary_growth_rate: float = 0.015,
    turnover_rate: float = 0.02,
    entry_assumptions: EntryAssumptions | None = None,
    contribution_multiplier: float = 1.4,
    start_year: int = 2026,
    retirement_age: int = 65,
    capital_withdrawal_fraction: float = 0.35,
    conversion_rate: float = 0.068,
    model_active: str = "pre_generated",
) -> Stage2DEngineResult:
    """Stage-2D Monte-Carlo entry point. Adapter over the stochastic runner."""
    if not isinstance(initial_state, BVGPortfolioState):
        raise TypeError(
            f"initial_state must be BVGPortfolioState, got {type(initial_state).__name__}"
        )
    horizon = _validate_non_bool_int(horizon_years, "horizon_years")
    if horizon < 0:
        raise ValueError(f"horizon_years must be >= 0, got {horizon}")

    rate_paths = _validate_rate_paths_active(
        rate_paths_active, horizon, name="rate_paths_active", allow_zero_paths=False
    )
    retired_interest_rate = _validate_non_bool_real(
        retired_interest_rate, "retired_interest_rate"
    )
    if retired_interest_rate <= -1:
        raise ValueError(
            f"retired_interest_rate must be > -1, got {retired_interest_rate}"
        )
    salary_growth_rate = _validate_non_bool_real(
        salary_growth_rate, "salary_growth_rate"
    )
    if salary_growth_rate < 0.0 or salary_growth_rate > MAX_PERMITTED_SALARY_GROWTH_RATE:
        raise ValueError(
            "salary_growth_rate must be in "
            f"[0.0, {MAX_PERMITTED_SALARY_GROWTH_RATE}], got {salary_growth_rate}"
        )
    turnover_rate = _validate_non_bool_real(turnover_rate, "turnover_rate")
    if turnover_rate < 0.0 or turnover_rate > MAX_PERMITTED_TURNOVER_RATE:
        raise ValueError(
            "turnover_rate must be in "
            f"[0.0, {MAX_PERMITTED_TURNOVER_RATE}], got {turnover_rate}"
        )
    contribution_multiplier = _validate_non_bool_real(
        contribution_multiplier, "contribution_multiplier"
    )
    if contribution_multiplier < 0:
        raise ValueError(
            f"contribution_multiplier must be >= 0, got {contribution_multiplier}"
        )
    start_year = _validate_non_bool_int(start_year, "start_year")
    if start_year < 2000:
        raise ValueError(f"start_year must be >= 2000, got {start_year}")
    retirement_age = _validate_non_bool_int(retirement_age, "retirement_age")
    if retirement_age < 0:
        raise ValueError(f"retirement_age must be >= 0, got {retirement_age}")
    capital_withdrawal_fraction = _validate_non_bool_real(
        capital_withdrawal_fraction, "capital_withdrawal_fraction"
    )
    if capital_withdrawal_fraction < 0.0 or capital_withdrawal_fraction > 1.0:
        raise ValueError(
            "capital_withdrawal_fraction must be in [0.0, 1.0], "
            f"got {capital_withdrawal_fraction}"
        )
    conversion_rate = _validate_non_bool_real(conversion_rate, "conversion_rate")
    if conversion_rate < 0:
        raise ValueError(f"conversion_rate must be >= 0, got {conversion_rate}")
    if not isinstance(model_active, str) or not model_active.strip():
        raise ValueError("model_active must be a non-empty string")

    if entry_assumptions is None:
        entry = get_default_entry_assumptions()
    elif isinstance(entry_assumptions, EntryAssumptions):
        entry = entry_assumptions
    else:
        raise TypeError(
            "entry_assumptions must be EntryAssumptions or None, "
            f"got {type(entry_assumptions).__name__}"
        )
    if entry.entry_age >= retirement_age:
        raise ValueError(
            "entry_assumptions.entry_age must be < retirement_age "
            f"({entry.entry_age} >= {retirement_age})"
        )

    base_assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon,
        retirement_age=max(retirement_age, 1),
        valuation_terminal_age=max(retirement_age, 1) + 1,
        active_crediting_rate=FlatRateCurve(0.0),  # overridden per path
        retired_interest_rate=FlatRateCurve(retired_interest_rate),
        technical_discount_rate=FlatRateCurve(retired_interest_rate),
        economic_discount_rate=FlatRateCurve(retired_interest_rate),
        salary_growth_rate=FlatRateCurve(salary_growth_rate),
        conversion_rate=FlatRateCurve(conversion_rate),
        turnover_rate=turnover_rate,
        capital_withdrawal_fraction=capital_withdrawal_fraction,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(entry),
    )

    stochastic = run_stochastic_bvg_engine(
        initial_state=initial_state,
        assumptions=base_assumptions,
        rate_paths_active=rate_paths,
        model_active=model_active,
    )

    path_results = tuple(
        Stage2DPathResult(
            path_index=i,
            cashflows=res.cashflows,
            portfolio_states=res.portfolio_states,
            active_rate_path=tuple(float(v) for v in rate_paths[i]),
        )
        for i, res in enumerate(stochastic.path_results)
    )

    return Stage2DEngineResult(
        n_paths=rate_paths.shape[0],
        horizon_years=horizon,
        path_results=path_results,
        rate_paths_active=rate_paths.copy(),
        model_active=model_active,
    )
