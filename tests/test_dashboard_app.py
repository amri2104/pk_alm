"""Tests for the Streamlit dashboard MVP."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from pk_alm.dashboard import runner as dashboard_runner

_REPO_ROOT = Path(__file__).resolve().parent.parent
_APP_PATH = _REPO_ROOT / "src" / "pk_alm" / "dashboard" / "app.py"
_DASHBOARD_DIR = _REPO_ROOT / "src" / "pk_alm" / "dashboard"


def _app_source() -> str:
    return _APP_PATH.read_text()


def test_dashboard_app_file_exists() -> None:
    assert _APP_PATH.exists()


def test_dashboard_title_sidebar_controls_tabs_and_session_state_are_declared() -> None:
    text = _app_source()

    assert "Enhanced Portfolio Analytics for Pension Funds" in text
    assert "ACTUS/AAL-based ALM cockpit" in text
    for label in (
        "scenario_name",
        "start_year",
        "horizon_years",
        "asset_mode",
        "target_funding_ratio",
        "technical_discount_rate",
        "active_crediting_rate",
        "annual_asset_return",
        "contribution_multiplier",
        "conversion_rate",
        "capital_withdrawal_fraction",
        "turnover_rate",
        "salary_growth_rate",
        "Run scenario",
    ):
        assert label in text or label in (_DASHBOARD_DIR / "controls.py").read_text()
    for tab_label in (
        "Overview",
        "Funding Ratio",
        "Cashflows",
        "Assets & Liabilities",
        "ACTUS Diagnostics",
        "Validation",
        "Export",
    ):
        assert tab_label in text
    assert 'st.session_state["dashboard_result"]' in text
    assert 'st.session_state["dashboard_params"]' in text


def test_dashboard_no_result_message_and_button_flow_are_declared() -> None:
    text = _app_source()

    assert "Configure scenario parameters in the sidebar and click Run scenario" in text
    assert "if run_clicked:" in text
    assert "Running BVG, ACTUS and ALM analytics..." in text
    assert "runner.run_dashboard_scenario(params)" in text


def test_dashboard_code_does_not_write_generated_outputs() -> None:
    combined = "\n".join(
        path.read_text()
        for path in sorted(_DASHBOARD_DIR.glob("*.py"))
    )

    assert "output_dir" not in combined
    assert "outputs/" not in combined
    assert ".to_csv(path" not in combined


def test_runner_maps_dashboard_params_to_full_alm(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    sentinel = object()

    def fake_run_full_alm_scenario(**kwargs):
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(
        dashboard_runner,
        "run_full_alm_scenario",
        fake_run_full_alm_scenario,
    )

    result = dashboard_runner.run_dashboard_scenario(
        {
            "scenario_name": "ui_case",
            "start_year": 2027,
            "horizon_years": 7,
            "asset_mode": "actus",
            "target_funding_ratio": 1.1,
            "technical_discount_rate": 0.02,
            "active_crediting_rate": 0.015,
            "annual_asset_return": 0.01,
            "contribution_multiplier": 1.5,
            "conversion_rate": 0.067,
            "capital_withdrawal_fraction": 0.3,
            "turnover_rate": 0.01,
            "salary_growth_rate": 0.005,
        }
    )

    assert result is sentinel
    assert calls == [
        {
            "scenario_id": "ui_case",
            "start_year": 2027,
            "horizon_years": 7,
            "target_funding_ratio": 1.1,
            "technical_interest_rate": 0.02,
            "active_interest_rate": 0.015,
            "annual_asset_return": 0.01,
            "contribution_multiplier": 1.5,
            "conversion_rate": 0.067,
            "capital_withdrawal_fraction": 0.3,
            "turnover_rate": 0.01,
            "salary_growth_rate": 0.005,
        }
    ]


def test_runner_rejects_unsupported_asset_mode() -> None:
    with pytest.raises(ValueError, match="asset_mode"):
        dashboard_runner.run_dashboard_scenario({"asset_mode": "deterministic"})


def _fake_analytics() -> SimpleNamespace:
    kpi = pd.DataFrame(
        [
            {
                "initial_funding_ratio_percent": 107.6,
                "final_funding_ratio_percent": 109.0,
                "minimum_funding_ratio_percent": 101.0,
                "years_below_100_percent": 0,
                "total_bvg_cashflow": -10.0,
                "total_actus_cashflow": 5.0,
                "total_combined_cashflow": -5.0,
                "first_year": 2026,
                "final_year": 2028,
                "liquidity_inflection_year": pd.NA,
                "currency": "CHF",
            }
        ]
    )
    funding = pd.DataFrame(
        {
            "projection_year": [0, 1],
            "asset_value": [107.6, 108.0],
            "total_stage1_liability": [100.0, 100.0],
            "funding_ratio": [1.076, 1.08],
            "funding_ratio_percent": [107.6, 108.0],
            "currency": ["CHF", "CHF"],
        }
    )
    annual = pd.DataFrame(
        {
            "reporting_year": [2026],
            "contribution_cashflow": [10.0],
            "pension_payment_cashflow": [-5.0],
            "capital_withdrawal_cashflow": [0.0],
            "other_cashflow": [0.0],
            "net_cashflow": [5.0],
            "structural_net_cashflow": [5.0],
            "cumulative_net_cashflow": [5.0],
            "cumulative_structural_net_cashflow": [5.0],
            "currency": ["CHF"],
        }
    )
    return SimpleNamespace(
        inputs=SimpleNamespace(target_funding_ratio=1.076),
        kpi_summary=kpi,
        funding_summary=kpi,
        funding_ratio_trajectory=funding,
        annual_cashflows=annual,
        cashflow_by_source_plot_table=pd.DataFrame(
            {
                "reporting_year": [2026, 2026],
                "source": ["BVG", "ACTUS"],
                "total_payoff": [-10.0, 5.0],
            }
        ),
        net_cashflow_plot_table=annual[
            [
                "reporting_year",
                "contribution_cashflow",
                "pension_payment_cashflow",
                "capital_withdrawal_cashflow",
                "other_cashflow",
                "net_cashflow",
                "structural_net_cashflow",
            ]
        ],
        combined_cashflows=pd.DataFrame(
            {
                "contractId": ["BVG", "ACTUS"],
                "time": pd.to_datetime(["2026-12-31", "2026-12-31"]),
                "type": ["PR", "IP"],
                "payoff": [-10.0, 5.0],
                "nominalValue": [0.0, 0.0],
                "currency": ["CHF", "CHF"],
                "source": ["BVG", "ACTUS"],
            }
        ),
        validation_report=pd.DataFrame(
            [
                {
                    "check_name": "ok",
                    "status": "pass",
                    "observed": "ok",
                    "expected": "ok",
                    "severity": "info",
                    "notes": "",
                }
            ]
        ),
    )


def _fake_result() -> SimpleNamespace:
    return SimpleNamespace(
        analytics_result=_fake_analytics(),
        aal_asset_result=SimpleNamespace(
            aal_version="fake",
            notes=("fake result",),
            event_summary=pd.DataFrame({"type": ["IP"], "count": [1]}),
            event_coverage_report=pd.DataFrame(),
            risk_factor_report=pd.DataFrame(),
            limitation_report=pd.DataFrame(),
        ),
    )


def test_optional_streamlit_apptest_initial_render_only() -> None:
    app_test_module = pytest.importorskip("streamlit.testing.v1")
    AppTest = app_test_module.AppTest

    app = AppTest.from_file(str(_APP_PATH)).run(timeout=10)

    assert not app.exception
    assert any("Enhanced Portfolio Analytics" in title.value for title in app.title)
    assert app.button
    assert any("Configure scenario parameters" in info.value for info in app.info)


def test_optional_streamlit_apptest_renders_fake_result(monkeypatch) -> None:
    app_test_module = pytest.importorskip("streamlit.testing.v1")
    AppTest = app_test_module.AppTest

    monkeypatch.setattr(
        dashboard_runner,
        "run_dashboard_scenario",
        lambda params: _fake_result(),
    )

    app = AppTest.from_file(str(_APP_PATH)).run(timeout=10)
    app.button[0].click().run(timeout=10)

    assert not app.exception
    assert any("Scenario run completed" in success.value for success in app.success)
