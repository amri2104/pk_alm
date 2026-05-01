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

## ADR 006: Why Demographic Dynamics Come Before Mortality

**Status:** Accepted (Bauplan)

**Decision:** Stage 2 introduces deterministic demographic dynamics (new entrants, turnover, salary growth). Mortality tables are deferred to Stage 3.

**Rationale:** The single most visible weakness of Stage 1 is the closed population. Adding entries, exits, and salary growth converts the model from a run-off projection into a going-concern projection and removes the artefact that drives the funding-ratio trajectory toward 89.5 % in the demo. Mortality is a separate concern: it requires actuarial mortality tables (BVG 2020 / 2025), it is orthogonal to entry/exit mechanics, and it primarily affects the retiree side. Implementing demographic dynamics first lets Stage 3 plug into a stable open-population skeleton instead of fighting two new layers at once.

**Consequence:** Stage 2 keeps `valuation_terminal_age = 90` as the retiree run-off cap. Retirees still leave the population only via terminal age. Stage 3 will replace the terminal-age cap with mortality-table-based decrement.

## ADR 007: Why Salary Growth Is a Single Deterministic Scalar in Stage 2

**Status:** Accepted (Bauplan)

**Decision:** Salary growth in Stage 2 is a single scenario-level parameter `salary_growth_rate`, applied uniformly to all active cohorts each year.

**Rationale:** Stochastic or per-age salary growth belongs with Stage 5 (stochastic models) or with a calibrated wage-curve scenario, not with the first open-population baseline. A flat scalar (default 1.5 %) is transparent, manually checkable, and isolates the demographic effect from any wage-distribution effect. This is consistent with ADR 002 (deterministic before stochastic).

**Consequence:** Per-age, per-cohort, and stochastic salary curves are out of Stage-2 scope. They can be added later as a separate scenario layer without changing `salary_dynamics.py`'s signature, only its inputs.

## ADR 008: Why Turnover Is Applied Before Projection and After PR/RP

**Status:** Accepted (Bauplan)

**Decision:** In the Stage-2 year-loop, turnover is applied *after* the year's PR/RP cashflows are emitted from the current state, but *before* one-year projection (interest crediting + aging).

**Rationale:** A leaver is part of the active book at the start of the year — they earned their last age credit and triggered their PR contribution. They then leave with their vested capital before the year's interest is credited. This matches Swiss Freizügigkeitsleistung practice (BVG Art. 17): the vested capital snapshot is taken at the moment of leaving, not at year-end after projection. Putting turnover after projection would credit a full year's interest to leavers, which is wrong; putting it before PR/RP would skip the leaver's last contribution, which is also wrong.

**Consequence:** Turnover sits between cashflow emission (step 1) and projection (step 3) in the canonical Stage-2 loop. The `EX` cashflow uses the per-person capital *as observed at year-start*, which is the same value that drives the PR contribution.

## ADR 009: Why New Entrants Get Zero Entry Capital by Default

**Status:** Accepted (Bauplan)

**Decision:** `EntryAssumptions.entry_capital_per_person = 0` by default. No `IN` cashflow is emitted unless the scenario sets a positive entry capital explicitly.

**Rationale:** In reality, a new entrant typically brings Freizügigkeitsleistung from a previous pension fund. Modelling this realistically requires a distribution of entry capitals tied to age and prior tenure, which is calibration territory. A default of zero is the conservative, transparent choice: it lets the BVG age-credit mechanic accumulate capital from scratch and makes the entry effect easy to read in the cashflow output. Users who want to model FZL-importing entries can pass a calibrated scalar.

**Consequence:** With default Stage-2 settings, the funding ratio receives no asset injection from entries — only contribution-side dynamics matter. This isolates the demographic effect and keeps the baseline analytically clean.

## ADR 010: Why Stage 2 Has Its Own Engine and Scenario Instead of Mutating Stage 1

**Status:** Accepted (Bauplan)

**Decision:** Stage 2 introduces `engine_stage2.py` and `scenarios/stage2_baseline.py` as parallel files. The Stage-1 engine and the Stage-1 scenario are not modified.

**Rationale:** Stage 1 is the protected reference baseline (per the AGENTS.md Protected Baseline rule). Mutating `engine.py` to take new optional parameters would break that protection: even if the defaults reproduce Stage-1 behaviour, the test suite around Stage 1 implicitly depends on the file's identity. A parallel file keeps the protection guarantee literal: `git diff` on `engine.py` shows no change after Stage 2 lands. This also gives Stage 2 room to evolve its own validation rules and result dataclass without entangling them with Stage-1 invariants.

**Consequence:** Two engines exist (`engine.py`, `engine_stage2.py`). Both can call into the shared building blocks (`portfolio_projection`, `retirement_transition`, `cashflow_generation`). The Stage-2 test suite includes a mandatory equivalence test that pins Stage-2-with-zero-levers identical to Stage 1, so the duplication does not drift.
