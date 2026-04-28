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
- Deterministic ACTUS-style fixed-rate bond fixtures implemented as
  manually checkable adapter inputs.
- Separate asset-cashflow overlay helper implemented for combining BVG
  baseline cashflows with ACTUS-style fixture cashflows.
- Optional AAL availability probe implemented for future real AAL integration.
- Optional AAL API introspection and real-AAL smoke tests document that AAL
  `1.0.12` can construct `PAM` and `Portfolio` objects when available.
- Standalone annual/monthly time-grid feasibility utilities implemented for
  later monthly cashflow work.
- Standalone monthly BVG PR/RP cashflow generator
  (`src/pk_alm/bvg/monthly_cashflow_generation.py`) implemented on top of
  the time-grid layer. PR/RP only; KA and retirement transitions are out of
  scope. Not wired into the default Stage-1 baseline.
- Standalone monthly-vs-annual BVG cashflow reconciliation utility
  (`src/pk_alm/analytics/monthly_reconciliation.py`) implemented to prove
  monthly PR/RP totals equal the annual generator's totals. Not wired into
  the default Stage-1 baseline.
- Optional AAL asset boundary (`src/pk_alm/adapters/aal_asset_boundary.py`)
  implemented: constructs real AAL `PAM` and `Portfolio` objects when AAL is
  available; offline ACTUS fixture fallback delivers schema-valid cashflows
  without AAL. `PublicActusService` is not called; no production event
  generation is added to the default baseline.
- Separate pension fund AAL asset demo
  (`src/pk_alm/scenarios/aal_asset_demo.py` and
  `examples/pension_fund_aal_asset_demo.py`) implemented for combining
  Stage-1 BVG liability cashflows with AAL Asset Boundary fallback cashflows.
  It is separate from `run_stage1_baseline(...)`, uses `output_dir=None`, and
  does not change the default Stage-1 CSV outputs.
- Offline-safe multi-contract AAL/ACTUS asset portfolio layer
  (`src/pk_alm/adapters/aal_asset_portfolio.py`) implemented: per-contract
  specs map into dynamic AAL PAM terms and optional real AAL `Portfolio`
  construction when AAL is available; reproducible cashflows still use the
  ACTUS fixture/adapter fallback with `source="ACTUS"`. Service-backed AAL
  event generation is handled by the separate AAL Asset Engine, not by this
  portfolio-spec helper.
- AAL Asset Engine v1 (`src/pk_alm/assets/aal_engine.py`) implemented. AAL
  is the strategic asset engine; `generation_mode="aal"` is the main asset
  path, while `generation_mode="fallback"` is an explicit
  test/comparison/development path. There is no silent fallback.
- Full ALM Scenario (`src/pk_alm/scenarios/full_alm_scenario.py`)
  implemented: combines BVG liability cashflows with AAL asset-engine
  cashflows through the shared `CashflowRecord` schema without mutating the
  protected Stage-1 outputs.
- ALM KPI / plot-ready output layer (`src/pk_alm/analytics/alm_kpis.py`)
  implemented: KPI summary, cashflow-by-source table, and net-cashflow table.
  Sprint 8 adds a separate reporting package for CSV export, matplotlib PNG
  plots, and caller-supplied benchmark/plausibility tables.
- Repository hygiene cleanup performed: generated Python caches and local
  `.DS_Store` files were removed without deleting, renaming, or deprecating
  source modules, tests, examples, docs, or protected Stage-1 outputs.
- The Stage-1 baseline scenario is available as both a library function and a
  manual-run script.
- Current tests: **1068 passed, 18 skipped**.

## Quick Run

Run the test suite:

```bash
python -m pytest -v
```

Run the Stage-1 baseline demo:

```bash
python examples/stage1_baseline.py
```

Run the separate pension fund AAL asset demo:

```bash
python examples/pension_fund_aal_asset_demo.py
```

Run the Full ALM reporting workflow with explicit offline fallback:

```bash
python examples/full_alm_reporting_workflow.py
```

Run the integrated Full ALM scenario from Python by calling
`run_full_alm_scenario(...)`. Its default asset path is
`generation_mode="aal"` and requires the optional AAL install profile:

```bash
python3 -m pip install -e ".[aal]"
```

For offline development or comparison, pass `generation_mode="fallback"`
explicitly. The fallback path is not the conceptual main asset path.

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
- [docs/time_grid_feasibility.md](docs/time_grid_feasibility.md) — feasibility
  note for future monthly cashflow timing.
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
- Deterministic ACTUS-style fixed-rate bond fixtures exist as manual
  test/example data for the adapter boundary; they are not an ACTUS engine.
- A separate asset-cashflow overlay helper can combine BVG baseline cashflows
  with ACTUS-style fixture cashflows for annual liquidity analytics.
- The overlay is a shared-schema demonstration, not the default Stage-1
  scenario, and the default Stage-1 CSV outputs remain unchanged.
- An optional AAL availability probe can detect `awesome_actus_lib`, version
  metadata, and expose `get_aal_module()` as a controlled future gateway.
- Optional AAL API introspection and `tests/test_aal_real_contract_smoke.py`
  show that real AAL `PAM` and `Portfolio` objects can be constructed when AAL
  is available. `PublicActusService.generateEvents(...)` appears
  service-backed via `/eventsBatch`, so no production AAL event adapter has
  been added. Sprint 5C recorded `753 passed, 8 skipped` in the system
  environment and `761 passed` in the temporary AAL venv.
- `src/pk_alm/time_grid.py` provides standalone annual/monthly feasibility
  utilities. The annual baseline remains the reference, and monthly simulation
  is not part of the default Stage-1 run.
- `src/pk_alm/bvg/monthly_cashflow_generation.py` and
  `src/pk_alm/analytics/monthly_reconciliation.py` provide a standalone
  monthly BVG PR/RP cashflow generator and a monthly-vs-annual reconciliation
  utility on top of the time-grid layer. They cover only PR and RP; they do
  not implement KA / retirement-transition timing, monthly valuation, or
  monthly asset roll-forward, and they are not wired into the default
  Stage-1 baseline.
- An optional AAL asset boundary (`src/pk_alm/adapters/aal_asset_boundary.py`)
  can construct real AAL `PAM` and `Portfolio` objects when AAL is available
  and delivers offline schema-valid ACTUS cashflows as a fallback. It is not
  wired into the default Stage-1 baseline and does not call
  `PublicActusService`.
- A separate pension fund AAL asset demo can combine Stage-1 BVG liability
  cashflows with AAL Asset Boundary fallback cashflows for annual liquidity
  analytics. The demo is a shared-schema demonstration, not the default
  Stage-1 baseline, and it calls `run_stage1_baseline(...)` only with
  `output_dir=None`.
- `src/pk_alm/adapters/aal_asset_portfolio.py` provides an offline-safe
  multi-contract AAL/ACTUS asset portfolio layer. It can construct multiple
  real AAL `PAM` model objects and one real AAL `Portfolio` when AAL is
  available, while reproducible cashflow output uses the existing ACTUS
  fixture/adapter fallback. It is not wired into the default Stage-1 baseline,
  does not call `PublicActusService`, and is not a calibrated real pension
  fund asset allocation.
- `src/pk_alm/assets/aal_engine.py` is the strategic asset-side engine. Its
  default `generation_mode="aal"` path uses AAL and raises clearly when AAL or
  the service-backed event path is unavailable. The explicit
  `generation_mode="fallback"` path is for tests, comparison, and offline
  development only; it is never used silently.
- `src/pk_alm/scenarios/full_alm_scenario.py` is the integrated BVG + AAL
  scenario layer. It preserves the canonical `CashflowRecord` schema and does
  not replace or mutate the protected `run_stage1_baseline(...)` outputs.
- `src/pk_alm/analytics/alm_kpis.py` produces an ALM KPI summary plus
  plot-ready DataFrames for cashflows by source and net cashflows.
- `src/pk_alm/reporting/` exports Full ALM scenario outputs, saves matplotlib
  PNG plots, and prepares benchmark/plausibility tables from caller-provided
  reference values. It does not add Streamlit or new economic assumptions.
- AAL remains optional for the package installation and is not a dependency of
  the protected Stage-1 baseline. Install the optional profile with
  `pip install -e ".[aal]"` when running the strategic AAL asset path locally.
- No stochastic interest-rate scenarios yet.
- No mortality, new entrants, wage growth, inflation, survivor benefits, or
  disability benefits.
- The `total_stage1_liability` reported by the valuation layer is a
  deterministic Stage-1 proxy and intentionally excludes technical reserves.

These extensions are deferred to later sprints; see
`docs/implementation_progress.md` for the next planned step.
