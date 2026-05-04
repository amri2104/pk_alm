import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from pk_alm.scenarios.stage2d_stochastic import (
    MC_METADATA_COLUMNS,
    RATE_PATHS_SUMMARY_COLUMNS,
    STAGE2D_OUTPUT_FILENAMES,
    Stage2DStochasticResult,
    run_stage2d_stochastic,
)


@pytest.fixture(autouse=True)
def _requires_stochastic_rates() -> None:
    pytest.importorskip("stochastic_rates")


def _file_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {
        file_path.name: hashlib.sha256(file_path.read_bytes()).hexdigest()
        for file_path in sorted(path.glob("*"))
        if file_path.is_file()
    }


def test_stage2d_runs_end_to_end_with_50_paths() -> None:
    result = run_stage2d_stochastic(
        horizon_years=3,
        n_paths=50,
        seed=123,
        output_dir=None,
    )
    assert isinstance(result, Stage2DStochasticResult)
    assert result.output_dir is None
    assert result.engine_result.n_paths == 50
    assert result.engine_result.horizon_years == 3
    assert len(result.funding_ratio_percentiles) == 4
    assert result.rate_paths_technical.shape == (50, 4)


def test_stage2d_writes_exactly_five_csv_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "stage2d_stochastic"
    result = run_stage2d_stochastic(
        horizon_years=2,
        n_paths=10,
        seed=42,
        output_dir=output_dir,
    )
    assert result.output_dir == output_dir
    assert sorted(p.name for p in output_dir.glob("*.csv")) == sorted(
        STAGE2D_OUTPUT_FILENAMES
    )
    for filename in STAGE2D_OUTPUT_FILENAMES:
        assert isinstance(pd.read_csv(output_dir / filename), pd.DataFrame)


def test_stage2d_does_not_touch_protected_output_directories(tmp_path: Path) -> None:
    protected = [
        Path("outputs/stage1_baseline"),
        Path("outputs/stage2a_population"),
        Path("outputs/stage2b_mortality"),
        Path("outputs/stage2c_dynamic_parameters"),
    ]
    before = {path: _file_hashes(path) for path in protected}
    run_stage2d_stochastic(
        horizon_years=2,
        n_paths=10,
        seed=7,
        output_dir=tmp_path / "stage2d",
    )
    after = {path: _file_hashes(path) for path in protected}
    assert after == before


def test_same_seed_writes_byte_identical_csv_outputs(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    kwargs = dict(horizon_years=3, n_paths=20, seed=99)

    run_stage2d_stochastic(output_dir=first_dir, **kwargs)
    run_stage2d_stochastic(output_dir=second_dir, **kwargs)

    for filename in STAGE2D_OUTPUT_FILENAMES:
        assert (first_dir / filename).read_bytes() == (
            second_dir / filename
        ).read_bytes()


def test_different_seeds_change_aggregates() -> None:
    first = run_stage2d_stochastic(
        horizon_years=3,
        n_paths=30,
        seed=1,
        output_dir=None,
    )
    second = run_stage2d_stochastic(
        horizon_years=3,
        n_paths=30,
        seed=2,
        output_dir=None,
    )
    assert not first.funding_ratio_percentiles.equals(
        second.funding_ratio_percentiles
    )


@pytest.mark.parametrize("model", ["vasicek", "cir", "ho_lee", "hull_white"])
def test_each_short_rate_model_runs(model: str) -> None:
    result = run_stage2d_stochastic(
        horizon_years=2,
        n_paths=5,
        seed=11,
        model_active=model,
        model_technical=model,
        output_dir=None,
    )
    assert result.engine_result.model_active == model
    assert result.mc_metadata.iloc[0]["model_technical"] == model


def test_active_and_technical_model_mismatch_runs() -> None:
    result = run_stage2d_stochastic(
        horizon_years=2,
        n_paths=5,
        seed=12,
        model_active="vasicek",
        model_technical="cir",
        output_dir=None,
    )
    assert result.engine_result.model_active == "vasicek"
    assert result.mc_metadata.iloc[0]["model_technical"] == "cir"


def test_metadata_contains_model_params() -> None:
    result = run_stage2d_stochastic(
        horizon_years=2,
        n_paths=5,
        seed=13,
        output_dir=None,
    )
    metadata = result.mc_metadata
    assert list(metadata.columns) == list(MC_METADATA_COLUMNS)
    row = metadata.iloc[0]
    assert row["n_paths"] == 5
    assert row["seed"] == 13
    active_params = json.loads(row["model_active_params"])
    technical_params = json.loads(row["model_technical_params"])
    assert active_params["sigma"] == 0.001
    assert technical_params["sigma"] == 0.005
    assert "calibrator" in active_params


def test_rate_paths_summary_schema() -> None:
    result = run_stage2d_stochastic(
        horizon_years=2,
        n_paths=5,
        seed=14,
        output_dir=None,
    )
    assert list(result.rate_paths_summary.columns) == list(RATE_PATHS_SUMMARY_COLUMNS)
    assert list(result.rate_paths_summary["projection_year"]) == [0, 1, 2]
