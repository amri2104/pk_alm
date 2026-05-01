# Claude Code Project Memory

This repository is the clean rebuild for the bachelor thesis **Enhanced Portfolio Analytics for Pension Funds using ACTUS and Python**.

Current scope: **Stage 1 / Goal 1 only**. Build a deterministic pension fund ALM baseline for cashflow projection, liquidity-risk analysis, funding-ratio analysis, and transparent validation.

Before implementation, read:

- `docs/stage1_spec.md`
- `docs/domain_notes.md`
- `docs/decisions.md`

Do not implement Goal 2 going-concern strategy, stochastic interest-rate scenarios, mortality tables, wage growth, inflation, dynamic rebalancing, early/deferred retirement, disability benefits, or survivor benefits unless explicitly requested later.

Engineering rules:

- Work in small increments.
- Explain intended file changes before changing files; if in plan mode, ask for confirmation first.
- Prefer pure functions before engines.
- Add tests for every financial formula.
- Run `pytest` before summarizing implementation changes.
- Keep calculations transparent and manually checkable.

Domain conventions:

- Positive `payoff` = inflow to the pension fund.
- Negative `payoff` = outflow from the pension fund.
- `source` column is mandatory.
- Stage-1 Liability Proxy = active savings capital + retiree obligation PV.
- Technical reserves are not implemented in Stage 1.
- `Pensionierungsverlust` is reported as KPI / P&L effect and must not be double-counted if retiree PV already includes it.
