"""Tab body renderers for the Goal-1 cockpit."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import pandas as pd

from . import charts, kpi_cards, theme

_CSS_PATH = Path(__file__).parent / "cockpit.css"


def inject_css(st: Any) -> None:
    try:
        css_text = _CSS_PATH.read_text(encoding="utf-8")
    except OSError:
        css_text = ""
    if css_text:
        st.markdown(f"<style>{css_text}</style>", unsafe_allow_html=True)


def render_tab_strip(st: Any, labels: tuple[str, ...]) -> str:
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = labels[0]
    current = st.session_state["active_tab"]
    if current not in labels:
        current = labels[0]
        st.session_state["active_tab"] = current
    selected = st.radio(
        "Active section",
        labels,
        index=labels.index(current),
        horizontal=True,
        label_visibility="collapsed",
        key="tab_strip_radio",
    )
    if selected != st.session_state["active_tab"]:
        st.session_state["active_tab"] = selected
    return selected


def section_title(st: Any, text: str) -> None:
    st.markdown(
        f'<div class="section-title">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_empty_state(
    st: Any,
    *,
    title: str = "No run yet",
    body: str = "Configure your fund inputs, then trigger a run.",
    cta_label: str = "Go to Run tab",
    target_tab: str = "Run",
    key: str = "empty_state_cta",
) -> None:
    st.markdown(
        f'<div class="empty-state">'
        f'<div class="empty-state-title">▶ {html.escape(title)}</div>'
        f'<div class="empty-state-body">{html.escape(body)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    st.button(
        cta_label,
        key=key,
        on_click=lambda: st.session_state.update(active_tab=target_tab),
    )


def _format_chf(value: float) -> str:
    return f"{value:,.0f} CHF"


def _format_pct(value: float, *, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def _format_pct_decimal(value: float, *, decimals: int = 2) -> str:
    return f"{value * 100:.{decimals}f}%"


def render_snapshot_panel(
    st: Any,
    *,
    scenario: str,
    horizon: int,
    start_year: int,
    member_count: int,
    opening_assets: float,
    target_funding_ratio: float,
) -> None:
    rows = [
        ("Scenario", html.escape(scenario)),
        ("Horizon", f"{horizon} years"),
        ("Start year", str(start_year)),
        ("Members", f"{member_count:,}"),
        ("Opening assets", _format_chf(opening_assets)),
        ("Target FR", _format_pct(target_funding_ratio * 100, decimals=1)),
    ]
    body = "".join(
        f'<div class="snapshot-row">'
        f'<span class="snapshot-label">{label}</span>'
        f'<span class="snapshot-value">{value}</span>'
        f"</div>"
        for label, value in rows
    )
    st.markdown(
        f'<div class="snapshot-panel">'
        f'<div class="section-title">Fund snapshot</div>'
        f"{body}</div>",
        unsafe_allow_html=True,
    )


def _kpi_specs(result: Any, *, full: bool = False) -> list[kpi_cards.KpiSpec]:
    if result is None:
        base = [
            kpi_cards.KpiSpec("Funding ratio (current)", "—", "Run to populate", "neutral"),
            kpi_cards.KpiSpec("Net cashflow Y1", "—", "Run to populate", "neutral"),
            kpi_cards.KpiSpec("Structural inflection", "—", "Run to populate", "neutral"),
            kpi_cards.KpiSpec("Underfunding prob", "—", "Run to populate", "neutral"),
        ]
        if not full:
            return base
        return base + [
            kpi_cards.KpiSpec("Funding ratio (final)", "—", "Run to populate", "neutral"),
            kpi_cards.KpiSpec("Funding ratio (minimum)", "—", "Run to populate", "neutral"),
            kpi_cards.KpiSpec("Income yield", "—", "Run to populate", "neutral"),
            kpi_cards.KpiSpec("Liability gap (terminal)", "—", "Run to populate", "neutral"),
        ]
    row = result.kpi_summary.iloc[0]
    fr_current = float(row["current_funding_ratio_percent"])
    fr_final = float(row["final_funding_ratio_percent"])
    fr_min = float(row["minimum_funding_ratio_percent"])
    net_cf = float(row["net_cashflow_current_year"])
    inflection = row["liquidity_inflection_year"]
    inflection_value = None if pd.isna(inflection) else int(inflection)
    underfunding = row.get("underfunding_probability")
    underfunding_value = None if underfunding is None or pd.isna(underfunding) else float(underfunding)
    income_yield = float(row["income_yield"])
    pension_loss = float(row["pensionierungsverlust"])

    primary = [
        kpi_cards.KpiSpec(
            "Funding ratio (current)",
            _format_pct(fr_current, decimals=1),
            f"target {float(result.input.target_funding_ratio) * 100:.1f}%",
            kpi_cards.funding_ratio_status(fr_current),
        ),
        kpi_cards.KpiSpec(
            "Net cashflow Y1",
            _format_chf(net_cf),
            "incl. investment income",
            kpi_cards.cashflow_status(net_cf),
        ),
        kpi_cards.KpiSpec(
            "Structural inflection",
            "none in horizon" if inflection_value is None else str(inflection_value),
            "first year structural net < 0",
            kpi_cards.liquidity_status(inflection_value),
        ),
        kpi_cards.KpiSpec(
            "Underfunding prob",
            "n/a" if underfunding_value is None else _format_pct_decimal(underfunding_value, decimals=1),
            "stochastic ever-below-100%",
            kpi_cards.underfunding_status(underfunding_value),
        ),
    ]
    if not full:
        return primary

    secondary = [
        kpi_cards.KpiSpec(
            "Funding ratio (final)",
            _format_pct(fr_final, decimals=1),
            "year horizon",
            kpi_cards.funding_ratio_status(fr_final),
        ),
        kpi_cards.KpiSpec(
            "Funding ratio (minimum)",
            _format_pct(fr_min, decimals=1),
            "worst trajectory point",
            kpi_cards.funding_ratio_status(fr_min),
        ),
        kpi_cards.KpiSpec(
            "Income yield",
            _format_pct_decimal(income_yield, decimals=2),
            "income / opening assets",
            "neutral",
        ),
        kpi_cards.KpiSpec(
            "Liability gap (terminal)",
            _format_chf(pension_loss),
            "PV - residual capital",
            "neutral",
        ),
    ]
    return primary + secondary


def render_overview(st: Any, result: Any, snapshot: dict[str, Any] | None) -> None:
    section_title(st, "Cockpit overview")
    kpi_cards.render_kpi_grid(st, _kpi_specs(result), cols=4)

    if result is None:
        render_empty_state(
            st,
            title="Run to populate cockpit",
            body=(
                "Defaults are calibrated to Complementa-2024 sector averages. "
                "Click Run to launch a baseline workflow, or visit Configure first."
            ),
            cta_label="Go to Run",
            target_tab="Run",
            key="overview_empty_cta",
        )
        return

    target_fr = float(result.input.target_funding_ratio)
    left, right = st.columns([3, 1])
    with left:
        st.plotly_chart(
            charts.funding_ratio_chart(
                result.funding_ratio_trajectory,
                target_funding_ratio=target_fr,
            ),
            use_container_width=True,
            theme=None,
        )
    with right:
        if snapshot:
            render_snapshot_panel(st, **snapshot)

    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(
            charts.net_cashflow_chart(result.net_cashflow),
            use_container_width=True,
            theme=None,
        )
    with col_b:
        st.plotly_chart(
            charts.assets_vs_liabilities_chart(result.funding_ratio_trajectory),
            use_container_width=True,
            theme=None,
        )


def render_configure(
    st: Any,
    *,
    default_allocation: pd.DataFrame,
    default_bonds: pd.DataFrame,
    default_active: pd.DataFrame,
    default_retirees: pd.DataFrame,
) -> dict[str, Any]:
    section_title(st, "Configure inputs")
    sub_tabs = st.tabs(
        ["Allocation", "Bond ladder", "Active cohorts", "Retirees", "Assumptions"]
    )

    with sub_tabs[0]:
        st.caption("Asset allocation weights — must sum to 1.0.")
        upload = st.file_uploader("Upload allocation CSV", type=["csv"], key="allocation_upload")
        allocation = pd.read_csv(upload) if upload else default_allocation.copy(deep=True)
        allocation = st.data_editor(
            allocation,
            num_rows="dynamic",
            width="stretch",
            key="allocation_editor",
        )
        try:
            st.plotly_chart(
                charts.allocation_donut_chart(allocation),
                use_container_width=True,
                theme=None,
            )
        except Exception:
            pass

        st.caption("Asset engine — ACTUS uses public AAL server when reachable.")
        engine_label = st.selectbox(
            "Asset engine",
            ("ACTUS / AAL live engine", "Deterministic proxy for local testing"),
            index=0,
            key="asset_engine_select",
        )
        asset_engine_mode = (
            "actus" if engine_label.startswith("ACTUS") else "deterministic_proxy"
        )

    with sub_tabs[1]:
        st.caption("PAM bond ladder — rows scaled to bond bucket weight.")
        bond_upload = st.file_uploader("Upload bond CSV", type=["csv"], key="bond_upload")
        bonds = pd.read_csv(bond_upload) if bond_upload else default_bonds.copy(deep=True)
        bonds = st.data_editor(
            bonds, num_rows="dynamic", width="stretch", key="bond_editor"
        )

    with sub_tabs[2]:
        active_upload = st.file_uploader(
            "Upload active cohorts CSV", type=["csv"], key="active_upload"
        )
        active = pd.read_csv(active_upload) if active_upload else default_active.copy(deep=True)
        active = st.data_editor(
            active, num_rows="dynamic", width="stretch", key="active_editor"
        )

    with sub_tabs[3]:
        retiree_upload = st.file_uploader(
            "Upload retiree cohorts CSV", type=["csv"], key="retiree_upload"
        )
        retirees = (
            pd.read_csv(retiree_upload) if retiree_upload else default_retirees.copy(deep=True)
        )
        retirees = st.data_editor(
            retirees, num_rows="dynamic", width="stretch", key="retiree_editor"
        )

    with sub_tabs[4]:
        st.caption("Scenario assumptions — scalars feed the workflow directly.")
        cols = st.columns(3)
        with cols[0]:
            horizon_years = st.number_input("horizon_years", 0, 40, 12, 1)
            start_year = st.number_input("start_year", 2000, 2100, 2026, 1)
            target_funding_ratio = st.number_input(
                "target_funding_ratio", 0.01, 3.0, 1.076, 0.001, format="%.3f"
            )
        with cols[1]:
            valuation_terminal_age = st.number_input(
                "valuation_terminal_age", 65, 120, 90, 1
            )
            salary_growth_rate = st.number_input(
                "salary_growth_rate", 0.0, 0.2, 0.015, 0.001, format="%.3f"
            )
            turnover_rate = st.number_input(
                "turnover_rate", 0.0, 1.0, 0.02, 0.005, format="%.3f"
            )
        with cols[2]:
            entry_count_per_year = st.number_input("entry_count_per_year", 0, 100, 1, 1)
            scenario_preset = st.selectbox(
                "Scenario preset",
                (
                    "Baseline",
                    "Interest +100bp",
                    "Interest -100bp",
                    "Equity -20%",
                    "Real Estate -15%",
                    "Combined",
                ),
                index=0,
            )

    return {
        "allocation_table": allocation,
        "bond_table": bonds,
        "active_table": active,
        "retiree_table": retirees,
        "asset_engine_mode": asset_engine_mode,
        "horizon_years": horizon_years,
        "start_year": start_year,
        "target_funding_ratio": target_funding_ratio,
        "valuation_terminal_age": valuation_terminal_age,
        "salary_growth_rate": salary_growth_rate,
        "turnover_rate": turnover_rate,
        "entry_count_per_year": entry_count_per_year,
        "scenario_preset": scenario_preset,
    }


def render_run_panel(
    st: Any,
    *,
    aal_status: str,
    aal_message: str,
    short_rate_models: tuple[str, ...],
) -> dict[str, Any]:
    section_title(st, "Run controls")
    pill_class = {
        "ok": "status-pill-ok",
        "available": "status-pill-ok",
        "warn": "status-pill-warn",
        "unavailable": "status-pill-warn",
        "alert": "status-pill-alert",
    }.get(aal_status, "status-pill-neutral")
    st.markdown(
        f'<div class="snapshot-panel">'
        f'<div class="snapshot-row">'
        f'<span class="snapshot-label">AAL / ACTUS server</span>'
        f'<span class="status-pill {pill_class}">{html.escape(aal_status)}</span>'
        f"</div>"
        f'<div class="muted-caption">{html.escape(aal_message)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    cols = st.columns(2)
    with cols[0]:
        from pk_alm.bvg_liability_engine.actuarial_assumptions.mortality import (
            DEFAULT_EK0105_TABLE_ID,
            MORTALITY_MODE_EK0105,
            MORTALITY_MODE_OFF,
            SUPPORTED_EK0105_TABLE_IDS,
        )

        mortality_mode = st.selectbox(
            "mortality_mode",
            (MORTALITY_MODE_EK0105, MORTALITY_MODE_OFF),
            index=0,
            key="run_mortality_mode",
        )
        mortality_table_id = st.selectbox(
            "mortality_table",
            SUPPORTED_EK0105_TABLE_IDS,
            index=SUPPORTED_EK0105_TABLE_IDS.index(DEFAULT_EK0105_TABLE_ID),
            key="run_mortality_table",
        )
    with cols[1]:
        stochastic_enabled = st.checkbox("Enable stochastic rate sidecar", value=False)
        model_active = st.selectbox(
            "model_active", short_rate_models, index=len(short_rate_models) - 1
        )
        model_technical = st.selectbox(
            "model_technical", short_rate_models, index=len(short_rate_models) - 1
        )
        n_paths = st.number_input("n_paths", 1, 5000, 100, 10)
        seed = st.number_input("seed", 0, 1_000_000, 42, 1)

    history = st.session_state.get("run_history", [])
    if history:
        st.divider()
        section_title(st, "Recent runs")
        for entry in history[-5:][::-1]:
            st.markdown(
                f'<div class="snapshot-row">'
                f'<span class="snapshot-label">{html.escape(entry["timestamp"])}</span>'
                f'<span class="snapshot-value">{html.escape(entry["scenario"])} · '
                f'{entry["fr_final"]:.1f}%</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

    return {
        "mortality_mode": mortality_mode,
        "mortality_table_id": mortality_table_id,
        "stochastic_enabled": stochastic_enabled,
        "model_active": model_active,
        "model_technical": model_technical,
        "n_paths": n_paths,
        "seed": seed,
    }


def render_results_and_risk(st: Any, result: Any) -> None:
    section_title(st, "Results & risk")
    if result is None:
        render_empty_state(
            st,
            title="No results yet",
            body="Run a scenario from the Run tab to populate detailed results.",
            cta_label="Go to Run",
            target_tab="Run",
            key="results_empty_cta",
        )
        return

    kpi_cards.render_kpi_grid(st, _kpi_specs(result, full=True), cols=4)

    st.divider()
    cols = st.columns(2)
    with cols[0]:
        st.plotly_chart(
            charts.net_cashflow_chart(result.net_cashflow),
            use_container_width=True,
            theme=None,
        )
    with cols[1]:
        st.plotly_chart(
            charts.cashflow_by_source_chart(result.cashflow_by_source),
            use_container_width=True,
            theme=None,
        )

    st.divider()
    section_title(st, "Validation checks")
    st.plotly_chart(
        charts.validation_checks_table(result.validation_checks),
        use_container_width=True,
        theme=None,
    )

    if result.stochastic_summary is not None and not result.stochastic_summary.empty:
        st.divider()
        section_title(st, "Stochastic terminal funding ratio")
        st.plotly_chart(
            charts.stochastic_summary_chart(result.stochastic_summary),
            use_container_width=True,
            theme=None,
        )


def render_stress_lab(
    st: Any,
    *,
    scenario_cache: dict[str, Any],
    on_run_all: Any,
) -> None:
    section_title(st, "Stress lab")
    st.caption(
        "Runs the 6 scenario presets in deterministic-proxy mode (no ACTUS, "
        "no stochastic) for fast comparison. Funding-ratio trajectories may "
        "differ from a full ACTUS run by a few percentage points."
    )
    cols = st.columns([3, 1])
    with cols[1]:
        st.button(
            "Run all 5 scenarios",
            key="run_stress_all",
            on_click=on_run_all,
            type="primary",
        )

    if not scenario_cache:
        render_empty_state(
            st,
            title="No scenarios cached",
            body="Run all 5 scenarios from the button above to populate this view.",
            cta_label="Go to Run",
            target_tab="Run",
            key="stress_empty_cta",
        )
        return

    overlay_input = {
        name: payload["funding_ratio_trajectory"]
        for name, payload in scenario_cache.items()
    }
    st.plotly_chart(
        charts.scenario_overlay_chart(overlay_input, metric="funding_ratio_percent"),
        use_container_width=True,
        theme=None,
    )

    rows = []
    baseline_final = None
    for name, payload in scenario_cache.items():
        fr = payload["funding_ratio_trajectory"]
        kpis = payload["kpi_summary"].iloc[0]
        final_fr = float(kpis["final_funding_ratio_percent"])
        if name.lower().startswith("baseline"):
            baseline_final = final_fr
        rows.append(
            {
                "scenario": name,
                "FR initial (%)": float(kpis["current_funding_ratio_percent"]),
                "FR final (%)": final_fr,
                "FR min (%)": float(kpis["minimum_funding_ratio_percent"]),
                "Inflection": kpis.get("liquidity_inflection_year") or "—",
            }
        )
    table = pd.DataFrame(rows)
    if baseline_final is not None:
        table["Δ vs Baseline (pp)"] = table["FR final (%)"] - baseline_final
    st.dataframe(table, width="stretch", hide_index=True)


def render_methodology(st: Any, *, comparison: Any, on_run_comparison: Any) -> None:
    section_title(st, "Methodology")
    st.markdown(
        """
**Workflow architecture**

```
Population → BVG Engine (Stage 2C) → Mortality-aware valuation (Stage 2B)
          → Funding ratio trajectory → KPIs → Validation checks
                                  ↘  ACTUS asset engine (sidecar)
                                  ↘  Stage 2D stochastic rates (sidecar)
```

**Calibration anchors and conventions**

- `target_funding_ratio` calibrates initial asset volume so that
  `assets_year_0 = liability_year_0 × target_funding_ratio`. This is an
  initialisation anchor, not an empirical reading. Trajectory dynamics
  thereafter are model-driven.
- `conversion_rate = 6.8%` is the gesetzlicher BVG-Mindestumwandlungssatz
  (Art. 14 BVG, status quo after the 2024 reform vote). The kassen-spezifische
  effective UWS (Complementa 2024 average ~5.19%) applies only to
  Überobligatorium and is out of scope.
- `active_interest_rate = 1.25%` is the BVG-Mindestzins 2024 applied to
  Obligatorium savings capital. Real PK-effective rates can exceed this
  (Complementa 2024 average ~3.9%) but are not modelled at cohort level.
- BVG cashflow events are emitted at year-end for each transition year,
  i.e. years `start_year .. start_year + horizon - 1`. Snapshots span
  `0 .. horizon` (one extra terminal state). Asset side terminates at
  `start_year + horizon`, producing a TD spike at the terminal date that
  represents portfolio liquidation, not operational cashflow.
- Active capital growth (BVG min interest credit) is a balance-sheet event
  applied inside `project_active_cohort_one_year`. The PR cashflow
  represents only the contribution; the interest credit is reflected in
  the next snapshot's `total_capital_active`, not as a separate cashflow.
- ACT-cohorts hit BVG age-credit brackets (10% → 15% at age 45 etc.) and
  the AHV-cap (`MAX_AHV_SALARY = 88,200 CHF`); per-cohort PR therefore
  shows a step at bracket transitions and plateaus once the cap binds.
"""
    )
    st.divider()
    section_title(st, "Stage comparison")
    cols = st.columns([3, 1])
    with cols[1]:
        st.button(
            "Run / Load Stage Comparison",
            key="run_stage_comparison",
            on_click=on_run_comparison,
        )
    if comparison is None:
        st.caption(
            "Stage modes available: core, full_alm_actus, population, mortality, "
            "dynamic_parameters, stochastic_rates."
        )
    else:
        st.dataframe(comparison.comparison_table, width="stretch", hide_index=True)
        st.dataframe(comparison.stage_explanations, width="stretch", hide_index=True)

    st.divider()
    section_title(st, "Limitations")
    st.markdown(
        """
- Complementa plausibility checks are dashboard indicators, not calibration.
- Population assumptions are scenario parameters, not empirical calibration.
- Gender columns are UI metadata only; mortality remains a global EK0105 table choice.
- EK 0105 is educational and not production-grade Swiss PK mortality.
- Dynamic parameters are parameter paths, not management actions.
- Stage 2D floors negative simulated rates at zero.
- AAL public server: STK dividends and CSH temporal events not emitted.
- Goal 1 does not implement going-concern strategy, rebalancing, or management actions.
"""
    )

    st.divider()
    section_title(st, "References")
    st.markdown(
        """
- BVG (Swiss Federal Law on Occupational Pensions, LPP).
- EK 0105 educational Swiss mortality tables (EKM / EKF).
- ACTUS standard — Algorithmic Contract Type Unified Standards.
- Complementa Risiko Check-up 2024 (sector benchmark context).
"""
    )


def serialize_session_config(state: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    for key, value in state.items():
        if isinstance(value, (str, int, float, bool)):
            payload[key] = value
    return json.dumps(payload, indent=2)
