"""Tests for Sprint 9 Full ALM user-facing workflow."""

import inspect
import os
import runpy
from pathlib import Path

import pandas as pd
import pytest

from pk_alm.reporting.full_alm_export import FULL_ALM_EXPORT_FILENAMES
from pk_alm.reporting.plots import FULL_ALM_PLOT_FILENAMES
from pk_alm.workflows import full_alm_workflow
from pk_alm.workflows.full_alm_workflow import (
    FullALMWorkflowResult,
    run_full_alm_reporting_workflow,
    summarize_generated_outputs,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROTECTED_OUTPUTS_DIR = _REPO_ROOT / "outputs" / "stage1_baseline"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_EXAMPLE_PATH = _REPO_ROOT / "examples" / "full_alm_reporting_workflow.py"


def test_workflow_explicit_fallback_creates_csv_and_png_outputs(tmp_path):
    result = run_full_alm_reporting_workflow(
        tmp_path,
        generation_mode="fallback",
    )

    assert isinstance(result, FullALMWorkflowResult)
    assert result.output_dir == tmp_path.resolve()
    assert result.generation_mode == "fallback"
    assert tuple(result.generated_files.keys()) == ("csv", "png", "benchmark")
    assert len(result.generated_files["csv"]) == len(FULL_ALM_EXPORT_FILENAMES)
    assert len(result.generated_files["png"]) == len(FULL_ALM_PLOT_FILENAMES)
    assert result.generated_files["benchmark"] == ()

    for path in result.generated_files["csv"]:
        assert path.exists()
        assert path.suffix == ".csv"
        path.relative_to(tmp_path)
        assert not pd.read_csv(path).empty

    for path in result.generated_files["png"]:
        assert path.exists()
        assert path.suffix == ".png"
        path.relative_to(tmp_path)
        assert path.stat().st_size > 0


def test_workflow_does_not_create_benchmark_without_inputs(tmp_path):
    result = run_full_alm_reporting_workflow(
        tmp_path,
        generation_mode="fallback",
    )

    assert result.benchmark_path is None
    assert result.generated_files["benchmark"] == ()
    assert not (tmp_path / "benchmark_plausibility.csv").exists()


def test_workflow_creates_benchmark_when_references_are_passed(tmp_path):
    result = run_full_alm_reporting_workflow(
        tmp_path,
        generation_mode="fallback",
        benchmark_reference_values={"final_funding_ratio_percent": 100.0},
        benchmark_notes={"final_funding_ratio_percent": "caller reference"},
    )

    assert result.benchmark_path is not None
    assert result.benchmark_path.name == "benchmark_plausibility.csv"
    assert result.generated_files["benchmark"] == (result.benchmark_path,)
    assert result.benchmark_path.exists()

    benchmark = pd.read_csv(result.benchmark_path)
    assert "final_funding_ratio_percent" in set(benchmark["metric"])


def test_workflow_rejects_protected_stage1_output_path():
    with pytest.raises(ValueError):
        run_full_alm_reporting_workflow(
            _PROTECTED_OUTPUTS_DIR,
            generation_mode="fallback",
        )


def test_workflow_does_not_mutate_stage1_baseline_outputs(tmp_path):
    if not _PROTECTED_OUTPUTS_DIR.exists():
        pytest.skip("outputs/stage1_baseline/ does not exist")

    csv_files = sorted(_PROTECTED_OUTPUTS_DIR.glob("*.csv"))
    assert csv_files
    before = {path: os.path.getmtime(path) for path in csv_files}

    run_full_alm_reporting_workflow(
        tmp_path,
        generation_mode="fallback",
    )

    after = {path: os.path.getmtime(path) for path in csv_files}
    assert after == before


def test_workflow_default_generation_mode_is_aal():
    sig = inspect.signature(run_full_alm_reporting_workflow)
    assert sig.parameters["generation_mode"].default == "aal"


def test_aal_errors_propagate_without_silent_fallback(tmp_path, monkeypatch):
    def raise_import_error(output_dir, *, generation_mode="aal", **scenario_kwargs):
        assert generation_mode == "aal"
        raise ImportError("simulated missing AAL")

    monkeypatch.setattr(
        full_alm_workflow,
        "export_full_alm_results",
        raise_import_error,
    )

    with pytest.raises(ImportError, match="simulated missing AAL"):
        run_full_alm_reporting_workflow(tmp_path)

    assert not tmp_path.exists() or list(tmp_path.iterdir()) == []


def test_example_script_is_import_safe_and_main_guarded():
    namespace = runpy.run_path(str(_EXAMPLE_PATH), run_name="not_main")
    text = _EXAMPLE_PATH.read_text()

    assert "main" in namespace
    assert 'if __name__ == "__main__":' in text
    assert "main()" in text


def test_generated_files_summary_is_stable(tmp_path):
    result = run_full_alm_reporting_workflow(
        tmp_path,
        generation_mode="fallback",
        benchmark_model_values={"conversion_rate_percent": 6.8},
    )
    summary = summarize_generated_outputs(result)

    assert list(summary.keys()) == [
        "output_dir",
        "generation_mode",
        "csv_count",
        "png_count",
        "benchmark_available",
        "total_generated_files",
    ]
    assert summary["output_dir"] == tmp_path.resolve()
    assert summary["generation_mode"] == "fallback"
    assert summary["csv_count"] == len(FULL_ALM_EXPORT_FILENAMES)
    assert summary["png_count"] == len(FULL_ALM_PLOT_FILENAMES)
    assert summary["benchmark_available"] is True
    assert summary["total_generated_files"] == (
        len(FULL_ALM_EXPORT_FILENAMES) + len(FULL_ALM_PLOT_FILENAMES) + 1
    )


def test_workflow_does_not_modify_pyproject_or_add_streamlit(tmp_path):
    before = _PYPROJECT.read_text()
    before_mtime = os.path.getmtime(_PYPROJECT)

    run_full_alm_reporting_workflow(
        tmp_path,
        generation_mode="fallback",
    )

    after = _PYPROJECT.read_text()
    assert after == before
    assert os.path.getmtime(_PYPROJECT) == before_mtime
    assert "streamlit" not in after.lower()
