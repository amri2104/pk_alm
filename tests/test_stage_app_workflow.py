from pathlib import Path

import pandas as pd
import pytest

from pk_alm.workflows.stage_app_workflow import (
    MODE_CORE,
    MODE_DYNAMIC_PARAMETERS,
    MODE_FULL_ALM_ACTUS,
    MODE_METADATA,
    MODE_MORTALITY,
    MODE_POPULATION,
    MODE_STOCHASTIC_RATES,
    PROTECTED_OUTPUT_DIRS,
    STREAMLIT_OUTPUT_DIRS,
    load_generated_csv_outputs,
    run_stage,
    summarize_available_outputs,
)


EXPECTED_MODES = (
    MODE_CORE,
    MODE_FULL_ALM_ACTUS,
    MODE_POPULATION,
    MODE_MORTALITY,
    MODE_DYNAMIC_PARAMETERS,
    MODE_STOCHASTIC_RATES,
)


def test_dispatcher_recognizes_all_six_modes() -> None:
    assert tuple(MODE_METADATA) == EXPECTED_MODES


def test_unknown_mode_raises_value_error() -> None:
    with pytest.raises(ValueError):
        run_stage("unknown", horizon_years=1)


def test_each_mode_maps_to_streamlit_specific_output_dir() -> None:
    assert STREAMLIT_OUTPUT_DIRS == {
        MODE_CORE: Path("outputs/streamlit_core"),
        MODE_FULL_ALM_ACTUS: Path("outputs/streamlit_full_alm_actus"),
        MODE_POPULATION: Path("outputs/streamlit_population"),
        MODE_MORTALITY: Path("outputs/streamlit_mortality"),
        MODE_DYNAMIC_PARAMETERS: Path("outputs/streamlit_dynamic_parameters"),
        MODE_STOCHASTIC_RATES: Path("outputs/streamlit_stochastic"),
    }


def test_protected_stage_output_dirs_are_not_used() -> None:
    streamlit_dirs = {path.as_posix() for path in STREAMLIT_OUTPUT_DIRS.values()}
    protected_dirs = {path.as_posix() for path in PROTECTED_OUTPUT_DIRS}
    assert streamlit_dirs.isdisjoint(protected_dirs)


def test_run_stage_rejects_caller_supplied_output_dir() -> None:
    with pytest.raises(ValueError):
        run_stage(MODE_CORE, horizon_years=1, output_dir="outputs/stage1_baseline")


def test_load_and_summarize_generated_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "streamlit_outputs"
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True)
    pd.DataFrame({"a": [1], "b": [2]}).to_csv(
        output_dir / "funding_summary.csv",
        index=False,
    )
    pd.DataFrame({"x": [3]}).to_csv(output_dir / "nested.csv", index=False)
    (plots_dir / "funding_ratio_trajectory.png").write_bytes(b"png")

    csv_outputs = load_generated_csv_outputs(output_dir)
    summary = summarize_available_outputs(output_dir)

    assert sorted(csv_outputs) == ["funding_summary.csv", "nested.csv"]
    assert summary["csv_count"] == 2
    assert summary["png_count"] == 1
    assert "funding_summary.csv" in summary["key_tables"]


@pytest.mark.parametrize(
    "mode_id",
    (MODE_CORE, MODE_POPULATION, MODE_MORTALITY, MODE_DYNAMIC_PARAMETERS),
)
def test_small_dispatcher_runs_for_fast_non_aal_modes(
    mode_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dirs = dict(STREAMLIT_OUTPUT_DIRS)
    output_dirs[mode_id] = tmp_path / mode_id
    monkeypatch.setattr(
        "pk_alm.workflows.stage_app_workflow.STREAMLIT_OUTPUT_DIRS",
        output_dirs,
    )

    kwargs: dict[str, object] = {
        "horizon_years": 1,
        "start_year": 2026,
        "target_funding_ratio": 1.076,
        "valuation_terminal_age": 90,
    }
    if mode_id == MODE_POPULATION:
        kwargs.update(
            {
                "salary_growth_rate": 0.015,
                "turnover_rate": 0.02,
                "entry_count_per_year": 1,
            }
        )
    if mode_id == MODE_MORTALITY:
        kwargs.update({"mortality_mode": "off"})
    if mode_id == MODE_DYNAMIC_PARAMETERS:
        kwargs.update(
            {
                "conversion_rate": 0.068,
                "active_interest_rate": 0.0176,
                "technical_interest_rate": 0.0176,
            }
        )

    result = run_stage(mode_id, **kwargs)

    assert result.mode_id == mode_id
    assert result.output_dir == output_dirs[mode_id]
    assert result.csv_outputs
    assert result.summary["csv_count"] == len(result.csv_outputs)
