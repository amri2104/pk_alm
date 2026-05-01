# Stage-1 Freeze

## Freeze Decision

Stage 1 is frozen as the protected deterministic reference baseline for the bachelor thesis project. The freeze covers the Stage-1 BVG liability projection, deterministic asset roll-forward, funding-ratio analytics, cashflow schema, and protected CSV outputs documented in `docs/stage1_outputs.md`.

No Stage-1 freeze task should change model logic, `run_stage1_baseline(...)`, or files under `outputs/stage1_baseline/`.

## Stage-1 Purpose

Stage 1 provides a manually checkable deterministic ALM baseline for a Swiss pension fund. It exists to make cashflow timing, liability projection, liquidity pressure, and funding-ratio mechanics transparent before later actuarial, demographic, stochastic, or strategy layers are added.

## What Stage 1 Contains

- BVG cohort data structures for active and retired members.
- Deterministic active capital accumulation and retiree run-off.
- Contribution, pension-payment, and capital-withdrawal cashflows.
- Retirement transition at ordinary retirement age.
- Retiree obligation present value using an annuity-due convention.
- `Pensionierungsverlust` as a KPI / P&L effect.
- Stage-1 Liability Proxy:

```text
active savings capital + retiree obligation PV
```

- Deterministic asset roll-forward calibrated to the target opening funding ratio.
- Annual cashflow aggregation and liquidity inflection indicators.
- Funding-ratio trajectory and funding summary.
- Shared `CashflowRecord` schema with mandatory `source`.

## What Stage 1 Does Not Contain

- Technical reserves.
- Mortality tables.
- New entrants.
- Exits / turnover.
- Salary growth.
- Inflation or pension indexation.
- Dynamic rebalancing.
- Stochastic interest-rate scenarios.
- Full BVG regulatory replication.
- Going-concern strategy logic.
- Production-grade market-data ingestion.

Technical reserves are not implemented in Stage 1. They are deferred to Stage 2+ / future actuarial extensions.

## Architecture

Stage 1 is organised around three engines and one integration contract:

1. BVG Liability Engine: `src/pk_alm/bvg/`
2. AAL Asset Engine: `src/pk_alm/assets/aal_engine.py`
3. ALM Analytics Engine: `src/pk_alm/analytics/`
4. Shared CashflowRecord schema: `src/pk_alm/cashflows/schema.py`

The protected Stage-1 reference scenario is `src/pk_alm/scenarios/stage1_baseline.py`. The integrated Full ALM scenario in `src/pk_alm/scenarios/full_alm_scenario.py` is separate and does not replace the Stage-1 baseline.

## Protected Outputs

The protected Stage-1 output directory is:

```text
outputs/stage1_baseline/
```

It contains the seven protected CSV outputs:

- `cashflows.csv`
- `valuation_snapshots.csv`
- `annual_cashflows.csv`
- `asset_snapshots.csv`
- `funding_ratio_trajectory.csv`
- `funding_summary.csv`
- `scenario_summary.csv`

Full ALM reporting outputs belong outside this directory, typically under `outputs/full_alm_scenario/`. Reporting helpers reject `outputs/stage1_baseline/` and child paths as Full ALM export targets.

## AAL / Fallback Policy

`generation_mode="aal"` is the strategic asset-engine path. It requires the optional AAL dependency and service-backed event generation.

`generation_mode="fallback"` is explicit support for tests, comparison, and offline development. The system must not silently switch from AAL mode to fallback mode. AAL errors propagate unless the caller explicitly requests fallback mode.

AAL remains optional for package installation and is not a dependency of the protected Stage-1 baseline.

## Test Protection

The current full-suite command is:

```bash
python3 -m pytest
```

Current confirmed result:

```text
1074 passed, 36 skipped
```

Stage-1 protection is covered by tests for:

- Stage-1 scenario outputs and CSV roundtrips.
- BVG formulas, cohorts, projection, retirement transitions, valuation, and cashflow generation.
- Shared cashflow schema validation and source handling.
- Funding, funding summary, annual cashflow analytics, and scenario result summaries.
- AAL/fallback mode behavior and no-silent-fallback guarantees.
- Full ALM export/workflow rejection of protected Stage-1 output paths.

## Known Limitations

Stage 1 is a deterministic thesis baseline, not a calibrated production pension fund model. The default portfolio is intentionally small and manually inspectable. Long-horizon results reflect closed-population run-off and should be interpreted as a baseline mechanics demonstration.

The Stage-1 Liability Proxy is not a full actuarial technical liability. Technical reserves, mortality, open-population dynamics, and stochastic market scenarios remain out of scope.

## Handover To Stage 2

Stage 2 should build on the frozen Stage-1 baseline without mutating it. New mechanics should live in parallel modules or explicitly planned extension layers, with tests proving that Stage-1 outputs and `run_stage1_baseline(...)` remain unchanged.

Recommended handover order:

1. Population dynamics.
2. Mortality layer.
3. Salary and contribution growth.
4. Stochastic interest-rate integration.
5. Going-concern strategy layer.
