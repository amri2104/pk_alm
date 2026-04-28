# Stage 1 Specification

## Purpose

Stage 1 defines a deterministic economic ALM baseline for a Swiss pension fund. The goal is to project asset and liability cashflows, identify liquidity pressure, and compute funding-ratio development under a transparent set of assumptions.

This stage is intentionally simple. It creates a manually checkable foundation before adding stochastic scenarios, richer demographic dynamics, or strategy optimization.

## Stage 1 Scope

Stage 1 covers Goal 1 of the bachelor thesis:

- Project asset-side and liability-side cashflows over a defined horizon.
- Compute funding ratio at inception and over time.
- Compute structural net cashflows.
- Identify the liquidity inflection point.
- Report income yield from contractual and proxy income cashflows.
- Report `Pensionierungsverlust` as a KPI / P&L effect.
- Run deterministic stress scenarios.
- Validate results against plausibility ranges from the thesis documents and Complementa-style benchmarks.

## Explicit Non-Scope

Stage 1 does not include:

- Goal 2 going-concern strategy optimization.
- Stochastic interest-rate scenarios.
- Mortality tables.
- Wage growth.
- Inflation.
- Dynamic rebalancing.
- Early or deferred retirement.
- Disability benefits.
- Survivor benefits.
- Full regulatory replication.
- Multi-factor market models.

These topics may be added in later stages, but they must not leak into the Stage 1 baseline.

## Architecture

Stage 1 uses a three-engine architecture:

1. **BVG Liability Engine**
   - Models pension fund liabilities with purpose-built Python logic.
   - Produces liability cashflows and obligation snapshots.

2. **AAL Asset Engine**
   - Models asset-side cashflows.
   - Uses AAL/ACTUS mainly for contractual asset cashflows, especially bonds.
   - Allows proxy models for equities and real estate with external value assumptions.

3. **ALM Analytics Engine**
   - Merges asset and liability cashflows.
   - Computes KPIs, liquidity indicators, funding ratios, and stress results.

All engines communicate through a shared cashflow schema.

## Shared Cashflow Schema

Every cashflow event must use the same columns:

- `contractId`: ACTUS contract ID, BVG cohort ID, or proxy ID.
- `time`: event date.
- `type`: event code.
- `payoff`: cash amount from the pension fund perspective.
- `nominalValue`: current nominal value, vested capital, or state value.
- `currency`: always `CHF` in Stage 1.
- `source`: event origin, such as `ACTUS` or `BVG`.

The `source` column is mandatory because some event codes can appear in more than one engine. For example, `PR` can mean principal redemption on the asset side or contribution inflow on the BVG side.

## Sign Convention

The sign convention is always from the pension fund perspective:

- Positive `payoff` = cash inflow to the pension fund.
- Negative `payoff` = cash outflow from the pension fund.
- Zero `payoff` = state update only.

Examples:

- Contributions are positive.
- Coupons, dividends, rents, and redemptions are positive.
- Pension payments and capital withdrawals are negative.
- Vested-capital updates and present-value updates are zero-payoff state events.

## BVG Liability Engine

The BVG Liability Engine models the liability side as a deterministic cohort model.

Core responsibilities:

- Compute coordinated salary.
- Compute age credits.
- Accumulate active savings capital.
- Generate contribution cashflows.
- Convert active members into retirees at ordinary retirement age.
- Split retirement capital into annuity-financed capital and capital withdrawal.
- Compute retiree pension present value with annuity-due convention.
- Generate pension cashflows.
- Compute technical reserves.
- Produce obligation snapshots.
- Report `Pensionierungsverlust`.

The Stage 1 obligation value is:

```text
V(t) = active savings capital + retiree PV + technical reserves
```

`Pensionierungsverlust` is not added separately to `V(t)` if retiree PV already reflects the full pension obligation.

## Asset / ACTUS Portfolio Engine

The asset engine models asset-side cashflows and market values.

Expected Stage 1 modelling:

- Bonds should be represented through ACTUS-style contractual cashflows where possible.
- ACTUS is used mainly for contractual asset cashflows, especially bonds.
- Equities and real estate may be proxy models with external value and income assumptions.
- Cash may be represented as a simple cash position.
- Alternatives may be excluded or treated as a documented constant block in Stage 1.

Bond runoff is allowed in the baseline. Matured principal can be held as cash. Naive reinvestment can later be added as a sensitivity, but it is not part of the first baseline.

AAL must not be a hard dependency of the protected Stage-1 baseline. In the current implementation, the strategic asset-side path lives in the separate AAL Asset Engine: `generation_mode="aal"` is the main asset path, while `generation_mode="fallback"` is an explicit test/comparison/development path only. The optional install profile is `[aal]`.

## ALM Analytics Engine

The ALM Analytics Engine combines asset and liability outputs.

Core responsibilities:

- Validate cashflow schema.
- Merge asset and liability cashflows.
- Filter cash events from state events.
- Compute annual structural net cashflow.
- Compute cumulative net cashflow as supporting information.
- Compute funding ratio.
- Compute income yield.
- Compute `Pensionierungsverlust` summaries.
- Apply deterministic stress scenarios.

## Calibration Principle

Initial assets should be calibrated to the initial funding-ratio benchmark, not fixed blindly at CHF 100m.

The calibration principle is:

```text
initial assets = V(0) * target funding ratio
```

This keeps the model internally consistent when the liability side changes. It also makes the opening funding ratio meaningful and comparable to benchmark assumptions.

## Funding Ratio Definition

The funding ratio is:

```text
Deckungsgrad(t) = assets(t) / V(t) * 100
```

Where:

```text
V(t) = active savings capital + retiree PV + technical reserves
```

Assets must reflect both market-value assumptions and cashflow effects. Pension payments and capital withdrawals should reduce available assets unless a scenario explicitly injects liquidity or financing assumptions.

## Liquidity Inflection Point Definition

The main liquidity KPI is the **structural cashflow**:

```text
contributions
+ coupons
+ dividends
+ rental income
- pensions
- capital withdrawals
```

The structural liquidity inflection point is the first year in which this annual structural cashflow becomes negative.

Cumulative net cashflow may also be reported as supporting information, but it is not the primary structural liquidity KPI.

## Stress Scenario Philosophy

Stage 1 stress scenarios are deterministic. Their purpose is to test sensitivity and interpretation, not to estimate probability distributions.

Appropriate Stage 1 stresses include:

- Interest-rate up shock.
- Interest-rate down shock.
- Equity market value shock.
- Real estate market value shock.
- Combined market stress.

Stochastic Monte Carlo scenarios belong to a later stage.

## Validation Strategy

Validation must combine internal formula checks and external plausibility checks.

Internal checks:

- Coordinated salary formula.
- Age-credit brackets.
- Interest-crediting order.
- Annuity-due present value.
- Pension present-value roll-forward.
- Correct sign convention.
- No double-counting of `Pensionierungsverlust`.

External plausibility checks:

- Opening funding ratio should match the target benchmark.
- Income yield should be in a plausible range.
- Obligations per insured person should be plausible.
- Stress scenarios should move results in economically explainable directions.

Every financial formula should have a test with manually checkable numbers.

## Known Limitations

Stage 1 is not a full going-concern pension fund model. In particular:

- Closed-population runoff can produce unrealistic long-horizon funding-ratio paths.
- No mortality table is used.
- No new entrants are modelled.
- Salaries are constant.
- Pension indexation is ignored.
- Equity and real estate are proxy models.
- Bond reinvestment is not part of the baseline.
- No dynamic allocation strategy is modelled.

These limitations must be discussed in thesis text and should guide later extension stages.
