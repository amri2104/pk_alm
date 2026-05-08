"""Validation report helpers for the ALM Analytics Engine."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from pk_alm.actus_asset_engine.deterministic import validate_asset_dataframe
from pk_alm.alm_analytics_engine.cashflows import validate_annual_cashflow_dataframe
from pk_alm.alm_analytics_engine.funding import validate_funding_ratio_dataframe
from pk_alm.alm_analytics_engine.funding_summary import (
    validate_funding_summary_dataframe,
)
from pk_alm.bvg_liability_engine.pension_logic.valuation import (
    validate_valuation_dataframe,
)
from pk_alm.cashflows.schema import validate_cashflow_dataframe

ALM_VALIDATION_REPORT_COLUMNS = (
    "check_name",
    "status",
    "observed",
    "expected",
    "severity",
    "notes",
)


def _row(
    *,
    check_name: str,
    status: str,
    observed: object,
    expected: object,
    severity: str,
    notes: str = "",
) -> dict[str, object]:
    return {
        "check_name": check_name,
        "status": status,
        "observed": str(observed),
        "expected": str(expected),
        "severity": severity,
        "notes": notes,
    }


def _check(
    rows: list[dict[str, object]],
    *,
    check_name: str,
    expected: object,
    fn: Callable[[], object],
    severity: str = "error",
) -> None:
    try:
        observed = fn()
    except Exception as exc:
        rows.append(
            _row(
                check_name=check_name,
                status="fail",
                observed=type(exc).__name__,
                expected=expected,
                severity=severity,
                notes=str(exc),
            )
        )
        return
    rows.append(
        _row(
            check_name=check_name,
            status="pass",
            observed=observed,
            expected=expected,
            severity="info",
        )
    )


def _assert_equal(observed: object, expected: object) -> object:
    if observed != expected:
        raise ValueError(f"{observed!r} != {expected!r}")
    return observed


def build_alm_validation_report(
    *,
    input_data: object,
    combined_cashflows: pd.DataFrame,
    annual_cashflows: pd.DataFrame,
    funding_ratio_trajectory: pd.DataFrame,
    funding_summary: pd.DataFrame,
    kpi_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Build a stable validation report for a completed analytics run."""
    rows: list[dict[str, object]] = []

    _check(
        rows,
        check_name="bvg_cashflow_schema_valid",
        expected=True,
        fn=lambda: validate_cashflow_dataframe(input_data.bvg_cashflows),
    )
    _check(
        rows,
        check_name="asset_cashflow_schema_valid",
        expected=True,
        fn=lambda: validate_cashflow_dataframe(input_data.asset_cashflows),
    )
    _check(
        rows,
        check_name="currency_consistency",
        expected=input_data.currency,
        fn=lambda: _currency_observed(input_data),
    )
    _check(
        rows,
        check_name="projection_year_alignment",
        expected=list(input_data.valuation_snapshots["projection_year"]),
        fn=lambda: _assert_equal(
            list(input_data.asset_snapshots["projection_year"]),
            list(input_data.valuation_snapshots["projection_year"]),
        ),
    )
    _check(
        rows,
        check_name="asset_snapshots_valid",
        expected=True,
        fn=lambda: validate_asset_dataframe(input_data.asset_snapshots),
    )
    _check(
        rows,
        check_name="valuation_snapshots_valid",
        expected=True,
        fn=lambda: validate_valuation_dataframe(input_data.valuation_snapshots),
    )
    _check(
        rows,
        check_name="combined_cashflows_schema_valid",
        expected=True,
        fn=lambda: validate_cashflow_dataframe(combined_cashflows),
    )
    _check(
        rows,
        check_name="combined_cashflows_row_count_equals_parts",
        expected=len(input_data.bvg_cashflows) + len(input_data.asset_cashflows),
        fn=lambda: _assert_equal(
            len(combined_cashflows),
            len(input_data.bvg_cashflows) + len(input_data.asset_cashflows),
        ),
    )
    _check(
        rows,
        check_name="annual_cashflows_valid",
        expected=True,
        fn=lambda: validate_annual_cashflow_dataframe(annual_cashflows),
    )
    _check(
        rows,
        check_name="funding_ratio_trajectory_valid",
        expected=True,
        fn=lambda: validate_funding_ratio_dataframe(funding_ratio_trajectory),
    )
    _check(
        rows,
        check_name="funding_summary_valid",
        expected=True,
        fn=lambda: validate_funding_summary_dataframe(funding_summary),
    )
    _check(
        rows,
        check_name="kpi_summary_no_missing",
        expected="no required missing values",
        fn=lambda: _kpi_missing_observed(kpi_summary),
    )

    report = pd.DataFrame(rows, columns=list(ALM_VALIDATION_REPORT_COLUMNS))
    validate_alm_validation_report_dataframe(report)
    return report


def _currency_observed(input_data: object) -> str:
    observed: set[str] = set()
    for frame in (
        input_data.bvg_cashflows,
        input_data.asset_cashflows,
        input_data.asset_snapshots,
        input_data.valuation_snapshots,
    ):
        if not frame.empty and "currency" in frame.columns:
            observed.update(str(value) for value in frame["currency"].unique())
    if observed != {input_data.currency}:
        raise ValueError(f"observed currencies {sorted(observed)}")
    return ",".join(sorted(observed))


def _kpi_missing_observed(kpi_summary: pd.DataFrame) -> str:
    if not isinstance(kpi_summary, pd.DataFrame):
        raise TypeError("kpi_summary must be a pandas DataFrame")
    required = [col for col in kpi_summary.columns if col != "liquidity_inflection_year"]
    if kpi_summary.empty:
        raise ValueError("kpi_summary must not be empty")
    if kpi_summary[required].isna().any().any():
        raise ValueError("kpi_summary has missing required values")
    return "ok"


def validate_alm_validation_report_dataframe(df: pd.DataFrame) -> bool:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    missing = [col for col in ALM_VALIDATION_REPORT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if list(df.columns) != list(ALM_VALIDATION_REPORT_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(ALM_VALIDATION_REPORT_COLUMNS)}"
        )
    valid_status = {"pass", "fail", "warning"}
    valid_severity = {"error", "warning", "info"}
    for idx, row in df.iterrows():
        if row["status"] not in valid_status:
            raise ValueError(f"row {idx}: invalid status {row['status']!r}")
        if row["severity"] not in valid_severity:
            raise ValueError(f"row {idx}: invalid severity {row['severity']!r}")
        for col in ALM_VALIDATION_REPORT_COLUMNS:
            if col in ("status", "severity"):
                continue
            if not isinstance(row[col], str):
                raise TypeError(f"row {idx}: {col} must be str")
    return True
