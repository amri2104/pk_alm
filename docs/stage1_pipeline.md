# Stage-1 Pipeline

## Purpose

This document describes how the current deterministic Stage-1 BVG baseline
runs end-to-end. It is intended as a technical explanation for the
implementation, not a user tutorial. For the broader scope and methodology
see `docs/stage1_spec.md`, `docs/domain_notes.md`, and `docs/decisions.md`.

## Pipeline Overview

```
build_default_stage1_portfolio()
    → run_bvg_engine(...)
        → value_portfolio_states(...)
            → summarize_cashflows_by_year(...)
                → build_deterministic_asset_trajectory(...)
                    → build_funding_ratio_trajectory(...)
                        → summarize_funding_ratio(...)
                            → find_liquidity_inflection_year(...)
                                → build_scenario_result_summary(...)
                                    → optional CSV export
```

Each step is a thin coordinator over already-tested components. The pipeline
is encapsulated in `run_stage1_baseline(...)` in
`src/pk_alm/scenarios/stage1_baseline.py`.

## Step 1 — Initial Portfolio

The initial state is a `BVGPortfolioState` containing two collections:

- **Active cohorts** (`ActiveCohort`): a non-empty stream of contributing
  members described by `cohort_id`, `age`, `count`, `gross_salary_per_person`,
  and `capital_active_per_person`.
- **Retired cohorts** (`RetiredCohort`): a stream of pensioners described by
  `cohort_id`, `age`, `count`, `annual_pension_per_person`, and
  `capital_rente_per_person`.

Aggregate values such as `total_capital_active`, `annual_age_credit_total`,
and `annual_pension_total` are derived by dataclass properties at the cohort
and portfolio level. They are not stored separately and cannot drift.

The default demo portfolio has cohort IDs `ACT_40`, `ACT_55`, and `RET_70` and
is intentionally small.

## Step 2 — BVG Engine

`run_bvg_engine` is a deterministic multi-year coordinator. For each year in
the projection horizon it executes the same fixed sequence:

1. Generate regular PR/RP cashflows from the *current* state.
2. Project the portfolio one year forward (interest crediting and ageing).
3. Apply retirement transitions to the projected state: any active cohort
   that has reached the retirement age is converted into a retired cohort.
4. Emit a KA capital withdrawal cashflow for every retiring cohort, dated to
   the same year-end event date.
5. Append the transitioned state to the trajectory.

This timing convention is important: a cohort that starts a year at age 64
emits a final regular contribution flow for that year, ages to 65, then
retires at year-end (KA), and only starts paying RP from the following year.

Event-type meanings used by the BVG engine:

- **PR** — contribution proxy / active inflow.
- **RP** — pension payment outflow.
- **KA** — capital withdrawal outflow.

After the loop, `len(portfolio_states) == horizon_years + 1` and the
combined cashflow DataFrame is validated against the shared schema.

## Step 3 — Cashflow Schema

The shared cashflow schema has exactly seven columns, in this order:

- `contractId` — ACTUS contract ID, BVG cohort ID, or proxy ID.
- `time` — event date (normalised to `pd.Timestamp`).
- `type` — event code (e.g. `PR`, `RP`, `KA`).
- `payoff` — signed cash amount from the pension fund's perspective.
- `nominalValue` — current nominal value, vested capital, or state value.
- `currency` — always `CHF` in Stage 1.
- `source` — event origin (`BVG`, `ACTUS`, or `MANUAL`).

Sign convention from the pension fund's perspective:

- positive `payoff` = cash inflow to the pension fund,
- negative `payoff` = cash outflow from the pension fund,
- zero `payoff` = state update only.

### Minimal ACTUS Adapter Boundary

Sprint 4A adds `src/pk_alm/adapters/actus_adapter.py`, a small boundary that
maps simplified ACTUS/AAL-style event dictionaries to canonical
`CashflowRecord` objects and schema-valid DataFrames with `source="ACTUS"`.
This preserves the shared cashflow schema as the integration contract.

The adapter is not wired into `run_stage1_baseline(...)`, does not change the
seven Stage-1 CSV outputs, and does not install, import, or call AAL. The
deterministic BVG baseline remains the reference Stage-1 scenario.

Sprint 4B adds `src/pk_alm/adapters/actus_fixtures.py`, which provides
deterministic ACTUS-style fixed-rate bond events as test/example inputs for
this adapter boundary. These fixtures are manually checkable data, not an
ACTUS engine, and they are not wired into the Stage-1 scenario.

Sprint 4C adds `src/pk_alm/scenarios/asset_overlay.py`, a separate helper
that combines `run_stage1_baseline(...).engine_result.cashflows` with
ACTUS-style fixed-rate bond fixture cashflows and recomputes annual cashflow
analytics. This overlay demonstrates the shared cashflow schema, but it is
not part of `run_stage1_baseline(...)` and does not change the default CSV
exports.

Sprint 5A adds `src/pk_alm/adapters/aal_probe.py`, an optional import/version
probe and `get_aal_module()` gateway for later real AAL integration. The probe
does not generate AAL cashflows and is not wired into the default Stage-1
baseline.

Sprint 5B adds optional AAL API-surface introspection, and Sprint 5C records
real-AAL smoke-test findings: AAL `1.0.12` can construct `PAM` and `Portfolio`
objects in a temporary venv, and useful public symbols include `PAM`,
`Portfolio`, `CashFlowStream`, `PublicActusService`, `IncomeAnalysis`,
`LiquidityAnalysis`, and `ValueAnalysis`. `PublicActusService.generateEvents(...)`
appears service-backed via `/eventsBatch`. AAL remains outside the protected
Stage-1 baseline, but it is now used by the separate AAL Asset Engine when
that engine is run with `generation_mode="aal"`.

## Step 4 — Valuation Snapshots

`value_portfolio_states` builds one valuation row per portfolio state in the
trajectory. The valuation is a deterministic Stage-1 proxy.

Per snapshot:

- Active liabilities are proxied by the accumulated active savings capital
  (`total_capital_active`).
- Retired liabilities are proxied by the present value of future pensions
  discounted at `technical_interest_rate` until `valuation_terminal_age`
  (`retiree_obligation_pv`).
- `pensionierungsverlust = retiree_obligation_pv - total_capital_rente`,
  which may be positive, zero, or negative.
- `total_stage1_liability = total_capital_active + retiree_obligation_pv`.

Technical provisions / technical reserves (longevity, risk, fluctuation,
additional reserves for pension losses) are intentionally excluded.
`total_stage1_liability` is therefore not a full actuarial technical
liability; it is a transparent Stage-1 proxy.

## Step 5 — Annual Cashflow Analytics

`summarize_cashflows_by_year` aggregates the engine's cashflow DataFrame into
one row per reporting year:

- `contribution_cashflow` — sum of `payoff` where `type == "PR"`.
- `pension_payment_cashflow` — sum of `payoff` where `type == "RP"`.
- `capital_withdrawal_cashflow` — sum of `payoff` where `type == "KA"`.
- `other_cashflow` — sum of `payoff` for all other event types.
- `net_cashflow` — sum of all four buckets above (includes everything).
- `structural_net_cashflow` — `contribution_cashflow + pension_payment_cashflow`.
  KA is **excluded** from structural net cashflow because capital withdrawals
  are transition / lump-sum events, not part of the structural going-concern
  liquidity picture.
- `cumulative_net_cashflow` and `cumulative_structural_net_cashflow` —
  running totals sorted by `reporting_year`.

The validator `validate_annual_cashflow_dataframe` checks the schema,
re-validates the two identities row by row, and rejects multiple currencies.

### Time-Grid Feasibility

Sprint 6A adds `src/pk_alm/time_grid.py`, a standalone annual/monthly
time-grid helper for future monthly cashflow work. It can construct annual
year-end grids, monthly calendar month-end grids, split annual amounts, and
convert annual effective rates to periodic rates.

The annual baseline remains the reference. Monthly simulation is not wired
into `run_stage1_baseline(...)`, and this utility does not change the BVG
engine, valuation snapshots, deterministic asset roll-forward, funding-ratio
analytics, scenario summaries, or default CSV exports.

### Monthly PR/RP Cashflow Generation and Reconciliation

Sprint 6B adds `src/pk_alm/bvg/monthly_cashflow_generation.py`, a standalone
monthly BVG PR/RP cashflow generator that distributes per-cohort annual age
credit totals (PR) and annual pension totals (RP) across calendar
month-ends using `build_time_grid(..., frequency="MONTHLY")`. It emits
records in the canonical 7-column cashflow schema with `source="BVG"`. KA
capital-withdrawal events and retirement transitions are intentionally out
of scope.

Sprint 6C adds `src/pk_alm/analytics/monthly_reconciliation.py`, a
standalone reconciliation utility that compares the monthly PR/RP totals to
the annual BVG generator's PR/RP totals via a frozen
`MonthlyReconciliationRow` dataclass and a validated
monthly reconciliation DataFrame. KA and any other event types are silently
ignored.

Both Sprint 6B and Sprint 6C are separate from the annual Stage-1 pipeline.
They are not wired into `run_stage1_baseline(...)`, do not modify the BVG
engine, valuation snapshots, deterministic asset roll-forward, funding-ratio
analytics, scenario summaries, or the seven default Stage-1 CSV outputs.
Monthly PR/RP simulation remains standalone; the annual baseline is still
the reference.

### AAL Asset Boundary

Sprint 7A adds `src/pk_alm/adapters/aal_asset_boundary.py`, a separate
optional asset-model boundary. It uses the existing `get_aal_module()`
gateway from `aal_probe.py` to access AAL without a top-level import.

When AAL is available, `build_aal_pam_contract(module)` and
`build_aal_portfolio(module, contracts)` construct real `PAM` and `Portfolio`
objects. When AAL is absent, `get_aal_asset_boundary_fallback_cashflows()`
delivers schema-valid ACTUS cashflows using the deterministic bond fixtures
from `actus_fixtures.py`.

`probe_aal_asset_boundary()` reports which steps succeeded via the frozen
`AALAssetBoundaryProbeResult` dataclass. The `service_generation_attempted`
field is hard-enforced False by `__post_init__` — `PublicActusService` is
never called and no network endpoint is contacted. Production event
generation is intentionally not attempted by this boundary module.

This boundary is not part of `run_stage1_baseline(...)` and does not change
the seven default Stage-1 CSV outputs.

### Pension Fund AAL Asset Demo

Sprint 7B adds `src/pk_alm/scenarios/aal_asset_demo.py` and
`examples/pension_fund_aal_asset_demo.py` as a separate combined cashflow
demonstration. The helper runs the deterministic Stage-1 BVG baseline in
memory with `run_stage1_baseline(..., output_dir=None)`, obtains
schema-valid `ACTUS` cashflows from the AAL Asset Boundary fallback, combines
both DataFrames, and recomputes annual cashflow analytics plus structural and
net liquidity inflection years on the shared schema.

This demo shows the intended bridge between the custom BVG liability side and
the AAL/ACTUS asset side, but it is deliberately outside the default
`run_stage1_baseline(...)` pipeline. It does not write or modify the seven
default Stage-1 CSV outputs, does not require AAL, does not call
`PublicActusService`, and does not add production AAL service-backed
cashflow generation.

### AAL/ACTUS Asset Portfolio v1

Sprint 7C adds `src/pk_alm/adapters/aal_asset_portfolio.py`, an
offline-safe multi-contract asset portfolio layer. It represents each asset
with a frozen contract spec and supports a small default portfolio of CHF
fixed-rate PAM-like contracts with distinct contract IDs, maturities,
notional amounts, and coupon rates. This is a manually inspectable modelling
fixture, not a calibrated real pension fund asset allocation.

When AAL is available, the portfolio layer can map each spec into the
existing minimal AAL PAM term structure and construct multiple real AAL
`PAM` objects plus one real AAL `Portfolio`. This is model construction only:
`PublicActusService` is not called, no network endpoint is contacted, and
service-backed event generation is delegated to the later AAL Asset Engine.

For reproducibility without AAL, the same specs are converted into
schema-valid `ACTUS` cashflows through the existing fixed-rate fixture and
`actus_adapter.py` path. The fallback DataFrame validates against the shared
cashflow schema and keeps `source="ACTUS"` on every row, so it can be used by
the existing cashflow analytics while remaining separate from
`run_stage1_baseline(...)`.

### AAL Asset Engine v1

Sprint 7D adds `src/pk_alm/assets/aal_engine.py`, the strategic asset-side
engine. This engine is separate from the protected Stage-1 baseline.

The main asset path is:

```text
run_aal_asset_engine(generation_mode="aal")
    → build AAL PAM contracts from portfolio specs
        → build an AAL Portfolio
            → call PublicActusService.generateEvents(...)
                → map AAL events into the CashflowRecord schema
```

This path requires the optional AAL install profile (`pk-alm[aal]`) and a
reachable service-backed AAL event-generation path. If AAL is absent or the
service path fails, the engine raises a clear error.

The explicit support path is:

```text
run_aal_asset_engine(generation_mode="fallback")
    → build ACTUS-style fixture cashflows
        → validate the CashflowRecord schema
```

The fallback path exists for tests, comparison, and offline development. It
is not the conceptual main asset path and is never selected silently.

### Full ALM Scenario

Sprint 7E adds `src/pk_alm/scenarios/full_alm_scenario.py`, a separate
integrated scenario layer above the protected Stage-1 pipeline:

```text
run_stage1_baseline(..., output_dir=None)
    + run_aal_asset_engine(...)
        → concatenate BVG and ACTUS/AAL cashflows
            → validate the shared CashflowRecord schema
                → recompute annual cashflow analytics
```

The Full ALM Scenario combines BVG liability cashflows with AAL asset-engine
cashflows through the shared schema. It does not replace
`run_stage1_baseline(...)`, does not export the seven protected Stage-1 CSV
outputs, and does not mutate existing files under `outputs/stage1_baseline/`.

### ALM KPI / Plot-ready Outputs

Sprint 7F adds `src/pk_alm/analytics/alm_kpis.py`, a reporting layer for Full
ALM results. It produces:

- an `ALMKPISummary` with stable headline KPIs,
- a cashflow-by-source plot table with `reporting_year`, `source`, and
  `total_payoff`,
- a net-cashflow plot table that projects the validated annual cashflow
  buckets.

This layer introduces no new actuarial assumptions, market assumptions, or
funding-ratio logic. It does not create actual matplotlib charts, Streamlit
screens, or dashboard output.

### Architecture Consolidation and Documentation

Sprint 7G reviewed the architecture with documentation context and confirmed
the current three-engine structure: BVG Liability Engine, AAL Asset Engine,
and ALM Analytics Engine connected by the shared `CashflowRecord` bridge.

Sprint 7H consolidates documentation naming and current status around that
architecture. Older demo/intermediate modules remain documented as support
layers; they are not deleted, renamed, or deprecated in this sprint.

## Step 6 — Asset Snapshots

`build_deterministic_asset_trajectory` produces `asset_snapshots`. It
calibrates initial assets from the opening liability proxy and target funding
ratio:

```text
initial assets = total_stage1_liability(0) * target funding ratio
```

For each later projection year, assets are rolled forward with a deterministic
return on opening assets and the annual `net_cashflow` settled at year-end:

```text
closing_asset_value = opening_asset_value * (1 + annual_return_rate)
                    + net_cashflow
```

The asset trajectory explicitly maps `projection_year` to calendar
`reporting_year` using the scenario `start_year`. It does not infer this
mapping from the first annual cashflow row.

## Step 7 — Funding Ratio

`build_funding_ratio_trajectory` produces `funding_ratio_trajectory` by
combining asset snapshots with valuation snapshots:

```text
funding_ratio = closing_asset_value / total_stage1_liability
funding_ratio_percent = funding_ratio * 100
```

The denominator is the current deterministic Stage-1 liability proxy,
`total_stage1_liability`. Technical reserves remain excluded.

## Step 8 — Funding Summary

`summarize_funding_ratio` produces a compact `funding_summary` table from the
funding-ratio trajectory. It reports thesis-ready indicators such as initial,
final, minimum, and maximum funding ratio, the projection year in which the
minimum and maximum values first occur, years below 100%, years below the
target funding ratio, and underfunding flags.

The `minimum_funding_ratio_projection_year` and
`maximum_funding_ratio_projection_year` fields are deliberately named to make
it explicit that they are **projection years (0..N)**, not calendar years.
Calendar years appear separately in the scenario summary as `start_year` and
`end_year` and in the liquidity-inflection fields.

This summary adds no new financial mathematics; it is a validated aggregation
of the existing `funding_ratio_trajectory`.

## Step 9 — Liquidity Inflection Year

`find_liquidity_inflection_year` returns the first reporting year where the
chosen net cashflow is strictly negative:

- `use_structural=True` searches `structural_net_cashflow` (the primary
  Stage-1 KPI defined in the spec).
- `use_structural=False` searches `net_cashflow`.

Both values are stored on the `Stage1BaselineResult` so callers do not have
to re-call the function.

## Step 10 — Scenario Result Summary

`build_scenario_result_summary` produces a one-row `scenario_summary` table
after the valuation, cashflow, asset, funding-ratio, funding-summary, and
liquidity-inflection outputs are available. It aggregates the baseline run
into thesis-ready fields such as `scenario_id`, `horizon_years`, initial and
final liabilities, initial and final assets, funding-ratio summary indicators,
underfunding flags, and structural/net liquidity inflection years.

This table is reporting-only. It does not change the BVG liability logic, the
asset roll-forward, the funding-ratio formula, the valuation definition, or
the shared cashflow schema.

## Reproducibility

The project pins the pipeline behaviour via tests. To verify reproducibility:

```bash
python -m pytest -v
```

To run the demo and produce CSVs:

```bash
python examples/stage1_baseline.py
```

To run the separate pension fund AAL asset demo without writing Stage-1 CSVs:

```bash
python examples/pension_fund_aal_asset_demo.py
```

When running directly from the repository's `src/` layout without an editable
install, use `PYTHONPATH=src python3 examples/stage1_baseline.py`.

CSV outputs are written to `outputs/stage1_baseline/` relative to the working
directory and contain exactly the columns of the in-memory DataFrames,
including `asset_snapshots.csv`, `funding_ratio_trajectory.csv`, and
`funding_summary.csv`, and `scenario_summary.csv`.

## Default Assumptions

The `run_stage1_baseline` defaults are intentionally simple and explicit:

- `contribution_multiplier = 1.4` — simplified scalar applied to the BVG
  age-credit total to approximate the combined employer + employee + risk +
  admin contribution share. It is **not** a measured plan contribution rate
  and will be replaced when a calibrated scenario layer is added.
- `annual_asset_return = 0.0` — deterministic baseline assumption so that the
  funding-ratio trajectory is driven purely by liability accumulation and net
  cashflows. This is **not** a return forecast; positive return scenarios can
  be passed explicitly via the `annual_asset_return` parameter.
- `target_funding_ratio = 1.076` — calibrates opening assets via
  `initial_assets = total_stage1_liability(0) * target_funding_ratio`.
- `total_stage1_liability` excludes technical reserves and remains a Stage-1
  proxy as documented in Step 4.

## Interpretation Warning

The current default demo is intentionally small and manually inspectable.
Its outputs are a property of the demo inputs, not empirical findings about
any real pension fund. Results should not yet be compared to Complementa
benchmarks or to any individual fund's reported figures. Calibration to
realistic populations belongs to a later sprint. The deterministic Stage-1
baseline remains a transparent reference case, not calibrated empirical
evidence.
