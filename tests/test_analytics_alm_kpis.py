"""Tests for the ALM KPI / plot-ready output layer (Sprint 7F)."""

import math
from functools import lru_cache

import pandas as pd
import pytest

from pk_alm.alm_analytics_engine.alm_kpis import (
    ALM_KPI_SUMMARY_COLUMNS,
    CASHFLOW_BY_SOURCE_PLOT_COLUMNS,
    NET_CASHFLOW_PLOT_COLUMNS,
    ALMKPISummary,
    alm_kpi_summary_to_dataframe,
    build_alm_kpi_summary,
    build_cashflow_by_source_plot_table,
    build_net_cashflow_plot_table,
)
from pk_alm.scenarios.full_alm_scenario import run_full_alm_scenario


@lru_cache(maxsize=1)
def _scenario():
    return run_full_alm_scenario().alm_analytics_result


# ---------------------------------------------------------------------------
# A. Dataclass invariants
# ---------------------------------------------------------------------------


def _good_kpi_kwargs() -> dict:
    return dict(
        initial_funding_ratio_percent=110.0,
        final_funding_ratio_percent=95.0,
        minimum_funding_ratio_percent=90.0,
        years_below_100_percent=4,
        total_bvg_cashflow=-100.0,
        total_actus_cashflow=50.0,
        total_combined_cashflow=-50.0,
        first_year=2026,
        final_year=2037,
        liquidity_inflection_year=2030,
        currency="CHF",
    )


def test_kpi_dataclass_validates_basic_invariants():
    summary = ALMKPISummary(**_good_kpi_kwargs())
    assert isinstance(summary.to_dict(), dict)


def test_kpi_dataclass_rejects_bool_int_field():
    kwargs = _good_kpi_kwargs()
    kwargs["years_below_100_percent"] = True
    with pytest.raises(TypeError):
        ALMKPISummary(**kwargs)


def test_kpi_dataclass_rejects_negative_years_below_100():
    kwargs = _good_kpi_kwargs()
    kwargs["years_below_100_percent"] = -1
    with pytest.raises(ValueError):
        ALMKPISummary(**kwargs)


def test_kpi_dataclass_rejects_final_year_before_first_year():
    kwargs = _good_kpi_kwargs()
    kwargs["first_year"] = 2030
    kwargs["final_year"] = 2025
    with pytest.raises(ValueError):
        ALMKPISummary(**kwargs)


def test_kpi_dataclass_rejects_inflection_year_outside_range():
    kwargs = _good_kpi_kwargs()
    kwargs["liquidity_inflection_year"] = 2050
    with pytest.raises(ValueError):
        ALMKPISummary(**kwargs)


def test_kpi_dataclass_accepts_none_inflection_year():
    kwargs = _good_kpi_kwargs()
    kwargs["liquidity_inflection_year"] = None
    summary = ALMKPISummary(**kwargs)
    assert summary.liquidity_inflection_year is None


def test_kpi_dataclass_rejects_inconsistent_combined_total():
    kwargs = _good_kpi_kwargs()
    kwargs["total_combined_cashflow"] = 999.0
    with pytest.raises(ValueError):
        ALMKPISummary(**kwargs)


def test_kpi_dataclass_rejects_nan_funding_ratio():
    kwargs = _good_kpi_kwargs()
    kwargs["initial_funding_ratio_percent"] = float("nan")
    with pytest.raises(ValueError):
        ALMKPISummary(**kwargs)


# ---------------------------------------------------------------------------
# B. KPI builder from a Full ALM result
# ---------------------------------------------------------------------------


def test_build_alm_kpi_summary_from_full_alm_scenario():
    scenario = _scenario()
    summary = build_alm_kpi_summary(scenario)
    assert isinstance(summary, ALMKPISummary)


def test_build_alm_kpi_summary_rejects_non_scenario_result():
    with pytest.raises(TypeError):
        build_alm_kpi_summary("not a scenario")


def test_kpi_total_cashflow_identity_holds():
    scenario = _scenario()
    summary = build_alm_kpi_summary(scenario)
    assert math.isclose(
        summary.total_combined_cashflow,
        summary.total_bvg_cashflow + summary.total_actus_cashflow,
        abs_tol=1e-5,
    )


def test_kpi_total_combined_equals_combined_payoff_sum():
    scenario = _scenario()
    summary = build_alm_kpi_summary(scenario)
    expected = float(scenario.combined_cashflows["payoff"].sum())
    assert math.isclose(summary.total_combined_cashflow, expected, abs_tol=1e-5)


def test_kpi_first_and_final_years_match_annual_cashflows():
    scenario = _scenario()
    summary = build_alm_kpi_summary(scenario)
    years = [int(y) for y in scenario.annual_cashflows["reporting_year"]]
    assert summary.first_year == min(years)
    assert summary.final_year == max(years)


# ---------------------------------------------------------------------------
# C. Funding-ratio KPIs match Stage-1 funding summary (no new assumptions)
# ---------------------------------------------------------------------------


def test_funding_kpis_match_stage1_funding_summary():
    scenario = _scenario()
    summary = build_alm_kpi_summary(scenario)
    fs = scenario.funding_summary.iloc[0]
    assert summary.initial_funding_ratio_percent == pytest.approx(
        float(fs["initial_funding_ratio_percent"])
    )
    assert summary.final_funding_ratio_percent == pytest.approx(
        float(fs["final_funding_ratio_percent"])
    )
    assert summary.minimum_funding_ratio_percent == pytest.approx(
        float(fs["minimum_funding_ratio_percent"])
    )
    assert summary.years_below_100_percent == int(fs["years_below_100_percent"])


def test_kpi_layer_introduces_no_new_assumptions():
    # Verify that running KPI builder twice produces equal results — i.e.
    # no hidden randomness, time-of-day, or environment dependency.
    scenario = _scenario()
    a = build_alm_kpi_summary(scenario)
    b = build_alm_kpi_summary(scenario)
    assert a.to_dict() == b.to_dict()


# ---------------------------------------------------------------------------
# D. Summary DataFrame
# ---------------------------------------------------------------------------


def test_kpi_summary_dataframe_has_one_row():
    summary = build_alm_kpi_summary(_scenario())
    df = alm_kpi_summary_to_dataframe(summary)
    assert len(df) == 1


def test_kpi_summary_dataframe_has_stable_columns():
    summary = build_alm_kpi_summary(_scenario())
    df = alm_kpi_summary_to_dataframe(summary)
    assert list(df.columns) == list(ALM_KPI_SUMMARY_COLUMNS)


def test_kpi_summary_dataframe_rejects_non_summary_input():
    with pytest.raises(TypeError):
        alm_kpi_summary_to_dataframe({"foo": "bar"})


# ---------------------------------------------------------------------------
# E. Plot-ready cashflow-by-source table
# ---------------------------------------------------------------------------


def test_cashflow_by_source_plot_table_not_empty():
    scenario = _scenario()
    df = build_cashflow_by_source_plot_table(scenario.combined_cashflows)
    assert not df.empty


def test_cashflow_by_source_plot_table_has_stable_columns():
    scenario = _scenario()
    df = build_cashflow_by_source_plot_table(scenario.combined_cashflows)
    assert list(df.columns) == list(CASHFLOW_BY_SOURCE_PLOT_COLUMNS)


def test_cashflow_by_source_plot_table_actus_visible_as_separate_source():
    scenario = _scenario()
    df = build_cashflow_by_source_plot_table(scenario.combined_cashflows)
    sources = set(df["source"].unique())
    assert "BVG" in sources
    assert "ACTUS" in sources


def test_cashflow_by_source_plot_table_does_not_mutate_input():
    scenario = _scenario()
    snapshot = scenario.combined_cashflows.copy(deep=True)
    build_cashflow_by_source_plot_table(scenario.combined_cashflows)
    pd.testing.assert_frame_equal(scenario.combined_cashflows, snapshot)


def test_cashflow_by_source_plot_table_year_totals_match_groupby():
    scenario = _scenario()
    df = build_cashflow_by_source_plot_table(scenario.combined_cashflows)
    # totals per (year, source) must equal the direct groupby sum
    work = scenario.combined_cashflows.copy(deep=True)
    work["reporting_year"] = pd.to_datetime(work["time"]).dt.year.astype(int)
    expected = (
        work.groupby(["reporting_year", "source"])["payoff"].sum().reset_index()
    )
    for _, row in expected.iterrows():
        match = df[
            (df["reporting_year"] == int(row["reporting_year"]))
            & (df["source"] == row["source"])
        ]
        assert len(match) == 1
        assert match.iloc[0]["total_payoff"] == pytest.approx(float(row["payoff"]))


# ---------------------------------------------------------------------------
# F. Plot-ready net-cashflow table
# ---------------------------------------------------------------------------


def test_net_cashflow_plot_table_not_empty():
    scenario = _scenario()
    df = build_net_cashflow_plot_table(scenario.annual_cashflows)
    assert not df.empty


def test_net_cashflow_plot_table_has_stable_columns():
    scenario = _scenario()
    df = build_net_cashflow_plot_table(scenario.annual_cashflows)
    assert list(df.columns) == list(NET_CASHFLOW_PLOT_COLUMNS)


def test_net_cashflow_plot_table_does_not_mutate_input():
    scenario = _scenario()
    snapshot = scenario.annual_cashflows.copy(deep=True)
    build_net_cashflow_plot_table(scenario.annual_cashflows)
    pd.testing.assert_frame_equal(scenario.annual_cashflows, snapshot)


def test_net_cashflow_plot_table_values_match_annual_cashflows():
    scenario = _scenario()
    df = build_net_cashflow_plot_table(scenario.annual_cashflows)
    for col in NET_CASHFLOW_PLOT_COLUMNS:
        assert list(df[col]) == list(scenario.annual_cashflows[col])
