# Implementation Progress

## Current Status

The repository now contains a deterministic Stage-1 BVG liability baseline. The
current implementation covers BVG formulas, cohort dataclasses, portfolio state
and projections, retirement transitions, BVG cashflow generation, multi-year
liability projection, deterministic liability valuation snapshots, annual
liquidity analytics, deterministic asset roll-forward, funding-ratio trajectory,
funding-ratio summary analytics, scenario-level result summary reporting, and
an end-to-end demo scenario with CSV export.

The full test suite currently passes with **582 passed**.

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

## Current Architecture

The codebase is organised into seven layers, each tested independently:

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

Current expected result: **582 passed**.

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
- No ACTUS asset integration.
- No multi-asset allocation, rebalancing, or market-data ingestion.
- `total_stage1_liability` is **not** a full actuarial technical liability. It
  is a deterministic Stage-1 proxy and intentionally excludes technical
  provisions / technical reserves (longevity, risk, fluctuation, additional
  reserves for pension losses).
- Asset-side modelling is limited to a deterministic aggregate baseline.

## Next Planned Step

Sprint 4A should be a minimal ACTUS/AAL adapter exploration, not full
integration. The deterministic Stage-1 baseline should remain the reference
baseline while adapter boundaries, data-shape compatibility, and dependency
options are explored.
