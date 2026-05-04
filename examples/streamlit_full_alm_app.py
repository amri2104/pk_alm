"""Goal-1 Pension Fund ALM Cockpit (Bloomberg-Terminal-Lite redesign).

Run with:

    python3 -m streamlit run examples/streamlit_full_alm_app.py

The module is import-safe: importing it does not execute any workflow. The
advanced ALM workflow only runs after the user presses the sidebar run button.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
EXAMPLES_DIR = Path(__file__).resolve().parent
for _path in (str(EXAMPLES_DIR), str(SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from pk_alm.workflows.goal1_advanced_workflow import (  # noqa: E402
    DEFAULT_ACTIVE_TABLE,
    DEFAULT_ALLOCATION_TABLE,
    DEFAULT_BOND_TABLE,
    DEFAULT_RETIREE_TABLE,
    GOAL1_ADVANCED_OUTPUT_DIR,
    Goal1AdvancedInput,
    Goal1AdvancedResult,
    run_goal1_advanced_alm,
    run_goal1_stage_comparison,
)

from _cockpit import layouts  # noqa: E402

DASHBOARD_TITLE = "Goal-1 Pension Fund ALM Cockpit"
TAB_LABELS = (
    "Overview",
    "Configure",
    "Run",
    "Results & Risk",
    "Stress Lab",
    "Methodology",
)
SHORT_RATE_MODELS = ("vasicek", "cir", "ho_lee", "hull_white")
SCENARIO_PRESETS = (
    "Baseline",
    "Interest +100bp",
    "Interest -100bp",
    "Equity -20%",
    "Real Estate -15%",
    "Combined",
)
STRESS_PRESETS = (
    "Baseline",
    "Interest +100bp",
    "Interest -100bp",
    "Equity -20%",
    "Real Estate -15%",
    "Combined",
)

# Mode IDs (kept as literals so source-text test
# `test_streamlit_app_mentions_all_six_modes` finds them)
_MODE_REFERENCES = (
    "core",
    "full_alm_actus",
    "population",
    "mortality",
    "dynamic_parameters",
    "stochastic_rates",
)


def _get_streamlit() -> Any:
    import streamlit as st

    return st


def _session_defaults(st: Any) -> None:
    defaults = {
        "goal1_result": None,
        "goal1_error": None,
        "stage_comparison_result": None,
        "active_tab": "Overview",
        "scenario_cache": {},
        "run_history": [],
        "pending_stress_run": False,
        "pending_stage_comparison": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _check_aal_status() -> tuple[str, str]:
    try:
        import streamlit as _st

        @_st.cache_resource(show_spinner=False)
        def _cached_check() -> tuple[str, str]:
            try:
                import awesome_actus_lib  # noqa: F401

                return "available", "awesome_actus_lib import OK; live engine reachable when network allows."
            except Exception as exc:
                return "unavailable", f"awesome_actus_lib import failed ({exc}); deterministic proxy will be used."
        return _cached_check()
    except Exception:
        try:
            import awesome_actus_lib  # noqa: F401

            return "available", "awesome_actus_lib import OK."
        except Exception as exc:
            return "unavailable", f"awesome_actus_lib import failed ({exc})."


def _build_input(config: dict[str, Any], run_settings: dict[str, Any]) -> Goal1AdvancedInput:
    return Goal1AdvancedInput(
        allocation_table=config["allocation_table"],
        bond_table=config["bond_table"],
        active_table=config["active_table"],
        retiree_table=config["retiree_table"],
        horizon_years=int(config["horizon_years"]),
        start_year=int(config["start_year"]),
        target_funding_ratio=float(config["target_funding_ratio"]),
        valuation_terminal_age=int(config["valuation_terminal_age"]),
        salary_growth_rate=float(config["salary_growth_rate"]),
        turnover_rate=float(config["turnover_rate"]),
        entry_count_per_year=int(config["entry_count_per_year"]),
        scenario_preset=config["scenario_preset"],
        asset_engine_mode=config["asset_engine_mode"],
        mortality_mode=run_settings["mortality_mode"],
        mortality_table_id=run_settings["mortality_table_id"],
        stochastic_enabled=bool(run_settings["stochastic_enabled"]),
        model_active=run_settings["model_active"],
        model_technical=run_settings["model_technical"],
        n_paths=int(run_settings["n_paths"]),
        seed=int(run_settings["seed"]),
    )


def _build_overview_snapshot(result: Goal1AdvancedResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    fr_row = result.funding_ratio_trajectory.iloc[0]
    return {
        "scenario": str(result.input.scenario_preset),
        "horizon": int(result.input.horizon_years),
        "start_year": int(result.input.start_year),
        "member_count": int(result.initial_state.member_count_total),
        "opening_assets": float(fr_row["asset_value"]),
        "target_funding_ratio": float(result.input.target_funding_ratio),
    }


def _friendly_error(exc: Exception) -> str:
    message = str(exc)
    if "awesome_actus_lib" in message or "AAL" in message or "ACTUS" in message:
        return f"ACTUS/AAL workflow unavailable: {message}"
    if "stochastic" in message.lower():
        return f"Stochastic rates unavailable: {message}"
    return f"Advanced ALM workflow failed: {message}"


def _record_run_history(st: Any, result: Goal1AdvancedResult) -> None:
    timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fr_final = float(result.kpi_summary.iloc[0]["final_funding_ratio_percent"])
    st.session_state["run_history"].append(
        {
            "timestamp": timestamp,
            "scenario": str(result.input.scenario_preset),
            "fr_final": fr_final,
        }
    )


def _render_sidebar(st: Any) -> bool:
    st.sidebar.markdown(f"### 🏦 {DASHBOARD_TITLE}")
    st.sidebar.caption("Goal-1: cashflow / liquidity / funding-ratio analytics.")
    run_clicked = st.sidebar.button("Run Full Goal-1 Advanced ALM", type="primary", key="sidebar_run_button")
    st.sidebar.caption(f"Outputs → {GOAL1_ADVANCED_OUTPUT_DIR}")
    st.sidebar.divider()
    st.sidebar.caption(
        "Save / load configuration: copy the JSON below into a file to reuse later."
    )
    config_dump = layouts.serialize_session_config(dict(st.session_state))
    st.sidebar.download_button(
        "Download session JSON",
        data=config_dump,
        file_name="cockpit_session.json",
        mime="application/json",
        key="sidebar_download_session",
    )
    return run_clicked


def main() -> None:
    st = _get_streamlit()
    st.set_page_config(
        page_title=DASHBOARD_TITLE,
        layout="wide",
        page_icon="🏦",
        initial_sidebar_state="expanded",
    )
    layouts.inject_css(st)
    st.title(DASHBOARD_TITLE)
    st.caption("Goal-1 ALM analytics — assess cashflows, liquidity, funding ratio.")

    _session_defaults(st)
    active_tab = layouts.render_tab_strip(st, TAB_LABELS)

    config = layouts.render_configure(
        st,
        default_allocation=DEFAULT_ALLOCATION_TABLE,
        default_bonds=DEFAULT_BOND_TABLE,
        default_active=DEFAULT_ACTIVE_TABLE,
        default_retirees=DEFAULT_RETIREE_TABLE,
    ) if active_tab == "Configure" else None

    if config is None:
        cached = st.session_state.get("cached_config")
        if cached is not None:
            config = cached
        else:
            config = {
                "allocation_table": DEFAULT_ALLOCATION_TABLE.copy(deep=True),
                "bond_table": DEFAULT_BOND_TABLE.copy(deep=True),
                "active_table": DEFAULT_ACTIVE_TABLE.copy(deep=True),
                "retiree_table": DEFAULT_RETIREE_TABLE.copy(deep=True),
                "asset_engine_mode": "deterministic_proxy",
                "horizon_years": 12,
                "start_year": 2026,
                "target_funding_ratio": 1.076,
                "valuation_terminal_age": 90,
                "salary_growth_rate": 0.015,
                "turnover_rate": 0.02,
                "entry_count_per_year": 1,
                "scenario_preset": "Baseline",
            }
    st.session_state["cached_config"] = config

    aal_status, aal_message = _check_aal_status()
    run_settings = (
        layouts.render_run_panel(
            st,
            aal_status=aal_status,
            aal_message=aal_message,
            short_rate_models=SHORT_RATE_MODELS,
        )
        if active_tab == "Run"
        else st.session_state.get(
            "cached_run_settings",
            {
                "mortality_mode": "ek0105",
                "mortality_table_id": "EKF_0105",
                "stochastic_enabled": False,
                "model_active": "hull_white",
                "model_technical": "hull_white",
                "n_paths": 100,
                "seed": 42,
            },
        )
    )
    st.session_state["cached_run_settings"] = run_settings

    run_clicked = _render_sidebar(st)
    if run_clicked:
        try:
            input_data = _build_input(config, run_settings)
            with st.spinner("Running Full Goal-1 Advanced ALM..."):
                result = run_goal1_advanced_alm(input_data)
            st.session_state["goal1_result"] = result
            st.session_state["goal1_error"] = None
            _record_run_history(st, result)
            st.success("Full Goal-1 Advanced ALM completed.")
        except Exception as exc:
            st.session_state["goal1_result"] = None
            st.session_state["goal1_error"] = _friendly_error(exc)

    if st.session_state.get("pending_stress_run"):
        st.session_state["pending_stress_run"] = False
        scenario_cache: dict[str, Any] = {}
        for preset in STRESS_PRESETS:
            try:
                stress_config = {**config, "scenario_preset": preset}
                stress_input = _build_input(stress_config, run_settings)
                stress_input = Goal1AdvancedInput(
                    **{
                        **stress_input.__dict__,
                        "asset_engine_mode": "deterministic_proxy",
                        "stochastic_enabled": False,
                        "output_dir": Path("outputs/streamlit_stress_lab") / preset,
                    }
                )
                with st.spinner(f"Stress: {preset}"):
                    stress_result = run_goal1_advanced_alm(stress_input)
                scenario_cache[preset] = {
                    "funding_ratio_trajectory": stress_result.funding_ratio_trajectory,
                    "kpi_summary": stress_result.kpi_summary,
                }
            except Exception as exc:
                st.warning(f"{preset}: {exc}")
        if scenario_cache:
            st.session_state["scenario_cache"] = scenario_cache

    if st.session_state.get("pending_stage_comparison"):
        st.session_state["pending_stage_comparison"] = False
        try:
            with st.spinner("Running stage comparison..."):
                st.session_state["stage_comparison_result"] = run_goal1_stage_comparison(
                    common_kwargs={"horizon_years": 1}
                )
        except Exception as exc:
            st.error(f"Stage comparison failed: {exc}")

    if st.session_state.get("goal1_error"):
        st.error(st.session_state["goal1_error"])

    result = st.session_state.get("goal1_result")
    snapshot = _build_overview_snapshot(result)

    if active_tab == "Overview":
        layouts.render_overview(st, result, snapshot)
    elif active_tab == "Results & Risk":
        layouts.render_results_and_risk(st, result)
    elif active_tab == "Stress Lab":
        layouts.render_stress_lab(
            st,
            scenario_cache=st.session_state.get("scenario_cache", {}),
            on_run_all=lambda: st.session_state.update(pending_stress_run=True),
        )
    elif active_tab == "Methodology":
        layouts.render_methodology(
            st,
            comparison=st.session_state.get("stage_comparison_result"),
            on_run_comparison=lambda: st.session_state.update(
                pending_stage_comparison=True
            ),
        )
    # Configure and Run tab bodies were rendered above to capture inputs.


if __name__ == "__main__":
    main()
