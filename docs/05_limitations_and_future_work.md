# Limitations and Future Work

## Liability Limitations

- Stage-1 liability is a proxy: active savings capital plus retiree PV.
- No technical reserves or Wertschwankungsreserve.
- No Ueberobligatorium modeling.
- No disability or survivor benefits.
- EK0105 mortality is simplified and educational only.

## Asset Limitations

- Equity, real estate, and alternatives are proxy models.
- Public AAL server does not emit STK dividends or CSH interest events.
- No calibrated pension-fund asset allocation.
- Stress presets apply weight shocks, not market-value shocks.

## ALM / Strategy Limitations

- No dynamic rebalancing or strategy optimization.
- No liability-driven investment or hedging logic.
- No multi-sponsor or plan-specific rule modeling.

## Stochastic Limitations

- Stochastic scope is rates only, not full asset returns.
- Active and technical rate paths use a shared-seed proxy, not calibrated
  correlation.
- Fan charts are limited to terminal percentiles without per-year ribbons.

## Practical Use Limitations

- Prototype for academic use only.
- Not production-grade for regulatory or actuarial reporting.
- No market data ingestion or automated data validation pipeline.

## Future Work (Concrete)

- BVG 2020 / VZ 2020 mortality tables.
- Ueberobligatorium logic and plan-specific parameters.
- Technical reserves and Wertschwankungsreserve modeling.
- Market-value shocks instead of weight shocks.
- Rebalancing and allocation policy rules.
- Fan chart with per-year percentiles.
- Stochastic asset returns and correlated risk factors.
- Inflation and pension indexation.
- PDF and Excel reporting packages.
