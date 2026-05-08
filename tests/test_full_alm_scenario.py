"""Tests for the Full ALM scenario."""

import dataclasses
import os
from pathlib import Path

import pandas as pd
import pytest

from pk_alm.actus_asset_engine.aal_asset_portfolio import make_pam_contract_config
from pk_alm.actus_asset_engine.aal_engine import AALAssetEngineResult
from pk_alm.actus_asset_engine.risk_factors import AALRiskFactorSet
from pk_alm.actus_asset_engine.simulation_settings import AALSimulationSettings
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe
from pk_alm.scenarios import full_alm_scenario as scenario_mod
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


def _fake_asset_result() -> AALAssetEngineResult:
    contract = make_pam_contract_config(
        contract_id="TEST_PAM",
        start_year=2026,
        maturity_year=2028,
        nominal_value=100_000.0,
        coupon_rate=0.02,
    )
    cashflows = pd.DataFrame(
        [
            {
                "contractId": "TEST_PAM",
                "time": pd.Timestamp("2028-12-31"),
                "type": "IP",
                "payoff": 2_000.0,
                "nominalValue": 100_000.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
            {
                "contractId": "TEST_PAM",
                "time": pd.Timestamp("2028-12-31"),
                "type": "MD",
                "payoff": 100_000.0,
                "nominalValue": 0.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
        ],
        columns=CASHFLOW_COLUMNS,
    )
    return AALAssetEngineResult(
        cashflows=cashflows,
        contracts=(contract,),
        risk_factors=AALRiskFactorSet(),
        settings=AALSimulationSettings(
            analysis_date="2026-01-01T00:00:00",
            event_start_date="2026-01-01T00:00:00",
            event_end_date="2038-12-31T00:00:00",
        ),
        event_summary=pd.DataFrame(),
        event_coverage_report=pd.DataFrame(),
        risk_factor_report=pd.DataFrame(),
        limitation_report=pd.DataFrame(),
        aal_version="fake",
        notes=("fake AAL result",),
    )


@pytest.fixture()
def fake_aal_engine(monkeypatch):
    calls = []

    def fake_run_aal_asset_engine(*, contracts=None, risk_factors=None, settings=None):
        calls.append(contracts)
        return _fake_asset_result()

    monkeypatch.setattr(
        scenario_mod,
        "run_aal_asset_engine",
        fake_run_aal_asset_engine,
    )
    return calls


def test_result_is_frozen(fake_aal_engine):
    result = run_full_alm_scenario()
    assert dataclasses.is_dataclass(result)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.generation_mode = "fallback"  # type: ignore[misc]


def test_full_alm_scenario_runs_with_required_aal_path(fake_aal_engine):
    result = run_full_alm_scenario()
    assert isinstance(result, FullALMScenarioResult)
    assert isinstance(result.stage1_result, Stage1BaselineResult)
    assert isinstance(result.aal_asset_result, AALAssetEngineResult)
    assert result.generation_mode == "aal"
    assert result.aal_asset_result.generation_mode == "aal"


def test_asset_contracts_are_passed_to_aal_engine(fake_aal_engine):
    contracts = (
        make_pam_contract_config(
            contract_id="CUSTOM",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        ),
    )
    run_full_alm_scenario(asset_contracts=contracts)
    assert fake_aal_engine == [contracts]


def test_combined_row_count_equals_bvg_plus_asset_rows(fake_aal_engine):
    result = run_full_alm_scenario()
    assert len(result.combined_cashflows) == (
        len(result.bvg_cashflows) + len(result.asset_cashflows)
    )


def test_combined_sources_include_bvg_and_actus(fake_aal_engine):
    result = run_full_alm_scenario()
    sources = set(result.combined_cashflows["source"].unique())
    assert "BVG" in sources
    assert "ACTUS" in sources


def test_combined_cashflows_preserve_canonical_schema(fake_aal_engine):
    result = run_full_alm_scenario()
    assert list(result.combined_cashflows.columns) == list(CASHFLOW_COLUMNS)
    assert validate_cashflow_dataframe(result.combined_cashflows) is True


def test_combined_cashflows_sorted_deterministically(fake_aal_engine):
    result = run_full_alm_scenario()
    df = result.combined_cashflows
    expected = df.sort_values(
        ["time", "source", "contractId", "type"],
        ignore_index=True,
    )
    pd.testing.assert_frame_equal(df, expected)


def test_annual_cashflows_not_empty(fake_aal_engine):
    result = run_full_alm_scenario()
    assert not result.annual_cashflows.empty


def test_asset_cashflows_have_source_actus_only(fake_aal_engine):
    result = run_full_alm_scenario()
    assert set(result.asset_cashflows["source"]) == {"ACTUS"}


def test_bvg_cashflows_have_source_bvg_only(fake_aal_engine):
    result = run_full_alm_scenario()
    assert (result.bvg_cashflows["source"] == "BVG").all()


def test_stage1_baseline_outputs_unchanged_by_full_alm(fake_aal_engine):
    before = run_stage1_baseline(output_dir=None)
    run_full_alm_scenario()
    after = run_stage1_baseline(output_dir=None)
    pd.testing.assert_frame_equal(before.engine_result.cashflows, after.engine_result.cashflows)
    pd.testing.assert_frame_equal(before.annual_cashflows, after.annual_cashflows)
    pd.testing.assert_frame_equal(
        before.funding_ratio_trajectory,
        after.funding_ratio_trajectory,
    )


def test_stage1_output_files_not_modified_by_full_alm(fake_aal_engine):
    if not _OUTPUTS_DIR.exists():
        pytest.skip("outputs/stage1_baseline/ does not exist")
    csv_files = list(_OUTPUTS_DIR.glob("*.csv"))
    assert csv_files
    mtimes_before = {f: os.path.getmtime(f) for f in csv_files}
    run_full_alm_scenario()
    mtimes_after = {f: os.path.getmtime(f) for f in csv_files}
    assert mtimes_before == mtimes_after


def test_pyproject_not_modified_by_full_alm(fake_aal_engine):
    assert _PYPROJECT.exists()
    mtime_before = os.path.getmtime(_PYPROJECT)
    contents_before = _PYPROJECT.read_text()
    run_full_alm_scenario()
    assert os.path.getmtime(_PYPROJECT) == mtime_before
    assert _PYPROJECT.read_text() == contents_before


def test_run_stage1_baseline_produces_byte_equal_results_after_full_alm(fake_aal_engine):
    direct = run_stage1_baseline(output_dir=None)
    via_scenario = run_full_alm_scenario().stage1_result
    pd.testing.assert_frame_equal(
        direct.engine_result.cashflows,
        via_scenario.engine_result.cashflows,
    )
    pd.testing.assert_frame_equal(direct.annual_cashflows, via_scenario.annual_cashflows)


def test_full_alm_scenario_runs_against_live_aal_service():
    result = run_full_alm_scenario()
    assert result.generation_mode == "aal"
    assert result.aal_asset_result.aal_available is True
    assert validate_cashflow_dataframe(result.combined_cashflows) is True
