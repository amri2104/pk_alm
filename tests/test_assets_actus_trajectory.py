"""Tests for ACTUS asset trajectory from contract configs."""

import pandas as pd
import pytest

from pk_alm.actus_asset_engine.aal_asset_portfolio import (
    make_csh_contract_config,
    make_pam_contract_config,
    make_stk_contract_config_from_nominal,
)
from pk_alm.actus_asset_engine.actus_trajectory import (
    ACTUS_ASSET_TRAJECTORY_COLUMNS,
    compute_actus_asset_trajectory,
)
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS


def _configs():
    return (
        make_pam_contract_config(
            contract_id="PAM_1",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        ),
        make_stk_contract_config_from_nominal(
            contract_id="STK_1",
            start_year=2026,
            divestment_year=2030,
            nominal_value=200_000.0,
            dividend_yield=0.025,
            market_value_growth=0.04,
        ),
        make_csh_contract_config(
            contract_id="CSH_1",
            start_year=2026,
            nominal_value=50_000.0,
        ),
    )


def _cashflows():
    return pd.DataFrame(
        [
            {
                "contractId": "PAM_1",
                "time": pd.Timestamp("2027-12-31"),
                "type": "IP",
                "payoff": 2_000.0,
                "nominalValue": 100_000.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
            {
                "contractId": "PAM_1",
                "time": pd.Timestamp("2028-12-31"),
                "type": "MD",
                "payoff": 100_000.0,
                "nominalValue": 0.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
            {
                "contractId": "STK_1",
                "time": pd.Timestamp("2030-12-31"),
                "type": "TD",
                "payoff": 233_971.712,
                "nominalValue": 0.0,
                "currency": "CHF",
                "source": "ACTUS",
            },
        ],
        columns=list(CASHFLOW_COLUMNS),
    )


def test_compute_actus_asset_trajectory_schema_and_horizon():
    result = compute_actus_asset_trajectory(
        _configs(),
        _cashflows(),
        horizon_years=4,
        initial_cash=10_000.0,
    )

    assert list(result.columns) == list(ACTUS_ASSET_TRAJECTORY_COLUMNS)
    assert result["year"].tolist() == [2026, 2027, 2028, 2029, 2030]


def test_compute_actus_asset_trajectory_values_open_and_matured_positions():
    result = compute_actus_asset_trajectory(
        _configs(),
        _cashflows(),
        horizon_years=4,
        initial_cash=10_000.0,
    )

    row_2026 = result.loc[result["year"].eq(2026)].iloc[0]
    row_2027 = result.loc[result["year"].eq(2027)].iloc[0]
    row_2028 = result.loc[result["year"].eq(2028)].iloc[0]
    row_2030 = result.loc[result["year"].eq(2030)].iloc[0]

    assert row_2026["pam_value"] == pytest.approx(100_000.0)
    assert row_2026["stk_market_value"] == pytest.approx(200_000.0)
    assert row_2026["csh_value"] == pytest.approx(50_000.0)
    assert row_2027["cash_balance"] == pytest.approx(12_000.0)
    assert row_2027["coupon_income"] == pytest.approx(2_000.0)
    assert row_2028["pam_value"] == pytest.approx(0.0)
    assert row_2028["realized_maturity_or_td"] == pytest.approx(100_000.0)
    assert row_2030["stk_market_value"] == pytest.approx(0.0)


def test_compute_actus_asset_trajectory_rejects_non_config_items():
    with pytest.raises(TypeError):
        compute_actus_asset_trajectory([{"contractID": "BAD"}], _cashflows(), 1)
