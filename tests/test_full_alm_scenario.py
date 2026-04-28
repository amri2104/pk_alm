"""Tests for the Full ALM scenario (Sprint 7E)."""

import dataclasses
import os
from pathlib import Path

import pandas as pd
import pytest

from pk_alm.adapters.aal_probe import (
    AAL_DISTRIBUTION_NAMES,
    AAL_MODULE_NAME,
    AALAvailability,
)
from pk_alm.assets.aal_engine import AALAssetEngineResult
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe
from pk_alm.scenarios.full_alm_scenario import (
    FullALMScenarioResult,
    run_full_alm_scenario,
)
from pk_alm.scenarios.stage1_baseline import (
    Stage1BaselineResult,
    run_stage1_baseline,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OUTPUTS_DIR = _REPO_ROOT / "outputs" / "stage1_baseline"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _force_aal_unavailable(monkeypatch) -> None:
    from pk_alm.assets import aal_engine

    fake = AALAvailability(
        is_available=False,
        module_name=AAL_MODULE_NAME,
        distribution_names=AAL_DISTRIBUTION_NAMES,
        version=None,
        import_error="simulated absence for test",
    )
    monkeypatch.setattr(aal_engine, "check_aal_availability", lambda: fake)


# ---------------------------------------------------------------------------
# A. Fallback mode (always run)
# ---------------------------------------------------------------------------


def test_result_is_frozen():
    result = run_full_alm_scenario(generation_mode="fallback")
    assert dataclasses.is_dataclass(result)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.generation_mode = "aal"  # type: ignore[misc]


def test_fallback_mode_works_explicitly_without_aal():
    result = run_full_alm_scenario(generation_mode="fallback")
    assert isinstance(result, FullALMScenarioResult)
    assert isinstance(result.stage1_result, Stage1BaselineResult)
    assert isinstance(result.aal_asset_result, AALAssetEngineResult)


def test_generation_mode_recorded():
    result = run_full_alm_scenario(generation_mode="fallback")
    assert result.generation_mode == "fallback"
    assert result.aal_asset_result.generation_mode == "fallback"


def test_fallback_mode_clearly_reported_in_aal_result_notes():
    result = run_full_alm_scenario(generation_mode="fallback")
    joined = " | ".join(result.aal_asset_result.notes)
    assert "fallback" in joined.lower()
    assert "AAL was not used" in joined


# ---------------------------------------------------------------------------
# B. Combined cashflows
# ---------------------------------------------------------------------------


def test_combined_row_count_equals_bvg_plus_asset_rows():
    result = run_full_alm_scenario(generation_mode="fallback")
    assert len(result.combined_cashflows) == (
        len(result.bvg_cashflows) + len(result.asset_cashflows)
    )


def test_combined_sources_include_bvg_and_actus():
    result = run_full_alm_scenario(generation_mode="fallback")
    sources = set(result.combined_cashflows["source"].unique())
    assert "BVG" in sources
    assert "ACTUS" in sources


def test_combined_cashflows_preserve_canonical_schema():
    result = run_full_alm_scenario(generation_mode="fallback")
    assert list(result.combined_cashflows.columns) == list(CASHFLOW_COLUMNS)
    assert validate_cashflow_dataframe(result.combined_cashflows) is True


def test_combined_cashflows_sorted_deterministically():
    result = run_full_alm_scenario(generation_mode="fallback")
    df = result.combined_cashflows
    expected = df.sort_values(
        ["time", "source", "contractId", "type"],
        ignore_index=True,
    )
    pd.testing.assert_frame_equal(df, expected)


def test_annual_cashflows_not_empty():
    result = run_full_alm_scenario(generation_mode="fallback")
    assert not result.annual_cashflows.empty


def test_asset_cashflows_have_source_actus_only():
    result = run_full_alm_scenario(generation_mode="fallback")
    assert (result.asset_cashflows["source"] == "ACTUS").all()


def test_bvg_cashflows_have_source_bvg_only():
    result = run_full_alm_scenario(generation_mode="fallback")
    assert (result.bvg_cashflows["source"] == "BVG").all()


# ---------------------------------------------------------------------------
# C. Generation mode validation and no-silent-fallback
# ---------------------------------------------------------------------------


def test_invalid_generation_mode_rejected():
    with pytest.raises(ValueError):
        run_full_alm_scenario(generation_mode="silent")


def test_aal_mode_does_not_silently_fall_back(monkeypatch):
    _force_aal_unavailable(monkeypatch)
    with pytest.raises(ImportError):
        run_full_alm_scenario(generation_mode="aal")


def test_default_generation_mode_is_aal():
    import inspect

    sig = inspect.signature(run_full_alm_scenario)
    assert sig.parameters["generation_mode"].default == "aal"


# ---------------------------------------------------------------------------
# D. Stage-1 protection
# ---------------------------------------------------------------------------


def test_stage1_baseline_outputs_unchanged_by_full_alm():
    before = run_stage1_baseline(output_dir=None)
    run_full_alm_scenario(generation_mode="fallback")
    after = run_stage1_baseline(output_dir=None)
    pd.testing.assert_frame_equal(
        before.engine_result.cashflows,
        after.engine_result.cashflows,
    )
    pd.testing.assert_frame_equal(before.annual_cashflows, after.annual_cashflows)
    pd.testing.assert_frame_equal(
        before.funding_ratio_trajectory,
        after.funding_ratio_trajectory,
    )


def test_stage1_output_files_not_modified_by_full_alm():
    if not _OUTPUTS_DIR.exists():
        pytest.skip("outputs/stage1_baseline/ does not exist")
    csv_files = list(_OUTPUTS_DIR.glob("*.csv"))
    assert csv_files
    mtimes_before = {f: os.path.getmtime(f) for f in csv_files}
    run_full_alm_scenario(generation_mode="fallback")
    mtimes_after = {f: os.path.getmtime(f) for f in csv_files}
    assert mtimes_before == mtimes_after


def test_pyproject_not_modified_by_full_alm():
    assert _PYPROJECT.exists()
    mtime_before = os.path.getmtime(_PYPROJECT)
    contents_before = _PYPROJECT.read_text()
    run_full_alm_scenario(generation_mode="fallback")
    assert os.path.getmtime(_PYPROJECT) == mtime_before
    assert _PYPROJECT.read_text() == contents_before


def test_run_stage1_baseline_produces_byte_equal_results_after_full_alm():
    direct = run_stage1_baseline(output_dir=None)
    via_scenario = run_full_alm_scenario(generation_mode="fallback").stage1_result
    pd.testing.assert_frame_equal(
        direct.engine_result.cashflows,
        via_scenario.engine_result.cashflows,
    )
    pd.testing.assert_frame_equal(
        direct.annual_cashflows, via_scenario.annual_cashflows
    )


# ---------------------------------------------------------------------------
# E. AAL-required (skip without AAL or when service unreachable)
# ---------------------------------------------------------------------------


def test_aal_mode_runs_against_real_aal_or_skips():
    pytest.importorskip("awesome_actus_lib")
    try:
        result = run_full_alm_scenario(generation_mode="aal")
    except RuntimeError as exc:
        pytest.skip(f"AAL service path unreachable in this env: {exc}")
    assert result.generation_mode == "aal"
    assert result.aal_asset_result.aal_available is True
    assert validate_cashflow_dataframe(result.combined_cashflows) is True
