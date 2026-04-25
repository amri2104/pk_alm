# Agent Instructions

This repository is the clean rebuild for the bachelor thesis:

**Enhanced Portfolio Analytics for Pension Funds using ACTUS and Python**

The repository implements **Stage 1 / Goal 1 only**: a deterministic economic ALM baseline for pension fund cashflows, liquidity risk, and funding-ratio analysis.

## Required Reading

Before implementation work, agents must read:

- `docs/stage1_spec.md`
- `docs/domain_notes.md`
- `docs/decisions.md`

These files define the project scope, domain assumptions, architectural decisions, and modelling boundaries.

## Scope Boundaries

Do not implement the following unless a later task explicitly changes the scope:

- No Goal 2 going-concern strategy optimization yet.
- No stochastic interest-rate scenarios yet.
- No mortality tables.
- No wage growth.
- No inflation.
- No dynamic rebalancing.
- No early or deferred retirement.
- No disability or survivor benefits.

Stage 1 is a deterministic baseline, not a full production pension fund model.

## Engineering Rules

- Work in small increments.
- Prefer pure functions before engines or orchestration classes.
- Add tests for every financial formula.
- Run `pytest` before summarizing implementation changes.
- Keep calculations transparent and manually checkable.
- Avoid hidden assumptions in formulas; document calibration choices.
- Do not add AAL or stochastic-rates as hard dependencies until an adapter task explicitly asks for it.

## Domain Conventions

- Positive `payoff` means cash inflow to the pension fund.
- Negative `payoff` means cash outflow from the pension fund.
- The `source` column is mandatory and must identify the origin of each event.
- The shared cashflow schema is the integration contract between engines.
- `V(t) = active savings capital + retiree PV + technical reserves`.
- `Pensionierungsverlust` is a KPI / P&L effect.
- Do not add `Pensionierungsverlust` separately to obligations if retiree PV already includes the full pension obligation.

## Implementation Posture

The first implementation should prioritize correctness and explainability over feature breadth. If a result cannot be manually checked with a small example, the model is not yet simple enough.
