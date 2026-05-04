import math

import pandas as pd
import pytest

from pk_alm.alm_analytics_engine.cashflows import ANNUAL_CASHFLOW_COLUMNS
from pk_alm.actus_asset_engine.deterministic import (
    ASSET_SNAPSHOT_COLUMNS,
    DeterministicAssetSnapshot,
    asset_snapshots_to_dataframe,
    build_deterministic_asset_trajectory,
    calibrate_initial_assets,
    project_assets_one_year,
    validate_asset_dataframe,
)
from pk_alm.bvg_liability_engine.pension_logic.valuation import VALUATION_COLUMNS


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


def _annual_df(years_and_net):
    rows = []
    cumulative_net = 0.0
    cumulative_structural = 0.0
    for year, net in years_and_net:
        net = float(net)
        cumulative_net += net
        cumulative_structural += net
        rows.append(
            {
                "reporting_year": year,
                "contribution_cashflow": net,
                "pension_payment_cashflow": 0.0,
                "capital_withdrawal_cashflow": 0.0,
                "other_cashflow": 0.0,
                "net_cashflow": net,
                "structural_net_cashflow": net,
                "cumulative_net_cashflow": cumulative_net,
                "cumulative_structural_net_cashflow": cumulative_structural,
                "currency": "CHF",
            }
        )
    return pd.DataFrame(rows, columns=list(ANNUAL_CASHFLOW_COLUMNS))


def _valid_snapshot(**overrides):
    kwargs = dict(
        projection_year=0,
        opening_asset_value=1000.0,
        investment_return=0.0,
        net_cashflow=0.0,
        closing_asset_value=1000.0,
        annual_return_rate=0.0,
        currency="CHF",
    )
    kwargs.update(overrides)
    return DeterministicAssetSnapshot(**kwargs)


def _valid_asset_df():
    return asset_snapshots_to_dataframe(
        [
            _valid_snapshot(),
            _valid_snapshot(
                projection_year=1,
                opening_asset_value=1000.0,
                investment_return=20.0,
                net_cashflow=-50.0,
                closing_asset_value=970.0,
                annual_return_rate=0.02,
            ),
        ]
    )


# ---------------------------------------------------------------------------
# A. Calibrate initial assets
# ---------------------------------------------------------------------------


def test_calibrate_initial_assets_uses_decimal_funding_ratio():
    assert calibrate_initial_assets(1000.0, 1.076) == pytest.approx(1076.0)


@pytest.mark.parametrize("bad", [True, None, "x", math.nan, 0.0, -1.0])
def test_calibrate_initial_assets_invalid_liability_raises(bad):
    with pytest.raises((TypeError, ValueError)):
        calibrate_initial_assets(bad, 1.076)


@pytest.mark.parametrize("bad", [False, None, "x", math.nan, 0.0, -1.0])
def test_calibrate_initial_assets_invalid_target_ratio_raises(bad):
    with pytest.raises((TypeError, ValueError)):
        calibrate_initial_assets(1000.0, bad)


# ---------------------------------------------------------------------------
# B. Project assets one year
# ---------------------------------------------------------------------------


def test_project_assets_one_year_values():
    snapshot = project_assets_one_year(
        1000.0,
        -50.0,
        0.02,
        projection_year=1,
    )

    assert snapshot.investment_return == pytest.approx(20.0)
    assert snapshot.closing_asset_value == pytest.approx(970.0)
    assert snapshot.projection_year == 1
    assert snapshot.currency == "CHF"


@pytest.mark.parametrize("bad", [True, None, "x", math.nan])
def test_project_assets_one_year_invalid_opening_raises(bad):
    with pytest.raises((TypeError, ValueError)):
        project_assets_one_year(bad, 0.0, 0.0, projection_year=1)


def test_project_assets_one_year_rejects_invalid_projection_year():
    with pytest.raises(ValueError):
        project_assets_one_year(1000.0, 0.0, 0.0, projection_year=0)


# ---------------------------------------------------------------------------
# C. Asset snapshot to_dict
# ---------------------------------------------------------------------------


def test_asset_snapshot_to_dict_keys_in_order():
    snapshot = _valid_snapshot()
    assert list(snapshot.to_dict().keys()) == list(ASSET_SNAPSHOT_COLUMNS)


def test_asset_snapshot_rejects_inconsistent_closing_value():
    with pytest.raises(ValueError):
        _valid_snapshot(closing_asset_value=999.0)


# ---------------------------------------------------------------------------
# D. DataFrame conversion
# ---------------------------------------------------------------------------


def test_asset_snapshots_to_dataframe_shape_and_columns():
    df = _valid_asset_df()
    assert df.shape == (2, len(ASSET_SNAPSHOT_COLUMNS))
    assert list(df.columns) == list(ASSET_SNAPSHOT_COLUMNS)
    assert validate_asset_dataframe(df) is True


def test_empty_asset_snapshots_returns_empty_dataframe_with_columns():
    df = asset_snapshots_to_dataframe([])
    assert df.empty
    assert list(df.columns) == list(ASSET_SNAPSHOT_COLUMNS)
    assert validate_asset_dataframe(df) is True


def test_asset_snapshots_to_dataframe_rejects_non_snapshot():
    with pytest.raises(TypeError):
        asset_snapshots_to_dataframe([object()])


# ---------------------------------------------------------------------------
# E. Build deterministic asset trajectory
# ---------------------------------------------------------------------------


def test_build_deterministic_asset_trajectory_values():
    valuation = _valuation_df([1000.0, 1100.0, 1200.0])
    annual = _annual_df([(2026, -50.0), (2027, 100.0)])

    df = build_deterministic_asset_trajectory(
        valuation,
        annual,
        target_funding_ratio=1.1,
        annual_return_rate=0.02,
        start_year=2026,
    )

    assert list(df["projection_year"]) == [0, 1, 2]
    assert list(df["closing_asset_value"]) == pytest.approx(
        [1100.0, 1072.0, 1193.44]
    )
    assert validate_asset_dataframe(df) is True


def test_build_deterministic_asset_trajectory_custom_start_year():
    valuation = _valuation_df([1000.0, 1100.0, 1200.0])
    annual = _annual_df([(2030, -50.0), (2031, 100.0)])

    df = build_deterministic_asset_trajectory(
        valuation,
        annual,
        target_funding_ratio=1.1,
        annual_return_rate=0.02,
        start_year=2030,
    )

    assert list(df["net_cashflow"]) == pytest.approx([0.0, -50.0, 100.0])
    assert list(df["closing_asset_value"]) == pytest.approx(
        [1100.0, 1072.0, 1193.44]
    )


def test_build_deterministic_asset_trajectory_rejects_start_year_mismatch():
    valuation = _valuation_df([1000.0, 1100.0, 1200.0])
    annual = _annual_df([(2026, -50.0), (2027, 100.0)])

    with pytest.raises(ValueError):
        build_deterministic_asset_trajectory(
            valuation,
            annual,
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=2030,
        )


# ---------------------------------------------------------------------------
# F. Horizon zero
# ---------------------------------------------------------------------------


def test_build_deterministic_asset_trajectory_horizon_zero():
    valuation = _valuation_df([1000.0])
    annual = _annual_df([])

    df = build_deterministic_asset_trajectory(
        valuation,
        annual,
        target_funding_ratio=1.1,
        annual_return_rate=0.02,
        start_year=2026,
    )

    assert df.shape == (1, len(ASSET_SNAPSHOT_COLUMNS))
    assert int(df.iloc[0]["projection_year"]) == 0
    assert df.iloc[0]["opening_asset_value"] == pytest.approx(1100.0)
    assert df.iloc[0]["closing_asset_value"] == pytest.approx(1100.0)
    assert df.iloc[0]["annual_return_rate"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# G. Validate asset dataframe
# ---------------------------------------------------------------------------


def test_validate_asset_dataframe_valid_returns_true():
    assert validate_asset_dataframe(_valid_asset_df()) is True


def test_validate_asset_dataframe_rejects_non_dataframe():
    with pytest.raises(TypeError):
        validate_asset_dataframe("not a df")


def test_validate_asset_dataframe_rejects_missing_column():
    df = _valid_asset_df().drop(columns=["net_cashflow"])
    with pytest.raises(ValueError):
        validate_asset_dataframe(df)


def test_validate_asset_dataframe_rejects_wrong_column_order():
    df = _valid_asset_df()
    with pytest.raises(ValueError):
        validate_asset_dataframe(df[list(reversed(ASSET_SNAPSHOT_COLUMNS))])


def test_validate_asset_dataframe_rejects_missing_value():
    df = _valid_asset_df()
    df.loc[0, "opening_asset_value"] = pd.NA
    with pytest.raises(ValueError):
        validate_asset_dataframe(df)


def test_validate_asset_dataframe_rejects_invalid_rate():
    df = _valid_asset_df()
    df.loc[1, "annual_return_rate"] = -1.0
    with pytest.raises(ValueError):
        validate_asset_dataframe(df)


def test_validate_asset_dataframe_rejects_inconsistent_closing_value():
    df = _valid_asset_df()
    df.loc[1, "closing_asset_value"] = 999.0
    with pytest.raises(ValueError):
        validate_asset_dataframe(df)


# ---------------------------------------------------------------------------
# H. Immutability
# ---------------------------------------------------------------------------


def test_build_deterministic_asset_trajectory_does_not_mutate_inputs():
    valuation = _valuation_df([1000.0, 1100.0, 1200.0])
    annual = _annual_df([(2026, -50.0), (2027, 100.0)])
    valuation_before = valuation.copy(deep=True)
    annual_before = annual.copy(deep=True)

    build_deterministic_asset_trajectory(
        valuation,
        annual,
        target_funding_ratio=1.1,
        annual_return_rate=0.02,
        start_year=2026,
    )

    pd.testing.assert_frame_equal(valuation, valuation_before)
    pd.testing.assert_frame_equal(annual, annual_before)


# ---------------------------------------------------------------------------
# I. Invalid trajectory inputs
# ---------------------------------------------------------------------------


def test_build_trajectory_rejects_bad_valuation_type():
    with pytest.raises(TypeError):
        build_deterministic_asset_trajectory(
            "not a df",
            _annual_df([]),
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=2026,
        )


def test_build_trajectory_rejects_bad_annual_cashflows_type():
    with pytest.raises(TypeError):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0]),
            "not a df",
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=2026,
        )


def test_build_trajectory_rejects_row_count_mismatch():
    with pytest.raises(ValueError):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0, 1100.0, 1200.0]),
            _annual_df([(2026, -50.0)]),
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=2026,
        )


def test_build_trajectory_rejects_first_projection_year_not_zero():
    with pytest.raises(ValueError):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0], projection_years=[1]),
            _annual_df([]),
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=2026,
        )


@pytest.mark.parametrize("bad", [True, None, "x", math.nan, 0.0, -1.0])
def test_build_trajectory_rejects_invalid_target_funding_ratio(bad):
    with pytest.raises((TypeError, ValueError)):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0]),
            _annual_df([]),
            target_funding_ratio=bad,
            annual_return_rate=0.02,
            start_year=2026,
        )


@pytest.mark.parametrize("bad", [False, None, "x", math.nan, -1.0, -2.0])
def test_build_trajectory_rejects_invalid_annual_return_rate(bad):
    with pytest.raises((TypeError, ValueError)):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0]),
            _annual_df([]),
            target_funding_ratio=1.1,
            annual_return_rate=bad,
            start_year=2026,
        )


@pytest.mark.parametrize("bad", [True, None, "x", -1])
def test_build_trajectory_rejects_invalid_start_year(bad):
    with pytest.raises((TypeError, ValueError)):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0]),
            _annual_df([]),
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=bad,
        )


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_build_trajectory_rejects_invalid_currency(bad):
    with pytest.raises(ValueError):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0]),
            _annual_df([]),
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=2026,
            currency=bad,
        )


def test_build_trajectory_rejects_unsorted_reporting_years():
    with pytest.raises(ValueError):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0, 1100.0, 1200.0]),
            _annual_df([(2027, 100.0), (2026, -50.0)]),
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=2026,
        )


def test_build_trajectory_rejects_duplicated_reporting_years():
    with pytest.raises(ValueError):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0, 1100.0, 1200.0]),
            _annual_df([(2026, -50.0), (2026, 100.0)]),
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=2026,
        )


def test_build_trajectory_rejects_non_contiguous_reporting_years():
    with pytest.raises(ValueError):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0, 1100.0, 1200.0]),
            _annual_df([(2026, -50.0), (2028, 100.0)]),
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=2026,
        )


def test_build_trajectory_rejects_missing_projection_year_lookup():
    with pytest.raises(ValueError):
        build_deterministic_asset_trajectory(
            _valuation_df([1000.0, 1100.0], projection_years=[0, 2]),
            _annual_df([(2026, -50.0)]),
            target_funding_ratio=1.1,
            annual_return_rate=0.02,
            start_year=2026,
        )
