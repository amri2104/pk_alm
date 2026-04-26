import math

import pandas as pd
import pytest

from pk_alm.analytics.funding import (
    FUNDING_RATIO_COLUMNS,
    build_funding_ratio_trajectory,
    calculate_funding_ratio,
    validate_funding_ratio_dataframe,
)
from pk_alm.assets.deterministic import ASSET_SNAPSHOT_COLUMNS
from pk_alm.bvg.valuation import VALUATION_COLUMNS


def _asset_df(closing_values, projection_years=None):
    if projection_years is None:
        projection_years = list(range(len(closing_values)))
    rows = []
    for projection_year, closing in zip(projection_years, closing_values):
        rows.append(
            {
                "projection_year": projection_year,
                "opening_asset_value": float(closing),
                "investment_return": 0.0,
                "net_cashflow": 0.0,
                "closing_asset_value": float(closing),
                "annual_return_rate": 0.0,
                "currency": "CHF",
            }
        )
    return pd.DataFrame(rows, columns=list(ASSET_SNAPSHOT_COLUMNS))


def _valuation_df(liabilities, projection_years=None):
    if projection_years is None:
        projection_years = list(range(len(liabilities)))
    rows = []
    for projection_year, liability in zip(projection_years, liabilities):
        rows.append(
            {
                "projection_year": projection_year,
                "active_count_total": 1,
                "retired_count_total": 0,
                "member_count_total": 1,
                "total_capital_active": float(liability),
                "total_capital_rente": 0.0,
                "retiree_obligation_pv": 0.0,
                "pensionierungsverlust": 0.0,
                "total_stage1_liability": float(liability),
                "technical_interest_rate": 0.0176,
                "valuation_terminal_age": 90,
                "currency": "CHF",
            }
        )
    return pd.DataFrame(rows, columns=list(VALUATION_COLUMNS))


def _funding_df():
    rows = [
        {
            "projection_year": 0,
            "asset_value": 1076.0,
            "total_stage1_liability": 1000.0,
            "funding_ratio": 1.076,
            "funding_ratio_percent": 107.6,
            "currency": "CHF",
        },
        {
            "projection_year": 1,
            "asset_value": 1100.0,
            "total_stage1_liability": 1000.0,
            "funding_ratio": 1.1,
            "funding_ratio_percent": 110.0,
            "currency": "CHF",
        },
    ]
    return pd.DataFrame(rows, columns=list(FUNDING_RATIO_COLUMNS))


# ---------------------------------------------------------------------------
# A. Calculate funding ratio
# ---------------------------------------------------------------------------


def test_calculate_funding_ratio_values():
    assert calculate_funding_ratio(1076.0, 1000.0) == pytest.approx(1.076)


def test_calculate_funding_ratio_rejects_invalid_asset_type():
    with pytest.raises(TypeError):
        calculate_funding_ratio("x", 1000.0)


def test_calculate_funding_ratio_rejects_invalid_liability_type():
    with pytest.raises(TypeError):
        calculate_funding_ratio(1000.0, "x")


@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_calculate_funding_ratio_rejects_non_positive_liability(bad):
    with pytest.raises(ValueError):
        calculate_funding_ratio(1000.0, bad)


@pytest.mark.parametrize("asset_value, liability", [(math.nan, 1000.0), (1.0, math.nan)])
def test_calculate_funding_ratio_rejects_nan(asset_value, liability):
    with pytest.raises(ValueError):
        calculate_funding_ratio(asset_value, liability)


# ---------------------------------------------------------------------------
# B. Build funding ratio trajectory
# ---------------------------------------------------------------------------


def test_build_funding_ratio_trajectory_values():
    df = build_funding_ratio_trajectory(
        _asset_df([1076.0, 1100.0]),
        _valuation_df([1000.0, 1000.0]),
    )

    assert list(df.columns) == list(FUNDING_RATIO_COLUMNS)
    assert list(df["funding_ratio"]) == pytest.approx([1.076, 1.1])
    assert list(df["funding_ratio_percent"]) == pytest.approx([107.6, 110.0])
    assert validate_funding_ratio_dataframe(df) is True


# ---------------------------------------------------------------------------
# C. Validate funding ratio DataFrame
# ---------------------------------------------------------------------------


def test_validate_funding_ratio_dataframe_valid_returns_true():
    assert validate_funding_ratio_dataframe(_funding_df()) is True


def test_validate_funding_ratio_dataframe_empty_returns_true():
    df = pd.DataFrame(columns=list(FUNDING_RATIO_COLUMNS))
    assert validate_funding_ratio_dataframe(df) is True


def test_validate_funding_ratio_dataframe_rejects_non_dataframe():
    with pytest.raises(TypeError):
        validate_funding_ratio_dataframe("not a df")


def test_validate_funding_ratio_dataframe_rejects_missing_column():
    df = _funding_df().drop(columns=["funding_ratio"])
    with pytest.raises(ValueError):
        validate_funding_ratio_dataframe(df)


def test_validate_funding_ratio_dataframe_rejects_wrong_column_order():
    df = _funding_df()
    with pytest.raises(ValueError):
        validate_funding_ratio_dataframe(df[list(reversed(FUNDING_RATIO_COLUMNS))])


def test_validate_funding_ratio_dataframe_rejects_missing_value():
    df = _funding_df()
    df.loc[0, "asset_value"] = pd.NA
    with pytest.raises(ValueError):
        validate_funding_ratio_dataframe(df)


def test_validate_funding_ratio_dataframe_rejects_invalid_liability():
    df = _funding_df()
    df.loc[0, "total_stage1_liability"] = 0.0
    with pytest.raises(ValueError):
        validate_funding_ratio_dataframe(df)


def test_validate_funding_ratio_dataframe_rejects_inconsistent_ratio():
    df = _funding_df()
    df.loc[0, "funding_ratio"] = 2.0
    with pytest.raises(ValueError):
        validate_funding_ratio_dataframe(df)


def test_validate_funding_ratio_dataframe_rejects_inconsistent_percent():
    df = _funding_df()
    df.loc[0, "funding_ratio_percent"] = 1.0
    with pytest.raises(ValueError):
        validate_funding_ratio_dataframe(df)


# ---------------------------------------------------------------------------
# D. Mismatch checks
# ---------------------------------------------------------------------------


def test_build_funding_ratio_trajectory_rejects_row_count_mismatch():
    with pytest.raises(ValueError):
        build_funding_ratio_trajectory(
            _asset_df([1076.0]),
            _valuation_df([1000.0, 1000.0]),
        )


def test_build_funding_ratio_trajectory_rejects_projection_year_mismatch():
    with pytest.raises(ValueError):
        build_funding_ratio_trajectory(
            _asset_df([1076.0, 1100.0], projection_years=[0, 2]),
            _valuation_df([1000.0, 1000.0], projection_years=[0, 1]),
        )


# ---------------------------------------------------------------------------
# E. Negative assets
# ---------------------------------------------------------------------------


def test_build_funding_ratio_trajectory_allows_negative_assets():
    df = build_funding_ratio_trajectory(
        _asset_df([-50.0]),
        _valuation_df([100.0]),
    )

    assert df.iloc[0]["asset_value"] == pytest.approx(-50.0)
    assert df.iloc[0]["funding_ratio"] == pytest.approx(-0.5)
    assert df.iloc[0]["funding_ratio_percent"] == pytest.approx(-50.0)


# ---------------------------------------------------------------------------
# F. Immutability
# ---------------------------------------------------------------------------


def test_build_funding_ratio_trajectory_does_not_mutate_inputs():
    assets = _asset_df([1076.0, 1100.0])
    valuation = _valuation_df([1000.0, 1000.0])
    assets_before = assets.copy(deep=True)
    valuation_before = valuation.copy(deep=True)

    build_funding_ratio_trajectory(assets, valuation)

    pd.testing.assert_frame_equal(assets, assets_before)
    pd.testing.assert_frame_equal(valuation, valuation_before)
