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
                → find_liquidity_inflection_year(...)
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

## Step 6 — Liquidity Inflection Year

`find_liquidity_inflection_year` returns the first reporting year where the
chosen net cashflow is strictly negative:

- `use_structural=True` searches `structural_net_cashflow` (the primary
  Stage-1 KPI defined in the spec).
- `use_structural=False` searches `net_cashflow`.

Both values are stored on the `Stage1BaselineResult` so callers do not have
to re-call the function.

## Reproducibility

The project pins the pipeline behaviour via tests. To verify reproducibility:

```bash
python -m pytest -v
```

To run the demo and produce CSVs:

```bash
python examples/stage1_baseline.py
```

CSV outputs are written to `outputs/stage1_baseline/` relative to the working
directory and contain exactly the columns of the in-memory DataFrames.

## Interpretation Warning

The current default demo is intentionally small and manually inspectable.
Its outputs are a property of the demo inputs, not empirical findings about
any real pension fund. Results should not yet be compared to Complementa
benchmarks or to any individual fund's reported figures. Calibration to
realistic populations belongs to a later sprint together with the asset
side and the funding ratio.
