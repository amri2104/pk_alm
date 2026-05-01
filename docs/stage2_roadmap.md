# Stage-2 Roadmap

Stage 2 should extend the frozen Stage-1 baseline without changing the protected Stage-1 implementation or outputs. Each layer should be introduced explicitly, with focused tests and documentation that separate new assumptions from the Stage-1 reference.

## Stage 2A Population Dynamics

Introduce deterministic population movement outside the frozen Stage-1 baseline.

Scope:

- New entrants.
- Exits / turnover.
- Open-population cohort updates.
- Separate Stage-2 scenario outputs.

Guardrails:

- Do not modify `run_stage1_baseline(...)`.
- Do not overwrite `outputs/stage1_baseline/*`.
- Keep Stage-1 equivalence tests for zero population-dynamics levers.

Caveat:

The default Stage-2A demo uses a small population. With `turnover_rate=0.02`
and deterministic `floor(count * turnover_rate)`, no exits are realised in the
default run. The default Stage-2A result is therefore mainly driven by annual
new entrants and salary growth. Turnover functionality is implemented and
tested separately, but it is not a material driver of the default demo output.

## Stage 2B Mortality Layer

Add an actuarial mortality layer after the population skeleton is stable.

Stage 2B uses EK 0105 only as a simplified educational mortality input. It
must not be presented as a current Swiss pension-fund standard. BVG 2020 /
VZ 2020 would be more appropriate for real pension-fund valuation, but are
out of scope for this prototype.

Scope:

- Mortality-table inputs.
- Mortality-weighted retiree pension cashflows and retiree present values.
- Mortality-aware retiree obligation valuation.
- Explicit assumptions and validation cases.

Guardrails:

- Do not present terminal-age run-off and mortality-table valuation as the same method.
- Keep mortality assumptions visible and testable.
- Do not decrement retired cohort counts in portfolio states in the Stage-2B prototype.

## Stage 2C Salary / Contribution Growth

Add deterministic salary and contribution growth assumptions.

Scope:

- Salary growth parameterization.
- Contribution projection affected by salary evolution.
- Scenario-level sensitivity reporting.

Guardrails:

- Keep stochastic salary paths out of this layer unless separately planned.
- Keep growth assumptions out of reporting-only code.

## Stage 2D Stochastic Interest-Rate Integration

Integrate stochastic interest-rate scenarios only after deterministic Stage-2 mechanics are stable.

Scope:

- Scenario path inputs.
- Yield-curve or rate-path adapters.
- Asset and liability sensitivity outputs.
- Distributional result summaries.

Guardrails:

- Do not replace the deterministic Stage-1 baseline.
- Do not silently mix deterministic and stochastic outputs.
- Keep AAL/fallback mode explicit.

## Stage 2E Going-Concern Strategy Layer

Add strategy logic as a separate layer after population, mortality, salary, and stochastic-rate assumptions are explicit.

Scope:

- Going-concern ALM interpretation.
- Strategy rules.
- Rebalancing or allocation policy, if explicitly planned.
- Scenario comparison outputs.

Guardrails:

- Do not hide new financial assumptions inside reporting layers.
- Do not call strategy outputs Stage-1 results.
- Preserve the protected Stage-1 output directory and baseline tests.
