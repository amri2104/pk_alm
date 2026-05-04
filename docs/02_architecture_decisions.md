# Architecture Decisions

## ADR Summary (Condensed)

1. Three-engine architecture with a shared CashflowRecord schema.
   - Rationale: keep liability, asset, and analytics logic separated and
     independently testable.

2. BVG liabilities remain purpose-built Python logic.
   - Rationale: BVG pension mechanics are not a standard ACTUS contract type.

3. Stage-1 baseline is deterministic and protected.
   - Rationale: deterministic outputs are easier to validate and must remain
     a stable reference.

4. Full ALM scenario is separate from Stage-1.
   - Rationale: integrated BVG + ACTUS cashflows must not mutate the protected
     Stage-1 output set.

5. CashflowRecord is the integration contract.
   - Rationale: a single schema allows consistent aggregation and validation
     across BVG and ACTUS sources.

6. Pensionierungsverlust is a KPI, not a liability add-on.
   - Rationale: the retiree PV already represents the obligation; adding the
     gap again would double-count.

7. AAL is the strategic asset engine; no silent fallback.
   - Rationale: ACTUS/AAL is required for contractual asset cashflows and must
     fail loudly if unavailable. Deterministic proxy mode is explicit.

8. ACTUS server limitations are documented, not patched silently.
   - Rationale: the public AAL server does not emit STK dividends or CSH
     interest events. The cockpit can synthesize MANUAL income for reporting
     but the asset engine does not fabricate ACTUS cashflows.

9. EK0105 mortality is educational.
   - Rationale: EK0105 is a simplified input; BVG 2020 / VZ 2020 would be
     closer to production practice.

10. Stage-2D is stochastic rate sensitivity only.
    - Rationale: only active and technical rates are stochastic; assets,
      salary growth, turnover, and UWS remain deterministic.

11. Shared-seed rate paths are a shared-shock proxy, not correlation.
    - Rationale: active and technical rate models are instantiated with the
      same seed by default. This is not a calibrated correlation model.

12. The optional `stochastic_rates` package is explicitly required.
    - Rationale: Stage-2D uses an external rate-model library and fails with
      a clear install message if missing.
