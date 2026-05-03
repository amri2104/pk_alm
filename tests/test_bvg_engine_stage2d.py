import numpy as np
import pandas as pd
import pytest

from pk_alm.bvg.engine_stage2c import run_bvg_engine_stage2c
from pk_alm.bvg.engine_stage2d import Stage2DEngineResult, run_bvg_engine_stage2d
from pk_alm.bvg.entry_dynamics import EntryAssumptions
from pk_alm.scenarios.stage2c_dynamic_parameters import (
    build_default_initial_portfolio_stage2c,
)


def test_stage2d_n10_smoke() -> None:
    result = run_bvg_engine_stage2d(
        build_default_initial_portfolio_stage2c(),
        horizon_years=3,
        rate_paths_active=np.full((10, 3), 0.0176),
        retired_interest_rate=0.0176,
        model_active="test",
    )
    assert isinstance(result, Stage2DEngineResult)
    assert result.n_paths == 10
    assert result.horizon_years == 3
    assert len(result.path_results) == 10


def test_single_constant_path_reproduces_stage2c_scalar_engine() -> None:
    initial = build_default_initial_portfolio_stage2c()
    stage2c = run_bvg_engine_stage2c(
        initial,
        horizon_years=4,
        active_interest_rate=0.0176,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.0,
        turnover_rate=0.0,
        entry_assumptions=EntryAssumptions(entry_count_per_year=0),
        conversion_rate=0.068,
    )
    stage2d = run_bvg_engine_stage2d(
        initial,
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
            build_default_initial_portfolio_stage2c(),
            horizon_years=3,
            rate_paths_active=np.empty((0, 3)),
            retired_interest_rate=0.0176,
        )


def test_zero_horizon_returns_empty_path_cashflows() -> None:
    result = run_bvg_engine_stage2d(
        build_default_initial_portfolio_stage2c(),
        horizon_years=0,
        rate_paths_active=np.empty((2, 0)),
        retired_interest_rate=0.0176,
    )
    assert result.horizon_years == 0
    assert len(result.path_results) == 2
    for path in result.path_results:
        assert path.cashflows.empty
        assert len(path.portfolio_states) == 1
        assert path.active_rate_path == ()


def test_path_array_shape_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        run_bvg_engine_stage2d(
            build_default_initial_portfolio_stage2c(),
            horizon_years=3,
            rate_paths_active=np.full((2, 2), 0.0176),
            retired_interest_rate=0.0176,
        )


def test_path_traceability() -> None:
    rates = np.array([[0.01, 0.02], [0.03, 0.04]])
    result = run_bvg_engine_stage2d(
        build_default_initial_portfolio_stage2c(),
        horizon_years=2,
        rate_paths_active=rates,
        retired_interest_rate=0.0176,
    )
    for i, path in enumerate(result.path_results):
        assert path.active_rate_path == pytest.approx(tuple(rates[i]))


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
