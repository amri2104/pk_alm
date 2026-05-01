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

## Stage 2B Mortality Layer

Add an actuarial mortality layer after the population skeleton is stable.

Scope:

- Mortality-table inputs.
- Retiree decrement logic.
- Mortality-aware retiree obligation valuation.
- Explicit assumptions and validation cases.

Guardrails:

- Do not present terminal-age run-off and mortality-table valuation as the same method.
- Keep mortality assumptions visible and testable.

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
