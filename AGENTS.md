# Agent Operating Guide

This repository is the clean rebuild for the bachelor thesis:

**Enhanced Portfolio Analytics for Pension Funds using ACTUS and Python**

The project is a cashflow-based ALM tool for Swiss pension funds. It combines
purpose-built Python logic for BVG liabilities with ACTUS/AAL-based asset
cashflows and analytics around liquidity, funding ratios, KPIs, and
plot-ready outputs.

## Required Reading

Before implementation work, read:

- `docs/stage1_spec.md`
- `docs/domain_notes.md`
- `docs/decisions.md`

These files define the modelling scope, domain conventions, architectural
decisions, and current Stage-1 boundaries.

## Architecture

The current architecture has three engines plus one shared integration
contract:

1. **BVG Liability Engine** — liability-side BVG cohorts, projections,
   retirement transitions, cashflows, and valuation.
2. **AAL Asset Engine** — strategic asset-side engine using AAL/ACTUS.
3. **ALM Analytics Engine** — combines cashflows and builds liquidity,
   funding-ratio, KPI, and plot-ready outputs.

The shared `CashflowRecord` schema is the bridge between engines:

```text
contractId, time, type, payoff, nominalValue, currency, source
```

The `source` column is mandatory. Positive `payoff` means inflow to the
pension fund; negative `payoff` means outflow.

## AAL And Fallback Rules

- AAL is the strategic asset engine for the asset side.
- `generation_mode="aal"` is the main asset path.
- `generation_mode="fallback"` is explicit only for tests, comparison, and
  offline development.
- Never silently fall back from AAL mode to fallback mode.
- AAL is optional for package installation and must not become a dependency of
  the protected Stage-1 baseline unless explicitly planned.

## Protected Baseline

The Stage-1 BVG baseline is the protected deterministic reference. Do not
modify it accidentally, and do not claim that `full_alm_scenario.py` replaces
`stage1_baseline.py`.

Do not touch:

```text
outputs/stage1_baseline/*
```

`stage1_outputs.md` documents only the seven protected Stage-1 CSV outputs,
not the Full ALM scenario.

## Scope Boundaries

Do not add the following unless explicitly planned:

- Streamlit
- stochastic scenarios or stochastic rates
- mortality tables
- wage growth
- inflation
- new entrants
- dynamic rebalancing
- early/deferred retirement
- disability or survivor benefits
- new financial assumptions hidden inside reporting layers

## Current Sprint Naming

- Sprint 7A — AAL Asset Boundary
- Sprint 7B — Pension Fund AAL Asset Demo
- Sprint 7C — AAL/ACTUS Asset Portfolio v1
- Sprint 7D — AAL Asset Engine v1
- Sprint 7E — Full ALM Scenario
- Sprint 7F — ALM KPI / Plot-ready Outputs
- Sprint 7G — Repository Cleanup Analysis / Hygiene
- Sprint 7I — Documentation Consolidation
- Sprint 7J — Agent Operating Guide

## Testing

Current full suite status:

```text
1074 passed, 36 skipped
```

Default test command:

```bash
python3 -m pytest
```

For focused work, run the relevant targeted tests first, then the full suite
when feasible. Documentation-only changes should at least run:

```bash
python3 -m pytest tests/test_documentation_status.py
```

## Engineering Posture

- Work in small increments.
- Prefer pure functions before orchestration classes.
- Keep calculations transparent and manually checkable.
- Add or preserve tests for financial formulas and schema contracts.
- Treat older demo/intermediate modules as support/demo layers unless a task
  explicitly asks to remove or consolidate them.
- Do not delete, rename, or move modules during documentation/config tasks.
