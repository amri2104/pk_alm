# Stage 2 Extensions Summary

## Purpose

Stage 2 demonstrates that the frozen Stage-1 ALM baseline can be extended
without mutating Stage 1. The extensions are implemented as parallel scenario
layers that reuse the protected Stage-1 mechanics where appropriate and write
their own outputs.

## Stage 2A - Population Dynamics

Stage 2A adds deterministic population dynamics to the BVG liability path:

- entries: new active cohorts can join at year-end and contribute from the
  following projection year.
- turnover mechanism: active cohorts can produce deterministic exits and `EX`
  cashflows after regular contribution cashflows.
- salary growth: active salaries can grow deterministically over the projection
  horizon.
- `demographic_summary`: reports entries, exits, retirements, residual turnover,
  and end-of-year active and retired person counts.
- `cashflows_by_type`: reports annual cashflow totals by event type.
- output directory: `outputs/stage2a_population/`.

Caveat: the default Stage-2A demo uses `turnover_rate=0.02`, but the portfolio
is small. Because realised exits use deterministic `floor(count * rate)`, no
exits are realised in the default run. The default Stage-2A result is therefore
mainly driven by annual new entrants and salary growth.

## Stage 2B - Mortality Overlay

Stage 2B adds a minimal mortality overlay on top of Stage 2A:

- EK 0105 is used as a simplified educational mortality input.
- `mortality_mode="off"` reproduces Stage 2A exactly for the shared outputs.
- `mortality_mode="ek0105"` adjusts expected `RP` cashflows and
  mortality-weighted retiree present value only.
- retired cohort counts are not decremented in portfolio states.
- output directory: `outputs/stage2b_mortality/`.

Caveat: EK 0105 is not presented as a current Swiss pension-fund standard.
BVG 2020 / VZ 2020 would be more appropriate for real pension-fund valuation,
but they are out of scope for this prototype. Stage 2B is not a full actuarial
pension-fund valuation.

## Key Test Status

- Stage 2A final full suite: `1124 passed, 19 skipped`.
- Stage 2B final full suite: `1140 passed, 19 skipped`.
- Stage-1 outputs remained protected.

## Interpretation Limits

The Stage 2 extensions do not include:

- technical reserves
- survivor benefits
- disability benefits
- stochastic rates
- rebalancing
- a going-concern strategy layer
- production-grade actuarial valuation

## Suggested Thesis Wording

1. "Stage 2A illustrates how deterministic population dynamics can be layered
   onto the frozen Stage-1 ALM baseline without changing the Stage-1 engine or
   protected output set."

2. "In the default Stage-2A demonstration, turnover is implemented but not a
   material output driver because the small cohort counts and deterministic
   floor rule produce zero realised exits."

3. "Stage 2B uses EK 0105 as a simplified educational mortality overlay for
   expected retiree cashflows and retiree present values; it should not be read
   as a production-grade Swiss pension-fund valuation."
