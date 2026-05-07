import numpy as np
import pandas as pd
import pytest

from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.assumptions.rate_curves import from_dynamic_parameter
from pk_alm.bvg_liability_engine.orchestration import run_bvg_engine
from pk_alm.bvg_liability_engine.orchestration.stochastic_runner import (
    BVGStochasticResult,
    run_stochastic_bvg_engine,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import EntryAssumptions
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import FixedEntryPolicy
from pk_alm.scenarios.stage2c_dynamic_parameters import (
    build_default_initial_portfolio_stage2c,
)


def _assumptions(
    *,
    horizon_years: int,
    active_interest_rate=0.0176,
    retired_interest_rate: float = 0.0176,
    salary_growth_rate: float = 0.015,
    turnover_rate: float = 0.02,
    entry_assumptions: EntryAssumptions | None = None,
    contribution_multiplier: float = 1.4,
    start_year: int = 2026,
    retirement_age: int = 65,
    capital_withdrawal_fraction: float = 0.35,
    conversion_rate=0.068,
) -> BVGAssumptions:
    entry = (
        entry_assumptions
        if entry_assumptions is not None
        else EntryAssumptions()
    )
    return BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon_years,
        retirement_age=retirement_age,
        valuation_terminal_age=90,
        active_crediting_rate=from_dynamic_parameter(
            active_interest_rate,
            start_year=start_year,
            horizon_years=max(horizon_years, 1),
        ),
        retired_interest_rate=FlatRateCurve(retired_interest_rate),
        technical_discount_rate=FlatRateCurve(retired_interest_rate),
        economic_discount_rate=FlatRateCurve(retired_interest_rate),
        salary_growth_rate=FlatRateCurve(salary_growth_rate),
        conversion_rate=from_dynamic_parameter(
            conversion_rate,
            start_year=start_year,
            horizon_years=max(horizon_years, 1),
        ),
        turnover_rate=turnover_rate,
        capital_withdrawal_fraction=capital_withdrawal_fraction,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(entry),
    )


def run_bvg_engine_stage2d(
    initial_state,
    *,
    horizon_years,
    rate_paths_active,
    retired_interest_rate,
    salary_growth_rate=0.015,
    turnover_rate=0.02,
    entry_assumptions=None,
    contribution_multiplier=1.4,
    start_year=2026,
    retirement_age=65,
    capital_withdrawal_fraction=0.35,
    conversion_rate=0.068,
    model_active="pre_generated",
) -> BVGStochasticResult:
    assumptions = _assumptions(
        horizon_years=horizon_years,
        retired_interest_rate=retired_interest_rate,
        salary_growth_rate=salary_growth_rate,
        turnover_rate=turnover_rate,
        entry_assumptions=entry_assumptions,
        contribution_multiplier=contribution_multiplier,
        start_year=start_year,
        retirement_age=retirement_age,
        capital_withdrawal_fraction=capital_withdrawal_fraction,
        conversion_rate=conversion_rate,
    )
    return run_stochastic_bvg_engine(
        initial_state=initial_state,
        assumptions=assumptions,
        rate_paths_active=rate_paths_active,
        model_active=model_active,
    )


def test_stage2d_n10_smoke() -> None:
    result = run_bvg_engine_stage2d(
        initial_state=build_default_initial_portfolio_stage2c(),
        horizon_years=3,
        rate_paths_active=np.full((10, 3), 0.0176),
        retired_interest_rate=0.0176,
        model_active="test",
    )
    assert isinstance(result, BVGStochasticResult)
    assert result.n_paths == 10
    assert result.horizon_years == 3
    assert len(result.path_results) == 10


def test_single_constant_path_reproduces_stage2c_scalar_engine() -> None:
    initial = build_default_initial_portfolio_stage2c()
    stage2c = run_bvg_engine(
        initial_state=initial,
        assumptions=_assumptions(
            horizon_years=4,
            active_interest_rate=0.0176,
            retired_interest_rate=0.0176,
            salary_growth_rate=0.0,
            turnover_rate=0.0,
            entry_assumptions=EntryAssumptions(entry_count_per_year=0),
            conversion_rate=0.068,
        ),
    )
    stage2d = run_bvg_engine_stage2d(
        initial_state=initial,
        horizon_years=4,
        rate_paths_active=np.full((1, 4), 0.0176),
        retired_interest_rate=0.0176,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
        conversion_rate=0.068,
    )
    path = stage2d.path_results[0]
    pd.testing.assert_frame_equal(path.cashflows, stage2c.cashflows)
    assert path.portfolio_states == stage2c.portfolio_states


def test_zero_paths_raise() -> None:
    with pytest.raises(ValueError):
        run_bvg_engine_stage2d(
            initial_state=build_default_initial_portfolio_stage2c(),
            horizon_years=3,
            rate_paths_active=np.empty((0, 3)),
            retired_interest_rate=0.0176,
        )


def test_zero_horizon_returns_empty_path_cashflows() -> None:
    result = run_bvg_engine_stage2d(
        initial_state=build_default_initial_portfolio_stage2c(),
        horizon_years=0,
        rate_paths_active=np.empty((2, 0)),
        retired_interest_rate=0.0176,
    )
    assert result.horizon_years == 0
    assert len(result.path_results) == 2
    for path in result.path_results:
        assert path.cashflows.empty
        assert len(path.portfolio_states) == 1
    assert result.rate_paths_active.shape == (2, 0)


def test_path_array_shape_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        run_bvg_engine_stage2d(
            initial_state=build_default_initial_portfolio_stage2c(),
            horizon_years=3,
            rate_paths_active=np.full((2, 2), 0.0176),
            retired_interest_rate=0.0176,
        )


def test_path_traceability() -> None:
    rates = np.array([[0.01, 0.02], [0.03, 0.04]])
    result = run_bvg_engine_stage2d(
        initial_state=build_default_initial_portfolio_stage2c(),
        horizon_years=2,
        rate_paths_active=rates,
        retired_interest_rate=0.0176,
    )
    np.testing.assert_allclose(result.rate_paths_active, rates)


def test_same_input_produces_bit_identical_output() -> None:
    kwargs = dict(
        initial_state=build_default_initial_portfolio_stage2c(),
        horizon_years=2,
        rate_paths_active=np.array([[0.01, 0.02], [0.03, 0.01]]),
        retired_interest_rate=0.0176,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
    )
    first = run_bvg_engine_stage2d(**kwargs)
    second = run_bvg_engine_stage2d(**kwargs)
    assert first.rate_paths_active.tolist() == second.rate_paths_active.tolist()
    for first_path, second_path in zip(first.path_results, second.path_results):
        pd.testing.assert_frame_equal(first_path.cashflows, second_path.cashflows)
        assert first_path.portfolio_states == second_path.portfolio_states
