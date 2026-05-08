"""Sidebar controls for the Streamlit dashboard."""

from __future__ import annotations

from pk_alm.dashboard.runner import SUPPORTED_ASSET_MODES


def render_sidebar_controls(sidebar: object) -> tuple[dict[str, object], bool]:
    """Render sidebar widgets and return parameters plus run-click state."""
    sidebar.header("Scenario settings")
    params: dict[str, object] = {
        "scenario_name": sidebar.text_input(
            "scenario_name",
            value="dashboard_scenario",
        ),
        "start_year": sidebar.number_input(
            "start_year",
            min_value=2020,
            max_value=2050,
            value=2026,
            step=1,
        ),
        "horizon_years": sidebar.slider(
            "horizon_years",
            min_value=1,
            max_value=30,
            value=12,
            step=1,
        ),
        "asset_mode": sidebar.selectbox(
            "asset_mode",
            options=list(SUPPORTED_ASSET_MODES),
            index=0,
        ),
        "target_funding_ratio": sidebar.number_input(
            "target_funding_ratio",
            min_value=0.5,
            max_value=2.0,
            value=1.076,
            step=0.001,
            format="%.3f",
        ),
        "technical_discount_rate": sidebar.number_input(
            "technical_discount_rate",
            min_value=-0.05,
            max_value=0.20,
            value=0.0176,
            step=0.001,
            format="%.4f",
        ),
        "active_crediting_rate": sidebar.number_input(
            "active_crediting_rate",
            min_value=-0.05,
            max_value=0.20,
            value=0.0176,
            step=0.001,
            format="%.4f",
        ),
        "annual_asset_return": sidebar.number_input(
            "annual_asset_return",
            min_value=-1.0,
            max_value=1.0,
            value=0.0,
            step=0.005,
            format="%.4f",
        ),
    }

    with sidebar.expander("Advanced settings"):
        params["contribution_multiplier"] = sidebar.number_input(
            "contribution_multiplier",
            min_value=0.0,
            max_value=5.0,
            value=1.4,
            step=0.05,
            format="%.3f",
        )
        params["conversion_rate"] = sidebar.number_input(
            "conversion_rate",
            min_value=0.0,
            max_value=0.20,
            value=0.068,
            step=0.001,
            format="%.4f",
        )
        params["capital_withdrawal_fraction"] = sidebar.number_input(
            "capital_withdrawal_fraction",
            min_value=0.0,
            max_value=1.0,
            value=0.35,
            step=0.01,
            format="%.3f",
        )
        params["turnover_rate"] = sidebar.number_input(
            "turnover_rate",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.005,
            format="%.4f",
        )
        params["salary_growth_rate"] = sidebar.number_input(
            "salary_growth_rate",
            min_value=-0.10,
            max_value=0.20,
            value=0.0,
            step=0.001,
            format="%.4f",
        )

    run_clicked = sidebar.button("Run scenario", type="primary")
    return params, bool(run_clicked)

