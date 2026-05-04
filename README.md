# pk_alm

Enhanced Portfolio Analytics for Pension Funds using ACTUS and Python.

This repository is an academic ALM prototype for Swiss pension funds. It
combines a BVG liability model with ACTUS/AAL asset cashflows and a shared
cashflow analytics layer to produce liquidity, funding ratio, KPI, and
plot-ready outputs.

## Architecture

- BVG Liability Engine (purpose-built Python)
- AAL Asset Engine (ACTUS/AAL contractual asset cashflows)
- ALM Analytics Engine (aggregation, KPIs, reporting)
- Shared CashflowRecord schema (integration contract)

## Quick Start

Install core dependencies:

```bash
python3 -m pip install -e .
```

Optional Streamlit cockpit:

```bash
python3 -m pip install -e ".[app]"
```

Optional stochastic rate package (local sibling repo):

```bash
python3 -m pip install -e ../stochastic_rates
```

Run Stage-1 baseline (protected deterministic reference):

```bash
python3 examples/stage1_baseline.py
```

Run Full ALM reporting (ACTUS/AAL service required):

```bash
python3 examples/full_alm_reporting_workflow.py
```

Run the Goal-1 Advanced Cockpit:

```bash
python3 -m streamlit run examples/streamlit_full_alm_app.py
```

## Documentation

- docs/01_final_model_documentation.md
- docs/02_architecture_decisions.md
- docs/03_results_and_validation.md
- docs/04_user_workflow.md
- docs/05_limitations_and_future_work.md

## Scope Notes

- Stage-1 baseline outputs are protected and remain deterministic.
- Full ALM scenario combines BVG and ACTUS/AAL cashflows without mutating
  Stage-1 outputs.
- Stage-2D is stochastic rate sensitivity only, not full stochastic ALM.
- Stage-1 liability is a proxy and excludes technical reserves.
- Equity, real estate, and alternatives are proxy models, not full ACTUS
  instruments.
