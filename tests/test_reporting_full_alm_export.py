"""Tests for Sprint 8 Full ALM reporting exports."""

import inspect
import os
from pathlib import Path

import pandas as pd
import pytest

from pk_alm.analytics.alm_kpis import (
    ALM_KPI_SUMMARY_COLUMNS,
    CASHFLOW_BY_SOURCE_PLOT_COLUMNS,
    NET_CASHFLOW_PLOT_COLUMNS,
)
from pk_alm.analytics.cashflows import ANNUAL_CASHFLOW_COLUMNS
from pk_alm.analytics.funding import FUNDING_RATIO_COLUMNS
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS
from pk_alm.reporting import full_alm_export
from pk_alm.reporting.full_alm_export import (
    FULL_ALM_EXPORT_FILENAMES,
    FullALMExportResult,
    export_full_alm_result,
    export_full_alm_results,
)
from pk_alm.scenarios.full_alm_scenario import run_full_alm_scenario

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROTECTED_OUTPUTS_DIR = _REPO_ROOT / "outputs" / "stage1_baseline"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


@pytest.fixture()
def fallback_scenario():
    return run_full_alm_scenario(generation_mode="fallback")


def _read_exported_csvs(result: FullALMExportResult) -> dict[str, pd.DataFrame]:
    return {
        key: pd.read_csv(path)
        for key, path in sorted(result.output_paths.items())
    }


def test_export_full_alm_result_exports_precomputed_result_without_rerun(
    tmp_path,
    monkeypatch,
    fallback_scenario,
):
    def fail_if_called(**kwargs):
        raise AssertionError(f"scenario runner should not be called: {kwargs}")

    monkeypatch.setattr(full_alm_export, "run_full_alm_scenario", fail_if_called)

    result = export_full_alm_result(fallback_scenario, tmp_path)

    assert isinstance(result, FullALMExportResult)
    assert result.scenario_result is fallback_scenario
    assert result.output_dir == tmp_path.resolve()
    assert set(result.output_paths) == set(FULL_ALM_EXPORT_FILENAMES)


def test_export_full_alm_results_wrapper_default_generation_mode_is_aal(
    tmp_path,
    monkeypatch,
    fallback_scenario,
):
    calls = []

    def fake_run_full_alm_scenario(*, generation_mode="aal", **scenario_kwargs):
        calls.append((generation_mode, scenario_kwargs))
        return fallback_scenario

    monkeypatch.setattr(
        full_alm_export,
        "run_full_alm_scenario",
        fake_run_full_alm_scenario,
    )

    export_full_alm_results(tmp_path)

    assert calls == [("aal", {})]
    sig = inspect.signature(export_full_alm_results)
    assert sig.parameters["generation_mode"].default == "aal"


def test_export_full_alm_results_passes_explicit_fallback_and_kwargs(
    tmp_path,
    monkeypatch,
    fallback_scenario,
):
    calls = []

    def fake_run_full_alm_scenario(*, generation_mode="aal", **scenario_kwargs):
        calls.append((generation_mode, scenario_kwargs))
        return fallback_scenario

    monkeypatch.setattr(
        full_alm_export,
        "run_full_alm_scenario",
        fake_run_full_alm_scenario,
    )

    export_full_alm_results(
        tmp_path,
        generation_mode="fallback",
        scenario_id="reporting_test",
        horizon_years=3,
    )

    assert calls == [
        ("fallback", {"scenario_id": "reporting_test", "horizon_years": 3})
    ]


def test_export_functions_reject_protected_stage1_output_targets(
    fallback_scenario,
):
    with pytest.raises(ValueError):
        export_full_alm_result(fallback_scenario, _PROTECTED_OUTPUTS_DIR)

    with pytest.raises(ValueError):
        export_full_alm_result(fallback_scenario, _PROTECTED_OUTPUTS_DIR / "child")

    with pytest.raises(ValueError):
        export_full_alm_results(_PROTECTED_OUTPUTS_DIR, generation_mode="fallback")

    with pytest.raises(ValueError):
        export_full_alm_results(
            _PROTECTED_OUTPUTS_DIR / "child",
            generation_mode="fallback",
        )


def test_aal_failures_propagate_without_silent_fallback(tmp_path, monkeypatch):
    def raise_import_error(*, generation_mode="aal", **scenario_kwargs):
        assert generation_mode == "aal"
        raise ImportError("simulated missing AAL")

    monkeypatch.setattr(
        full_alm_export,
        "run_full_alm_scenario",
        raise_import_error,
    )

    with pytest.raises(ImportError, match="simulated missing AAL"):
        export_full_alm_results(tmp_path)

    assert not tmp_path.exists() or list(tmp_path.iterdir()) == []


def test_exported_csvs_exist_are_readable_and_have_stable_columns(
    tmp_path,
    fallback_scenario,
):
    result = export_full_alm_result(fallback_scenario, tmp_path)
    frames = _read_exported_csvs(result)

    assert list(frames["kpi_summary"].columns) == list(ALM_KPI_SUMMARY_COLUMNS)
    assert list(frames["annual_cashflows"].columns) == list(ANNUAL_CASHFLOW_COLUMNS)
    assert list(frames["cashflow_by_source"].columns) == list(
        CASHFLOW_BY_SOURCE_PLOT_COLUMNS
    )
    assert list(frames["net_cashflow"].columns) == list(NET_CASHFLOW_PLOT_COLUMNS)
    assert list(frames["combined_cashflows"].columns) == list(CASHFLOW_COLUMNS)
    assert list(frames["funding_ratio_trajectory"].columns) == list(
        FUNDING_RATIO_COLUMNS
    )

    for key, path in result.output_paths.items():
        assert path.exists(), key
        assert path.is_file(), key
        path.relative_to(tmp_path)
        assert path.name == FULL_ALM_EXPORT_FILENAMES[key]


def test_export_does_not_touch_stage1_baseline_outputs(
    tmp_path,
    fallback_scenario,
):
    if not _PROTECTED_OUTPUTS_DIR.exists():
        pytest.skip("outputs/stage1_baseline/ does not exist")

    csv_files = sorted(_PROTECTED_OUTPUTS_DIR.glob("*.csv"))
    assert csv_files
    before = {path: os.path.getmtime(path) for path in csv_files}

    export_full_alm_result(fallback_scenario, tmp_path)

    after = {path: os.path.getmtime(path) for path in csv_files}
    assert after == before


def test_export_does_not_modify_pyproject_or_add_streamlit(
    tmp_path,
    fallback_scenario,
):
    before = _PYPROJECT.read_text()
    before_mtime = os.path.getmtime(_PYPROJECT)

    export_full_alm_result(fallback_scenario, tmp_path)

    after = _PYPROJECT.read_text()
    assert after == before
    assert os.path.getmtime(_PYPROJECT) == before_mtime
    assert "streamlit" not in after.lower()
