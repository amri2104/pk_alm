import math

import pandas as pd
import pytest

from pk_alm.adapters.actus_fixtures import (
    build_fixed_rate_bond_cashflow_dataframe,
)
from pk_alm.analytics.cashflows import (
    summarize_cashflows_by_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe
from pk_alm.scenarios.asset_overlay import (
    AssetOverlayResult,
    run_stage1_baseline_with_bond_overlay,
)
from pk_alm.scenarios.stage1_baseline import (
    Stage1BaselineResult,
    run_stage1_baseline,
)


def _annual_net_by_year(df: pd.DataFrame) -> dict[int, float]:
    return {
        int(row["reporting_year"]): float(row["net_cashflow"])
        for _, row in df.iterrows()
    }


def _annual_other_by_year(df: pd.DataFrame) -> dict[int, float]:
    return {
        int(row["reporting_year"]): float(row["other_cashflow"])
        for _, row in df.iterrows()
    }


def _good_result() -> AssetOverlayResult:
    return run_stage1_baseline_with_bond_overlay(horizon_years=1)


def _good_kwargs() -> dict:
    result = _good_result()
    return {
        "baseline_result": result.baseline_result,
        "asset_cashflows": result.asset_cashflows,
        "combined_cashflows": result.combined_cashflows,
        "combined_annual_cashflows": result.combined_annual_cashflows,
        "combined_liquidity_inflection_year_structural": (
            result.combined_liquidity_inflection_year_structural
        ),
        "combined_liquidity_inflection_year_net": (
            result.combined_liquidity_inflection_year_net
        ),
    }


# ---------------------------------------------------------------------------
# A. Standard overlay result shape
# ---------------------------------------------------------------------------


def test_standard_overlay_result_shape_and_validation():
    result = run_stage1_baseline_with_bond_overlay()

    assert isinstance(result, AssetOverlayResult)
    assert isinstance(result.baseline_result, Stage1BaselineResult)
    assert validate_cashflow_dataframe(result.asset_cashflows) is True
    assert validate_cashflow_dataframe(result.combined_cashflows) is True
    assert validate_annual_cashflow_dataframe(result.combined_annual_cashflows) is True
    assert (result.asset_cashflows["source"] == "ACTUS").all()


# ---------------------------------------------------------------------------
# B. Combined row count
# ---------------------------------------------------------------------------


def test_combined_row_count_equals_baseline_plus_asset_rows():
    result = run_stage1_baseline_with_bond_overlay()

    assert len(result.combined_cashflows) == (
        len(result.baseline_result.engine_result.cashflows)
        + len(result.asset_cashflows)
    )


# ---------------------------------------------------------------------------
# C. ACTUS events remain in other_cashflow
# ---------------------------------------------------------------------------


def test_actus_events_remain_in_other_cashflow():
    result = run_stage1_baseline_with_bond_overlay(
        bond_start_year=2026,
        bond_maturity_year=2028,
        bond_nominal_value=100000.0,
        bond_annual_coupon_rate=0.02,
    )

    baseline_other = _annual_other_by_year(result.baseline_result.annual_cashflows)
    combined_other = _annual_other_by_year(result.combined_annual_cashflows)

    assert combined_other[2027] - baseline_other.get(2027, 0.0) == pytest.approx(
        2000.0
    )
    assert combined_other[2028] - baseline_other.get(2028, 0.0) == pytest.approx(
        102000.0
    )


# ---------------------------------------------------------------------------
# D. Combined net cashflow equals BVG plus ACTUS
# ---------------------------------------------------------------------------


def test_combined_net_cashflow_equals_bvg_plus_actus_by_year():
    result = run_stage1_baseline_with_bond_overlay(
        bond_start_year=2026,
        bond_maturity_year=2028,
        bond_nominal_value=100000.0,
        bond_annual_coupon_rate=0.02,
    )

    baseline_by_year = _annual_net_by_year(result.baseline_result.annual_cashflows)
    actus_annual = summarize_cashflows_by_year(result.asset_cashflows)
    actus_by_year = _annual_net_by_year(actus_annual)
    combined_by_year = _annual_net_by_year(result.combined_annual_cashflows)

    for year, actus_net in actus_by_year.items():
        expected = baseline_by_year.get(year, 0.0) + actus_net
        assert combined_by_year[year] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# E. Purchase event option
# ---------------------------------------------------------------------------


def test_purchase_event_option_adds_negative_start_year_other_cashflow():
    result = run_stage1_baseline_with_bond_overlay(
        start_year=2026,
        include_purchase_event=True,
        bond_nominal_value=100000.0,
    )

    ied = result.asset_cashflows[result.asset_cashflows["type"] == "IED"]
    assert len(ied) == 1
    assert ied.iloc[0]["payoff"] == pytest.approx(-100000.0)
    assert ied.iloc[0]["time"] == pd.Timestamp("2026-01-01")

    baseline_other = _annual_other_by_year(result.baseline_result.annual_cashflows)
    combined_other = _annual_other_by_year(result.combined_annual_cashflows)
    assert combined_other[2026] - baseline_other.get(2026, 0.0) == pytest.approx(
        -100000.0
    )


# ---------------------------------------------------------------------------
# F. Horizon zero behavior
# ---------------------------------------------------------------------------


def test_horizon_zero_overlay_keeps_valid_asset_cashflows():
    result = run_stage1_baseline_with_bond_overlay(horizon_years=0)

    assert result.baseline_result.engine_result.cashflows.empty
    assert not result.asset_cashflows.empty
    assert validate_cashflow_dataframe(result.combined_cashflows) is True
    assert validate_annual_cashflow_dataframe(result.combined_annual_cashflows) is True


# ---------------------------------------------------------------------------
# G. Custom bond parameters
# ---------------------------------------------------------------------------


def test_custom_bond_parameters():
    result = run_stage1_baseline_with_bond_overlay(
        horizon_years=1,
        bond_contract_id="BOND_CUSTOM",
        bond_nominal_value=250000.0,
        bond_annual_coupon_rate=0.03,
        bond_start_year=2030,
        bond_maturity_year=2032,
        bond_currency="CHF",
    )

    assert set(result.asset_cashflows["contractId"]) == {"BOND_CUSTOM"}

    coupon_rows = result.asset_cashflows[result.asset_cashflows["type"] == "IP"]
    assert list(coupon_rows["payoff"]) == pytest.approx([7500.0, 7500.0])

    actus_annual = summarize_cashflows_by_year(result.asset_cashflows)
    row_2032 = actus_annual[actus_annual["reporting_year"] == 2032].iloc[0]
    assert row_2032["net_cashflow"] == pytest.approx(257500.0)


# ---------------------------------------------------------------------------
# H. Mixed-currency overlay rejected
# ---------------------------------------------------------------------------


def test_mixed_currency_overlay_rejected_by_annual_analytics():
    with pytest.raises(ValueError, match="one currency"):
        run_stage1_baseline_with_bond_overlay(bond_currency="EUR")


# ---------------------------------------------------------------------------
# I. Combined cashflows are sorted chronologically
# ---------------------------------------------------------------------------


def test_combined_cashflows_are_sorted_chronologically():
    result = run_stage1_baseline_with_bond_overlay(
        start_year=2026,
        include_purchase_event=True,
    )

    assert result.combined_cashflows["time"].is_monotonic_increasing
    assert result.combined_cashflows.iloc[0]["time"] == pd.Timestamp("2026-01-01")
    assert result.combined_cashflows.iloc[0]["type"] == "IED"


# ---------------------------------------------------------------------------
# J. Immutability / no mutation
# ---------------------------------------------------------------------------


def test_overlay_does_not_mutate_independent_baseline_result():
    baseline = run_stage1_baseline(output_dir=None)
    baseline_cashflows = baseline.engine_result.cashflows.copy(deep=True)
    baseline_annual = baseline.annual_cashflows.copy(deep=True)
    baseline_funding = baseline.funding_ratio_trajectory.copy(deep=True)

    result = run_stage1_baseline_with_bond_overlay()

    pd.testing.assert_frame_equal(
        baseline.engine_result.cashflows,
        baseline_cashflows,
    )
    pd.testing.assert_frame_equal(baseline.annual_cashflows, baseline_annual)
    pd.testing.assert_frame_equal(
        baseline.funding_ratio_trajectory,
        baseline_funding,
    )
    assert result.combined_cashflows is not result.baseline_result.engine_result.cashflows


# ---------------------------------------------------------------------------
# K. Invalid result dataclass construction
# ---------------------------------------------------------------------------


def test_result_rejects_wrong_baseline_result_type():
    kw = _good_kwargs()
    kw["baseline_result"] = "not a baseline"
    with pytest.raises(TypeError):
        AssetOverlayResult(**kw)


def test_result_rejects_non_dataframe_asset_cashflows():
    kw = _good_kwargs()
    kw["asset_cashflows"] = "not a dataframe"
    with pytest.raises(TypeError):
        AssetOverlayResult(**kw)


def test_result_rejects_non_dataframe_combined_cashflows():
    kw = _good_kwargs()
    kw["combined_cashflows"] = "not a dataframe"
    with pytest.raises(TypeError):
        AssetOverlayResult(**kw)


def test_result_rejects_non_dataframe_combined_annual_cashflows():
    kw = _good_kwargs()
    kw["combined_annual_cashflows"] = "not a dataframe"
    with pytest.raises(TypeError):
        AssetOverlayResult(**kw)


def test_result_rejects_non_actus_asset_cashflows():
    kw = _good_kwargs()
    bad_asset = kw["asset_cashflows"].copy(deep=True)
    bad_asset.loc[0, "source"] = "MANUAL"
    kw["asset_cashflows"] = bad_asset
    with pytest.raises(ValueError, match="ACTUS"):
        AssetOverlayResult(**kw)


def test_result_rejects_combined_row_count_mismatch():
    kw = _good_kwargs()
    kw["combined_cashflows"] = kw["combined_cashflows"].iloc[:-1].copy(deep=True)
    with pytest.raises(ValueError, match="exactly"):
        AssetOverlayResult(**kw)


def test_result_rejects_bool_structural_inflection_year():
    kw = _good_kwargs()
    kw["combined_liquidity_inflection_year_structural"] = True
    with pytest.raises(TypeError):
        AssetOverlayResult(**kw)


def test_result_rejects_bool_net_inflection_year():
    kw = _good_kwargs()
    kw["combined_liquidity_inflection_year_net"] = False
    with pytest.raises(TypeError):
        AssetOverlayResult(**kw)


# ---------------------------------------------------------------------------
# L. Invalid bond parameters propagate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bond_contract_id": ""},
        {"bond_start_year": True, "bond_maturity_year": 2028},
        {"bond_start_year": 2026, "bond_maturity_year": 2026},
        {"bond_nominal_value": 0.0},
        {"bond_nominal_value": math.nan},
        {"bond_annual_coupon_rate": -0.01},
        {"include_purchase_event": "yes"},
    ],
)
def test_invalid_bond_parameters_propagate(kwargs):
    with pytest.raises((TypeError, ValueError)):
        run_stage1_baseline_with_bond_overlay(**kwargs)


def test_output_dir_is_not_accepted():
    with pytest.raises(TypeError):
        run_stage1_baseline_with_bond_overlay(output_dir=None)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# M. Default Stage-1 baseline unchanged
# ---------------------------------------------------------------------------


def test_default_stage1_baseline_unchanged_before_and_after_overlay():
    before = run_stage1_baseline(output_dir=None)
    run_stage1_baseline_with_bond_overlay()
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
