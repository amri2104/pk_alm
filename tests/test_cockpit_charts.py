"""Tests for cockpit chart factories and KPI status helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _REPO_ROOT / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

go = pytest.importorskip("plotly.graph_objects")

from _cockpit import charts, kpi_cards, theme  # noqa: E402


def _funding_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "projection_year": [2026, 2027, 2028],
            "asset_value": [10_000.0, 10_400.0, 10_900.0],
            "total_stage1_liability": [9_300.0, 9_500.0, 9_700.0],
            "funding_ratio": [1.075, 1.094, 1.123],
            "funding_ratio_percent": [107.5, 109.4, 112.3],
            "currency": ["CHF"] * 3,
        }
    )


def _net_cashflow_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "reporting_year": [2026, 2027, 2028],
            "contribution_cashflow": [500, 510, 520],
            "pension_payment_cashflow": [-300, -320, -360],
            "capital_withdrawal_cashflow": [-50, -55, -60],
            "other_cashflow": [10, 12, 14],
            "net_cashflow": [160, 147, -114],
            "structural_net_cashflow": [200, 190, 100],
        }
    )


def _cashflow_by_source_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "reporting_year": [2026, 2026, 2027, 2027],
            "source": ["BVG", "ACTUS", "BVG", "ACTUS"],
            "total_payoff": [500.0, 200.0, 510.0, 220.0],
        }
    )


def _stochastic_summary_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "final_p5": 0.85,
                "final_p50": 1.05,
                "final_p95": 1.25,
                "VaR_5": 0.85,
                "ES_5": 0.78,
                "P_underfunding": 0.12,
            }
        ]
    )


def _validation_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"metric": "funding ratio", "value": 1.08, "benchmark": "around 1.0", "passed": True},
            {"metric": "income yield", "value": 0.02, "benchmark": "non-negative", "passed": True},
            {"metric": "stress check", "value": -0.5, "benchmark": "positive", "passed": False},
        ]
    )


def _allocation_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "asset_class": ["bonds", "equities", "real_estate", "cash"],
            "weight": [0.40, 0.30, 0.20, 0.10],
        }
    )


# Funding ratio chart
def test_funding_ratio_chart_returns_figure() -> None:
    fig = charts.funding_ratio_chart(_funding_df(), target_funding_ratio=1.10)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1
    assert any(trace.mode and "lines" in trace.mode for trace in fig.data)


def test_funding_ratio_chart_empty_safe() -> None:
    fig = charts.funding_ratio_chart(pd.DataFrame())
    assert isinstance(fig, go.Figure)


# Net cashflow chart
def test_net_cashflow_chart_returns_figure() -> None:
    fig = charts.net_cashflow_chart(_net_cashflow_df())
    assert isinstance(fig, go.Figure)
    assert any(trace.type == "bar" for trace in fig.data)


def test_net_cashflow_chart_empty_safe() -> None:
    fig = charts.net_cashflow_chart(pd.DataFrame())
    assert isinstance(fig, go.Figure)


def test_net_cashflow_chart_no_negatives_no_inflection_line() -> None:
    df = _net_cashflow_df().copy()
    df["net_cashflow"] = [10, 20, 30]
    fig = charts.net_cashflow_chart(df)
    assert isinstance(fig, go.Figure)


# Cashflow-by-source
def test_cashflow_by_source_chart_returns_figure() -> None:
    fig = charts.cashflow_by_source_chart(_cashflow_by_source_df())
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 2


def test_cashflow_by_source_chart_empty_safe() -> None:
    fig = charts.cashflow_by_source_chart(pd.DataFrame())
    assert isinstance(fig, go.Figure)


# Assets vs Liabilities
def test_assets_vs_liabilities_chart_returns_figure() -> None:
    fig = charts.assets_vs_liabilities_chart(_funding_df())
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 3


def test_assets_vs_liabilities_chart_empty_safe() -> None:
    fig = charts.assets_vs_liabilities_chart(pd.DataFrame())
    assert isinstance(fig, go.Figure)


# Scenario overlay
def test_scenario_overlay_chart_returns_figure() -> None:
    scenarios = {
        "Baseline": _funding_df(),
        "Interest +100bp": _funding_df().assign(funding_ratio_percent=[105, 107, 110]),
    }
    fig = charts.scenario_overlay_chart(scenarios)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_scenario_overlay_chart_empty_safe() -> None:
    fig = charts.scenario_overlay_chart({})
    assert isinstance(fig, go.Figure)


# Stochastic summary
def test_stochastic_summary_chart_returns_figure() -> None:
    fig = charts.stochastic_summary_chart(_stochastic_summary_df())
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


def test_stochastic_summary_chart_empty_safe() -> None:
    fig = charts.stochastic_summary_chart(None)
    assert isinstance(fig, go.Figure)


# Validation table
def test_validation_checks_table_returns_figure() -> None:
    fig = charts.validation_checks_table(_validation_df())
    assert isinstance(fig, go.Figure)


def test_validation_checks_table_empty_safe() -> None:
    fig = charts.validation_checks_table(pd.DataFrame())
    assert isinstance(fig, go.Figure)


# Allocation donut
def test_allocation_donut_chart_returns_figure() -> None:
    fig = charts.allocation_donut_chart(_allocation_df())
    assert isinstance(fig, go.Figure)


def test_allocation_donut_chart_empty_safe() -> None:
    fig = charts.allocation_donut_chart(pd.DataFrame())
    assert isinstance(fig, go.Figure)


# KPI status helpers
@pytest.mark.parametrize(
    "percent,expected",
    [
        (115.0, "ok"),
        (110.0, "ok"),
        (109.9, "neutral"),
        (100.0, "neutral"),
        (99.9, "warn"),
        (90.0, "warn"),
        (89.9, "alert"),
        (None, "neutral"),
    ],
)
def test_funding_ratio_status(percent, expected) -> None:
    assert kpi_cards.funding_ratio_status(percent) == expected


@pytest.mark.parametrize(
    "year,expected",
    [(None, "ok"), (15, "warn"), (5, "alert"), (10, "alert")],
)
def test_liquidity_status(year, expected) -> None:
    assert kpi_cards.liquidity_status(year) == expected


@pytest.mark.parametrize(
    "prob,expected",
    [(0.01, "ok"), (0.0499, "ok"), (0.05, "warn"), (0.10, "warn"), (0.15, "alert"), (0.30, "alert"), (None, "neutral")],
)
def test_underfunding_status(prob, expected) -> None:
    assert kpi_cards.underfunding_status(prob) == expected


@pytest.mark.parametrize(
    "net,expected",
    [(100, "ok"), (0, "neutral"), (-50, "warn"), (None, "neutral")],
)
def test_cashflow_status(net, expected) -> None:
    assert kpi_cards.cashflow_status(net) == expected


def test_cockpit_template_registered() -> None:
    import plotly.io as pio

    template = theme.cockpit_template()
    assert template is not None
    assert "cockpit" in pio.templates
