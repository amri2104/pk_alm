"""Stage 2D Monte Carlo BVG engine for stochastic active interest paths."""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pk_alm.bvg.cashflow_generation import generate_bvg_cashflow_dataframe_for_state
from pk_alm.bvg.entry_dynamics import (
    EntryAssumptions,
    apply_entries_to_portfolio,
    get_default_entry_assumptions,
)
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.projection import project_portfolio_one_year
from pk_alm.bvg.retirement_transition import apply_retirement_transitions_to_portfolio
from pk_alm.bvg.salary_dynamics import (
    MAX_PERMITTED_SALARY_GROWTH_RATE,
    apply_salary_growth_to_portfolio,
)
from pk_alm.bvg.turnover import (
    MAX_PERMITTED_TURNOVER_RATE,
    apply_turnover_to_portfolio,
)
from pk_alm.cashflows.schema import (
    CASHFLOW_COLUMNS,
    cashflow_records_to_dataframe,
    validate_cashflow_dataframe,
)


@dataclass(frozen=True)
class Stage2DPathResult:
    """Result for one stochastic active-interest path."""

    path_index: int
    cashflows: pd.DataFrame
    portfolio_states: tuple[BVGPortfolioState, ...]
    active_rate_path: tuple[float, ...]

    def __post_init__(self) -> None:
        path_index = _validate_non_bool_int(self.path_index, "path_index")
        if path_index < 0:
            raise ValueError(f"path_index must be >= 0, got {path_index}")
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
        _validate_float_tuple(
            self.active_rate_path,
            "active_rate_path",
            len(self.portfolio_states) - 1,
            allow_negative=True,
        )


@dataclass(frozen=True)
class Stage2DEngineResult:
    """Container for the full Stage-2D Monte Carlo BVG engine run."""

    n_paths: int
    horizon_years: int
    path_results: tuple[Stage2DPathResult, ...]
    rate_paths_active: np.ndarray
    model_active: str

    def __post_init__(self) -> None:
        n_paths = _validate_non_bool_int(self.n_paths, "n_paths")
        horizon = _validate_non_bool_int(self.horizon_years, "horizon_years")
        if n_paths <= 0:
            raise ValueError(f"n_paths must be > 0, got {n_paths}")
        if horizon < 0:
            raise ValueError(f"horizon_years must be >= 0, got {horizon}")
        if not isinstance(self.path_results, tuple):
            raise TypeError("path_results must be tuple")
        if len(self.path_results) != n_paths:
            raise ValueError(
                f"path_results length must be {n_paths}, got {len(self.path_results)}"
            )
        for i, result in enumerate(self.path_results):
            if not isinstance(result, Stage2DPathResult):
                raise TypeError(
                    f"path_results[{i}] must be Stage2DPathResult, "
                    f"got {type(result).__name__}"
                )
            if result.path_index != i:
                raise ValueError(f"path_results[{i}].path_index must be {i}")
            if len(result.portfolio_states) != horizon + 1:
                raise ValueError(
                    f"path_results[{i}].portfolio_states length must be {horizon + 1}"
                )
        rate_paths = _validate_rate_paths_active(
            self.rate_paths_active,
            horizon,
            name="rate_paths_active",
            allow_zero_paths=False,
        )
        if rate_paths.shape[0] != n_paths:
            raise ValueError(
                f"rate_paths_active first dimension must be {n_paths}, "
                f"got {rate_paths.shape[0]}"
            )
        if not isinstance(self.model_active, str) or not self.model_active.strip():
            raise ValueError("model_active must be a non-empty string")


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
    """Run the BVG projection once per active-interest-rate path."""
    if not isinstance(initial_state, BVGPortfolioState):
        raise TypeError(
            f"initial_state must be BVGPortfolioState, got {type(initial_state).__name__}"
        )
    horizon = _validate_non_bool_int(horizon_years, "horizon_years")
    if horizon < 0:
        raise ValueError(f"horizon_years must be >= 0, got {horizon}")
    rate_paths = _validate_rate_paths_active(
        rate_paths_active,
        horizon,
        name="rate_paths_active",
        allow_zero_paths=False,
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
    if (
        salary_growth_rate < 0.0
        or salary_growth_rate > MAX_PERMITTED_SALARY_GROWTH_RATE
    ):
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
        entry_assumptions_resolved = get_default_entry_assumptions()
    elif isinstance(entry_assumptions, EntryAssumptions):
        entry_assumptions_resolved = entry_assumptions
    else:
        raise TypeError(
            "entry_assumptions must be EntryAssumptions or None, "
            f"got {type(entry_assumptions).__name__}"
        )
    if entry_assumptions_resolved.entry_age >= retirement_age:
        raise ValueError(
            "entry_assumptions.entry_age must be < retirement_age "
            f"({entry_assumptions_resolved.entry_age} >= {retirement_age})"
        )

    path_results = tuple(
        _run_one_path(
            path_index=path_index,
            initial_state=initial_state,
            horizon_years=horizon,
            active_rate_path=tuple(float(v) for v in rate_paths[path_index]),
            retired_interest_rate=retired_interest_rate,
            salary_growth_rate=salary_growth_rate,
            turnover_rate=turnover_rate,
            entry_assumptions=entry_assumptions_resolved,
            contribution_multiplier=contribution_multiplier,
            start_year=start_year,
            retirement_age=retirement_age,
            capital_withdrawal_fraction=capital_withdrawal_fraction,
            conversion_rate=conversion_rate,
        )
        for path_index in range(rate_paths.shape[0])
    )
    return Stage2DEngineResult(
        n_paths=rate_paths.shape[0],
        horizon_years=horizon,
        path_results=path_results,
        rate_paths_active=rate_paths.copy(),
        model_active=model_active,
    )


def _run_one_path(
    *,
    path_index: int,
    initial_state: BVGPortfolioState,
    horizon_years: int,
    active_rate_path: tuple[float, ...],
    retired_interest_rate: float,
    salary_growth_rate: float,
    turnover_rate: float,
    entry_assumptions: EntryAssumptions,
    contribution_multiplier: float,
    start_year: int,
    retirement_age: int,
    capital_withdrawal_fraction: float,
    conversion_rate: float,
) -> Stage2DPathResult:
    states: list[BVGPortfolioState] = [initial_state]
    cashflow_frames: list[pd.DataFrame] = []
    current_state = initial_state

    for step in range(horizon_years):
        calendar_year = start_year + step
        event_date = pd.Timestamp(f"{calendar_year}-12-31")

        regular_df = generate_bvg_cashflow_dataframe_for_state(
            current_state, event_date, contribution_multiplier
        )
        turnover_result = apply_turnover_to_portfolio(
            current_state, turnover_rate, event_date
        )
        ex_df = cashflow_records_to_dataframe(turnover_result.cashflow_records)
        projected = project_portfolio_one_year(
            turnover_result.portfolio_state,
            active_rate_path[step],
            retired_interest_rate,
        )
        grown = apply_salary_growth_to_portfolio(projected, salary_growth_rate)
        transition = apply_retirement_transitions_to_portfolio(
            grown,
            event_date,
            retirement_age=retirement_age,
            capital_withdrawal_fraction=capital_withdrawal_fraction,
            conversion_rate=conversion_rate,
        )
        retire_df = cashflow_records_to_dataframe(transition.cashflow_records)
        post_entry, in_records = apply_entries_to_portfolio(
            transition.portfolio_state,
            entry_assumptions,
            calendar_year,
            event_date,
        )
        in_df = cashflow_records_to_dataframe(in_records)
        year_df = pd.concat(
            [regular_df, ex_df, retire_df, in_df],
            ignore_index=True,
        )
        validate_cashflow_dataframe(year_df)
        cashflow_frames.append(year_df)
        current_state = post_entry
        states.append(current_state)

    if cashflow_frames:
        cashflows = pd.concat(cashflow_frames, ignore_index=True)
    else:
        cashflows = pd.DataFrame(columns=list(CASHFLOW_COLUMNS))
    validate_cashflow_dataframe(cashflows)
    return Stage2DPathResult(
        path_index=path_index,
        cashflows=cashflows,
        portfolio_states=tuple(states),
        active_rate_path=active_rate_path,
    )


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


def _validate_float_tuple(
    value: object,
    name: str,
    expected_len: int,
    *,
    allow_negative: bool,
) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be tuple, got {type(value).__name__}")
    if len(value) != expected_len:
        raise ValueError(f"{name} length must be {expected_len}, got {len(value)}")
    for i, item in enumerate(value):
        fval = _validate_non_bool_real(item, f"{name}[{i}]")
        if not allow_negative and fval < 0:
            raise ValueError(f"{name}[{i}] must be >= 0, got {fval}")
        if fval <= -1:
            raise ValueError(f"{name}[{i}] must be > -1, got {fval}")
