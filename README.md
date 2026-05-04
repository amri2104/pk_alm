# pk_alm

Clean rebuild of the pension fund ALM simulation tool for the bachelor thesis
**Enhanced Portfolio Analytics for Pension Funds using ACTUS and Python**.

The current scope is **Stage 1 / Goal 1**: a deterministic economic ALM
baseline focused on cashflow projection, liquidity analysis, and a
transparent liability proxy with deterministic funding-ratio reporting.

## Current Status

- Deterministic Stage-1 BVG liability baseline implemented end-to-end.
- Deterministic asset baseline, funding-ratio trajectory, and funding summary
  implemented.
- Scenario-level result summary implemented for thesis-ready baseline
  reporting.
- Minimal ACTUS/AAL-style adapter boundary implemented for mapping simplified
  event dictionaries into the shared cashflow schema.
- AAL (`awesome-actus-lib>=1.0.12`) is a required dependency for asset-side
  ACTUS work.
- The former fixed-rate fixture, overlay, availability-probe, and API
  introspection support layers have been archived under `archive/`.
- Former standalone annual/monthly time-grid and monthly PR/RP feasibility
  utilities have been archived under `archive/`; they are no longer part of
  the active `pk_alm` package.
- AAL asset construction helpers
  (`src/pk_alm/actus_asset_engine/aal_asset_boundary.py`)
  implemented for real AAL `PAM` and `Portfolio` objects.
- The former separate pension fund AAL asset demo has been archived under
  `archive/`; the active AAL integration path is the AAL Asset Engine and
  Full ALM Scenario.
- Multi-contract AAL/ACTUS asset portfolio layer
  (`src/pk_alm/actus_asset_engine/aal_asset_portfolio.py`) implemented:
  per-contract specs map into dynamic AAL PAM terms and real AAL `Portfolio`
  construction.
- AAL Asset Engine v1 (`src/pk_alm/actus_asset_engine/aal_engine.py`)
  implemented. AAL is the required strategic asset engine for ACTUS cashflow
  generation.
- Full ALM Scenario (`src/pk_alm/scenarios/full_alm_scenario.py`)
  implemented: combines BVG liability cashflows with AAL asset-engine
  cashflows through the shared `CashflowRecord` schema without mutating the
  protected Stage-1 outputs.
- ALM KPI / plot-ready output layer
  (`src/pk_alm/alm_analytics_engine/alm_kpis.py`)
  implemented: KPI summary, cashflow-by-source table, and net-cashflow table.
  Sprint 8 adds a separate reporting package for CSV export, matplotlib PNG
  plots, and caller-supplied benchmark/plausibility tables.
- Repository hygiene cleanup performed: generated Python caches and local
  `.DS_Store` files were removed without deleting, renaming, or deprecating
  source modules, tests, examples, docs, or protected Stage-1 outputs.
- The Stage-1 baseline scenario is available as both a library function and a
  manual-run script.
- Current tests: **1007 passed, 12 skipped**.

## Package Architecture

The active code now exposes the thesis architecture through canonical engine
packages:

- BVG Liability Engine — `src/pk_alm/bvg_liability_engine/`
- ACTUS Asset Engine — `src/pk_alm/actus_asset_engine/`
- ALM Analytics Engine — `src/pk_alm/alm_analytics_engine/`
- Shared Cashflow Schema — `src/pk_alm/cashflows/schema.py`
- Workflow / Scenarios — `src/pk_alm/workflows/` and
  `src/pk_alm/scenarios/`
- Streamlit Cockpit — `examples/streamlit_full_alm_app.py` and
  `examples/_cockpit/`

Legacy shim packages have been removed from the active tree, so new work
should import from the canonical engine packages above.

## Quick Run

Run the test suite:

```bash
python3 -m pytest
```

Run the Stage-1 baseline demo:

```bash
python examples/stage1_baseline.py
```

Run the Full ALM reporting workflow:

```bash
python examples/full_alm_reporting_workflow.py
```

Run the Streamlit prototype:

```bash
python3 -m pip install -e ".[app]"
python3 -m streamlit run examples/streamlit_full_alm_app.py
```

## How to run the Streamlit app

Install the app extra in addition to the required core dependencies:

```bash
python3 -m pip install -e ".[app]"
```

Start the Goal-1 ALM Cockpit:

```bash
python3 -m streamlit run examples/streamlit_full_alm_app.py
```

### Cockpit Screenshot

The cockpit is a Bloomberg-Terminal-Lite dark-theme dashboard with six
analyst-workflow tabs: Overview, Configure, Run, Results & Risk, Stress Lab,
Methodology. Plotly charts (status-banded funding ratio, net-cashflow timeline
with liquidity inflection marker, stacked cashflow-by-source, assets-vs-liabilities
with surplus/deficit overlay) render on a navy palette with gold accents.

![Cockpit Overview](docs/screenshots/cockpit_overview.png)

The cockpit consumes the Goal-1 advanced ALM workflow and falls back to a
deterministic asset proxy when the live AAL/ACTUS service is unreachable.
Stochastic Rates uses the external `stochastic_rates` package; if it is not
installed, install it separately, for example with
`pip install -e ../stochastic_rates`.

The `app` extra installs Streamlit and Plotly. AAL is part of the main
project dependencies.

Run the integrated Full ALM scenario from Python by calling
`run_full_alm_scenario(...)`. The asset path always uses the required live
AAL/ACTUS service-backed event generation:

```bash
python3 -m pip install -e .
```

When working directly from the `src/` layout without an editable install, run:

```bash
PYTHONPATH=src python3 examples/stage1_baseline.py
```

Alternatively, install the package locally first:

```bash
python3 -m pip install -e .
python3 examples/stage1_baseline.py
```

## Generated Outputs

Running the demo writes seven CSV files to
`outputs/stage1_baseline/` (relative to the working directory):

- `outputs/stage1_baseline/cashflows.csv` — schema-valid BVG cashflows.
- `outputs/stage1_baseline/valuation_snapshots.csv` — Stage-1 liability
  snapshots per projection year.
- `outputs/stage1_baseline/annual_cashflows.csv` — annual cashflow
  analytics including the liquidity inflection year.
- `outputs/stage1_baseline/asset_snapshots.csv` — deterministic asset
  roll-forward snapshots.
- `outputs/stage1_baseline/funding_ratio_trajectory.csv` — funding-ratio
  trajectory based on `total_stage1_liability`.
- `outputs/stage1_baseline/funding_summary.csv` — compact funding-ratio
  summary for thesis reporting.
- `outputs/stage1_baseline/scenario_summary.csv` — one-row scenario result
  summary for baseline reporting.

Full ALM reporting exports are separate from the protected Stage-1 baseline.
The reporting helpers in `src/pk_alm/reporting/` can write files such as:

- `outputs/full_alm_scenario/full_alm_kpi_summary.csv`
- `outputs/full_alm_scenario/full_alm_combined_cashflows.csv`
- `outputs/full_alm_scenario/full_alm_annual_cashflows.csv`
- `outputs/full_alm_scenario/full_alm_cashflow_by_source.csv`
- `outputs/full_alm_scenario/full_alm_net_cashflow.csv`
- `outputs/full_alm_scenario/full_alm_funding_ratio_trajectory.csv`
- `outputs/full_alm_scenario/benchmark_plausibility.csv`
- `outputs/full_alm_scenario/plots/*.png`

These outputs are reporting artifacts for the integrated Full ALM scenario.
They do not replace or mutate `outputs/stage1_baseline/*`.

The standard workflow also saves PNG plots:

- `funding_ratio_trajectory.png` — funding-ratio percent by projection year.
- `net_cashflow.png` — annual net and structural net cashflows.
- `cashflow_by_source.png` — annual payoff totals split by `BVG` and `ACTUS`.
- `assets_vs_liabilities.png` — assets and the Stage-1 liability proxy.

`benchmark_plausibility.csv` is optional and is created only when the caller
provides benchmark reference values or additional model values.

## Documentation

- [docs/implementation_progress.md](docs/implementation_progress.md) —
  current sprint-by-sprint status, architecture summary, and known limitations.
- [docs/stage1_pipeline.md](docs/stage1_pipeline.md) — technical description
  of the end-to-end Stage-1 pipeline.
- [docs/stage1_outputs.md](docs/stage1_outputs.md) — reproducibility guide
  for the generated Stage-1 output files.
- [docs/user_workflow.md](docs/user_workflow.md) — short analyst workflow for
  the Full ALM reporting outputs.
- [docs/stage1_spec.md](docs/stage1_spec.md) — Stage-1 specification.
- [docs/domain_notes.md](docs/domain_notes.md) — domain background.
- [docs/decisions.md](docs/decisions.md) — architectural decision records.

## Scope

The current implementation is the **deterministic Stage-1 baseline**:

- Deterministic asset roll-forward, funding-ratio trajectory, and funding
  summary are included.
- Scenario-level result summary export is included.
- A minimal ACTUS/AAL-style adapter boundary exists for schema-compatible
  cashflow conversion.
- AAL is required for asset-side ACTUS work and is used through
  `PublicActusService.generateEvents(...)`.
- Former fixed-rate fixture, overlay, and API inspection helpers are archived
  under `archive/` and are not part of the active package.
- Former time-grid and monthly PR/RP feasibility helpers are archived under
  `archive/` and are not part of the active package or default Stage-1 run.
- `src/pk_alm/actus_asset_engine/aal_asset_boundary.py` constructs real AAL
  `PAM` and `Portfolio` objects.
- `src/pk_alm/actus_asset_engine/aal_asset_portfolio.py` provides a
  multi-contract AAL/ACTUS asset portfolio layer. It is not wired into the
  default Stage-1 baseline and is not a calibrated real pension fund asset
  allocation.
- `src/pk_alm/actus_asset_engine/aal_engine.py` is the strategic asset-side
  engine. Its live AAL path raises clearly when the service-backed event path
  is unavailable.
- `src/pk_alm/scenarios/full_alm_scenario.py` is the integrated BVG + AAL
  scenario layer. It preserves the canonical `CashflowRecord` schema and does
  not replace or mutate the protected `run_stage1_baseline(...)` outputs.
- `src/pk_alm/alm_analytics_engine/alm_kpis.py` produces an ALM KPI summary plus
  plot-ready DataFrames for cashflows by source and net cashflows.
- `src/pk_alm/reporting/` exports Full ALM scenario outputs, saves matplotlib
  PNG plots, and prepares benchmark/plausibility tables from caller-provided
  reference values. It does not add Streamlit or new economic assumptions.
- AAL is a main project dependency. The protected Stage-1 baseline still uses
  `actus_asset_engine/deterministic.py` as a transparent zero-asset-return
  reference baseline and therefore remains byte-stable across this AAL
  refactor.
- No stochastic interest-rate scenarios yet.
- No mortality, new entrants, wage growth, inflation, survivor benefits, or
  disability benefits.
- The `total_stage1_liability` reported by the valuation layer is a
  deterministic Stage-1 proxy and intentionally excludes technical reserves.

These extensions are deferred to later sprints; see
`docs/implementation_progress.md` for the next planned step.
