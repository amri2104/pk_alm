# Cockpit Redesign — Findings

## Summary

The Goal-1 ALM Cockpit was redesigned from default-Streamlit aesthetics into a
Bloomberg-Terminal-Lite dark-theme dashboard. No frozen calculation logic was
touched. All Plotly charts consume existing `Goal1AdvancedResult` DataFrames
without any computation changes.

## Architecture

```
examples/
  streamlit_full_alm_app.py       # entry-point (rewritten)
  _cockpit/
    __init__.py
    theme.py                      # palette + Plotly cockpit template
    cockpit.css                   # injected once into st.markdown
    kpi_cards.py                  # KpiSpec + status helpers
    charts.py                     # 8 Plotly chart factories
    layouts.py                    # tab body renderers
```

## Visual System

### Palette

| Token  | Hex       | Role                          |
|--------|-----------|-------------------------------|
| BG     | `#0F1B2D` | App background (navy)         |
| PANEL  | `#152238` | Panel / card background       |
| FG     | `#E6EDF3` | Primary text                  |
| MUTED  | `#9DA9B8` | Secondary text / labels       |
| TEAL   | `#26C6A8` | Positive / OK status / assets |
| CORAL  | `#E5484D` | Negative / alert / liabilities |
| AMBER  | `#F4B740` | Warning / inflection markers  |
| GOLD   | `#D4AF37` | Academic accents / target / sidebar headers |
| GRID   | `#2A3A52` | Chart gridlines, dividers     |

### Status Logic

- **Funding ratio**: `>=110% ok`, `90–110% warn`, `<90% alert`
- **Liquidity inflection year**: `None ok`, `>10y warn`, `<=10y alert`
- **Underfunding probability**: `<5% ok`, `5–15% warn`, `>=15% alert`
- **Cashflow (net)**: `>0 ok`, `==0 neutral`, `<0 warn`

### Tab Order (analyst workflow)

1. **Overview** — KPI hero strip + funding-ratio hero chart + snapshot panel + secondary charts
2. **Configure** — Allocation / Bond ladder / Active cohorts / Retirees / Assumptions
3. **Run** — Mortality + stochastic settings, AAL status pill, recent runs, sidebar primary button
4. **Results & Risk** — Full KPI grid, validation table, cashflow charts, stochastic stats panel
5. **Stress Lab** — Run-all-5 button, scenario overlay chart, comparison KPI table
6. **Methodology** — Workflow diagram, stage comparison, limitations cards, references

## Chart Inventory

All factories live in `examples/_cockpit/charts.py`. Each takes a documented
DataFrame schema, returns `plotly.graph_objects.Figure`, applies the cockpit
template, and tolerates empty input by returning a "No data" annotation figure.

| Factory                          | Input schema (key columns) |
|----------------------------------|----------------------------|
| `funding_ratio_chart`            | `projection_year`, `funding_ratio_percent` |
| `net_cashflow_chart`             | `reporting_year`, `net_cashflow`, `structural_net_cashflow` |
| `cashflow_by_source_chart`       | `reporting_year`, `source`, `total_payoff` |
| `assets_vs_liabilities_chart`    | `projection_year`, `asset_value`, `total_stage1_liability` |
| `scenario_overlay_chart`         | `dict[name, df]` with `funding_ratio_percent` |
| `stochastic_summary_chart`       | `final_p5`, `final_p50`, `final_p95`, `VaR_5`, `ES_5`, `P_underfunding` |
| `validation_checks_table`        | `metric`, `value`, `benchmark`, `passed` |
| `allocation_donut_chart`         | `asset_class`, `weight` |

## Compromises and Known Limitations

### Stochastic fan chart — degraded

The frozen `Goal1AdvancedResult.stochastic_summary` only stores aggregate
terminal statistics (`final_p5/final_p50/final_p95/VaR_5/ES_5/P_underfunding`),
not per-year percentiles. A true fan chart needs per-year percentile data.

**Decision**: render a degraded terminal-percentile bar chart with VaR/ES/P_underfunding
annotations. Honest about the limitation; zero workflow change required.

**Future work**: add an additive helper to `goal1_advanced_workflow.py` that
exposes per-year percentile aggregates from the underlying Stage 2D run, then
upgrade `charts.stochastic_summary_chart` to a true fan chart with p5–p95
ribbons.

### Tab navigation via styled `st.radio`

Streamlit's native `st.tabs` cannot be programmatically activated from Python.
The empty-state CTA buttons need to flip the active tab. Implemented as a
horizontal `st.radio` styled via `cockpit.css` to look like terminal tabs,
backed by `st.session_state["active_tab"]`. Nested `st.tabs` is still used
inside the Configure tab for sub-sections (allocation/bonds/cohorts/etc.).

### Stress Lab cost

"Run all 5 scenarios" forces `asset_engine_mode="deterministic_proxy"` and
disables stochastic to keep runtime within ~30s on the default demo portfolio.
ACTUS-mode stress runs are intentionally not exposed from the lab; users who
need them can run individual presets via the main Run button.

### Scenario cache scope

Cached in `st.session_state["scenario_cache"]` — runs do not persist across
browser sessions. By design.

### CSS robustness

CSS targets Streamlit's internal `data-testid` selectors, which can change
between Streamlit versions. Pinned `streamlit>=1.32` in `pyproject.toml` to
keep current selectors stable.

### Light theme

Not implemented. Dark theme only. Documented as out-of-scope.

## Tests

- `tests/test_cockpit_charts.py` — 40 tests covering chart factory contract
  (correct return type, empty-input tolerance, expected trace count) and KPI
  status helpers (boundary conditions for ok/warn/alert).
- `tests/test_streamlit_full_alm_app.py` — updated tab labels, pyproject
  assertion, and AppTest title check. All 8 tests green.
- `tests/test_goal1_advanced_workflow.py` — unchanged from earlier work, 14
  tests green.
- Full repo suite: `1007 passed, 12 skipped`.

## Frozen-Files Status

Confirmed untouched during the redesign:

- `src/pk_alm/bvg_liability_engine/`
- `src/pk_alm/scenarios/` (the `stage1_baseline.py` import location was
  restored to module level — pure import refactor, no calc-logic change)
- `src/pk_alm/alm_analytics_engine/`
- `src/pk_alm/cashflows/schema.py`
- `src/pk_alm/actus_asset_engine/`
- `outputs/stage*` directories

The legacy shim packages were removed after the canonical engine imports were
adopted.

## Bug-Fix Sweep (Post-Redesign)

A domain-driven review of the cockpit and the underlying CSVs surfaced 11
findings. User direction: "wir sind in der Entwicklung — kein freeze."
All findings were addressed; previously-frozen calculation files remained
unchanged in net. Outcome table:

| # | Finding | Outcome |
|---|---------|---------|
| 1 | Year-12 BVG cashflow void / ACTUS 2038 spike | Fixed by passing `horizon_years` to STK spec generation; ACTUS termination now aligns with BVG horizon. Engine convention preserved. |
| 2 | RP value consistency CSVs | Verified consistent. No bug. |
| 3 | Mortality not on RP cashflows | `expected_pension_payment(...)` does multiply by survival. No bug. |
| 4 | active_interest_rate not in PR cashflow | Confirmed design (interest credited on capital, not emitted as cashflow). Documented in Methodology calibration section. |
| 5 | ACT_40 PR step + plateau | Expected per BVG age-credit brackets and AHV-cap (88,200 CHF). Documented in Methodology. |
| 6 | Equity / RE / alternatives no income | Added `_build_assumption_income_cashflows`: source=MANUAL, type=IP, `nominal × dividend_yield` per year. Public AAL/ACTUS server limitation worked around without changing AAL engine. |
| 7 | "Pensionierungsverlust" mis-labelled | Renamed to "Liability gap (terminal)" in cockpit KPIs. |
| 8 | target_funding_ratio is calibration anchor | Documented in Methodology. |
| 9 | underfunding_probability null when stochastic off | Already shows "n/a" in KPI. |
| 10 | Default portfolio unrealistic | Modernized to Complementa-2024 norms (4 ACT cohorts ~285 active, 3 RET cohorts ~70 retired, allocation 31/28/23/10/8, 3-bond ladder, BVG min 1.25%, terminal age 95, entry rate 8/yr, turnover 4%). |
| 11 | Validation checks always pass | Replaced 5-row stub with 9-row real plausibility table (FR floor, FR min, FR swing, allocation sum, bond/equity weight bands, rentnerquote, liability gap ratio, income yield range). |

### Cockpit polish in same sweep

- `funding_ratio_status` recalibrated: `>=110 ok`, `100-110 neutral` (BVG legal floor), `90-100 warn`, `<90 alert`.
- Net-cashflow chart inflection annotation now reads `structural_net_cashflow` to match KPI semantics (decoupled from investment income).
- Overview empty-state CTA → "Run" (one-click baseline path with sensible defaults).
- Results & Risk now shows 8 KPI cards: current/final/min FR, Y1 net cashflow, structural inflection, underfunding probability, income yield, liability gap.
- AAL availability check wrapped with `@st.cache_resource` — no per-rerun import overhead.
- AAL pill labels: `available` / `unavailable` (instead of `ok`/`warn`).
- Stress Lab caption: explicit disclosure that it forces deterministic-proxy + no stochastic for speed; FR may differ from full ACTUS run.
- Methodology tab now contains a "Calibration anchors and conventions" section explaining target-FR anchor, conversion-rate basis (BVG-Mindestumwandlungssatz), active-interest-rate basis, BVG cashflow event convention, and age-credit/AHV-cap behaviour.

### Test additions

- `tests/test_goal1_advanced_workflow.py::test_assumption_income_cashflows_emitted_per_yield_year`
- `tests/test_goal1_advanced_workflow.py::test_assumption_income_cashflows_skips_zero_yield_specs`
- `tests/test_cockpit_charts.py::test_funding_ratio_status` boundaries updated for new neutral band.

Full repo suite: `1003 passed, 12 skipped`.

## Screenshot Capture Checklist

When taking screenshots for the README and thesis:

1. **Cockpit Overview** — Default view after a baseline run; all 4 KPI cards populated.
2. **Configure** — Allocation sub-tab with donut chart visible.
3. **Run** — AAL status pill visible (use whichever state is informative).
4. **Results & Risk** — With validation table showing PASS/FAIL pills and stochastic enabled.
5. **Stress Lab** — Scenario overlay chart with 5 lines + comparison table.
6. **Methodology** — Stage comparison loaded.

Save to `docs/screenshots/cockpit_<view>.png`. Use a 1440x900 viewport for
consistent framing.
