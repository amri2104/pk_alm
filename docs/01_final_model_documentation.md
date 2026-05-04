# Final Model Documentation

## Purpose

`pk_alm` is an academic ALM analytics prototype for Swiss pension funds. It
projects cashflows, liquidity, and funding ratios with a transparent
liability proxy and ACTUS/AAL-based asset cashflows. The tool is designed to
be explainable and manually checkable before adding complexity.

## Domain Context (ACTUS, AAL, Swiss PK-ALM)

- ACTUS defines standardized contract types and event logic for contractual
  cashflow generation.
- AAL (Awesome ACTUS Library) provides Python interfaces to ACTUS models and
  service-backed event generation.
- Swiss pension fund ALM requires a liability model that reflects BVG
  pension mechanics, which do not map cleanly to a single ACTUS contract.

## Architecture

The system uses three engines connected by a shared integration schema:

1. BVG Liability Engine (purpose-built Python)
2. AAL Asset Engine (ACTUS/AAL cashflows)
3. ALM Analytics Engine (aggregation, KPIs, reporting)

Scenario and workflow layers sit above the engines:

- Stage-1 Baseline (protected deterministic reference)
- Full ALM Scenario (BVG + ACTUS/AAL cashflows combined in memory)
- Goal-1 Advanced Workflow and Cockpit (Stage-2 extensions + UI)

## CashflowRecord Schema and Sign Convention

Schema (column order is fixed):

```
contractId, time, type, payoff, nominalValue, currency, source
```

- `source` is mandatory to disambiguate event types across engines.
- Sign convention is from the pension fund perspective:
  - Positive `payoff` = inflow
  - Negative `payoff` = outflow
  - Zero `payoff` = state update only

## Liability Model

- Stage-1 baseline is deterministic and provides a transparent proxy:

```
Stage-1 Liability Proxy = active savings capital + retiree obligation PV
```

- `Pensionierungsverlust` is reported as a KPI and is not added to the
  liability proxy to avoid double-counting.
- Stage-2 extensions layer deterministic population dynamics, simplified
  mortality (EK0105), and dynamic parameter paths.
- Stochastic rates are handled as a sensitivity sidecar (Stage-2D), not as a
  full stochastic ALM model.
- The liability model is not a full actuarial technical liability and does
  not include technical reserves or Ueberobligatorium logic.

## Asset Model

- Contractual assets (bonds, loans, annuities) use ACTUS/AAL cashflows via
  the AAL Asset Engine.
- Equity, real estate, and alternatives are proxy or assumption-based models
  rather than fully ACTUS-modeled instruments.
- The public AAL server does not emit STK dividends or CSH interest events;
  the cockpit synthesizes assumption-based income with `source="MANUAL"` to
  keep income KPIs readable.
- The deterministic proxy asset path is used for baseline runs and for fast
  stress comparisons when ACTUS is not used. There is no silent fallback.

## ALM Analytics

- Cashflow schema validation and merging across sources
- Annual cashflow aggregation and liquidity inflection detection
- Funding ratio trajectories and summary KPIs
- Plot-ready outputs and CSV exports for reporting

## Cockpit / Dashboard

The Goal-1 Advanced Cockpit is a Streamlit UI layer that:

- Runs the Stage-2C engine with optional mortality overlay
- Uses ACTUS/AAL for assets when selected
- Adds an optional Stage-2D stochastic rate sidecar for diagnostics
- Writes outputs to `outputs/streamlit_goal1_advanced/`

The cockpit is a UI only; it does not change core calculation logic.

## Stage Overview

- Stage-1 deterministic baseline: protected reference outputs
- Full ALM scenario: combines BVG cashflows with AAL asset cashflows
- Goal-1 Advanced Cockpit: UI over Stage-2C plus optional sidecars
- Stage-2 extensions: population dynamics, mortality overlay, dynamic
  parameters, and stochastic rate sensitivity

Stage-2D is rate sensitivity only. It is not a full stochastic multi-asset
ALM simulation.

## Prototype Disclaimer

This repository is an academic prototype, not a production pension-fund
system. Results are illustrative and depend on simplified inputs and
assumptions. Regulatory-grade valuation, full BVG detail, and calibrated
strategy optimization are out of scope.
