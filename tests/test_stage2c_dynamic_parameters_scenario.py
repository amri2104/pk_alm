import hashlib
from pathlib import Path

import pandas as pd
import pytest

from pk_alm.actus_asset_engine.deterministic import build_deterministic_asset_trajectory
from pk_alm.bvg_liability_engine.orchestration.engine_stage2 import run_bvg_engine_stage2
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import EntryAssumptions
from pk_alm.bvg_liability_engine.pension_logic.valuation import value_portfolio_states
from pk_alm.scenarios.stage2c_dynamic_parameters import (
    PARAMETER_TRAJECTORY_COLUMNS,
    STAGE2C_OUTPUT_FILENAMES,
    Stage2CResult,
    build_default_initial_portfolio_stage2c,
    run_stage2c_dynamic_parameters,
)
from pk_alm.alm_analytics_engine.cashflows import summarize_cashflows_by_year


def _file_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {
        file_path.name: hashlib.sha256(file_path.read_bytes()).hexdigest()
        for file_path in sorted(path.glob("*"))
        if file_path.is_file()
    }


def test_stage2c_runs_end_to_end_with_dynamic_parameters() -> None:
    result = run_stage2c_dynamic_parameters(
        horizon_years=4,
        active_interest_rate=(0.0176, 0.015),
        technical_interest_rate=(0.0176, 0.015, 0.014),
        conversion_rate=(0.068, 0.064),
        output_dir=None,
    )
    assert isinstance(result, Stage2CResult)
    assert result.output_dir is None
    assert len(result.parameter_trajectory) == 5
    assert result.parameter_trajectory.iloc[-1]["conversion_rate"] == 0.064
    assert result.parameter_trajectory.iloc[-1]["active_interest_rate"] == 0.015


def test_stage2c_writes_exactly_ten_csv_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "stage2c_dynamic_parameters"
    result = run_stage2c_dynamic_parameters(output_dir=output_dir)
    assert result.output_dir == output_dir
    assert sorted(p.name for p in output_dir.glob("*.csv")) == sorted(
        STAGE2C_OUTPUT_FILENAMES
    )
    for filename in STAGE2C_OUTPUT_FILENAMES:
        assert isinstance(pd.read_csv(output_dir / filename), pd.DataFrame)


def test_parameter_trajectory_schema_and_horizon_plus_one_rows() -> None:
    result = run_stage2c_dynamic_parameters(
        horizon_years=3,
        conversion_rate=(0.068, 0.064),
        active_interest_rate=(0.0176,),
        technical_interest_rate=(0.0176, 0.016, 0.015),
        output_dir=None,
    )
    params = result.parameter_trajectory
    assert list(params.columns) == list(PARAMETER_TRAJECTORY_COLUMNS)
    assert list(params["projection_year"]) == [0, 1, 2, 3]
    assert list(params["conversion_rate"]) == [0.068, 0.064, 0.064, 0.064]
    assert list(params["active_interest_rate"]) == [0.0176] * 4
    assert list(params["technical_interest_rate"]) == [0.0176, 0.016, 0.015, 0.015]


def test_stage2c_does_not_touch_protected_output_directories(tmp_path: Path) -> None:
    protected = [
        Path("outputs/stage1_baseline"),
        Path("outputs/stage2a_population"),
        Path("outputs/stage2b_mortality"),
    ]
    before = {path: _file_hashes(path) for path in protected}
    run_stage2c_dynamic_parameters(output_dir=tmp_path / "stage2c")
    after = {path: _file_hashes(path) for path in protected}
    assert after == before


def test_scalar_inputs_reproduce_stage2a_core_outputs() -> None:
    initial = build_default_initial_portfolio_stage2c()
    stage2a_engine = run_bvg_engine_stage2(
        initial,
        horizon_years=12,
        active_interest_rate=0.0176,
        retired_interest_rate=0.0176,
        salary_growth_rate=0.015,
        turnover_rate=0.02,
        entry_assumptions=EntryAssumptions(),
        contribution_multiplier=1.4,
        start_year=2026,
        conversion_rate=0.068,
    )
    stage2a_valuation = value_portfolio_states(
        stage2a_engine.portfolio_states,
        0.0176,
        90,
    )
    stage2a_annual = summarize_cashflows_by_year(stage2a_engine.cashflows)
    stage2a_assets = build_deterministic_asset_trajectory(
        stage2a_valuation,
        stage2a_annual,
        target_funding_ratio=1.076,
        annual_return_rate=0.0,
        start_year=2026,
    )

    stage2c = run_stage2c_dynamic_parameters(output_dir=None)
    pd.testing.assert_frame_equal(
        stage2c.cashflows.reset_index(drop=True),
        stage2a_engine.cashflows.reset_index(drop=True),
        check_dtype=False,
    )
    assert stage2c.engine_result.portfolio_states == stage2a_engine.portfolio_states
    pd.testing.assert_frame_equal(stage2c.valuation_snapshots, stage2a_valuation)
    pd.testing.assert_frame_equal(stage2c.asset_snapshots, stage2a_assets)


def test_stage2c_result_post_init_validation_rejects_bad_parameter_trajectory() -> None:
    result = run_stage2c_dynamic_parameters(output_dir=None)
    bad = result.parameter_trajectory.copy(deep=True)
    bad = bad[["projection_year", "active_interest_rate", "conversion_rate", "technical_interest_rate"]]
    with pytest.raises(ValueError):
        Stage2CResult(
            scenario_id=result.scenario_id,
            engine_result=result.engine_result,
            cashflows=result.cashflows,
            valuation_snapshots=result.valuation_snapshots,
            annual_cashflows=result.annual_cashflows,
            asset_snapshots=result.asset_snapshots,
            funding_ratio_trajectory=result.funding_ratio_trajectory,
            funding_summary=result.funding_summary,
            scenario_summary=result.scenario_summary,
            demographic_summary=result.demographic_summary,
            cashflows_by_type=result.cashflows_by_type,
            parameter_trajectory=bad,
            output_dir=None,
        )
