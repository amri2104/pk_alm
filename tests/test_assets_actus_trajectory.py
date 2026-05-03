"""Tests for ACTUS-mode asset trajectory snapshots."""

import pandas as pd
import pytest

from pk_alm.adapters.aal_asset_portfolio import CSHSpec, PAMSpec, STKSpec
from pk_alm.assets.actus_trajectory import (
    ACTUS_ASSET_TRAJECTORY_COLUMNS,
    compute_actus_asset_trajectory,
)
from pk_alm.cashflows.schema import CashflowRecord, cashflow_records_to_dataframe


def _specs():
    return (
        PAMSpec("PAM_1", 2026, 2028, 100_000.0, 0.02),
        STKSpec(
            "STK_1",
            2026,
            2029,
            quantity=1_000.0,
            price_at_purchase=100.0,
            price_at_termination=112.4864,
            dividend_yield=0.025,
            market_value_growth=0.04,
        ),
        CSHSpec("CSH_1", 2026, 50_000.0),
    )


def _cashflows():
    records = [
        CashflowRecord(
            "PAM_1",
            "2028-12-31T00:00:00",
            "IP",
            2_000.0,
            100_000.0,
            source="ACTUS",
        ),
        CashflowRecord(
            "PAM_1",
            "2028-12-31T00:00:00",
            "MD",
            100_000.0,
            0.0,
            source="ACTUS",
        ),
        CashflowRecord(
            "STK_1",
            "2029-12-31T00:00:00",
            "TD",
            112_486.4,
            0.0,
            source="ACTUS",
        ),
    ]
    return cashflow_records_to_dataframe(records)


def test_trajectory_has_expected_columns_and_decomposition():
    trajectory = compute_actus_asset_trajectory(
        _specs(),
        _cashflows(),
        horizon_years=3,
        initial_cash=10_000.0,
    )

    assert list(trajectory.columns) == list(ACTUS_ASSET_TRAJECTORY_COLUMNS)
    assert list(trajectory["year"]) == [2026, 2027, 2028, 2029]

    for _, row in trajectory.iterrows():
        expected = (
            row["cash_balance"]
            + row["pam_value"]
            + row["stk_market_value"]
            + row["csh_value"]
        )
        assert row["closing_asset_value"] == pytest.approx(expected)


def test_pam_value_drops_to_zero_after_maturity_year_end():
    trajectory = compute_actus_asset_trajectory(_specs(), _cashflows(), 3)
    assert trajectory.loc[trajectory["year"] == 2027, "pam_value"].iloc[0] == 100_000.0
    assert trajectory.loc[trajectory["year"] == 2028, "pam_value"].iloc[0] == 0.0


def test_stk_market_value_drops_to_zero_after_divestment_year_end():
    trajectory = compute_actus_asset_trajectory(_specs(), _cashflows(), 3)
    assert trajectory.loc[trajectory["year"] == 2028, "stk_market_value"].iloc[
        0
    ] == pytest.approx(100_000.0 * (1.04**2))
    assert trajectory.loc[trajectory["year"] == 2029, "stk_market_value"].iloc[0] == 0.0


def test_cash_balance_accumulates_realized_asset_cashflows():
    trajectory = compute_actus_asset_trajectory(
        _specs(),
        _cashflows(),
        horizon_years=3,
        initial_cash=10_000.0,
    )
    cash_by_year = dict(zip(trajectory["year"], trajectory["cash_balance"]))
    assert cash_by_year[2026] == pytest.approx(10_000.0)
    assert cash_by_year[2027] == pytest.approx(10_000.0)
    assert cash_by_year[2028] == pytest.approx(112_000.0)
    assert cash_by_year[2029] == pytest.approx(224_486.4)


def test_income_columns_split_coupon_and_realizations():
    trajectory = compute_actus_asset_trajectory(_specs(), _cashflows(), 3)
    row_2027 = trajectory[trajectory["year"] == 2027].iloc[0]
    row_2028 = trajectory[trajectory["year"] == 2028].iloc[0]
    row_2029 = trajectory[trajectory["year"] == 2029].iloc[0]

    assert row_2027["coupon_income"] == 0.0
    assert row_2028["coupon_income"] == 2_000.0
    assert row_2028["realized_maturity_or_td"] == 100_000.0
    assert row_2029["realized_maturity_or_td"] == 112_486.4


def test_trajectory_rejects_empty_specs():
    with pytest.raises(ValueError):
        compute_actus_asset_trajectory((), pd.DataFrame(), 3)
