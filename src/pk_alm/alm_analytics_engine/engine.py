"""Stateless orchestration for deterministic ALM analytics."""

from __future__ import annotations

import pandas as pd

from pk_alm.alm_analytics_engine.alm_kpis import (
    alm_kpi_summary_to_dataframe,
    build_alm_kpi_summary_from_tables,
)
from pk_alm.alm_analytics_engine.analytics_input import ALMAnalyticsInput
from pk_alm.alm_analytics_engine.analytics_result import ALMAnalyticsResult
from pk_alm.alm_analytics_engine.cashflows import summarize_cashflows_by_year
from pk_alm.alm_analytics_engine.funding import build_funding_ratio_trajectory
from pk_alm.alm_analytics_engine.funding_summary import (
    funding_summary_to_dataframe,
    summarize_funding_ratio,
)
from pk_alm.alm_analytics_engine.reporting.plot_tables import (
    build_funding_ratio_plot_table,
)
from pk_alm.alm_analytics_engine.reporting.thesis_tables import (
    build_scenario_comparison_table,
)
from pk_alm.alm_analytics_engine.validation import build_alm_validation_report
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe

_COMBINED_SORT_COLUMNS = ["time", "source", "contractId", "type"]


def _combine_cashflows(input_data: ALMAnalyticsInput) -> pd.DataFrame:
    combined = pd.concat(
        [input_data.bvg_cashflows, input_data.asset_cashflows],
        ignore_index=True,
    )
    if combined.empty:
        return pd.DataFrame(columns=list(CASHFLOW_COLUMNS))
    combined = combined.loc[:, list(CASHFLOW_COLUMNS)].copy(deep=True)
    combined["time"] = pd.to_datetime(combined["time"])
    combined = combined.sort_values(_COMBINED_SORT_COLUMNS, ignore_index=True)
    validate_cashflow_dataframe(combined)
    return combined


def run_alm_analytics(input_data: ALMAnalyticsInput) -> ALMAnalyticsResult:
    """Run the stateless ALM Analytics Engine."""
    if not isinstance(input_data, ALMAnalyticsInput):
        raise TypeError("input_data must be ALMAnalyticsInput")

    combined_cashflows = _combine_cashflows(input_data)
    annual_cashflows = summarize_cashflows_by_year(combined_cashflows)
    funding_ratio_trajectory = build_funding_ratio_trajectory(
        input_data.asset_snapshots,
        input_data.valuation_snapshots,
        currency=input_data.currency,
    )
    funding_summary = funding_summary_to_dataframe(
        summarize_funding_ratio(
            funding_ratio_trajectory,
            target_funding_ratio=input_data.target_funding_ratio,
            currency=input_data.currency,
        )
    )
    kpi_summary = alm_kpi_summary_to_dataframe(
        build_alm_kpi_summary_from_tables(
            bvg_cashflows=input_data.bvg_cashflows,
            asset_cashflows=input_data.asset_cashflows,
            combined_cashflows=combined_cashflows,
            annual_cashflows=annual_cashflows,
            funding_summary=funding_summary,
        )
    )
    from pk_alm.alm_analytics_engine.alm_kpis import (
        build_cashflow_by_source_plot_table,
        build_net_cashflow_plot_table,
    )

    cashflow_by_source = build_cashflow_by_source_plot_table(combined_cashflows)
    net_cashflow = build_net_cashflow_plot_table(annual_cashflows)
    funding_ratio_plot = build_funding_ratio_plot_table(
        funding_ratio_trajectory,
        target_funding_ratio=input_data.target_funding_ratio,
    )
    validation_report = build_alm_validation_report(
        input_data=input_data,
        combined_cashflows=combined_cashflows,
        annual_cashflows=annual_cashflows,
        funding_ratio_trajectory=funding_ratio_trajectory,
        funding_summary=funding_summary,
        kpi_summary=kpi_summary,
    )

    return ALMAnalyticsResult(
        inputs=input_data,
        combined_cashflows=combined_cashflows,
        annual_cashflows=annual_cashflows,
        funding_ratio_trajectory=funding_ratio_trajectory,
        funding_summary=funding_summary,
        kpi_summary=kpi_summary,
        cashflow_by_source_plot_table=cashflow_by_source,
        net_cashflow_plot_table=net_cashflow,
        funding_ratio_plot_table=funding_ratio_plot,
        validation_report=validation_report,
    )


def compare_alm_analytics_results(
    results: list[ALMAnalyticsResult],
) -> pd.DataFrame:
    """Compare multiple deterministic ALM analytics results."""
    return build_scenario_comparison_table(results)
