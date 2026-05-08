"""Streamlit entrypoint for the PK ALM dashboard."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_src_path() -> None:
    src_path = Path(__file__).resolve().parents[2]
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


_bootstrap_src_path()

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from pk_alm.dashboard import charts, runner, tables  # noqa: E402
from pk_alm.dashboard.controls import render_sidebar_controls  # noqa: E402
from pk_alm.dashboard.formatting import (  # noqa: E402
    format_chf,
    format_int,
    format_percent,
    safe_scalar,
)
from pk_alm.dashboard.styles import dashboard_css  # noqa: E402

TITLE = "Enhanced Portfolio Analytics for Pension Funds"
SUBTITLE = (
    "ACTUS/AAL-based ALM cockpit for pension fund cashflows, funding ratios "
    "and liquidity analytics."
)
NO_RESULT_MESSAGE = (
    "Configure scenario parameters in the sidebar and click Run scenario to "
    "populate the dashboard."
)
TAB_LABELS = (
    "Overview",
    "Funding Ratio",
    "Cashflows",
    "Assets & Liabilities",
    "ACTUS Diagnostics",
    "Validation",
    "Export",
)


def _validation_label(validation_report: pd.DataFrame) -> str:
    if not isinstance(validation_report, pd.DataFrame) or validation_report.empty:
        return "unknown"
    statuses = set(validation_report["status"].astype(str))
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    return "pass"


def _render_overview(analytics: object) -> None:
    kpi = analytics.kpi_summary
    validation_status = _validation_label(analytics.validation_report)
    cols = st.columns(6)
    cols[0].metric(
        "Initial funding ratio",
        format_percent(safe_scalar(kpi, "initial_funding_ratio_percent")),
    )
    cols[1].metric(
        "Final funding ratio",
        format_percent(safe_scalar(kpi, "final_funding_ratio_percent")),
    )
    cols[2].metric(
        "Minimum funding ratio",
        format_percent(safe_scalar(kpi, "minimum_funding_ratio_percent")),
    )
    cols[3].metric(
        "Years below 100%",
        format_int(safe_scalar(kpi, "years_below_100_percent")),
    )
    cols[4].metric(
        "Liquidity inflection",
        format_int(safe_scalar(kpi, "liquidity_inflection_year")),
    )
    cols[5].metric("Validation status", validation_status)
    st.dataframe(analytics.kpi_summary, use_container_width=True)
    st.dataframe(analytics.funding_summary, use_container_width=True)


def _render_funding_ratio(analytics: object) -> None:
    st.plotly_chart(charts.render_funding_ratio_chart(analytics), use_container_width=True)
    st.dataframe(analytics.funding_ratio_trajectory, use_container_width=True)


def _render_cashflows(analytics: object) -> None:
    st.plotly_chart(charts.render_cashflow_chart(analytics), use_container_width=True)
    st.plotly_chart(charts.render_net_cashflow_chart(analytics), use_container_width=True)
    st.dataframe(analytics.annual_cashflows, use_container_width=True)
    st.dataframe(analytics.cashflow_by_source_plot_table, use_container_width=True)
    st.dataframe(analytics.net_cashflow_plot_table, use_container_width=True)


def _render_assets_liabilities(analytics: object) -> None:
    st.plotly_chart(charts.render_asset_liability_chart(analytics), use_container_width=True)
    st.dataframe(analytics.funding_ratio_trajectory, use_container_width=True)


def _render_actus_diagnostics(result: object) -> None:
    aal_result = getattr(result, "aal_asset_result", None)
    if aal_result is None:
        st.info("No ACTUS diagnostics are available for this result.")
        return

    st.write(f"AAL version: {getattr(aal_result, 'aal_version', 'unknown')}")
    notes = getattr(aal_result, "notes", ())
    if notes:
        st.write("Notes")
        for note in notes:
            st.write(f"- {note}")

    rendered = False
    for label, attr in (
        ("Event summary", "event_summary"),
        ("Event coverage report", "event_coverage_report"),
        ("Risk factor report", "risk_factor_report"),
        ("Limitation report", "limitation_report"),
    ):
        frame = getattr(aal_result, attr, None)
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            st.subheader(label)
            st.dataframe(frame, use_container_width=True)
            rendered = True

    if not rendered:
        st.info("No ACTUS diagnostics tables are available for this result.")


def _render_validation(analytics: object) -> None:
    report = analytics.validation_report
    status = _validation_label(report)
    if status == "fail":
        st.error("Validation contains failing checks.")
    elif status == "warning":
        st.warning("Validation contains warnings.")
    else:
        st.success("Validation passed.")
    st.dataframe(report, use_container_width=True)


def _render_export(analytics: object) -> None:
    for name, frame in tables.analytics_export_frames(analytics).items():
        st.download_button(
            label=f"Download {name}.csv",
            data=tables.dataframe_to_csv_bytes(frame),
            file_name=f"{name}.csv",
            mime="text/csv",
            key=f"download_{name}",
        )
    st.caption(f"Total combined cashflow: {format_chf(safe_scalar(analytics.kpi_summary, 'total_combined_cashflow'))}")


def _render_result(result: object) -> None:
    analytics = result.analytics_result
    tabs = st.tabs(list(TAB_LABELS))
    with tabs[0]:
        _render_overview(analytics)
    with tabs[1]:
        _render_funding_ratio(analytics)
    with tabs[2]:
        _render_cashflows(analytics)
    with tabs[3]:
        _render_assets_liabilities(analytics)
    with tabs[4]:
        _render_actus_diagnostics(result)
    with tabs[5]:
        _render_validation(analytics)
    with tabs[6]:
        _render_export(analytics)


def main() -> None:
    st.set_page_config(
        page_title=TITLE,
        layout="wide",
    )
    st.markdown(dashboard_css(), unsafe_allow_html=True)
    st.title(TITLE)
    st.markdown(f'<div class="pk-alm-subtitle">{SUBTITLE}</div>', unsafe_allow_html=True)

    params, run_clicked = render_sidebar_controls(st.sidebar)

    if run_clicked:
        with st.spinner("Running BVG, ACTUS and ALM analytics..."):
            try:
                result = runner.run_dashboard_scenario(params)
            except Exception as exc:
                st.error(f"Scenario run failed: {exc}")
            else:
                st.session_state["dashboard_result"] = result
                st.session_state["dashboard_params"] = dict(params)
                st.success("Scenario run completed.")

    result = st.session_state.get("dashboard_result")
    if result is None:
        st.info(NO_RESULT_MESSAGE)
        return

    _render_result(result)


if __name__ == "__main__":
    main()
