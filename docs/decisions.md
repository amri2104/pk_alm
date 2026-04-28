# Architecture Decision Records

## ADR 001: Why Three Engines Instead of Pure ACTUS

**Status:** Accepted

**Decision:** Stage 1 uses three engines: BVG Liability Engine, AAL Asset Engine, and ALM Analytics Engine, connected by the shared cashflow schema.

**Rationale:** ACTUS is strong for standardized financial contract cashflows, especially asset-side instruments. Pension fund liabilities are governed by Swiss pension logic, cohort assumptions, contribution rules, conversion rates, and obligation valuation. These do not map cleanly to a single ACTUS contract type.

**Consequence:** The system keeps ACTUS/AAL where it is strongest, on the asset side, and uses purpose-built Python logic where pension fund semantics require it. The protected deterministic Stage-1 baseline remains runnable without AAL; the integrated Full ALM scenario uses the AAL Asset Engine separately.

## ADR 002: Why Stage 1 Is Deterministic Before Stochastic Scenarios

**Status:** Accepted

**Decision:** Stage 1 is deterministic. Stochastic interest-rate scenarios are deferred to a later stage.

**Rationale:** A deterministic baseline is easier to validate, explain, and debug. The thesis needs transparent ALM mechanics before adding stochastic market layers.

**Consequence:** Stage 1 focuses on traceable cashflows, funding ratio, liquidity inflection, and deterministic stress scenarios.

## ADR 003: Why BVG Liabilities Are Implemented in a Purpose-Built Python Engine

**Status:** Accepted

**Decision:** BVG liabilities are implemented in a dedicated Python engine rather than forced into ACTUS contract types.

**Rationale:** BVG liabilities involve coordinated salary, age credits, savings capital, conversion rates, pension present values, capital withdrawals, and technical reserves. These are institutional pension fund mechanics, not standard financial contracts.

**Consequence:** The BVG engine emits the same shared cashflow schema as the asset engine so that analytics remain integrated.

## ADR 004: Why Assets Are Calibrated to an Initial Funding-Ratio Benchmark

**Status:** Accepted

**Decision:** Initial assets are calibrated from initial obligations and target funding ratio.

**Rationale:** Fixing assets blindly at CHF 100m can make the opening funding ratio arbitrary. Calibrating assets to `V(0) * target funding ratio` keeps the initial balance sheet internally consistent and benchmark-aligned.

**Consequence:** Changes to liability assumptions automatically imply a consistent opening asset level.

## ADR 005: Why Pensionierungsverlust Is Reported as KPI but Not Double-Counted

**Status:** Accepted

**Decision:** `Pensionierungsverlust` is reported as a KPI / P&L effect and is not added separately to obligations if retiree PV already includes the full pension obligation.

**Rationale:** At retirement, active savings capital is removed. The annuity-financed part is converted into retiree pension PV. The difference between retiree PV and annuity-financed capital is the retirement loss. Adding it again to `V(t)` would double-count the obligation.

**Consequence:** `V(t)` remains `active savings capital + retiree PV + technical reserves`; `Pensionierungsverlust` is shown separately for interpretation.
