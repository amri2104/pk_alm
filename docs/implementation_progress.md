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

Sprint 7A.1 adds an optional AAL asset boundary
(`src/pk_alm/adapters/aal_asset_boundary.py`) that can construct real AAL
`PAM` and `Portfolio` objects when AAL is available, and provides an offline
ACTUS fixture fallback that delivers schema-valid ACTUS cashflows without AAL
or any network call. `PublicActusService` is not called; the default Stage-1
baseline and seven CSV outputs are unchanged.

The full system test suite currently passes with **897 passed, 12 skipped**.
The pre-Sprint-7A.1 system result was **874 passed, 8 skipped**, the
pre-Sprint-6A system result was **753 passed, 8 skipped**, and the
pre-Sprint-6B/6C system result was **809 passed, 8 skipped**. With AAL
`1.0.12` available in the temporary `/tmp/pk_alm_aal_venv` environment, the
Sprint 5C AAL-focused suite observation was **761 passed**.

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
| Sprint 7A.1 | AAL asset boundary | `src/pk_alm/adapters/aal_asset_boundary.py`, `tests/test_aal_asset_boundary.py` | Optional real AAL PAM/Portfolio construction when AAL available; offline ACTUS fixture fallback without AAL; `AALAssetBoundaryProbeResult` frozen dataclass with `service_generation_attempted` hard-enforced False; no network calls; not wired into Stage-1 baseline. | Offline fallback schema validation, source="ACTUS" enforcement, dataclass invariants (bool type checks, impossible-state rejections), probe offline behaviour with monkeypatch, AAL-conditional construction tests (4 skipped when AAL absent), Stage-1 no-side-effect check. |

## Current Architecture

The codebase is organised into twelve layers, each tested independently:

1. **BVG domain layer** — formulas, cohorts, portfolio state, projections,
   retirement transitions.
2. **Cashflow interface layer** — shared 7-column schema and BVG cashflow
   generation that emits schema-valid records.
3. **Engine layer** — deterministic multi-year liability projection that
   composes the lower layers and emits one combined cashflow DataFrame.
4. **Valuation layer** — Stage-1 liability snapshots with the simplified
   `total_stage1_liability` proxy.
5. **Asset layer** — deterministic initial asset calibration and asset
   roll-forward snapshots.
6. **Analytics layer** — annual cashflow aggregation, structural/net liquidity
   inflection year detection, funding-ratio trajectory, and funding-ratio
   summary.
7. **Scenario layer** — a reproducible Stage-1 demo runner with scenario
   result summary and CSV export.
8. **Adapter boundary layer** — a minimal ACTUS/AAL-style event dictionary
   adapter that emits canonical cashflow records with `source="ACTUS"`, plus
   deterministic fixed-rate bond fixtures for tests and examples.
9. **Overlay demonstration layer** — a separate asset-cashflow overlay helper
   that combines BVG baseline cashflows with ACTUS-style fixture cashflows for
   annual liquidity analytics without changing the default Stage-1 scenario.
10. **Optional AAL probe layer** — an import/version probe and controlled
    `get_aal_module()` gateway for later real AAL integration while keeping
    the deterministic baseline usable without AAL.
11. **Optional AAL introspection and smoke layer** — safe API-surface
    discovery plus optional real-AAL `PAM` / `Portfolio` construction tests.
    `PublicActusService` is visible, but event generation appears
    service-backed and no production event adapter exists yet.
12. **Time-grid feasibility layer** — standalone annual/monthly grid helpers
    for later PR/RP monthly timing experiments. The annual baseline remains
    the reference.
13. **Monthly BVG PR/RP cashflow layer** — standalone generator that
    distributes per-cohort PR and RP totals across calendar month-ends using
    the time-grid helpers and emits canonical-schema records. KA / retirement
    transitions, monthly valuation, monthly asset roll-forward, and default
    Stage-1 wiring are deliberately out of scope.
14. **Monthly reconciliation layer** — standalone validator and reconciliation
    utility that proves monthly PR/RP totals equal the annual BVG generator's
    PR/RP totals up to a small tolerance. KA and other event types are
    ignored. The default Stage-1 baseline is not modified.
15. **AAL asset boundary layer** — optional real AAL `PAM`/`Portfolio`
    construction when AAL is available, plus an offline ACTUS fixture fallback
    that delivers schema-valid ACTUS cashflows without AAL or any network call.
    `service_generation_attempted` is hard-enforced False in the
    `AALAssetBoundaryProbeResult` dataclass. The default Stage-1 baseline is
    not modified.

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
python -m pytest -v
```

Current expected result: **897 passed, 12 skipped**.

Sprint 5C also recorded an AAL-available temporary-venv result:
**761 passed**. The pre-Sprint-6B/6C system result was
**809 passed, 8 skipped**. The pre-Sprint-7A.1 system result was
**874 passed, 8 skipped**.

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
- No full ACTUS/AAL scenario integration. The current adapter boundary only
  maps simplified ACTUS/AAL-style event dictionaries and deterministic
  fixed-rate bond fixtures into the shared schema. The Sprint 4C overlay
  combines BVG and fixture cashflows separately for annual analytics, but it
  is not wired into the default Stage-1 baseline exports. Sprint 5A/5B can
  probe optional AAL availability and API surface metadata, and Sprint 5C can
  construct real AAL `PAM` and `Portfolio` objects when AAL is available, but
  it does not generate real AAL cashflows or make AAL part of the default
  baseline. `PublicActusService.generateEvents(...)` appears service-backed
  through `/eventsBatch`.
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
- Asset-side modelling is limited to a deterministic aggregate baseline.

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

The deterministic annual Stage-1 baseline should remain the reference
baseline. With Sprint 7A.1 completing the offline AAL asset boundary,
candidate next sprints include: a service-backed event-generation path
using `PublicActusService` as an explicit opt-in (requires a running ACTUS
service endpoint), integrating real AAL cashflow output into the annual
analytics overlay, monthly cashflow analytics with calendar-year aggregation
back to the annual reference, or multi-year monthly grids. Monthly KA /
retirement-transition timing, monthly valuation, monthly asset roll-forward,
full ACTUS/AAL scenario wiring, stochastic rates, and calibrated asset-side
modelling remain deferred.
