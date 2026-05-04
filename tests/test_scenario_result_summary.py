import math

import pandas as pd
import pytest

from pk_alm.alm_analytics_engine.cashflows import ANNUAL_CASHFLOW_COLUMNS
from pk_alm.scenarios.result_summary import (
    SCENARIO_RESULT_COLUMNS,
    ScenarioResultSummary,
    build_scenario_result_summary,
    scenario_result_summary_to_dataframe,
    validate_scenario_result_dataframe,
)
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline


def _build_summary_from_result(result, scenario_id="baseline"):
    return build_scenario_result_summary(
        scenario_id=scenario_id,
        valuation_snapshots=result.valuation_snapshots,
        annual_cashflows=result.annual_cashflows,
        asset_snapshots=result.asset_snapshots,
        funding_ratio_trajectory=result.funding_ratio_trajectory,
        funding_summary=result.funding_summary,
        liquidity_inflection_year_structural=(
            result.liquidity_inflection_year_structural
        ),
        liquidity_inflection_year_net=result.liquidity_inflection_year_net,
    )


def _standard_summary(**overrides):
    result = run_stage1_baseline(output_dir=None)
    summary = _build_summary_from_result(result)
    kwargs = summary.to_dict()
    kwargs.update(overrides)
    return ScenarioResultSummary(**kwargs)


# ---------------------------------------------------------------------------
# A. Standard summary build
# ---------------------------------------------------------------------------


def test_build_scenario_result_summary_standard_values():
    result = run_stage1_baseline(output_dir=None)
    summary = _build_summary_from_result(result, scenario_id="baseline")

    assert summary.scenario_id == "baseline"
    assert summary.horizon_years == 12
    assert summary.start_year == 2026
    assert summary.end_year == 2037
    assert summary.initial_funding_ratio_percent == pytest.approx(107.6)
    assert summary.final_funding_ratio_percent == pytest.approx(
        result.funding_ratio_trajectory.iloc[-1]["funding_ratio_percent"]
    )
    assert summary.minimum_funding_ratio_percent == pytest.approx(
        result.funding_summary.iloc[0]["minimum_funding_ratio_percent"]
    )
    assert summary.years_below_100_percent == int(
        result.funding_summary.iloc[0]["years_below_100_percent"]
    )
    assert (
        summary.liquidity_inflection_year_structural
        == result.liquidity_inflection_year_structural
    )
    assert summary.liquidity_inflection_year_net == result.liquidity_inflection_year_net


# ---------------------------------------------------------------------------
# B. DataFrame conversion
# ---------------------------------------------------------------------------


def test_scenario_result_summary_to_dataframe_single_summary():
    df = scenario_result_summary_to_dataframe(_standard_summary())

    assert df.shape == (1, len(SCENARIO_RESULT_COLUMNS))
    assert list(df.columns) == list(SCENARIO_RESULT_COLUMNS)
    assert validate_scenario_result_dataframe(df) is True


def test_scenario_result_summary_to_dataframe_list_of_two():
    df = scenario_result_summary_to_dataframe(
        [
            _standard_summary(scenario_id="baseline"),
            _standard_summary(scenario_id="custom"),
        ]
    )

    assert df.shape == (2, len(SCENARIO_RESULT_COLUMNS))
    assert list(df["scenario_id"]) == ["baseline", "custom"]


def test_scenario_result_summary_to_dataframe_empty_list():
    df = scenario_result_summary_to_dataframe([])

    assert df.empty
    assert list(df.columns) == list(SCENARIO_RESULT_COLUMNS)
    assert validate_scenario_result_dataframe(df) is True


@pytest.mark.parametrize("bad", [None, "x", {"summary": 1}])
def test_scenario_result_summary_to_dataframe_rejects_wrong_input_type(bad):
    with pytest.raises(TypeError):
        scenario_result_summary_to_dataframe(bad)


def test_scenario_result_summary_to_dataframe_rejects_wrong_item_type():
    with pytest.raises(TypeError):
        scenario_result_summary_to_dataframe([object()])


# ---------------------------------------------------------------------------
# C. Validation
# ---------------------------------------------------------------------------


def test_validate_scenario_result_dataframe_valid_returns_true():
    df = scenario_result_summary_to_dataframe(_standard_summary())
    assert validate_scenario_result_dataframe(df) is True


def test_validate_scenario_result_dataframe_empty_returns_true():
    df = pd.DataFrame(columns=list(SCENARIO_RESULT_COLUMNS))
    assert validate_scenario_result_dataframe(df) is True


def test_validate_scenario_result_dataframe_rejects_non_dataframe():
    with pytest.raises(TypeError):
        validate_scenario_result_dataframe("not a df")


def test_validate_scenario_result_dataframe_rejects_missing_column():
    df = scenario_result_summary_to_dataframe(_standard_summary()).drop(
        columns=["final_asset_value"]
    )
    with pytest.raises(ValueError):
        validate_scenario_result_dataframe(df)


def test_validate_scenario_result_dataframe_rejects_wrong_column_order():
    df = scenario_result_summary_to_dataframe(_standard_summary())
    with pytest.raises(ValueError):
        validate_scenario_result_dataframe(df[list(reversed(SCENARIO_RESULT_COLUMNS))])


def test_validate_scenario_result_dataframe_rejects_invalid_row_values():
    df = scenario_result_summary_to_dataframe(_standard_summary())
    df.loc[0, "initial_total_stage1_liability"] = 0.0
    with pytest.raises(ValueError):
        validate_scenario_result_dataframe(df)


def test_validate_scenario_result_dataframe_allows_none_inflection_fields():
    df = scenario_result_summary_to_dataframe(
        _standard_summary(
            liquidity_inflection_year_structural=None,
            liquidity_inflection_year_net=None,
        )
    )
    assert validate_scenario_result_dataframe(df) is True


def test_validate_scenario_result_dataframe_normalizes_nan_inflection_fields():
    df = scenario_result_summary_to_dataframe(_standard_summary())
    df.loc[0, "liquidity_inflection_year_structural"] = math.nan
    df.loc[0, "liquidity_inflection_year_net"] = pd.NA

    assert validate_scenario_result_dataframe(df) is True


def test_validate_scenario_result_dataframe_rejects_missing_required_value():
    df = scenario_result_summary_to_dataframe(_standard_summary())
    df.loc[0, "scenario_id"] = pd.NA
    with pytest.raises(ValueError):
        validate_scenario_result_dataframe(df)


# ---------------------------------------------------------------------------
# D. Horizon zero
# ---------------------------------------------------------------------------


def test_build_scenario_result_summary_horizon_zero():
    result = run_stage1_baseline(horizon_years=0, output_dir=None)
    summary = _build_summary_from_result(result)

    assert summary.horizon_years == 0
    assert summary.start_year == 0
    assert summary.end_year == 0
    assert summary.liquidity_inflection_year_structural is None
    assert summary.liquidity_inflection_year_net is None


# ---------------------------------------------------------------------------
# E. Invalid inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_build_scenario_result_summary_rejects_bad_scenario_id(bad):
    result = run_stage1_baseline(output_dir=None)
    with pytest.raises(ValueError):
        _build_summary_from_result(result, scenario_id=bad)


def test_build_scenario_result_summary_rejects_wrong_dataframe_type():
    result = run_stage1_baseline(output_dir=None)
    with pytest.raises(TypeError):
        build_scenario_result_summary(
            scenario_id="baseline",
            valuation_snapshots="not a df",
            annual_cashflows=result.annual_cashflows,
            asset_snapshots=result.asset_snapshots,
            funding_ratio_trajectory=result.funding_ratio_trajectory,
            funding_summary=result.funding_summary,
            liquidity_inflection_year_structural=(
                result.liquidity_inflection_year_structural
            ),
            liquidity_inflection_year_net=result.liquidity_inflection_year_net,
        )


def test_build_scenario_result_summary_rejects_empty_required_dataframe():
    result = run_stage1_baseline(output_dir=None)
    with pytest.raises(ValueError):
        build_scenario_result_summary(
            scenario_id="baseline",
            valuation_snapshots=result.valuation_snapshots.iloc[0:0],
            annual_cashflows=result.annual_cashflows,
            asset_snapshots=result.asset_snapshots,
            funding_ratio_trajectory=result.funding_ratio_trajectory,
            funding_summary=result.funding_summary,
            liquidity_inflection_year_structural=(
                result.liquidity_inflection_year_structural
            ),
            liquidity_inflection_year_net=result.liquidity_inflection_year_net,
        )


def test_build_scenario_result_summary_rejects_multirow_funding_summary():
    result = run_stage1_baseline(output_dir=None)
    funding_summary = pd.concat(
        [result.funding_summary, result.funding_summary],
        ignore_index=True,
    )

    with pytest.raises(ValueError):
        build_scenario_result_summary(
            scenario_id="baseline",
            valuation_snapshots=result.valuation_snapshots,
            annual_cashflows=result.annual_cashflows,
            asset_snapshots=result.asset_snapshots,
            funding_ratio_trajectory=result.funding_ratio_trajectory,
            funding_summary=funding_summary,
            liquidity_inflection_year_structural=(
                result.liquidity_inflection_year_structural
            ),
            liquidity_inflection_year_net=result.liquidity_inflection_year_net,
        )


def test_build_scenario_result_summary_rejects_bool_inflection_year():
    result = run_stage1_baseline(output_dir=None)
    with pytest.raises(TypeError):
        build_scenario_result_summary(
            scenario_id="baseline",
            valuation_snapshots=result.valuation_snapshots,
            annual_cashflows=result.annual_cashflows,
            asset_snapshots=result.asset_snapshots,
            funding_ratio_trajectory=result.funding_ratio_trajectory,
            funding_summary=result.funding_summary,
            liquidity_inflection_year_structural=True,
            liquidity_inflection_year_net=result.liquidity_inflection_year_net,
        )


def test_build_scenario_result_summary_rejects_empty_annual_for_positive_horizon():
    result = run_stage1_baseline(output_dir=None)
    empty_annual = pd.DataFrame(columns=list(ANNUAL_CASHFLOW_COLUMNS))

    with pytest.raises(ValueError):
        build_scenario_result_summary(
            scenario_id="baseline",
            valuation_snapshots=result.valuation_snapshots,
            annual_cashflows=empty_annual,
            asset_snapshots=result.asset_snapshots,
            funding_ratio_trajectory=result.funding_ratio_trajectory,
            funding_summary=result.funding_summary,
            liquidity_inflection_year_structural=(
                result.liquidity_inflection_year_structural
            ),
            liquidity_inflection_year_net=result.liquidity_inflection_year_net,
        )


def test_build_scenario_result_summary_rejects_annual_row_count_mismatch():
    result = run_stage1_baseline(output_dir=None)
    with pytest.raises(ValueError):
        build_scenario_result_summary(
            scenario_id="baseline",
            valuation_snapshots=result.valuation_snapshots,
            annual_cashflows=result.annual_cashflows.iloc[:-1],
            asset_snapshots=result.asset_snapshots,
            funding_ratio_trajectory=result.funding_ratio_trajectory,
            funding_summary=result.funding_summary,
            liquidity_inflection_year_structural=(
                result.liquidity_inflection_year_structural
            ),
            liquidity_inflection_year_net=result.liquidity_inflection_year_net,
        )


def test_build_scenario_result_summary_rejects_duplicate_reporting_years():
    result = run_stage1_baseline(horizon_years=2, output_dir=None)
    annual = result.annual_cashflows.copy(deep=True)
    annual.loc[1, "reporting_year"] = annual.loc[0, "reporting_year"]

    with pytest.raises(ValueError):
        build_scenario_result_summary(
            scenario_id="baseline",
            valuation_snapshots=result.valuation_snapshots,
            annual_cashflows=annual,
            asset_snapshots=result.asset_snapshots,
            funding_ratio_trajectory=result.funding_ratio_trajectory,
            funding_summary=result.funding_summary,
            liquidity_inflection_year_structural=(
                result.liquidity_inflection_year_structural
            ),
            liquidity_inflection_year_net=result.liquidity_inflection_year_net,
        )


def test_build_scenario_result_summary_rejects_unsorted_reporting_years():
    result = run_stage1_baseline(horizon_years=2, output_dir=None)
    annual = result.annual_cashflows.copy(deep=True).iloc[[1, 0]].reset_index(
        drop=True
    )

    with pytest.raises(ValueError):
        build_scenario_result_summary(
            scenario_id="baseline",
            valuation_snapshots=result.valuation_snapshots,
            annual_cashflows=annual,
            asset_snapshots=result.asset_snapshots,
            funding_ratio_trajectory=result.funding_ratio_trajectory,
            funding_summary=result.funding_summary,
            liquidity_inflection_year_structural=(
                result.liquidity_inflection_year_structural
            ),
            liquidity_inflection_year_net=result.liquidity_inflection_year_net,
        )


def test_build_scenario_result_summary_rejects_non_contiguous_reporting_years():
    result = run_stage1_baseline(horizon_years=2, output_dir=None)
    annual = result.annual_cashflows.copy(deep=True)
    annual.loc[1, "reporting_year"] = int(annual.loc[0, "reporting_year"]) + 2

    with pytest.raises(ValueError):
        build_scenario_result_summary(
            scenario_id="baseline",
            valuation_snapshots=result.valuation_snapshots,
            annual_cashflows=annual,
            asset_snapshots=result.asset_snapshots,
            funding_ratio_trajectory=result.funding_ratio_trajectory,
            funding_summary=result.funding_summary,
            liquidity_inflection_year_structural=(
                result.liquidity_inflection_year_structural
            ),
            liquidity_inflection_year_net=result.liquidity_inflection_year_net,
        )


# ---------------------------------------------------------------------------
# F. Immutability
# ---------------------------------------------------------------------------


def test_build_scenario_result_summary_does_not_mutate_inputs():
    result = run_stage1_baseline(output_dir=None)
    valuation_before = result.valuation_snapshots.copy(deep=True)
    annual_before = result.annual_cashflows.copy(deep=True)
    assets_before = result.asset_snapshots.copy(deep=True)
    trajectory_before = result.funding_ratio_trajectory.copy(deep=True)
    funding_summary_before = result.funding_summary.copy(deep=True)

    _build_summary_from_result(result)

    pd.testing.assert_frame_equal(result.valuation_snapshots, valuation_before)
    pd.testing.assert_frame_equal(result.annual_cashflows, annual_before)
    pd.testing.assert_frame_equal(result.asset_snapshots, assets_before)
    pd.testing.assert_frame_equal(
        result.funding_ratio_trajectory, trajectory_before
    )
    pd.testing.assert_frame_equal(result.funding_summary, funding_summary_before)
