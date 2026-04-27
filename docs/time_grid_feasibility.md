# Time-Grid Feasibility

## Purpose

The deterministic Stage-1 baseline remains annual and remains the reference
baseline. This document explains the standalone `src/pk_alm/time_grid.py`
utility layer added in Sprint 6A and how it prepares a later monthly
cashflow extension without changing the current engine or default outputs.

## Why Monthly Timing Matters

Annual cashflows are transparent and manually checkable, which makes them a
good first baseline. Liquidity pressure, however, often depends on under-year
timing: contributions, pension payments, coupons, redemptions, and benefit
payments may not occur at the same year-end date in practice. A monthly grid
is therefore a useful next step for liquidity analysis, while the annual
baseline remains the reference for reconciliation.

## What Could Change Later

Future monthly modelling can use the time grid to:

- place PR contribution proxy cashflows within the year,
- place RP pension payment cashflows within the year,
- convert annual rates to periodic rates with `(1 + r) ** (1 / 12) - 1`,
- split annual amounts evenly as a first approximation,
- aggregate monthly cashflows back to annual reporting years for comparison
  with the current baseline.

## What Does Not Change Yet

Sprint 6A does not change:

- the BVG engine,
- retirement-transition timing,
- valuation snapshots,
- deterministic asset roll-forward,
- funding-ratio analytics,
- scenario summaries,
- the seven default Stage-1 CSV outputs.

Monthly simulation is not wired into the default baseline. The time-grid
module is a feasibility layer only.

## Modelling Choices

The first monthly utility deliberately stays small:

- supported frequencies are `ANNUAL` and `MONTHLY`,
- annual grids use 31 December event dates,
- monthly grids use calendar month-end dates,
- annual amounts can be split evenly across periods,
- annual effective rates can be converted to equivalent periodic rates.

These choices are intentionally simple and manually checkable. They do not
yet represent a real pension fund payment calendar.

## Sprint 6B and Sprint 6C Status

- **Sprint 6B — implemented (PR/RP only).** A standalone monthly BVG PR/RP
  cashflow generator is now available in
  `src/pk_alm/bvg/monthly_cashflow_generation.py`. It uses
  `build_time_grid(..., frequency="MONTHLY")` from this module to emit
  schema-valid records with `source="BVG"` for each calendar month-end of a
  reporting year.
- **Sprint 6C — implemented (PR/RP only).** A standalone monthly-vs-annual
  reconciliation utility is now available in
  `src/pk_alm/analytics/monthly_reconciliation.py`. It validates that the
  monthly PR/RP totals equal the annual BVG generator's totals up to a
  small tolerance.

## Current Monthly Scope

The current monthly utilities are deliberately narrow:

- PR contribution proxy and RP pension payment events only.
- No KA capital-withdrawal monthly transition logic.
- No monthly valuation, no monthly funding ratio, no monthly asset
  roll-forward.
- No multi-year monthly grid in the generator (one reporting year at a
  time); the time-grid module itself can produce multi-year monthly grids
  but no consumer uses that yet.
- No calendar-aware payment days; month-end dates are used as a transparent
  simplification.
- Monthly PR/RP simulation is **not** wired into the default Stage-1
  baseline. The annual baseline remains the reference and the seven default
  Stage-1 CSV outputs are unchanged.

## Limitations

This feasibility layer still excludes mortality, wage growth, new entrants,
inflation, pension indexation, a real payment calendar, monthly valuation,
technical reserves, stochastic rates, and full ACTUS/AAL scenario wiring.
