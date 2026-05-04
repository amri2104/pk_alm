"""Plotly chart factories for the Goal-1 cockpit.

All factories return ``plotly.graph_objects.Figure``. They tolerate empty
DataFrames by returning a figure with a "No data" annotation. Plotly is
imported lazily inside each factory so module import stays cheap.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import theme


def _empty_figure(title: str = "") -> Any:
    import plotly.graph_objects as go

    theme.cockpit_template()
    fig = go.Figure()
    fig.update_layout(template="cockpit", title=title)
    fig.add_annotation(
        text="No data",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(color=theme.MUTED, size=14),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def funding_ratio_chart(
    df: pd.DataFrame,
    *,
    target_funding_ratio: float = 1.076,
    title: str = "Funding ratio trajectory",
) -> Any:
    import plotly.graph_objects as go

    theme.cockpit_template()
    if df is None or df.empty:
        return _empty_figure(title)

    work = df.sort_values("projection_year")
    fig = go.Figure()

    y_min = float(min(work["funding_ratio_percent"].min(), 80.0))
    y_max = float(max(work["funding_ratio_percent"].max(), 130.0))
    fig.add_hrect(
        y0=y_min - 5, y1=theme.FR_RED, fillcolor=theme.CORAL, opacity=0.08, line_width=0,
    )
    fig.add_hrect(
        y0=theme.FR_RED, y1=theme.FR_AMBER, fillcolor=theme.AMBER, opacity=0.08, line_width=0,
    )
    fig.add_hrect(
        y0=theme.FR_AMBER, y1=theme.FR_GREEN, fillcolor=theme.AMBER, opacity=0.05, line_width=0,
    )
    fig.add_hrect(
        y0=theme.FR_GREEN, y1=y_max + 5, fillcolor=theme.TEAL, opacity=0.08, line_width=0,
    )

    fig.add_hline(
        y=100.0,
        line=dict(color=theme.CORAL, dash="dash", width=1),
        annotation_text="100%",
        annotation_position="bottom right",
        annotation_font=dict(color=theme.CORAL, size=10),
    )
    target_pct = target_funding_ratio * 100.0
    fig.add_hline(
        y=target_pct,
        line=dict(color=theme.GOLD, dash="dot", width=1),
        annotation_text=f"target {target_pct:.1f}%",
        annotation_position="top right",
        annotation_font=dict(color=theme.GOLD, size=10),
    )

    fig.add_trace(
        go.Scatter(
            x=work["projection_year"],
            y=work["funding_ratio_percent"],
            mode="lines+markers",
            line=dict(color=theme.TEAL, width=2.5),
            marker=dict(color=theme.TEAL, size=7, line=dict(color=theme.BG, width=1)),
            name="Funding ratio",
            hovertemplate="Year %{x}<br>Funding ratio: %{y:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(
        template="cockpit",
        title=title,
        xaxis_title="Projection year",
        yaxis_title="Funding ratio (%)",
        showlegend=False,
        height=420,
    )
    fig.update_yaxes(range=[y_min - 5, y_max + 5])
    return fig


def net_cashflow_chart(
    df: pd.DataFrame,
    *,
    title: str = "Net cashflow timeline",
) -> Any:
    import plotly.graph_objects as go

    theme.cockpit_template()
    if df is None or df.empty:
        return _empty_figure(title)

    work = df.sort_values("reporting_year")
    bar_colors = [
        theme.TEAL if v >= 0 else theme.CORAL for v in work["net_cashflow"]
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=work["reporting_year"],
            y=work["net_cashflow"],
            marker_color=bar_colors,
            name="Net cashflow",
            hovertemplate="Year %{x}<br>Net: %{y:,.0f} CHF<extra></extra>",
        )
    )
    if "structural_net_cashflow" in work.columns:
        fig.add_trace(
            go.Scatter(
                x=work["reporting_year"],
                y=work["structural_net_cashflow"],
                mode="lines+markers",
                line=dict(color=theme.GOLD, width=2),
                marker=dict(color=theme.GOLD, size=6),
                name="Structural net",
                hovertemplate="Year %{x}<br>Structural: %{y:,.0f} CHF<extra></extra>",
            )
        )

    # Inflection uses structural net (contributions - pensions, ex-investment)
    # so it matches the KPI card semantics and reflects demographic stress.
    inflection_signal = (
        "structural_net_cashflow" if "structural_net_cashflow" in work.columns
        else "net_cashflow"
    )
    negatives = work[work[inflection_signal] < 0]
    if not negatives.empty:
        inflection = int(negatives.iloc[0]["reporting_year"])
        fig.add_vline(
            x=inflection,
            line=dict(color=theme.AMBER, dash="dash", width=1),
            annotation_text=f"Structural inflection ({inflection})",
            annotation_position="top left",
            annotation_font=dict(color=theme.AMBER, size=10),
        )

    fig.update_layout(
        template="cockpit",
        title=title,
        xaxis_title="Reporting year",
        yaxis_title="Cashflow (CHF)",
        barmode="overlay",
        height=340,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def cashflow_by_source_chart(
    df: pd.DataFrame,
    *,
    title: str = "Cashflow by source",
) -> Any:
    import plotly.graph_objects as go

    theme.cockpit_template()
    if df is None or df.empty:
        return _empty_figure(title)

    pivot = (
        df.pivot_table(
            index="reporting_year",
            columns="source",
            values="total_payoff",
            aggfunc="sum",
            fill_value=0.0,
        )
        .sort_index()
    )
    fig = go.Figure()
    for column in pivot.columns:
        color = theme.SOURCE_COLORS.get(str(column).upper(), theme.MUTED)
        fig.add_trace(
            go.Scatter(
                x=pivot.index,
                y=pivot[column],
                mode="lines",
                stackgroup="cf",
                line=dict(color=color, width=0.5),
                fillcolor=color,
                opacity=0.85,
                name=str(column),
                hovertemplate=f"{column}<br>Year %{{x}}<br>%{{y:,.0f}} CHF<extra></extra>",
            )
        )
    fig.update_layout(
        template="cockpit",
        title=title,
        xaxis_title="Reporting year",
        yaxis_title="Total payoff (CHF)",
        height=340,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def assets_vs_liabilities_chart(
    df: pd.DataFrame,
    *,
    title: str = "Assets vs Liabilities",
) -> Any:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    theme.cockpit_template()
    if df is None or df.empty:
        return _empty_figure(title)

    work = df.sort_values("projection_year")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=work["projection_year"],
            y=work["asset_value"],
            mode="lines",
            fill="tozeroy",
            line=dict(color=theme.TEAL, width=2),
            fillcolor="rgba(38, 198, 168, 0.15)",
            name="Assets",
            hovertemplate="Year %{x}<br>Assets: %{y:,.0f} CHF<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=work["projection_year"],
            y=work["total_stage1_liability"],
            mode="lines",
            fill="tozeroy",
            line=dict(color=theme.CORAL, width=2),
            fillcolor="rgba(229, 72, 77, 0.10)",
            name="Liabilities",
            hovertemplate="Year %{x}<br>Liabilities: %{y:,.0f} CHF<extra></extra>",
        ),
        secondary_y=False,
    )
    surplus = work["asset_value"] - work["total_stage1_liability"]
    fig.add_trace(
        go.Scatter(
            x=work["projection_year"],
            y=surplus,
            mode="lines+markers",
            line=dict(color=theme.GOLD, width=1.5, dash="dot"),
            marker=dict(color=theme.GOLD, size=5),
            name="Surplus / deficit",
            hovertemplate="Year %{x}<br>Surplus: %{y:,.0f} CHF<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.update_layout(
        template="cockpit",
        title=title,
        xaxis_title="Projection year",
        height=340,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text="Value (CHF)", secondary_y=False)
    fig.update_yaxes(title_text="Surplus (CHF)", secondary_y=True, showgrid=False)
    return fig


def scenario_overlay_chart(
    scenarios: dict[str, pd.DataFrame],
    *,
    metric: str = "funding_ratio_percent",
    x_col: str = "projection_year",
    title: str = "Scenario comparison",
) -> Any:
    import plotly.graph_objects as go

    theme.cockpit_template()
    valid = {
        name: df for name, df in scenarios.items()
        if isinstance(df, pd.DataFrame) and not df.empty and metric in df.columns
    }
    if not valid:
        return _empty_figure(title)

    palette = [theme.TEAL, theme.GOLD, theme.AMBER, theme.CORAL, "#7AA2F7", "#BB9AF7"]
    fig = go.Figure()
    for idx, (name, df) in enumerate(valid.items()):
        work = df.sort_values(x_col)
        is_baseline = name.lower().startswith("baseline")
        color = theme.TEAL if is_baseline else palette[(idx + 1) % len(palette)]
        width = 3 if is_baseline else 1.8
        fig.add_trace(
            go.Scatter(
                x=work[x_col],
                y=work[metric],
                mode="lines+markers",
                name=name,
                line=dict(color=color, width=width),
                marker=dict(color=color, size=5),
                hovertemplate=f"{name}<br>%{{x}}: %{{y:.1f}}<extra></extra>",
            )
        )
    fig.update_layout(
        template="cockpit",
        title=title,
        xaxis_title=x_col.replace("_", " ").title(),
        yaxis_title=metric.replace("_", " ").title(),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def stochastic_summary_chart(
    summary_df: pd.DataFrame | None,
    *,
    title: str = "Stochastic terminal funding ratio",
) -> Any:
    import plotly.graph_objects as go

    theme.cockpit_template()
    if summary_df is None or summary_df.empty:
        return _empty_figure(title)

    row = summary_df.iloc[0]
    p5 = float(row.get("final_p5", 0.0))
    p50 = float(row.get("final_p50", 0.0))
    p95 = float(row.get("final_p95", 0.0))
    var5 = float(row.get("VaR_5", 0.0))
    es5 = float(row.get("ES_5", 0.0))
    p_under = float(row.get("P_underfunding", 0.0))

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=["P5", "P50", "P95"],
            y=[p5, p50, p95],
            marker_color=[theme.CORAL, theme.GOLD, theme.TEAL],
            text=[f"{p5:.2f}", f"{p50:.2f}", f"{p95:.2f}"],
            textposition="outside",
            textfont=dict(color=theme.FG),
            hovertemplate="%{x}: %{y:.3f}<extra></extra>",
            showlegend=False,
        )
    )
    fig.add_annotation(
        xref="paper", yref="paper", x=0.02, y=0.98,
        text=(
            f"VaR(5%): <b>{var5:.3f}</b><br>"
            f"ES(5%): <b>{es5:.3f}</b><br>"
            f"P(underfunding): <b>{p_under:.1%}</b>"
        ),
        showarrow=False,
        align="left",
        font=dict(color=theme.FG, size=12),
        bgcolor=theme.PANEL,
        bordercolor=theme.GRID,
        borderwidth=1,
        borderpad=8,
    )
    fig.update_layout(
        template="cockpit",
        title=title,
        yaxis_title="Funding ratio",
        height=340,
    )
    return fig


def validation_checks_table(df: pd.DataFrame, *, title: str = "Validation checks") -> Any:
    import plotly.graph_objects as go

    theme.cockpit_template()
    if df is None or df.empty:
        return _empty_figure(title)

    statuses = [
        "PASS" if bool(p) else "FAIL" for p in df["passed"]
    ]
    status_colors = [
        theme.TEAL if s == "PASS" else theme.CORAL for s in statuses
    ]
    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=["Metric", "Value", "Benchmark", "Status"],
                    fill_color=theme.BG,
                    font=dict(color=theme.GOLD, size=12),
                    align="left",
                    line_color=theme.GRID,
                ),
                cells=dict(
                    values=[
                        df["metric"].astype(str),
                        [f"{float(v):,.4f}" for v in df["value"]],
                        df["benchmark"].astype(str),
                        statuses,
                    ],
                    fill_color=[theme.PANEL, theme.PANEL, theme.PANEL, status_colors],
                    font=dict(color=[theme.FG, theme.FG, theme.MUTED, theme.BG], size=11),
                    align="left",
                    line_color=theme.GRID,
                    height=28,
                ),
            )
        ]
    )
    fig.update_layout(
        template="cockpit",
        title=title,
        height=max(180, 60 + 32 * len(df)),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def allocation_donut_chart(
    df: pd.DataFrame, *, title: str = "Asset allocation"
) -> Any:
    import plotly.graph_objects as go

    theme.cockpit_template()
    if df is None or df.empty or "asset_class" not in df.columns or "weight" not in df.columns:
        return _empty_figure(title)

    palette = {
        "bonds": theme.GOLD,
        "equities": theme.TEAL,
        "real_estate": theme.AMBER,
        "cash": theme.MUTED,
        "alternatives": theme.CORAL,
    }
    colors = [palette.get(str(c).lower(), theme.MUTED) for c in df["asset_class"]]
    fig = go.Figure(
        data=[
            go.Pie(
                labels=df["asset_class"],
                values=df["weight"],
                hole=0.55,
                marker=dict(colors=colors, line=dict(color=theme.BG, width=2)),
                textinfo="label+percent",
                textfont=dict(color=theme.FG, size=11),
                hovertemplate="%{label}<br>%{value:.1%}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        template="cockpit",
        title=title,
        height=320,
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig
