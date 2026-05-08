"""Tests for the canonical ALM Analytics Engine orchestrator."""

from __future__ import annotations

import pandas as pd
import pytest

from pk_alm.actus_asset_engine.deterministic import ASSET_SNAPSHOT_COLUMNS
from pk_alm.alm_analytics_engine.alm_kpis import ALM_KPI_SUMMARY_COLUMNS
from pk_alm.alm_analytics_engine.analytics_input import ALMAnalyticsInput
from pk_alm.alm_analytics_engine.analytics_result import ALMAnalyticsResult
from pk_alm.alm_analytics_engine.cashflows import summarize_cashflows_by_year
from pk_alm.alm_analytics_engine.engine import (
    compare_alm_analytics_results,
    run_alm_analytics,
)
from pk_alm.alm_analytics_engine.funding import build_funding_ratio_trajectory
from pk_alm.alm_analytics_engine.reporting.plot_tables import (
    FUNDING_RATIO_PLOT_COLUMNS,
)
from pk_alm.alm_analytics_engine.reporting.thesis_tables import (
    ALM_SCENARIO_COMPARISON_COLUMNS,
)
from pk_alm.alm_analytics_engine.validation import ALM_VALIDATION_REPORT_COLUMNS
from pk_alm.bvg_liability_engine.pension_logic.valuation import VALUATION_COLUMNS
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS


def _bvg_cashflows(currency: str = "CHF") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "contractId": "BVG_PR",
                "time": pd.Timestamp("2026-12-31"),
                "type": "PR",
                "payoff": 100.0,
                "nominalValue": 0.0,
                "currency": currency,
                "source": "BVG",
            },
            {
                "contractId": "BVG_RP",
                "time": pd.Timestamp("2026-12-31"),
                "type": "RP",
                "payoff": -80.0,
                "nominalValue": 0.0,
                "currency": currency,
                "source": "BVG",
            },
        ],
        columns=list(CASHFLOW_COLUMNS),
    )


def _asset_cashflows(currency: str = "CHF") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "contractId": "ACTUS_BOND",
                "time": pd.Timestamp("2026-12-31"),
                "type": "IP",
                "payoff": 20.0,
                "nominalValue": 1_000.0,
                "currency": currency,
                "source": "ACTUS",
            }
        ],
        columns=list(CASHFLOW_COLUMNS),
    )


def _empty_asset_cashflows() -> pd.DataFrame:
    return pd.DataFrame(columns=list(CASHFLOW_COLUMNS))


def _asset_snapshots(currency: str = "CHF", years=(0, 1)) -> pd.DataFrame:
    rows = [
        {
            "projection_year": years[0],
            "opening_asset_value": 1_076.0,
            "investment_return": 0.0,
            "net_cashflow": 0.0,
            "closing_asset_value": 1_076.0,
            "annual_return_rate": 0.0,
            "currency": currency,
        },
        {
            "projection_year": years[1],
            "opening_asset_value": 1_076.0,
            "investment_return": 0.0,
            "net_cashflow": -26.0,
            "closing_asset_value": 1_050.0,
            "annual_return_rate": 0.0,
            "currency": currency,
        },
    ]
    return pd.DataFrame(rows, columns=list(ASSET_SNAPSHOT_COLUMNS))


def _valuation_snapshots(currency: str = "CHF", years=(0, 1)) -> pd.DataFrame:
    rows = []
    for year in years:
        rows.append(
            {
                "projection_year": year,
                "active_count_total": 1,
                "retired_count_total": 0,
                "member_count_total": 1,
                "total_capital_active": 1_000.0,
                "total_capital_rente": 0.0,
                "retiree_obligation_pv": 0.0,
                "pensionierungsverlust": 0.0,
                "total_stage1_liability": 1_000.0,
                "technical_interest_rate": 0.0176,
                "valuation_terminal_age": 90,
                "currency": currency,
            }
        )
    return pd.DataFrame(rows, columns=list(VALUATION_COLUMNS))


def _input(**overrides: object) -> ALMAnalyticsInput:
    data = {
        "bvg_cashflows": _bvg_cashflows(),
        "asset_cashflows": _asset_cashflows(),
        "asset_snapshots": _asset_snapshots(),
        "valuation_snapshots": _valuation_snapshots(),
        "scenario_name": "base_case",
        "target_funding_ratio": 1.076,
        "currency": "CHF",
    }
    data.update(overrides)
    return ALMAnalyticsInput(**data)  # type: ignore[arg-type]


def test_input_validation_rejects_currency_mismatch():
    with pytest.raises(ValueError, match="asset_cashflows currency"):
        _input(asset_cashflows=_asset_cashflows("EUR"))


def test_input_validation_rejects_projection_year_mismatch():
    with pytest.raises(ValueError, match="projection_year"):
        _input(asset_snapshots=_asset_snapshots(years=(0, 2)))


def test_input_validation_allows_empty_asset_cashflows():
    input_data = _input(asset_cashflows=_empty_asset_cashflows())
    assert input_data.asset_cashflows.empty


def test_input_validation_rejects_bad_target_ratio():
    with pytest.raises(ValueError, match="target_funding_ratio"):
        _input(target_funding_ratio=0.0)


def test_run_alm_analytics_builds_combined_cashflows_internally():
    result = run_alm_analytics(_input())

    assert isinstance(result, ALMAnalyticsResult)
    assert len(result.combined_cashflows) == len(result.inputs.bvg_cashflows) + len(
        result.inputs.asset_cashflows
    )
    expected = pd.concat(
        [result.inputs.bvg_cashflows, result.inputs.asset_cashflows],
        ignore_index=True,
    ).sort_values(["time", "source", "contractId", "type"], ignore_index=True)
    pd.testing.assert_frame_equal(result.combined_cashflows, expected)


def test_run_alm_analytics_reuses_existing_annual_and_funding_helpers():
    input_data = _input()
    result = run_alm_analytics(input_data)

    pd.testing.assert_frame_equal(
        result.annual_cashflows,
        summarize_cashflows_by_year(result.combined_cashflows),
    )
    pd.testing.assert_frame_equal(
        result.funding_ratio_trajectory,
        build_funding_ratio_trajectory(
            input_data.asset_snapshots,
            input_data.valuation_snapshots,
            currency="CHF",
        ),
    )


def test_kpi_plot_and_validation_tables_have_stable_columns():
    result = run_alm_analytics(_input())

    assert list(result.kpi_summary.columns) == list(ALM_KPI_SUMMARY_COLUMNS)
    assert not result.kpi_summary.drop(columns=["liquidity_inflection_year"]).isna().any().any()
    assert list(result.funding_ratio_plot_table.columns) == list(
        FUNDING_RATIO_PLOT_COLUMNS
    )
    assert list(result.validation_report.columns) == list(ALM_VALIDATION_REPORT_COLUMNS)
    expected_checks = {
        "bvg_cashflow_schema_valid",
        "asset_cashflow_schema_valid",
        "currency_consistency",
        "projection_year_alignment",
        "combined_cashflows_schema_valid",
        "combined_cashflows_row_count_equals_parts",
        "annual_cashflows_valid",
        "funding_ratio_trajectory_valid",
        "funding_summary_valid",
        "kpi_summary_no_missing",
    }
    assert expected_checks.issubset(set(result.validation_report["check_name"]))
    assert set(result.validation_report["status"]) == {"pass"}


def test_plot_tables_do_not_mutate_result_frames():
    result = run_alm_analytics(_input())
    combined_before = result.combined_cashflows.copy(deep=True)
    annual_before = result.annual_cashflows.copy(deep=True)
    funding_before = result.funding_ratio_trajectory.copy(deep=True)

    _ = result.cashflow_by_source_plot_table.copy(deep=True)
    _ = result.net_cashflow_plot_table.copy(deep=True)
    _ = result.funding_ratio_plot_table.copy(deep=True)

    pd.testing.assert_frame_equal(result.combined_cashflows, combined_before)
    pd.testing.assert_frame_equal(result.annual_cashflows, annual_before)
    pd.testing.assert_frame_equal(result.funding_ratio_trajectory, funding_before)


def test_compare_alm_analytics_results_returns_scenario_rows():
    result_a = run_alm_analytics(_input(scenario_name="base"))
    result_b = run_alm_analytics(
        _input(
            scenario_name="stress",
            asset_snapshots=_asset_snapshots(),
        )
    )

    table = compare_alm_analytics_results([result_a, result_b])

    assert list(table.columns) == list(ALM_SCENARIO_COMPARISON_COLUMNS)
    assert table["scenario_name"].tolist() == ["base", "stress"]
