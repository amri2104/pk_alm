from pathlib import Path

import pandas as pd
import pytest
from pk_alm.alm_analytics_engine.cashflows import (
    find_liquidity_inflection_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.alm_analytics_engine.funding import (
    FUNDING_RATIO_COLUMNS,
    validate_funding_ratio_dataframe,
)
from pk_alm.alm_analytics_engine.funding_summary import (
    FUNDING_SUMMARY_COLUMNS,
    validate_funding_summary_dataframe,
)
from pk_alm.actus_asset_engine.deterministic import (
    ASSET_SNAPSHOT_COLUMNS,
    validate_asset_dataframe,
)
from pk_alm.bvg_liability_engine.orchestration.engine import BVGEngineResult
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.valuation import validate_valuation_dataframe
from pk_alm.cashflows.schema import validate_cashflow_dataframe
from pk_alm.scenarios.stage1_baseline import (
    Stage1BaselineResult,
    build_default_stage1_portfolio,
    run_stage1_baseline,
)
from pk_alm.scenarios.result_summary import (
    SCENARIO_RESULT_COLUMNS,
    validate_scenario_result_dataframe,
)

EXAMPLE_PATH = (
    Path(__file__).resolve().parent.parent / "examples" / "stage1_baseline.py"
)


# ---------------------------------------------------------------------------
# A. Default portfolio
# ---------------------------------------------------------------------------


def test_default_portfolio_shape():
    p = build_default_stage1_portfolio()
    assert p.projection_year == 0
    assert tuple(c.cohort_id for c in p.active_cohorts) == ("ACT_40", "ACT_55")
    assert tuple(c.cohort_id for c in p.retired_cohorts) == ("RET_70",)
    assert p.active_count_total == 13
    assert p.retired_count_total == 5
    assert p.member_count_total == 18


# ---------------------------------------------------------------------------
# B. Run without export
# ---------------------------------------------------------------------------


def test_run_without_export_returns_valid_result():
    result = run_stage1_baseline(output_dir=None)

    assert isinstance(result, Stage1BaselineResult)
    assert isinstance(result.initial_state, BVGPortfolioState)
    assert isinstance(result.engine_result, BVGEngineResult)
    assert result.output_paths == {}

    assert validate_cashflow_dataframe(result.engine_result.cashflows) is True
    assert validate_valuation_dataframe(result.valuation_snapshots) is True
    assert validate_annual_cashflow_dataframe(result.annual_cashflows) is True
    assert validate_asset_dataframe(result.asset_snapshots) is True
    assert validate_funding_ratio_dataframe(result.funding_ratio_trajectory) is True
    assert validate_funding_summary_dataframe(result.funding_summary) is True
    assert validate_scenario_result_dataframe(result.scenario_summary) is True

    assert len(result.engine_result.portfolio_states) == 13
    assert not result.engine_result.cashflows.empty
    assert len(result.valuation_snapshots) == 13
    assert len(result.annual_cashflows) == 12
    assert len(result.asset_snapshots) == 13
    assert len(result.funding_ratio_trajectory) == 13
    assert len(result.funding_summary) == 1
    assert len(result.scenario_summary) == 1
    assert result.funding_ratio_trajectory.iloc[0][
        "funding_ratio_percent"
    ] == pytest.approx(107.6)

    summary = result.funding_summary.iloc[0]
    trajectory = result.funding_ratio_trajectory
    assert summary["initial_funding_ratio_percent"] == pytest.approx(107.6)
    assert summary["final_funding_ratio_percent"] == pytest.approx(
        trajectory.iloc[-1]["funding_ratio_percent"]
    )
    assert summary["minimum_funding_ratio_percent"] == pytest.approx(
        trajectory["funding_ratio_percent"].min()
    )
    expected_below_100 = int(
        (trajectory["funding_ratio_percent"] < 100.0 - 1e-5).sum()
    )
    assert int(summary["years_below_100_percent"]) == expected_below_100

    scenario = result.scenario_summary.iloc[0]
    assert scenario["scenario_id"] == "stage1_baseline"
    assert scenario["initial_funding_ratio_percent"] == pytest.approx(107.6)
    assert scenario["final_funding_ratio_percent"] == pytest.approx(
        trajectory.iloc[-1]["funding_ratio_percent"]
    )
    assert scenario["minimum_funding_ratio_percent"] == pytest.approx(
        summary["minimum_funding_ratio_percent"]
    )
    assert int(scenario["years_below_100_percent"]) == expected_below_100


# ---------------------------------------------------------------------------
# C. Retirement transition occurs in default horizon
# ---------------------------------------------------------------------------


def test_default_horizon_retires_act_55():
    result = run_stage1_baseline(output_dir=None)
    final = result.engine_result.final_state

    final_active_ids = tuple(c.cohort_id for c in final.active_cohorts)
    final_retired_ids = tuple(c.cohort_id for c in final.retired_cohorts)

    assert "ACT_55" not in final_active_ids
    assert "RET_FROM_ACT_55" in final_retired_ids
    assert (result.engine_result.cashflows["type"] == "KA").any()


# ---------------------------------------------------------------------------
# D. Annual cashflow analytics consistency
# ---------------------------------------------------------------------------


def test_annual_cashflows_year_range_and_inflection_consistency():
    result = run_stage1_baseline(output_dir=None)
    years = list(result.annual_cashflows["reporting_year"])

    assert years == sorted(years)
    assert years[0] == 2026
    assert years[-1] == 2037

    assert result.liquidity_inflection_year_structural == find_liquidity_inflection_year(
        result.annual_cashflows, use_structural=True
    )
    assert result.liquidity_inflection_year_net == find_liquidity_inflection_year(
        result.annual_cashflows, use_structural=False
    )


# ---------------------------------------------------------------------------
# E. Run with export
# ---------------------------------------------------------------------------


def test_run_with_export(tmp_path):
    result = run_stage1_baseline(output_dir=tmp_path)

    assert set(result.output_paths.keys()) == {
        "cashflows",
        "valuation_snapshots",
        "annual_cashflows",
        "asset_snapshots",
        "funding_ratio_trajectory",
        "funding_summary",
        "scenario_summary",
    }

    for key, path in result.output_paths.items():
        assert path.exists()
        assert path.is_file()
        # File lives under tmp_path
        path.relative_to(tmp_path)

    re_cashflows = pd.read_csv(result.output_paths["cashflows"])
    re_valuation = pd.read_csv(result.output_paths["valuation_snapshots"])
    re_annual = pd.read_csv(result.output_paths["annual_cashflows"])
    re_assets = pd.read_csv(result.output_paths["asset_snapshots"])
    re_funding = pd.read_csv(result.output_paths["funding_ratio_trajectory"])
    re_funding_summary = pd.read_csv(result.output_paths["funding_summary"])
    re_scenario_summary = pd.read_csv(result.output_paths["scenario_summary"])

    assert not re_cashflows.empty
    assert not re_valuation.empty
    assert not re_annual.empty
    assert not re_assets.empty
    assert not re_funding.empty
    assert not re_funding_summary.empty
    assert not re_scenario_summary.empty

    assert list(re_cashflows.columns) == list(
        result.engine_result.cashflows.columns
    )
    assert list(re_valuation.columns) == list(result.valuation_snapshots.columns)
    assert list(re_annual.columns) == list(result.annual_cashflows.columns)
    assert list(re_assets.columns) == list(ASSET_SNAPSHOT_COLUMNS)
    assert list(re_funding.columns) == list(FUNDING_RATIO_COLUMNS)
    assert list(re_funding_summary.columns) == list(FUNDING_SUMMARY_COLUMNS)
    assert list(re_scenario_summary.columns) == list(SCENARIO_RESULT_COLUMNS)

    # CSV roundtrip: every exported file must re-validate after pd.read_csv,
    # including bool columns (which pandas writes as the strings 'True'/'False').
    assert validate_cashflow_dataframe(re_cashflows) is True
    assert validate_valuation_dataframe(re_valuation) is True
    assert validate_annual_cashflow_dataframe(re_annual) is True
    assert validate_asset_dataframe(re_assets) is True
    assert validate_funding_ratio_dataframe(re_funding) is True
    assert validate_funding_summary_dataframe(re_funding_summary) is True
    assert validate_scenario_result_dataframe(re_scenario_summary) is True


# ---------------------------------------------------------------------------
# F. Parameter pass-through smoke test
# ---------------------------------------------------------------------------


def test_parameter_pass_through_horizon_and_multiplier():
    result = run_stage1_baseline(
        scenario_id="custom",
        horizon_years=1,
        start_year=2030,
        contribution_multiplier=2.0,
        target_funding_ratio=1.2,
        annual_asset_return=0.03,
        output_dir=None,
    )
    assert len(result.engine_result.portfolio_states) == 2
    assert len(result.annual_cashflows) == 1
    assert len(result.asset_snapshots) == 2
    assert len(result.funding_ratio_trajectory) == 2
    assert result.scenario_summary.iloc[0]["scenario_id"] == "custom"
    assert int(result.annual_cashflows.iloc[0]["reporting_year"]) == 2030
    assert result.funding_ratio_trajectory.iloc[0][
        "funding_ratio_percent"
    ] == pytest.approx(120.0)

    expected_year_1_cashflow = float(
        result.annual_cashflows.loc[
            result.annual_cashflows["reporting_year"] == 2030,
            "net_cashflow",
        ].iloc[0]
    )
    assert result.asset_snapshots.iloc[1]["net_cashflow"] == pytest.approx(
        expected_year_1_cashflow
    )
    assert result.asset_snapshots.iloc[1]["investment_return"] == pytest.approx(
        result.asset_snapshots.iloc[1]["opening_asset_value"] * 0.03
    )

    df = result.engine_result.cashflows
    pr_rows = df[df["type"] == "PR"]
    assert not pr_rows.empty

    # PR payoff for ACT_40 in year 1 should equal annual_age_credit_total * 2.0
    initial = result.initial_state
    act_40 = next(c for c in initial.active_cohorts if c.cohort_id == "ACT_40")
    expected_pr_act_40 = act_40.annual_age_credit_total * 2.0
    actual_pr_act_40 = float(
        pr_rows[pr_rows["contractId"] == "ACT_40"]["payoff"].iloc[0]
    )
    assert actual_pr_act_40 == pytest.approx(expected_pr_act_40)


# ---------------------------------------------------------------------------
# G. Invalid Stage1BaselineResult construction
# ---------------------------------------------------------------------------


def _good_result_kwargs():
    """Build a self-consistent kwargs dict for direct construction."""
    res = run_stage1_baseline(horizon_years=0, output_dir=None)
    return dict(
        initial_state=res.initial_state,
        engine_result=res.engine_result,
        cashflows=res.cashflows,
        valuation_snapshots=res.valuation_snapshots,
        annual_cashflows=res.annual_cashflows,
        asset_snapshots=res.asset_snapshots,
        funding_ratio_trajectory=res.funding_ratio_trajectory,
        funding_summary=res.funding_summary,
        scenario_summary=res.scenario_summary,
        liquidity_inflection_year_structural=None,
        liquidity_inflection_year_net=None,
        output_paths={},
    )


def test_construct_with_wrong_initial_state_raises():
    kw = _good_result_kwargs()
    kw["initial_state"] = "not a portfolio"
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_wrong_engine_result_raises():
    kw = _good_result_kwargs()
    kw["engine_result"] = "not an engine result"
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_invalid_valuation_snapshots_raises():
    kw = _good_result_kwargs()
    kw["valuation_snapshots"] = pd.DataFrame({"foo": [1]})
    with pytest.raises(ValueError):
        Stage1BaselineResult(**kw)


def test_construct_with_non_dataframe_valuation_raises():
    kw = _good_result_kwargs()
    kw["valuation_snapshots"] = "not a df"
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_invalid_annual_cashflows_raises():
    kw = _good_result_kwargs()
    kw["annual_cashflows"] = pd.DataFrame({"foo": [1]})
    with pytest.raises(ValueError):
        Stage1BaselineResult(**kw)


def test_construct_with_non_dataframe_annual_raises():
    kw = _good_result_kwargs()
    kw["annual_cashflows"] = "not a df"
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_invalid_asset_snapshots_raises():
    kw = _good_result_kwargs()
    kw["asset_snapshots"] = pd.DataFrame({"foo": [1]})
    with pytest.raises(ValueError):
        Stage1BaselineResult(**kw)


def test_construct_with_non_dataframe_asset_snapshots_raises():
    kw = _good_result_kwargs()
    kw["asset_snapshots"] = "not a df"
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_invalid_funding_ratio_trajectory_raises():
    kw = _good_result_kwargs()
    kw["funding_ratio_trajectory"] = pd.DataFrame({"foo": [1]})
    with pytest.raises(ValueError):
        Stage1BaselineResult(**kw)


def test_construct_with_non_dataframe_funding_ratio_trajectory_raises():
    kw = _good_result_kwargs()
    kw["funding_ratio_trajectory"] = "not a df"
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_invalid_funding_summary_raises():
    kw = _good_result_kwargs()
    kw["funding_summary"] = pd.DataFrame({"foo": [1]})
    with pytest.raises(ValueError):
        Stage1BaselineResult(**kw)


def test_construct_with_non_dataframe_funding_summary_raises():
    kw = _good_result_kwargs()
    kw["funding_summary"] = "not a df"
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_invalid_scenario_summary_raises():
    kw = _good_result_kwargs()
    kw["scenario_summary"] = pd.DataFrame({"foo": [1]})
    with pytest.raises(ValueError):
        Stage1BaselineResult(**kw)


def test_construct_with_non_dataframe_scenario_summary_raises():
    kw = _good_result_kwargs()
    kw["scenario_summary"] = "not a df"
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


@pytest.mark.parametrize("bad", ["x", 1.5, [1]])
def test_construct_with_bad_inflection_year_struct_raises(bad):
    kw = _good_result_kwargs()
    kw["liquidity_inflection_year_structural"] = bad
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_bool_inflection_year_struct_raises():
    kw = _good_result_kwargs()
    kw["liquidity_inflection_year_structural"] = True
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_bool_inflection_year_net_raises():
    kw = _good_result_kwargs()
    kw["liquidity_inflection_year_net"] = False
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


@pytest.mark.parametrize("bad", ["x", 1.5, [1]])
def test_construct_with_bad_inflection_year_net_raises(bad):
    kw = _good_result_kwargs()
    kw["liquidity_inflection_year_net"] = bad
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_non_dict_output_paths_raises():
    kw = _good_result_kwargs()
    kw["output_paths"] = ["not a dict"]
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


def test_construct_with_non_string_key_in_output_paths_raises(tmp_path):
    kw = _good_result_kwargs()
    kw["output_paths"] = {1: tmp_path / "x.csv"}
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


@pytest.mark.parametrize("bad_key", ["", "   "])
def test_construct_with_empty_key_in_output_paths_raises(tmp_path, bad_key):
    kw = _good_result_kwargs()
    kw["output_paths"] = {bad_key: tmp_path / "x.csv"}
    with pytest.raises(ValueError):
        Stage1BaselineResult(**kw)


def test_construct_with_non_path_value_in_output_paths_raises():
    kw = _good_result_kwargs()
    kw["output_paths"] = {"cashflows": "not a Path"}
    with pytest.raises(TypeError):
        Stage1BaselineResult(**kw)


# ---------------------------------------------------------------------------
# H. Example script exists and is import-safe
# ---------------------------------------------------------------------------


def test_example_script_exists_and_is_main_guarded():
    assert EXAMPLE_PATH.exists()
    text = EXAMPLE_PATH.read_text()
    assert 'if __name__ == "__main__":' in text


def test_example_script_does_not_run_on_import_via_text_inspection(tmp_path):
    # We never execute the example as __main__. Reading the source should
    # never produce side-effect files in cwd. Verify outputs/stage1_baseline
    # was not created merely by reading the file.
    text = EXAMPLE_PATH.read_text()
    assert "run_stage1_baseline" in text
    # No file should be written to tmp_path just from reading the source.
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# I. Custom short horizon
# ---------------------------------------------------------------------------


def test_horizon_zero_minimal_run():
    result = run_stage1_baseline(horizon_years=0, output_dir=None)
    assert len(result.engine_result.portfolio_states) == 1
    assert result.engine_result.cashflows.empty
    assert len(result.valuation_snapshots) == 1
    assert result.annual_cashflows.empty
    assert len(result.asset_snapshots) == 1
    assert len(result.funding_ratio_trajectory) == 1
    assert len(result.funding_summary) == 1
    assert len(result.scenario_summary) == 1
    assert result.funding_ratio_trajectory.iloc[0][
        "funding_ratio_percent"
    ] == pytest.approx(107.6)
    summary = result.funding_summary.iloc[0]
    assert summary["initial_funding_ratio_percent"] == pytest.approx(107.6)
    assert summary["final_funding_ratio_percent"] == pytest.approx(107.6)
    assert summary["minimum_funding_ratio_percent"] == pytest.approx(107.6)
    assert summary["maximum_funding_ratio_percent"] == pytest.approx(107.6)
    assert int(summary["years_below_100_percent"]) == 0
    scenario = result.scenario_summary.iloc[0]
    assert int(scenario["horizon_years"]) == 0
    assert int(scenario["start_year"]) == 0
    assert int(scenario["end_year"]) == 0
    assert result.liquidity_inflection_year_structural is None
    assert result.liquidity_inflection_year_net is None
