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

## Future Sprints

- **Sprint 6B:** add a monthly BVG PR/RP cashflow generator while leaving KA
  retirement-transition timing explicit and tested.
- **Sprint 6C:** add monthly analytics and annual aggregation comparison
  against the reference annual baseline.

## Limitations

This feasibility layer still excludes mortality, wage growth, new entrants,
inflation, pension indexation, a real payment calendar, monthly valuation,
technical reserves, stochastic rates, and full ACTUS/AAL scenario wiring.
