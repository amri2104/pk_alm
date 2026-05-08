"""Plotly chart helpers for the dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def _empty_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=title, template="plotly_white")
    return fig


def render_funding_ratio_chart(analytics: object) -> go.Figure:
    df = analytics.funding_ratio_trajectory
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _empty_figure("Funding Ratio")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["projection_year"],
            y=df["funding_ratio_percent"],
            mode="lines+markers",
            name="Funding ratio",
        )
    )
    fig.add_hline(y=100.0, line_dash="dash", line_color="#6b7280")
    target = float(analytics.inputs.target_funding_ratio) * 100.0
    fig.add_hline(y=target, line_dash="dot", line_color="#2563eb")
    fig.update_layout(
        title="Funding Ratio",
        xaxis_title="Projection year",
        yaxis_title="Funding ratio (%)",
        template="plotly_white",
    )
    return fig


def render_cashflow_chart(analytics: object) -> go.Figure:
    df = analytics.cashflow_by_source_plot_table
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _empty_figure("Cashflows by Source")
    fig = go.Figure()
    for source, group in df.groupby("source", sort=True):
        fig.add_trace(
            go.Bar(
                x=group["reporting_year"],
                y=group["total_payoff"],
                name=str(source),
            )
        )
    fig.update_layout(
        title="Cashflows by Source",
        xaxis_title="Reporting year",
        yaxis_title="Cashflow",
        barmode="group",
        template="plotly_white",
    )
    return fig


def render_net_cashflow_chart(analytics: object) -> go.Figure:
    df = analytics.net_cashflow_plot_table
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _empty_figure("Net Cashflow")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["reporting_year"],
            y=df["net_cashflow"],
            name="Net cashflow",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["reporting_year"],
            y=df["structural_net_cashflow"],
            mode="lines+markers",
            name="Structural net cashflow",
        )
    )
    fig.update_layout(
        title="Net Cashflow",
        xaxis_title="Reporting year",
        yaxis_title="Cashflow",
        template="plotly_white",
    )
    return fig


def render_asset_liability_chart(analytics: object) -> go.Figure:
    df = analytics.funding_ratio_trajectory
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _empty_figure("Assets & Liabilities")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["projection_year"],
            y=df["asset_value"],
            mode="lines+markers",
            name="Assets",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["projection_year"],
            y=df["total_stage1_liability"],
            mode="lines+markers",
            name="Liabilities",
        )
    )
    fig.update_layout(
        title="Assets & Liabilities",
        xaxis_title="Projection year",
        yaxis_title="Value",
        template="plotly_white",
    )
    return fig

