# Implementation Progress

## Current Status

The repository now contains a deterministic Stage-1 BVG liability baseline. The
current implementation covers BVG formulas, cohort dataclasses, portfolio state
and projections, retirement transitions, BVG cashflow generation, multi-year
liability projection, deterministic liability valuation snapshots, annual
liquidity analytics, deterministic asset roll-forward, funding-ratio trajectory,
funding-ratio summary analytics, scenario-level result summary reporting, and
an end-to-end demo scenario with CSV export. Sprint 4A also adds a minimal
ACTUS/AAL-style adapter boundary for converting simplified external event
dictionaries into the shared cashflow schema, and Sprint 4B adds deterministic
ACTUS-style fixed-rate bond fixtures as manually checkable adapter inputs.
Sprint 4C adds a separate asset-cashflow overlay helper that combines BVG
baseline cashflows with ACTUS-style fixed-rate bond fixture cashflows for
annual liquidity analytics. Sprint 5A adds an optional AAL availability probe
and import gateway for later real AAL integration without making AAL a hard
dependency. Sprint 5B adds optional AAL API-surface introspection, Sprint 5C
documents real-AAL smoke-test findings, and Sprint 6A adds a standalone
annual/monthly time-grid feasibility layer for future monthly cashflow work.
Sprint 6B adds a standalone monthly BVG PR/RP cashflow generator on top of
the time-grid layer, and Sprint 6C adds a monthly-vs-annual reconciliation
utility that proves monthly PR/RP timing preserves the corresponding annual
totals. Both Sprint 6B and Sprint 6C are standalone and not wired into the
default Stage-1 baseline; the seven default Stage-1 CSV outputs are
unchanged.

Sprint 7A adds an optional AAL asset boundary
(`src/pk_alm/adapters/aal_asset_boundary.py`) that can construct real AAL
`PAM` and `Portfolio` objects when AAL is available, and provides an offline
ACTUS fixture fallback that delivers schema-valid ACTUS cashflows without AAL
or any network call. `PublicActusService` is not called; the default Stage-1
baseline and seven CSV outputs are unchanged.

Sprint 7B adds a separate pension fund AAL asset demo
(`src/pk_alm/scenarios/aal_asset_demo.py` and
`examples/pension_fund_aal_asset_demo.py`) that combines Stage-1 BVG
liability cashflows with AAL Asset Boundary fallback cashflows in the shared
cashflow schema. The demo calls `run_stage1_baseline(...)` only with
`output_dir=None`, is not wired into the default Stage-1 baseline, and does
not change the seven default Stage-1 CSV outputs. It does not call
`PublicActusService` and does not add production AAL service-backed
cashflow generation.

Sprint 7C adds an offline-safe multi-contract AAL/ACTUS asset portfolio
layer (`src/pk_alm/adapters/aal_asset_portfolio.py`). It represents asset
contracts with per-contract specs, maps those specs into dynamic AAL PAM
terms when AAL is available, and can construct one real AAL `Portfolio` from
multiple PAM contracts. For reproducible offline execution, it builds
schema-valid fallback cashflows for all portfolio contracts through the
existing ACTUS fixture/adapter path with `source="ACTUS"`. AAL remains
optional for installation, and the default Stage-1 baseline remains
unchanged.

Sprint 7D adds the AAL Asset Engine v1 (`src/pk_alm/assets/aal_engine.py`).
AAL is the strategic asset-side engine. `generation_mode="aal"` is the main
asset path and requires AAL plus a reachable service-backed event-generation
path. `generation_mode="fallback"` is an explicit test/comparison/development
path that uses fixture cashflows; it is never selected silently. The optional
install profile is `pk-alm[aal]`.

Sprint 7E adds the Full ALM Scenario
(`src/pk_alm/scenarios/full_alm_scenario.py`). It combines BVG liability
cashflows from the protected Stage-1 baseline with AAL Asset Engine cashflows,
preserves the shared `CashflowRecord` schema, recomputes annual cashflow
analytics on the combined stream, and does not mutate the seven protected
Stage-1 CSV outputs.

Sprint 7F adds the ALM KPI / plot-ready output layer
(`src/pk_alm/analytics/alm_kpis.py`). It produces a compact KPI summary, a
cashflow-by-source plot table, and a net-cashflow plot table from existing
Full ALM outputs. It does not add actual matplotlib, Streamlit, or dashboard
plot rendering.

Sprint 7G is the repository cleanup analysis / hygiene sprint. It confirmed
that the current code still follows the three-engine architecture: BVG
Liability Engine, AAL Asset Engine, and ALM Analytics Engine connected by the
shared `CashflowRecord` bridge. It also classified core modules,
support/test infrastructure, demo/example modules, unsafe delete candidates,
and safe generated-file cleanup. The hygiene cleanup removed generated
Python caches and local `.DS_Store` files only; no source modules, tests,
examples, docs, or protected Stage-1 outputs were deleted, renamed, or
deprecated.

Sprint 7I consolidates the documentation around that current architecture,
the new sprint naming convention, repository hygiene, and the protected
distinction between the Stage-1 baseline and the integrated Full ALM
scenario.

Sprint 8 adds a thesis-ready reporting layer (`src/pk_alm/reporting/`) on top
of the Full ALM Scenario and ALM KPI outputs. It separates calculation from
I/O via `export_full_alm_result(...)` for already computed results and
`export_full_alm_results(...)` as a convenience wrapper. It writes Full ALM
CSV exports outside `outputs/stage1_baseline/`, saves matplotlib PNG plots,
and prepares benchmark/plausibility tables from caller-provided reference
values. It does not add Streamlit, stochastic modelling, or new financial
assumptions.

The full system test suite currently passes with **1074 passed, 36 skipped**.
Historical documentation-status anchors include earlier observations of
**874 passed, 8 skipped**, **809 passed, 8 skipped**,
**753 passed, 8 skipped**, and **761 passed** in an AAL-focused temporary
environment. These are not current expected results.

## Sprint Summary

| Sprint | Implemented Component | Main Files | Purpose | Test Coverage |
|---|---|---|---|---|
| Sprint 1A | Pure BVG formulas | `src/pk_alm/bvg/formulas.py`, `tests/test_bvg_formulas.py` | Coordinated salary, age credit rates, annuity factors, retiree PV, pensionierungsverlust. | Worked examples, boundary cases, invalid inputs. |
| Sprint 1B | BVG cohort dataclasses | `src/pk_alm/bvg/cohorts.py`, `tests/test_bvg_cohorts.py` | Active and retired cohort containers with per-person and total derived values. | Standard examples, boundary cases, invalid inputs, validation. |
| Sprint 1C | One-year cohort projection | `src/pk_alm/bvg/projection.py`, `tests/test_bvg_projection.py` | Pure projection of active and retired cohorts without mutation. | Ageing, interest, age credits, annuity-due pension capital roll-forward, immutability. |
| Sprint 1D | Portfolio state container | `src/pk_alm/bvg/portfolio.py`, `tests/test_bvg_portfolio.py` | Frozen portfolio state with active and retired cohorts plus aggregate properties. | Aggregates, tuple conversion, duplicate IDs, invalid types. |
| Sprint 1E | Portfolio projection | `src/pk_alm/bvg/portfolio_projection.py`, `tests/test_bvg_portfolio_projection.py` | Coordinate one-year projection over all cohorts. | Different active and retired rates, immutability, invalid inputs. |
| Sprint 2A | Shared cashflow schema | `src/pk_alm/cashflows/schema.py`, `tests/test_cashflow_schema.py` | Canonical 7-column cashflow schema: `contractId`, `time`, `type`, `payoff`, `nominalValue`, `currency`, `source`. | Sign convention, DataFrame conversion, validation, NaN/bool handling. |
| Sprint 2B | BVG cashflow generation | `src/pk_alm/bvg/cashflow_generation.py`, `tests/test_bvg_cashflow_generation.py` | Convert one `BVGPortfolioState` into BVG cashflow records and DataFrame rows. | PR/RP rows, contribution multiplier, event dates, immutability. |
| Sprint 2C | BVG engine runner | `src/pk_alm/bvg/engine.py`, `tests/test_bvg_engine.py` | Run deterministic multi-year BVG liability projection. | Zero/one/two-year horizons, contribution multiplier, different rates, result validation. |
| Sprint 2D | Retirement transitions | `src/pk_alm/bvg/retirement_transition.py`, `tests/test_bvg_retirement_transition.py`, updated `src/pk_alm/bvg/engine.py` | Convert active cohorts reaching retirement age into retired cohorts and emit KA capital withdrawal cashflows. | Boundary ages, capital withdrawal fractions, conversion rate, engine integration. |
| Sprint 2E | Liability valuation snapshots | `src/pk_alm/bvg/valuation.py`, `tests/test_bvg_valuation.py` | Value portfolio states as deterministic Stage-1 liability snapshots. | Active-only, retired-only, terminal age, pensionierungsverlust, missing values, float tolerance. |
| Sprint 2F | Annual cashflow analytics | `src/pk_alm/analytics/cashflows.py`, `tests/test_analytics_cashflows.py` | Aggregate cashflows by year and compute structural/net liquidity inflection years. | Grouping, cumulative sums, structural vs net cashflow, currency validation, dtype robustness. |
| Sprint 2G | Stage-1 baseline scenario | `src/pk_alm/scenarios/stage1_baseline.py`, `examples/stage1_baseline.py`, `tests/test_stage1_baseline_scenario.py` | End-to-end demonstrator: engine → valuation → analytics → CSV export. | Default portfolio, export, import safety, custom horizon, parameter pass-through. |
| Sprint 3A | Deterministic asset baseline and funding ratio | `src/pk_alm/assets/deterministic.py`, `src/pk_alm/analytics/funding.py`, `tests/test_assets_deterministic.py`, `tests/test_analytics_funding.py` | Calibrate initial assets from target funding ratio, roll assets forward using annual net cashflow and deterministic return, compute funding-ratio trajectory. | Initial asset calibration, one-year asset projection, asset trajectory, start_year/reporting_year alignment, funding-ratio validation, scenario integration. |
| Sprint 3B | Funding-ratio summary analytics | `src/pk_alm/analytics/funding_summary.py`, `tests/test_analytics_funding_summary.py` | Summarize funding-ratio trajectories into a compact thesis-ready result table. | Initial/final/min/max funding ratios, underfunding counts, target comparison, tie handling, validation, scenario integration. |
| Sprint 3C | Scenario result summary table | `src/pk_alm/scenarios/result_summary.py`, `tests/test_scenario_result_summary.py` | Build one-row scenario summary for thesis-ready baseline result reporting. | Standard scenario summary, horizon zero, invalid inputs, optional inflection fields, DataFrame conversion, export integration. |
| Sprint 3D | Stage-1 outputs and reproducibility documentation | `docs/stage1_outputs.md`, `docs/stage1_pipeline.md`, `README.md`, `tests/test_documentation_status.py` | Document all seven CSV outputs, reproduction command, interpretation warnings, and limitations. | Documentation-status tests and full pytest suite. |
| Sprint 3E | Pre-ACTUS cleanup | `src/pk_alm/analytics/funding_summary.py`, `src/pk_alm/scenarios/result_summary.py`, `examples/stage1_baseline.py`, `tests/test_stage1_baseline_scenario.py`, `docs/*` | Rename the funding-summary min/max year fields to the explicit `minimum_funding_ratio_projection_year` / `maximum_funding_ratio_projection_year` form; add CSV-roundtrip validation in the scenario export test; document `contribution_multiplier`, `annual_asset_return`, and Stage-1 liability proxy defaults. No model formulas changed. | Renamed-field tests, CSV-roundtrip validation in `test_run_with_export`, documentation-status tests. |
| Sprint 4A | Minimal ACTUS/AAL adapter boundary | `src/pk_alm/adapters/actus_adapter.py`, `tests/test_actus_adapter.py` | Map simplified ACTUS/AAL-style event dictionaries into the canonical `CashflowRecord` schema with `source="ACTUS"`. | Standard event mapping, defaults, negative payoffs, multi-event order, DataFrame conversion, empty input, invalid input, no mutation, and BVG+ACTUS schema concatenation smoke test. |
| Sprint 4B | ACTUS-style fixed-rate bond fixtures | `src/pk_alm/adapters/actus_fixtures.py`, `tests/test_actus_fixtures.py` | Create deterministic, manually checkable fixed-rate bond event dictionaries that flow through the Sprint 4A adapter into the canonical cashflow schema. | Standard bond events, purchase-event option, zero-coupon case, multi-year ordering, DataFrame helper, adapter integration, annual analytics integration, BVG+ACTUS combination smoke test, invalid inputs, deterministic output. |
| Sprint 4C | Asset cashflow overlay scenario | `src/pk_alm/scenarios/asset_overlay.py`, `tests/test_asset_overlay_scenario.py` | Combine deterministic BVG baseline cashflows with ACTUS-style fixed-rate bond fixture cashflows in a separate overlay helper, then recompute annual cashflow analytics on the combined schema-valid cashflow set. | Overlay result validation, exact combined row count, ACTUS events in `other_cashflow`, purchase-event option, horizon-zero behavior, custom bond parameters, mixed-currency rejection, chronological sorting, invalid inputs, and default Stage-1 baseline unchanged. |
| Sprint 5A | Optional AAL availability probe | `src/pk_alm/adapters/aal_probe.py`, `tests/test_aal_probe.py`, `tests/test_aal_optional_smoke.py` | Provide an optional import/version probe and controlled gateway for future real AAL integration without making AAL a hard dependency. | Availability dataclass validation, version metadata fallback, import success/failure, required-AAL error path, controlled module gateway, no top-level import, optional smoke tests skipped when AAL is absent. |
| Sprint 5B | Optional AAL API surface introspection | `src/pk_alm/adapters/aal_introspection.py`, `tests/test_aal_introspection.py`, `tests/test_aal_optional_api_surface.py` | Inspect the optional AAL API surface when available without creating contracts or generating cashflows. | Snapshot validation, public-name discovery, candidate-symbol filtering, report formatting, optional API-surface checks skipped when AAL is absent. |
| Sprint 5C | Real AAL smoke-test findings | `tests/test_aal_real_contract_smoke.py`, `docs/implementation_progress.md` | Document that AAL `1.0.12` can construct real `PAM` and `Portfolio` objects in a temporary venv, while event generation appears service-backed through `PublicActusService.generateEvents(...)/eventsBatch`. | Optional real-AAL smoke tests skip without AAL and pass in the AAL venv; no production AAL event adapter, dependency, or Stage-1 wiring added. |
| Sprint 6A | Time-grid and monthly-feasibility abstraction | `src/pk_alm/time_grid.py`, `tests/test_time_grid.py`, `docs/time_grid_feasibility.md` | Provide standalone annual/monthly time-grid helpers for future monthly cashflow simulation while keeping the annual baseline as the reference. | Frequency normalization, annual-to-periodic rate conversion, annual amount splitting, annual/monthly grid construction, leap-year month ends, DataFrame validation, and Stage-1 no-side-effect checks. |
| Sprint 6B | Monthly BVG PR/RP cashflow generator | `src/pk_alm/bvg/monthly_cashflow_generation.py`, `tests/test_bvg_monthly_cashflow_generation.py` | Standalone generator that distributes BVG PR contribution proxies and RP pension payments across calendar month-ends using `build_time_grid(..., frequency="MONTHLY")` while emitting canonical-schema records. KA capital-withdrawal events and retirement transitions are intentionally out of scope; the generator is not wired into the default Stage-1 baseline. | Standard 36-record portfolio output, per-cohort monthly amount checks, monthly-vs-annual total parity, schema-valid DataFrame, empty portfolio, contribution multiplier semantics, invalid inputs, leap-year February month-end, immutability, and chronological per-month ordering. |
| Sprint 6C | Monthly-vs-annual BVG cashflow reconciliation | `src/pk_alm/analytics/monthly_reconciliation.py`, `tests/test_monthly_reconciliation.py` | Standalone reconciliation utility that compares monthly PR/RP totals to the annual BVG generator using a frozen `MonthlyReconciliationRow` dataclass and a validated DataFrame in the canonical reconciliation schema. KA and other event types are silently ignored. The reconciliation does not touch the default Stage-1 baseline, valuation, asset roll-forward, funding-ratio analytics, or the seven default CSV outputs. | Standard reconciliation, convenience builder, tampered monthly cashflows, empty inputs producing zero PR/RP rows, KA ignored on either side, validator failure modes (non-DataFrame, missing/reordered columns, missing values, duplicate `(reporting_year, type)`, invalid event type, broken difference / abs_difference / is_close identities, bool reporting_year), and a Stage-1 no-side-effect check across `run_stage1_baseline(output_dir=None)`. |
| Sprint 7A | AAL Asset Boundary | `src/pk_alm/adapters/aal_asset_boundary.py`, `tests/test_aal_asset_boundary.py` | Optional real AAL PAM/Portfolio construction when AAL available; offline ACTUS fixture fallback without AAL; `AALAssetBoundaryProbeResult` frozen dataclass with `service_generation_attempted` hard-enforced False; no network calls; not wired into Stage-1 baseline. | Offline fallback schema validation, source="ACTUS" enforcement, dataclass invariants, probe offline behaviour, AAL-conditional construction tests, Stage-1 no-side-effect check. |
| Sprint 7B | Pension Fund AAL Asset Demo | `src/pk_alm/scenarios/aal_asset_demo.py`, `examples/pension_fund_aal_asset_demo.py`, `tests/test_pension_fund_aal_asset_demo.py` | Separate combined cashflow demo that joins Stage-1 BVG liability cashflows with AAL Asset Boundary fallback cashflows through the canonical schema. It uses `run_stage1_baseline(..., output_dir=None)`, does not call `PublicActusService`, does not require AAL, and is not wired into the default Stage-1 baseline. | Structured result validation, schema validation, row-count identity, `BVG` and `ACTUS` source checks, annual aggregation, no output mutation, baseline integrity, custom AAL parameters. |
| Sprint 7C | AAL/ACTUS Asset Portfolio v1 | `src/pk_alm/adapters/aal_asset_portfolio.py`, `tests/test_aal_asset_portfolio.py` | Multi-contract asset portfolio specs with dynamic AAL PAM term mapping and optional real AAL Portfolio construction. Offline fixture cashflows remain available as an explicit support path. Not wired into the default Stage-1 baseline. | Default portfolio validation, invalid spec fields, duplicate IDs, mixed-currency rejection, fallback schema/source validation, dynamic term checks, optional real-AAL construction tests, Stage-1 no-side-effect checks. |
| Sprint 7D | AAL Asset Engine v1 | `src/pk_alm/assets/aal_engine.py`, `tests/test_assets_aal_engine.py` | Strategic asset-side engine. `generation_mode="aal"` is the main AAL path; `generation_mode="fallback"` is explicit only for tests/comparison/development; no silent fallback; AAL remains optional through the `[aal]` install profile. | Fallback mode, generation-mode validation, no-silent-fallback behaviour, AAL event mapping, result dataclass invariants, Stage-1 no-side-effect checks, optional real-AAL service-path tests. |
| Sprint 7E | Full ALM Scenario | `src/pk_alm/scenarios/full_alm_scenario.py`, `tests/test_full_alm_scenario.py` | Combines BVG liability cashflows with AAL Asset Engine cashflows through the shared `CashflowRecord` schema and recomputes annual cashflow analytics without mutating protected Stage-1 outputs. | Combined row count, source preservation, canonical schema validation, deterministic sorting, generation-mode validation, no-silent-fallback behaviour, Stage-1 output protection, optional real-AAL path. |
| Sprint 7F | ALM KPI / Plot-ready Outputs | `src/pk_alm/analytics/alm_kpis.py`, `tests/test_analytics_alm_kpis.py` | Builds a compact ALM KPI summary, cashflow-by-source plot table, and net-cashflow plot table from Full ALM outputs. No actual matplotlib or Streamlit plots. | KPI dataclass invariants, builder validation, funding-summary consistency, cashflow identity checks, stable output columns, no input mutation. |
| Sprint 7G | Repository Cleanup Analysis / Hygiene | Read-only cleanup analysis; generated-file hygiene only | Reviewed docs and code architecture, classified core vs support/demo layers, identified unsafe delete candidates, and removed only generated Python caches / `.DS_Store` files. Source modules, tests, examples, docs, and protected Stage-1 outputs were not deleted, renamed, or deprecated. | Full suite stayed green after hygiene cleanup. |
| Sprint 7I | Documentation Consolidation | `README.md`, `docs/implementation_progress.md`, `docs/stage1_pipeline.md`, `docs/stage1_outputs.md` | Consolidates current sprint naming, repository hygiene status, current test status, AAL Asset Engine, Full ALM Scenario, KPI/plot-ready outputs, and the protected Stage-1 vs Full ALM distinction. | Documentation-only verification through documentation, Stage-1 baseline, Full ALM, KPI, and full-suite tests. |
| Sprint 8 | Thesis-ready Reporting, Plots, and Benchmark Preparation | `src/pk_alm/reporting/`, `tests/test_reporting_full_alm_export.py`, `tests/test_reporting_plots.py`, `tests/test_reporting_benchmark.py` | Exports Full ALM results to separate CSV files, saves matplotlib PNG plots, and builds caller-reference benchmark/plausibility tables without touching protected Stage-1 outputs. | Export/readback checks, calculation-vs-I/O separation, protected-output rejection, no-silent-fallback checks, PNG creation, input non-mutation, benchmark column and difference checks. |

## Current Architecture

The current architecture is organised around three engines and one shared
integration contract:

1. **BVG Liability Engine** — `src/pk_alm/bvg/` models the liability side:
   formulas, cohorts, portfolio states, yearly projection, retirement
   transitions, BVG cashflow generation, and deterministic Stage-1 valuation.
2. **AAL Asset Engine** — `src/pk_alm/assets/aal_engine.py` models the asset
   side. AAL is the strategic asset engine: `generation_mode="aal"` is the
   main path, and `generation_mode="fallback"` is an explicit
   test/comparison/development path only. The fallback path is never selected
   silently.
3. **ALM Analytics Engine** — `src/pk_alm/analytics/` validates and aggregates
   cashflows, computes structural liquidity and funding-ratio outputs, and
   builds ALM KPI / plot-ready tables.
4. **Shared CashflowRecord bridge** — `src/pk_alm/cashflows/schema.py` defines
   the canonical seven-column cashflow schema (`contractId`, `time`, `type`,
   `payoff`, `nominalValue`, `currency`, `source`). Both BVG and ACTUS/AAL
   asset cashflows use this schema before analytics combine them.

Scenario layers sit on top of these engines:

- `src/pk_alm/scenarios/stage1_baseline.py` is the protected deterministic
  Stage-1 reference scenario and the only producer of the seven protected
  Stage-1 CSV outputs.
- `src/pk_alm/scenarios/full_alm_scenario.py` is the integrated BVG + AAL
  scenario layer. It combines liability and asset-engine cashflows through
  the shared schema and recomputes annual analytics, but it does not replace
  or mutate `run_stage1_baseline(...)`.
- `src/pk_alm/reporting/` is the reporting/export layer above Full ALM. It
  writes thesis-ready CSV files, matplotlib PNG plots, and benchmark
  plausibility tables into caller-provided directories outside the protected
  Stage-1 output path.

Support and demo layers remain in the repository because they document the
incremental build path and provide useful test fixtures:

- `src/pk_alm/adapters/actus_adapter.py` and `actus_fixtures.py` are the
  schema adapter and manually checkable ACTUS-style fixture support.
- `src/pk_alm/adapters/aal_probe.py`, `aal_introspection.py`, and optional
  AAL smoke tests are diagnostic support for the optional AAL dependency.
- `src/pk_alm/adapters/aal_asset_boundary.py` and
  `aal_asset_portfolio.py` provide AAL construction helpers and portfolio
  specs used by the asset engine and demos.
- `src/pk_alm/scenarios/asset_overlay.py` and
  `src/pk_alm/scenarios/aal_asset_demo.py` are support/demo layers. They are
  not the canonical Full ALM scenario and are not deleted or deprecated here.
- `src/pk_alm/time_grid.py`,
  `src/pk_alm/bvg/monthly_cashflow_generation.py`, and
  `src/pk_alm/analytics/monthly_reconciliation.py` are standalone monthly
  feasibility/support layers. They are not wired into the protected Stage-1
  baseline.

Repository hygiene note: generated `__pycache__`, `.pyc`, and `.DS_Store`
files are not part of the architecture and may be removed safely. This does
not imply removal of any source, test, documentation, example, or protected
output file.

## Current End-to-End Demo

The end-to-end Stage-1 demo can be run with:

```bash
python examples/stage1_baseline.py
```

Expected output includes:

- the number of portfolio states,
- the number of cashflow rows,
- the number of annual cashflow rows,
- the number of asset snapshot rows,
- the number of funding-ratio rows,
- the scenario ID,
- the initial and final funding ratio,
- the minimum funding ratio and funding summary indicators,
- the structural liquidity inflection year,
- the net liquidity inflection year,
- the paths to the CSV outputs.

Generated CSV files (relative to the working directory):

- `outputs/stage1_baseline/cashflows.csv`
- `outputs/stage1_baseline/valuation_snapshots.csv`
- `outputs/stage1_baseline/annual_cashflows.csv`
- `outputs/stage1_baseline/asset_snapshots.csv`
- `outputs/stage1_baseline/funding_ratio_trajectory.csv`
- `outputs/stage1_baseline/funding_summary.csv`
- `outputs/stage1_baseline/scenario_summary.csv`

## Current Test Status

```bash
python3 -m pytest
```

Current expected result: **1074 passed, 36 skipped**.

The tests are part of the verification strategy for the bachelor thesis. They
serve as executable documentation: every financial formula has at least one
manually checkable example, every dataclass has boundary and invalid-input
tests, every validator has explicit failure-mode tests, and the scenario layer
has integration tests that pin down the pipeline.

## Known Limitations

The current implementation is intentionally narrow:

- The default demo portfolio is **not** calibrated to a real pension fund. It
  is a small, manually inspectable test/demo portfolio.
- No mortality tables.
- No new entrants.
- No wage growth.
- No inflation or pension indexation.
- No survivor benefits or disability benefits.
- No stochastic interest-rate scenarios in this Stage-1 baseline.
- The Full ALM Scenario exists, but it is not the protected Stage-1 baseline.
  `run_stage1_baseline(...)` remains the deterministic reference and the only
  default Stage-1 CSV export path. `run_full_alm_scenario(...)` combines BVG
  liability cashflows with AAL Asset Engine cashflows through the shared
  schema and leaves the seven protected Stage-1 outputs unchanged.
- AAL is the strategic asset engine, but AAL remains optional at package
  installation time and is not required by the protected Stage-1 baseline.
  `generation_mode="aal"` is the main asset-engine path and may require a
  reachable service-backed `PublicActusService.generateEvents(...)` endpoint.
  `generation_mode="fallback"` is explicit only for tests, comparison, and
  offline development; there is no silent fallback.
- The AAL/ACTUS asset portfolio is still a small, manually inspectable set of
  PAM-like contracts, not a calibrated real pension fund asset allocation.
- A standalone monthly BVG PR/RP cashflow generator
  (`src/pk_alm/bvg/monthly_cashflow_generation.py`) and a monthly-vs-annual
  reconciliation utility (`src/pk_alm/analytics/monthly_reconciliation.py`)
  exist on top of `src/pk_alm/time_grid.py`. They cover only PR and RP
  events, do not handle KA capital-withdrawals or retirement transitions,
  do not implement monthly valuation or monthly asset roll-forward, and are
  not wired into the default Stage-1 baseline. The annual baseline remains
  the reference and the seven default Stage-1 CSV outputs are unchanged.
- No multi-asset allocation, rebalancing, or market-data ingestion.
- `total_stage1_liability` is **not** a full actuarial technical liability. It
  is a deterministic Stage-1 proxy and intentionally excludes technical
  provisions / technical reserves (longevity, risk, fluctuation, additional
  reserves for pension losses).
- No dynamic multi-asset allocation, rebalancing, market-data ingestion, or
  strategy optimization.

## Baseline Default Assumptions

The `run_stage1_baseline` defaults are deliberately conservative and
transparent rather than calibrated:

- `contribution_multiplier = 1.4` is a simplified contribution inflow
  multiplier applied to the BVG age-credit total. It stands in for the combined
  employer + employee + risk + admin contribution share until a calibrated
  scenario layer is added; it is **not** a measured plan contribution rate.
- `annual_asset_return = 0.0` is a deterministic baseline assumption used to
  isolate the liability-driven funding-ratio trajectory. It is **not** a return
  forecast; positive return scenarios can be passed explicitly.
- `target_funding_ratio = 1.076` calibrates opening assets via
  `initial_assets = total_stage1_liability(0) * target_funding_ratio`.
- `minimum_funding_ratio_projection_year` and
  `maximum_funding_ratio_projection_year` in `funding_summary.csv` and
  `scenario_summary.csv` are reported as **projection years** (0..N), not
  calendar years. Calendar years for cashflow reporting use `start_year` and
  `end_year` instead.

## Next Planned Step

The deterministic annual Stage-1 baseline should remain the protected
reference baseline. After Sprint 8, the natural next coding step is thesis
scenario interpretation on top of the exported reporting artifacts: define
which explicit, caller-provided reference values belong in the benchmark
table and which generated PNGs are used in the written analysis.

Do not add stochastic rates, mortality, wage growth, inflation, dynamic
rebalancing, Streamlit, strategy optimization, monthly valuation, monthly
asset roll-forward, or technical-reserve modelling as the next step.
