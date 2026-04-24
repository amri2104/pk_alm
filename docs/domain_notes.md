# Domain Notes

## 1. Source Basis

These notes summarize the domain knowledge that currently frames the clean rebuild of `pk_alm`. They are based on the following working documents from the bachelor thesis environment:

- `ACTUS.pdf`, which explains the ACTUS standard and its role in standardized financial contract modelling.
- `MT_maierdon.pdf`, which documents Donat Maier's Awesome ACTUS Library (AAL) as a Python software package for ACTUS-based financial contract simulation and analysis.
- `PA_ACTUS_Lib_Analysis.pdf`, which documents the previous project thesis on stochastic interest-rate scenarios, curve calibration and ACTUS-compatible risk-factor integration.
- `04.09.2024_Medienmitteilung_Trends-bei-Pensionskassen.pdf`, which provides current Swiss pension fund context from the Complementa pension fund study.
- `T_VL_Vorlage_Bewertungsraster_PA_BA.pdf`, which clarifies that the bachelor thesis must show not only working code, but also a clear methodology, tests, documentation, critical discussion and reproducible results.

The purpose of this file is not to replace the formal thesis literature review. It is a project-level orientation document for the implementation: what the domain is, why the system is being built, and which modelling steps should come first.

## 2. ACTUS as the Conceptual Foundation

The starting point of this bachelor thesis is the ACTUS standard, short for Algorithmic Contract Types Unified Standards. ACTUS was introduced to address a fundamental problem in financial analysis: financial contracts are often described, stored and modelled differently across institutions. This makes it difficult to compare results, aggregate exposures and perform transparent risk analysis across portfolios.

ACTUS treats the financial contract as the elementary building block of financial analysis. The core idea is that a contract can be represented through standardized contract terms, event logic and external risk factors. From these inputs, algorithmic contract types generate future contract events and cash flows. This turns legal and economic contract descriptions into a standardized, machine-readable and reproducible representation.

The basic ACTUS chain is:

1. Contract terms describe the known contractual properties, such as notional amount, maturity, interest rate, payment frequency or amortization logic.
2. Risk factors describe the external environment, such as interest rates, reference indices, foreign exchange rates or other market variables.
3. Contract type algorithms transform the contract terms and risk-factor states into contract events.
4. Contract events produce cash flows over time.
5. The resulting cash-flow stream can be aggregated and analysed for liquidity, income, value, sensitivities and risk.

This chain is important because it separates known contractual information from uncertain future developments. The known part is the contract structure. The unknown part is the future evolution of risk factors. This separation makes it possible to run the same contract logic under different economic scenarios without redefining the contract itself.

For this bachelor thesis, ACTUS is primarily relevant on the asset side of a pension fund portfolio. Instruments such as bonds, mortgages, loans or annuity-like contracts can be represented through standardized ACTUS Contract Types. Their future cash flows can then be generated in a consistent way and used as inputs for pension fund Asset-Liability Management (ALM).

## 3. Awesome ACTUS Library as the Software Foundation

Although ACTUS provides a strong conceptual and mathematical standard, practical use requires accessible software tooling. Donat Maier's master thesis developed the Awesome ACTUS Library (AAL), a Python-based package for modelling, simulating and analysing financial contracts based on ACTUS.

AAL makes ACTUS usable in Python workflows. Instead of requiring users to work directly with the ACTUS backend infrastructure, AAL provides domain-level abstractions that are easier to use in research, education and applied analytics. The most relevant concepts are:

- `ContractModel`: represents an ACTUS financial contract, such as PAM or ANN, together with its contract terms and validation logic.
- `Portfolio`: groups multiple contracts and supports collective simulation and analysis.
- `RiskFactor`: represents external economic inputs such as yield curves or reference indices.
- `CashFlowStream`: wraps the event and cash-flow output of a simulation in an analysis-friendly structure.
- `ActusService`: communicates with an ACTUS simulation backend and returns generated events as a `CashFlowStream`.
- Value, income and liquidity analysis components: compute present values, income profiles and cash-flow aggregations over time.

The main architectural idea in AAL is a Model-Analysis-Service separation. The model layer holds contracts, portfolios and risk factors. The service layer handles communication with ACTUS simulation services. The analysis layer post-processes generated cash flows into financial metrics and visualizations.

The relevance of AAL for `pk_alm` is that it provides the existing software foundation for standardized contract-level asset cash flows. The bachelor thesis should not reimplement ACTUS contract logic from scratch. Instead, `pk_alm` should first build the pension-fund-specific ALM layer and later connect to AAL where standardized asset-side contract simulation becomes useful.

## 4. Stochastic Interest-Rate Scenarios as Previous Work

The previous project thesis extended the ACTUS/AAL ecosystem with a stochastic interest-rate scenario layer. This extension was motivated by the fact that deterministic valuation and cash-flow analysis are not sufficient for forward-looking ALM. Interest-rate-sensitive portfolios depend on the future evolution of the yield curve, and this future evolution is uncertain.

The project thesis implemented four classical one-factor short-rate models:

- Vasicek, an equilibrium model with mean-reverting Gaussian rates.
- CIR, an equilibrium model with state-dependent volatility and non-negative rates under suitable conditions.
- Ho-Lee, a no-arbitrage model with time-dependent drift and exact fitting to the initial term structure.
- Hull-White, a mean-reverting no-arbitrage model that combines curve fitting with more stable long-horizon behaviour than Ho-Lee.

The extension also introduced a curve calibration workflow. Sparse market curve inputs are transformed into a smooth representation suitable for simulation. For curve-fitting models such as Ho-Lee and Hull-White, the calibration step constructs the drift needed to reproduce the initial term structure. Flat-forward extrapolation is used to support long horizons in a stable way.

A key contribution of the previous work is the adapter from simulated interest-rate paths to ACTUS-compatible risk-factor representations. This makes it possible to run ACTUS-style contract analysis under many simulated scenarios rather than under a single deterministic curve.

The previous project thesis demonstrated this in a simplified ALM-style case study with an interest-rate-sensitive asset and liability. Instead of producing only one present value, the stochastic workflow produced a distribution of Net Present Values (NPVs), summary statistics and tail-risk measures such as Value-at-Risk (VaR) and Expected Shortfall (ES). This showed that stochastic scenarios reveal distributional and tail risks that deterministic parallel-shift analysis cannot capture.

For the bachelor thesis, this previous work is an important later-stage building block. It provides a stochastic market environment for scenario-based ALM. However, it should not be the first implementation layer of `pk_alm`. The new project first needs a clear deterministic pension fund ALM baseline before stochastic interest rates are added.

## 5. Pension Fund ALM as the Bachelor Thesis Domain

The bachelor thesis moves from financial contract analytics toward pension fund Asset-Liability Management. A pension fund is not only a portfolio of assets. It is a dynamic system in which asset cash flows, liability cash flows, member behaviour, contributions, benefit payments and investment strategy interact over time.

The central ALM question is whether the fund can meet its obligations while maintaining financial stability under different assumptions. This requires modelling both sides of the balance sheet:

- Assets, such as bonds, mortgages, equities, real estate, liquidity or alternative investments.
- Liabilities, such as pension payments, accrued retirement capital, technical provisions and future benefit obligations.
- Cash inflows, such as employer and employee contributions, asset income, redemptions and maturities.
- Cash outflows, such as pensions, lump-sum withdrawals, expenses and benefit payments.
- Balance-sheet indicators, especially asset value, liability value and funding ratio.
- Liquidity indicators, such as net cash-flow gaps and the ability to cover near-term payments.

A pension fund must also be understood as a going-concern institution. It does not simply run off a fixed balance sheet. Active members continue to pay contributions, members retire, pensioners receive benefits, the insured population changes, technical assumptions are revised and the investment strategy may be adjusted.

For `pk_alm`, this means that the system should eventually support dynamic ALM over time. It should make it possible to simulate how assets, liabilities, cash flows, funding ratios and liquidity indicators evolve over a projection horizon. It should also allow simple strategy rules, such as rebalancing the asset allocation or shifting between asset classes.

## 6. Practical Pension Fund Context

The Complementa pension fund study provides practical Swiss context for why this topic matters. Swiss pension funds operate in an environment where asset performance, interest rates, technical parameters and demographic developments all affect financial stability.

Several domain elements are especially relevant for the bachelor thesis:

- Funding ratio: The funding ratio, or Deckungsgrad, is a central indicator of pension fund health. It compares available assets with pension obligations.
- Investment performance: Asset returns can materially change funding levels and risk buffers.
- Asset allocation: Pension funds hold a mix of fixed-income assets, equities, real estate, alternatives, infrastructure and foreign investments. Strategic allocation strongly influences return and risk.
- Fixed-income exposure: Changes in the interest-rate environment affect bonds, mortgages and discounting assumptions. This connects directly to the previous stochastic interest-rate work.
- Technical interest rate: The technical discount rate influences the valuation of pensioner liabilities and technical provisions.
- Conversion rate: The Umwandlungssatz affects the transformation of retirement capital into pension payments and can create pension-loss effects if set too high relative to longevity and interest-rate assumptions.
- ALM study cycle: Pension funds typically perform ALM or asset-only studies every three to five years. Important triggers include changes in technical parameters, insured population, interest-rate environment and risk premia.

These points show that the bachelor thesis should not only be a technical simulation exercise. It should produce outputs that are meaningful in pension fund language: funding ratio development, liquidity needs, cash-flow profiles, asset-liability mismatch and the effect of strategy assumptions.

## 7. Modelling Strategy for pk_alm

The clean rebuild should be incremental. The first version should establish a simple deterministic ALM baseline before adding ACTUS, stochastic interest rates or detailed legal BVG mechanics.

The initial modelling strategy should be:

1. Start with a deterministic projection horizon, for example yearly periods.
2. Represent a simple pension fund balance sheet with opening assets and liabilities.
3. Model deterministic asset returns or asset cash flows at a high level.
4. Model liability cash flows in a simplified way, such as yearly pension payments and contributions.
5. Compute yearly asset value, liability value, net cash flow, funding ratio and liquidity gap.
6. Add simple strategy rules only after the baseline works, such as target allocation rebalancing.
7. Add going-concern population dynamics after the static version is plausible.
8. Add stochastic interest-rate scenarios after deterministic ALM outputs are validated.
9. Add ACTUS/AAL integration for asset-side contract cash flows after the ALM layer has clear interfaces.

This order matters. If the first implementation starts directly with ACTUS services, stochastic models and pension fund legal complexity, it becomes difficult to validate the basic ALM mechanics. A simple deterministic baseline gives the project a stable reference point and makes later extensions easier to test.

The first version of `pk_alm` should therefore focus on transparent data structures and traceable calculations. Each projected year should be explainable: what came in, what went out, how assets changed, how liabilities changed and why the funding ratio moved.

## 8. Initial Implementation Principle

The guiding principle for `pk_alm` is:

Start simple, validate every step, and only add complexity when the previous layer is stable.

For the bachelor thesis, this principle has both technical and academic value. Technically, it reduces the risk of building a complicated system whose results cannot be trusted. Academically, it supports a clear methodology: define the baseline, validate it, discuss its limitations and then justify each extension.

The first implementation layer should avoid:

- Full ACTUS integration.
- Stochastic interest-rate paths.
- Complex BVG legal details.
- Detailed demographic modelling.
- Production-grade market-data ingestion.
- Optimization or advanced portfolio construction.

The first implementation layer should include:

- A deterministic ALM projection.
- Simple asset and liability assumptions.
- Yearly cash-flow calculations.
- Funding ratio development.
- Liquidity indicators.
- Clear test cases with manually checkable numbers.
- Documentation that explains assumptions and limitations.

This creates a foundation that can later support the larger thesis path: from deterministic pension fund ALM to going-concern dynamics, then to strategy rules, stochastic scenarios and finally ACTUS-based asset cash-flow generation.
