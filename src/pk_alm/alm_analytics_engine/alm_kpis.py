"""Compact ALM KPI / plot-ready output layer.

This layer reads canonical ALM Analytics Engine outputs and produces:

- An :class:`ALMKPISummary` dataclass with a small set of stable KPIs.
- Plot-ready DataFrames for cashflow-by-source and net-cashflow visualization.

It does not introduce new actuarial assumptions, new market assumptions, or
new funding-ratio logic. Funding-ratio KPIs are read straight from the
funding summary; cashflow KPIs are derived from the existing combined and
annual cashflow DataFrames.
"""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.alm_analytics_engine.cashflows import (
    find_liquidity_inflection_year,
    validate_annual_cashflow_dataframe,
)
from pk_alm.alm_analytics_engine.funding_summary import (
    validate_funding_summary_dataframe,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe

ALM_KPI_SUMMARY_COLUMNS = (
    "initial_funding_ratio_percent",
    "final_funding_ratio_percent",
    "minimum_funding_ratio_percent",
    "years_below_100_percent",
    "total_bvg_cashflow",
    "total_actus_cashflow",
    "total_combined_cashflow",
    "first_year",
    "final_year",
    "liquidity_inflection_year",
    "currency",
)

CASHFLOW_BY_SOURCE_PLOT_COLUMNS = ("reporting_year", "source", "total_payoff")
NET_CASHFLOW_PLOT_COLUMNS = (
    "reporting_year",
    "contribution_cashflow",
    "pension_payment_cashflow",
    "capital_withdrawal_cashflow",
    "other_cashflow",
    "net_cashflow",
    "structural_net_cashflow",
)


# ---------------------------------------------------------------------------
# Validation helpers (local, mirroring existing analytics style)
# ---------------------------------------------------------------------------


def _validate_non_bool_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


def _validate_non_bool_real(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    return fval


def _validate_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


# ---------------------------------------------------------------------------
# KPI summary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ALMKPISummary:
    """Compact ALM KPI summary derived from existing scenario outputs."""

    initial_funding_ratio_percent: float
    final_funding_ratio_percent: float
    minimum_funding_ratio_percent: float
    years_below_100_percent: int
    total_bvg_cashflow: float
    total_actus_cashflow: float
    total_combined_cashflow: float
    first_year: int
    final_year: int
    liquidity_inflection_year: int | None
    currency: str = "CHF"

    def __post_init__(self) -> None:
        for fname in (
            "initial_funding_ratio_percent",
            "final_funding_ratio_percent",
            "minimum_funding_ratio_percent",
            "total_bvg_cashflow",
            "total_actus_cashflow",
            "total_combined_cashflow",
        ):
            _validate_non_bool_real(getattr(self, fname), fname)

        years_below = _validate_non_bool_int(
            self.years_below_100_percent, "years_below_100_percent"
        )
        if years_below < 0:
            raise ValueError(
                f"years_below_100_percent must be >= 0, got {years_below}"
            )

        first_year = _validate_non_bool_int(self.first_year, "first_year")
        final_year = _validate_non_bool_int(self.final_year, "final_year")
        if final_year < first_year:
            raise ValueError(
                "final_year must be >= first_year "
                f"({final_year} < {first_year})"
            )

        if self.liquidity_inflection_year is not None:
            year = _validate_non_bool_int(
                self.liquidity_inflection_year, "liquidity_inflection_year"
            )
            if not first_year <= year <= final_year:
                raise ValueError(
                    "liquidity_inflection_year must lie between first_year and "
                    f"final_year ({first_year} <= {year} <= {final_year})"
                )

        _validate_non_empty_string(self.currency, "currency")

        expected_combined = self.total_bvg_cashflow + self.total_actus_cashflow
        if not math.isclose(
            self.total_combined_cashflow,
            expected_combined,
            abs_tol=1e-5,
        ):
            raise ValueError(
                "total_combined_cashflow must equal total_bvg_cashflow + "
                f"total_actus_cashflow (expected {expected_combined}, "
                f"got {self.total_combined_cashflow})"
            )

    def to_dict(self) -> dict[str, object]:
        return {col: getattr(self, col) for col in ALM_KPI_SUMMARY_COLUMNS}


# ---------------------------------------------------------------------------
# KPI builder
# ---------------------------------------------------------------------------


def _sum_payoff(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float(df["payoff"].sum())


def build_alm_kpi_summary_from_tables(
    *,
    bvg_cashflows: pd.DataFrame,
    asset_cashflows: pd.DataFrame,
    combined_cashflows: pd.DataFrame,
    annual_cashflows: pd.DataFrame,
    funding_summary: pd.DataFrame,
) -> ALMKPISummary:
    """Build an ALMKPISummary from canonical analytics tables."""
    validate_cashflow_dataframe(bvg_cashflows)
    validate_cashflow_dataframe(asset_cashflows)
    validate_cashflow_dataframe(combined_cashflows)
    validate_annual_cashflow_dataframe(annual_cashflows)
    validate_funding_summary_dataframe(funding_summary)
    if funding_summary.empty:
        raise ValueError("funding_summary must not be empty")
    if len(funding_summary) != 1:
        raise ValueError("funding_summary must contain exactly one row")
    if annual_cashflows.empty:
        raise ValueError("annual_cashflows must not be empty")

    fs = funding_summary.iloc[0]
    years = [int(y) for y in annual_cashflows["reporting_year"]]
    currencies = set(annual_cashflows["currency"].unique().tolist())
    currency = currencies.pop() if len(currencies) == 1 else "CHF"

    return ALMKPISummary(
        initial_funding_ratio_percent=float(fs["initial_funding_ratio_percent"]),
        final_funding_ratio_percent=float(fs["final_funding_ratio_percent"]),
        minimum_funding_ratio_percent=float(fs["minimum_funding_ratio_percent"]),
        years_below_100_percent=int(fs["years_below_100_percent"]),
        total_bvg_cashflow=_sum_payoff(bvg_cashflows),
        total_actus_cashflow=_sum_payoff(asset_cashflows),
        total_combined_cashflow=_sum_payoff(combined_cashflows),
        first_year=min(years),
        final_year=max(years),
        liquidity_inflection_year=find_liquidity_inflection_year(
            annual_cashflows,
            use_structural=True,
        ),
        currency=currency,
    )


def build_alm_kpi_summary(analytics_result: object) -> ALMKPISummary:
    """Build an ALMKPISummary from an ALMAnalyticsResult."""
    from pk_alm.alm_analytics_engine.analytics_result import ALMAnalyticsResult

    if not isinstance(analytics_result, ALMAnalyticsResult):
        raise TypeError(
            f"analytics_result must be ALMAnalyticsResult, "
            f"got {type(analytics_result).__name__}"
        )
    return build_alm_kpi_summary_from_tables(
        bvg_cashflows=analytics_result.inputs.bvg_cashflows,
        asset_cashflows=analytics_result.inputs.asset_cashflows,
        combined_cashflows=analytics_result.combined_cashflows,
        annual_cashflows=analytics_result.annual_cashflows,
        funding_summary=analytics_result.funding_summary,
    )


def alm_kpi_summary_to_dataframe(summary: ALMKPISummary) -> pd.DataFrame:
    """Convert an ALMKPISummary into a one-row DataFrame with stable columns."""
    if not isinstance(summary, ALMKPISummary):
        raise TypeError(
            f"summary must be ALMKPISummary, got {type(summary).__name__}"
        )
    return pd.DataFrame(
        [summary.to_dict()],
        columns=list(ALM_KPI_SUMMARY_COLUMNS),
    )


def validate_alm_kpi_summary_dataframe(df: pd.DataFrame) -> bool:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    missing = [col for col in ALM_KPI_SUMMARY_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if list(df.columns) != list(ALM_KPI_SUMMARY_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(ALM_KPI_SUMMARY_COLUMNS)}"
        )
    if df.empty:
        return True
    for _, row in df.iterrows():
        ALMKPISummary(
            initial_funding_ratio_percent=row["initial_funding_ratio_percent"],
            final_funding_ratio_percent=row["final_funding_ratio_percent"],
            minimum_funding_ratio_percent=row["minimum_funding_ratio_percent"],
            years_below_100_percent=int(row["years_below_100_percent"]),
            total_bvg_cashflow=row["total_bvg_cashflow"],
            total_actus_cashflow=row["total_actus_cashflow"],
            total_combined_cashflow=row["total_combined_cashflow"],
            first_year=int(row["first_year"]),
            final_year=int(row["final_year"]),
            liquidity_inflection_year=(
                None
                if pd.isna(row["liquidity_inflection_year"])
                else int(row["liquidity_inflection_year"])
            ),
            currency=row["currency"],
        )
    return True


# ---------------------------------------------------------------------------
# Plot-ready tables
# ---------------------------------------------------------------------------


def build_cashflow_by_source_plot_table(
    combined_cashflows: pd.DataFrame,
) -> pd.DataFrame:
    """Build a plot-ready DataFrame summing payoff by reporting_year and source.

    The returned DataFrame has columns
    ``("reporting_year", "source", "total_payoff")`` and is sorted by
    reporting_year then source. The input is not mutated.
    """
    if not isinstance(combined_cashflows, pd.DataFrame):
        raise TypeError(
            f"combined_cashflows must be a pandas DataFrame, "
            f"got {type(combined_cashflows).__name__}"
        )
    validate_cashflow_dataframe(combined_cashflows)

    if combined_cashflows.empty:
        return pd.DataFrame(columns=list(CASHFLOW_BY_SOURCE_PLOT_COLUMNS))

    work = combined_cashflows.copy(deep=True)
    work["reporting_year"] = pd.to_datetime(work["time"]).dt.year.astype(int)
    grouped = (
        work.groupby(["reporting_year", "source"], as_index=False)["payoff"]
        .sum()
        .rename(columns={"payoff": "total_payoff"})
    )
    grouped = grouped.sort_values(
        ["reporting_year", "source"],
        ignore_index=True,
    )
    return grouped[list(CASHFLOW_BY_SOURCE_PLOT_COLUMNS)].reset_index(drop=True)


def build_net_cashflow_plot_table(
    annual_cashflows: pd.DataFrame,
) -> pd.DataFrame:
    """Build a plot-ready DataFrame projecting the existing annual cashflow buckets.

    The returned DataFrame is a column-subset copy of the input annual
    cashflows. The input is not mutated and no new financial assumptions
    are introduced.
    """
    if not isinstance(annual_cashflows, pd.DataFrame):
        raise TypeError(
            f"annual_cashflows must be a pandas DataFrame, "
            f"got {type(annual_cashflows).__name__}"
        )
    validate_annual_cashflow_dataframe(annual_cashflows)

    if annual_cashflows.empty:
        return pd.DataFrame(columns=list(NET_CASHFLOW_PLOT_COLUMNS))

    return (
        annual_cashflows[list(NET_CASHFLOW_PLOT_COLUMNS)]
        .copy(deep=True)
        .reset_index(drop=True)
    )
