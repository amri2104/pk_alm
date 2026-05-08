"""Thesis/reporting tables for ALM Analytics results."""

from __future__ import annotations

import pandas as pd

from pk_alm.alm_analytics_engine.alm_kpis import validate_alm_kpi_summary_dataframe
from pk_alm.alm_analytics_engine.cashflows import validate_annual_cashflow_dataframe
from pk_alm.alm_analytics_engine.funding import validate_funding_ratio_dataframe
from pk_alm.alm_analytics_engine.validation import (
    validate_alm_validation_report_dataframe,
)

ALM_SCENARIO_COMPARISON_COLUMNS = (
    "scenario_name",
    "initial_funding_ratio_percent",
    "final_funding_ratio_percent",
    "minimum_funding_ratio_percent",
    "years_below_100_percent",
    "liquidity_inflection_year",
    "total_bvg_cashflow",
    "total_actus_cashflow",
    "total_combined_cashflow",
)


def _require_result(result: object):
    from pk_alm.alm_analytics_engine.analytics_result import ALMAnalyticsResult

    if not isinstance(result, ALMAnalyticsResult):
        raise TypeError("result must be ALMAnalyticsResult")
    return result


def build_alm_kpi_table(result: object) -> pd.DataFrame:
    result = _require_result(result)
    validate_alm_kpi_summary_dataframe(result.kpi_summary)
    return result.kpi_summary.copy(deep=True)


def build_annual_cashflow_table(result: object) -> pd.DataFrame:
    result = _require_result(result)
    validate_annual_cashflow_dataframe(result.annual_cashflows)
    return result.annual_cashflows.copy(deep=True)


def build_funding_ratio_table(result: object) -> pd.DataFrame:
    result = _require_result(result)
    validate_funding_ratio_dataframe(result.funding_ratio_trajectory)
    return result.funding_ratio_trajectory.copy(deep=True)


def build_liquidity_table(result: object) -> pd.DataFrame:
    result = _require_result(result)
    row = result.kpi_summary.iloc[0]
    return pd.DataFrame(
        [
            {
                "scenario_name": result.inputs.scenario_name,
                "liquidity_inflection_year": row["liquidity_inflection_year"],
                "total_combined_cashflow": row["total_combined_cashflow"],
                "currency": row["currency"],
            }
        ]
    )


def build_alm_validation_table(result: object) -> pd.DataFrame:
    result = _require_result(result)
    validate_alm_validation_report_dataframe(result.validation_report)
    return result.validation_report.copy(deep=True)


def build_scenario_comparison_table(results: list[object] | tuple[object, ...]) -> pd.DataFrame:
    if not isinstance(results, (list, tuple)):
        raise TypeError("results must be a list or tuple")
    rows: list[dict[str, object]] = []
    for result in results:
        result = _require_result(result)
        row = result.kpi_summary.iloc[0]
        rows.append(
            {
                "scenario_name": result.inputs.scenario_name,
                "initial_funding_ratio_percent": row["initial_funding_ratio_percent"],
                "final_funding_ratio_percent": row["final_funding_ratio_percent"],
                "minimum_funding_ratio_percent": row["minimum_funding_ratio_percent"],
                "years_below_100_percent": row["years_below_100_percent"],
                "liquidity_inflection_year": row["liquidity_inflection_year"],
                "total_bvg_cashflow": row["total_bvg_cashflow"],
                "total_actus_cashflow": row["total_actus_cashflow"],
                "total_combined_cashflow": row["total_combined_cashflow"],
            }
        )
    return pd.DataFrame(rows, columns=list(ALM_SCENARIO_COMPARISON_COLUMNS))
