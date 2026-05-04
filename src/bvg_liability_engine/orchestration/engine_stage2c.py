"""Stage 2C BVG engine with dynamic UWS and BVG minimum interest."""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.bvg_liability_engine.pension_logic.cashflow_generation import generate_bvg_cashflow_dataframe_for_state
from pk_alm.bvg_liability_engine.actuarial_assumptions.dynamic_parameters import DynamicParameter, expand_parameter
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import (
    EntryAssumptions,
    apply_entries_to_portfolio,
    get_default_entry_assumptions,
)
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.projection import project_portfolio_one_year
from pk_alm.bvg_liability_engine.pension_logic.retirement_transition import apply_retirement_transitions_to_portfolio
from pk_alm.bvg_liability_engine.population_dynamics.salary_dynamics import (
    MAX_PERMITTED_SALARY_GROWTH_RATE,
    apply_salary_growth_to_portfolio,
)
from pk_alm.bvg_liability_engine.population_dynamics.turnover import (
    MAX_PERMITTED_TURNOVER_RATE,
    apply_turnover_to_portfolio,
)
from pk_alm.cashflows.schema import (
    CASHFLOW_COLUMNS,
    cashflow_records_to_dataframe,
    validate_cashflow_dataframe,
)


@dataclass(frozen=True)
class Stage2CEngineResult:
    """Frozen container for one Stage-2C BVG engine run."""

    portfolio_states: tuple[BVGPortfolioState, ...]
    cashflows: pd.DataFrame
    turnover_rounding_residual_count: tuple[float, ...]
    per_year_entries: tuple[int, ...]
    per_year_exits: tuple[int, ...]
    per_year_retirements: tuple[int, ...]
    salary_growth_rate: float
    turnover_rate: float
    entry_assumptions: EntryAssumptions
    active_interest_rate_trajectory: tuple[float, ...]
    conversion_rate_trajectory: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio_states, tuple):
            raise TypeError(
                f"portfolio_states must be tuple, got {type(self.portfolio_states).__name__}"
            )
        if len(self.portfolio_states) == 0:
            raise ValueError("portfolio_states must not be empty")
        for i, state in enumerate(self.portfolio_states):
            if not isinstance(state, BVGPortfolioState):
                raise TypeError(
                    f"portfolio_states[{i}] must be BVGPortfolioState, "
                    f"got {type(state).__name__}"
                )

        if not isinstance(self.cashflows, pd.DataFrame):
            raise TypeError(
                f"cashflows must be pandas DataFrame, got {type(self.cashflows).__name__}"
            )
        validate_cashflow_dataframe(self.cashflows)
        if not self.cashflows.empty and set(self.cashflows["source"]) != {"BVG"}:
            raise ValueError("cashflows source must be BVG")

        horizon_years = len(self.portfolio_states) - 1
        _validate_float_tuple(
            self.turnover_rounding_residual_count,
            "turnover_rounding_residual_count",
            horizon_years,
        )
        _validate_int_tuple(self.per_year_entries, "per_year_entries", horizon_years)
        _validate_int_tuple(self.per_year_exits, "per_year_exits", horizon_years)
        _validate_int_tuple(
            self.per_year_retirements, "per_year_retirements", horizon_years
        )
        _validate_float_tuple(
            self.active_interest_rate_trajectory,
            "active_interest_rate_trajectory",
            horizon_years,
        )
        _validate_float_tuple(
            self.conversion_rate_trajectory,
            "conversion_rate_trajectory",
            horizon_years,
        )

        salary_growth_rate = _validate_non_bool_real(
            self.salary_growth_rate, "salary_growth_rate"
        )
        if (
            salary_growth_rate < 0.0
            or salary_growth_rate > MAX_PERMITTED_SALARY_GROWTH_RATE
        ):
            raise ValueError(
                "salary_growth_rate must be in "
                f"[0.0, {MAX_PERMITTED_SALARY_GROWTH_RATE}], "
                f"got {salary_growth_rate}"
            )
        turnover_rate = _validate_non_bool_real(self.turnover_rate, "turnover_rate")
        if turnover_rate < 0.0 or turnover_rate > MAX_PERMITTED_TURNOVER_RATE:
            raise ValueError(
                "turnover_rate must be in "
                f"[0.0, {MAX_PERMITTED_TURNOVER_RATE}], got {turnover_rate}"
            )
        if not isinstance(self.entry_assumptions, EntryAssumptions):
            raise TypeError(
                "entry_assumptions must be EntryAssumptions, "
                f"got {type(self.entry_assumptions).__name__}"
            )

    @property
    def initial_state(self) -> BVGPortfolioState:
        return self.portfolio_states[0]

    @property
    def final_state(self) -> BVGPortfolioState:
        return self.portfolio_states[-1]

    @property
    def horizon_years(self) -> int:
        return len(self.portfolio_states) - 1

    @property
    def cashflow_count(self) -> int:
        return len(self.cashflows)

    @property
    def total_entries(self) -> int:
        return sum(self.per_year_entries)

    @property
    def total_exits(self) -> int:
        return sum(self.per_year_exits)

    @property
    def total_retirements(self) -> int:
        return sum(self.per_year_retirements)


def run_bvg_engine_stage2c(
    initial_state: BVGPortfolioState,
    horizon_years: int,
    active_interest_rate: DynamicParameter,
    retired_interest_rate: float,
    salary_growth_rate: float = 0.015,
    turnover_rate: float = 0.02,
    entry_assumptions: EntryAssumptions | None = None,
    contribution_multiplier: float = 1.4,
    start_year: int = 2026,
    retirement_age: int = 65,
    capital_withdrawal_fraction: float = 0.35,
    conversion_rate: DynamicParameter = 0.068,
) -> Stage2CEngineResult:
    """Project a BVG portfolio with dynamic active interest and conversion rate."""
    if not isinstance(initial_state, BVGPortfolioState):
        raise TypeError(
            f"initial_state must be BVGPortfolioState, got {type(initial_state).__name__}"
        )

    horizon_years = _validate_non_bool_int(horizon_years, "horizon_years")
    if horizon_years < 0:
        raise ValueError(f"horizon_years must be >= 0, got {horizon_years}")
    active_interest_trajectory = expand_parameter(
        active_interest_rate,
        horizon_years,
        "active_interest_rate",
    )
    conversion_rate_trajectory = expand_parameter(
        conversion_rate,
        horizon_years,
        "conversion_rate",
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

    states: list[BVGPortfolioState] = [initial_state]
    cashflow_frames: list[pd.DataFrame] = []
    residuals: list[float] = []
    per_year_entries: list[int] = []
    per_year_exits: list[int] = []
    per_year_retirements: list[int] = []
    current_state = initial_state

    for step in range(horizon_years):
        calendar_year = start_year + step
        event_date = pd.Timestamp(f"{calendar_year}-12-31")
        resolved_active_interest_rate = active_interest_trajectory[step]
        resolved_conversion_rate = conversion_rate_trajectory[step]

        regular_df = generate_bvg_cashflow_dataframe_for_state(
            current_state, event_date, contribution_multiplier
        )

        turnover_result = apply_turnover_to_portfolio(
            current_state, turnover_rate, event_date
        )
        ex_df = cashflow_records_to_dataframe(turnover_result.cashflow_records)
        post_turnover = turnover_result.portfolio_state

        projected = project_portfolio_one_year(
            post_turnover, resolved_active_interest_rate, retired_interest_rate
        )

        grown = apply_salary_growth_to_portfolio(projected, salary_growth_rate)

        retiring_persons = sum(
            cohort.count for cohort in grown.active_cohorts
            if cohort.age >= retirement_age
        )
        transition = apply_retirement_transitions_to_portfolio(
            grown,
            event_date,
            retirement_age=retirement_age,
            capital_withdrawal_fraction=capital_withdrawal_fraction,
            conversion_rate=resolved_conversion_rate,
        )
        retire_df = cashflow_records_to_dataframe(transition.cashflow_records)

        post_entry, in_records = apply_entries_to_portfolio(
            transition.portfolio_state,
            entry_assumptions_resolved,
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

        residuals.append(turnover_result.rounding_residual_count)
        per_year_entries.append(entry_assumptions_resolved.entry_count_per_year)
        per_year_exits.append(turnover_result.exited_count)
        per_year_retirements.append(retiring_persons)

        current_state = post_entry
        states.append(current_state)

    if cashflow_frames:
        cashflows = pd.concat(cashflow_frames, ignore_index=True)
    else:
        cashflows = pd.DataFrame(columns=list(CASHFLOW_COLUMNS))
    validate_cashflow_dataframe(cashflows)

    return Stage2CEngineResult(
        portfolio_states=tuple(states),
        cashflows=cashflows,
        turnover_rounding_residual_count=tuple(residuals),
        per_year_entries=tuple(per_year_entries),
        per_year_exits=tuple(per_year_exits),
        per_year_retirements=tuple(per_year_retirements),
        salary_growth_rate=salary_growth_rate,
        turnover_rate=turnover_rate,
        entry_assumptions=entry_assumptions_resolved,
        active_interest_rate_trajectory=active_interest_trajectory,
        conversion_rate_trajectory=conversion_rate_trajectory,
    )


def _validate_non_bool_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


def _validate_non_bool_real(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    return fval


def _validate_float_tuple(value: object, name: str, expected_len: int) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be tuple, got {type(value).__name__}")
    if len(value) != expected_len:
        raise ValueError(f"{name} length must be {expected_len}, got {len(value)}")
    for i, item in enumerate(value):
        fval = _validate_non_bool_real(item, f"{name}[{i}]")
        if fval < 0:
            raise ValueError(f"{name}[{i}] must be >= 0, got {fval}")


def _validate_int_tuple(value: object, name: str, expected_len: int) -> None:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be tuple, got {type(value).__name__}")
    if len(value) != expected_len:
        raise ValueError(f"{name} length must be {expected_len}, got {len(value)}")
    for i, item in enumerate(value):
        ival = _validate_non_bool_int(item, f"{name}[{i}]")
        if ival < 0:
            raise ValueError(f"{name}[{i}] must be >= 0, got {ival}")
