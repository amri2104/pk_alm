"""Tests for the pension fund AAL asset demo (Sprint 7A.2).

Coverage strategy:
- All tests run unconditionally (AAL not required; demo uses offline fallback).
- Core tests verify structure, row counts, sources, and schema compliance.
- No-network tests confirm service_generation_attempted is always False.
- No-side-effect tests confirm Stage-1 outputs and output files are unchanged.
"""

import os
from pathlib import Path

import pandas as pd
import pytest

from pk_alm.adapters.aal_asset_boundary import probe_aal_asset_boundary
from pk_alm.analytics.cashflows import (
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe
from pk_alm.scenarios.aal_asset_demo import (
    PensionFundAALAssetDemoResult,
    run_pension_fund_aal_asset_demo,
)
from pk_alm.scenarios.stage1_baseline import Stage1BaselineResult, run_stage1_baseline

_OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "stage1_baseline"


# ---------------------------------------------------------------------------
# A. Core result structure
# ---------------------------------------------------------------------------


def test_demo_returns_structured_result():
    result = run_pension_fund_aal_asset_demo()
    assert isinstance(result, PensionFundAALAssetDemoResult)
    assert isinstance(result.baseline_result, Stage1BaselineResult)
    assert isinstance(result.aal_cashflows, pd.DataFrame)
    assert isinstance(result.combined_cashflows, pd.DataFrame)
    assert isinstance(result.combined_annual_cashflows, pd.DataFrame)


def test_aal_cashflows_validate_with_schema():
    result = run_pension_fund_aal_asset_demo()
    assert validate_cashflow_dataframe(result.aal_cashflows) is True


def test_combined_cashflows_validate_with_schema():
    result = run_pension_fund_aal_asset_demo()
    assert validate_cashflow_dataframe(result.combined_cashflows) is True


def test_combined_annual_cashflows_validate():
    result = run_pension_fund_aal_asset_demo()
    assert validate_annual_cashflow_dataframe(result.combined_annual_cashflows) is True


# ---------------------------------------------------------------------------
# B. Row counts
# ---------------------------------------------------------------------------


def test_combined_row_count_equals_bvg_plus_aal_rows():
    result = run_pension_fund_aal_asset_demo()
    bvg_rows = len(result.baseline_result.engine_result.cashflows)
    aal_rows = len(result.aal_cashflows)
    assert len(result.combined_cashflows) == bvg_rows + aal_rows


def test_aal_cashflows_not_empty():
    result = run_pension_fund_aal_asset_demo()
    assert not result.aal_cashflows.empty


# ---------------------------------------------------------------------------
# C. Sources
# ---------------------------------------------------------------------------


def test_combined_sources_include_bvg_and_actus():
    result = run_pension_fund_aal_asset_demo()
    sources = set(result.combined_cashflows["source"].unique())
    assert "BVG" in sources
    assert "ACTUS" in sources


def test_aal_cashflows_source_is_always_actus():
    result = run_pension_fund_aal_asset_demo()
    assert (result.aal_cashflows["source"] == "ACTUS").all()


# ---------------------------------------------------------------------------
# D. Annual summary
# ---------------------------------------------------------------------------


def test_combined_annual_cashflows_not_empty():
    result = run_pension_fund_aal_asset_demo()
    assert not result.combined_annual_cashflows.empty


def test_combined_net_cashflow_equals_bvg_plus_aal_by_year():
    result = run_pension_fund_aal_asset_demo()

    bvg_annual = summarize_cashflows_by_year(
        result.baseline_result.engine_result.cashflows
    )
    aal_annual = summarize_cashflows_by_year(result.aal_cashflows)
    bvg_net = {int(r["reporting_year"]): float(r["net_cashflow"]) for _, r in bvg_annual.iterrows()}
    aal_net = {int(r["reporting_year"]): float(r["net_cashflow"]) for _, r in aal_annual.iterrows()}
    combined_net = {
        int(r["reporting_year"]): float(r["net_cashflow"])
        for _, r in result.combined_annual_cashflows.iterrows()
    }

    for year, aal_amount in aal_net.items():
        expected = bvg_net.get(year, 0.0) + aal_amount
        assert combined_net[year] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# E. Inflection year fields
# ---------------------------------------------------------------------------


def test_inflection_year_structural_is_int_or_none():
    result = run_pension_fund_aal_asset_demo()
    val = result.combined_liquidity_inflection_year_structural
    assert val is None or (isinstance(val, int) and not isinstance(val, bool))


def test_inflection_year_net_is_int_or_none():
    result = run_pension_fund_aal_asset_demo()
    val = result.combined_liquidity_inflection_year_net
    assert val is None or (isinstance(val, int) and not isinstance(val, bool))


# ---------------------------------------------------------------------------
# F. No network / service call
# ---------------------------------------------------------------------------


def test_probe_service_generation_attempted_is_always_false():
    probe = probe_aal_asset_boundary()
    assert probe.service_generation_attempted is False


def test_demo_does_not_require_aal_installed():
    # The demo uses the offline fallback and must succeed without AAL.
    result = run_pension_fund_aal_asset_demo()
    assert not result.aal_cashflows.empty


# ---------------------------------------------------------------------------
# G. Stage-1 no-side-effect
# ---------------------------------------------------------------------------


def test_stage1_baseline_outputs_unchanged_by_demo():
    before = run_stage1_baseline(output_dir=None)

    run_pension_fund_aal_asset_demo()

    after = run_stage1_baseline(output_dir=None)

    pd.testing.assert_frame_equal(
        before.engine_result.cashflows,
        after.engine_result.cashflows,
    )
    pd.testing.assert_frame_equal(before.annual_cashflows, after.annual_cashflows)
    pd.testing.assert_frame_equal(
        before.funding_ratio_trajectory, after.funding_ratio_trajectory
    )


def test_stage1_output_files_not_modified_by_demo():
    if not _OUTPUTS_DIR.exists():
        pytest.skip("outputs/stage1_baseline/ does not exist")

    csv_files = list(_OUTPUTS_DIR.glob("*.csv"))
    assert csv_files, "expected CSV files in outputs/stage1_baseline/"

    mtimes_before = {f: os.path.getmtime(f) for f in csv_files}
    run_pension_fund_aal_asset_demo()
    mtimes_after = {f: os.path.getmtime(f) for f in csv_files}

    assert mtimes_before == mtimes_after


# ---------------------------------------------------------------------------
# H. Parameters
# ---------------------------------------------------------------------------


def test_custom_aal_contract_id():
    result = run_pension_fund_aal_asset_demo(aal_contract_id="CUSTOM_PAM")
    assert (result.aal_cashflows["contractId"] == "CUSTOM_PAM").all()


def test_include_purchase_event_adds_ied_row():
    result = run_pension_fund_aal_asset_demo(aal_include_purchase_event=True)
    ied_rows = result.aal_cashflows[result.aal_cashflows["type"] == "IED"]
    assert len(ied_rows) == 1


def test_horizon_zero_keeps_valid_aal_cashflows():
    result = run_pension_fund_aal_asset_demo(horizon_years=0)
    assert result.baseline_result.engine_result.cashflows.empty
    assert not result.aal_cashflows.empty
    assert validate_cashflow_dataframe(result.combined_cashflows) is True
    assert validate_annual_cashflow_dataframe(result.combined_annual_cashflows) is True


# ---------------------------------------------------------------------------
# I. Baseline result integrity
# ---------------------------------------------------------------------------


def test_baseline_result_in_demo_matches_standalone_baseline():
    demo = run_pension_fund_aal_asset_demo()
    standalone = run_stage1_baseline(output_dir=None)

    pd.testing.assert_frame_equal(
        demo.baseline_result.engine_result.cashflows,
        standalone.engine_result.cashflows,
    )
    pd.testing.assert_frame_equal(
        demo.baseline_result.annual_cashflows,
        standalone.annual_cashflows,
    )


# ---------------------------------------------------------------------------
# J. Dataclass validation
# ---------------------------------------------------------------------------


def _good_demo_kwargs() -> dict:
    result = run_pension_fund_aal_asset_demo(horizon_years=1)
    return {
        "baseline_result": result.baseline_result,
        "aal_cashflows": result.aal_cashflows,
        "combined_cashflows": result.combined_cashflows,
        "combined_annual_cashflows": result.combined_annual_cashflows,
        "combined_liquidity_inflection_year_structural": (
            result.combined_liquidity_inflection_year_structural
        ),
        "combined_liquidity_inflection_year_net": (
            result.combined_liquidity_inflection_year_net
        ),
    }


def test_result_rejects_non_stage1_baseline_result():
    kwargs = _good_demo_kwargs()
    kwargs["baseline_result"] = "not a result"
    with pytest.raises(TypeError):
        PensionFundAALAssetDemoResult(**kwargs)


def test_result_rejects_wrong_combined_row_count():
    kwargs = _good_demo_kwargs()
    # Remove one row to break the row-count invariant.
    kwargs["combined_cashflows"] = kwargs["combined_cashflows"].iloc[:-1].copy()
    with pytest.raises(ValueError):
        PensionFundAALAssetDemoResult(**kwargs)
