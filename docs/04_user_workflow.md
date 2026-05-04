# User Workflow

## Installation

```bash
python3 -m pip install -e .
```

Optional Streamlit cockpit dependencies:

```bash
python3 -m pip install -e ".[app]"
```

Optional stochastic rate package (local sibling repo):

```bash
python3 -m pip install -e ../stochastic_rates
```

## Tests

```bash
python3 -m pytest tests/test_documentation_status.py
python3 -m pytest
```

## Run Stage-1 Baseline

```bash
python3 examples/stage1_baseline.py
```

Outputs are written to `outputs/stage1_baseline/`.

## Run Full ALM Reporting (ACTUS/AAL)

```bash
python3 examples/full_alm_reporting_workflow.py
```

This requires the ACTUS/AAL service to be reachable. It writes to
`outputs/full_alm_scenario/` and does not modify Stage-1 outputs.

## Start the Goal-1 Advanced Cockpit

```bash
python3 -m streamlit run examples/streamlit_full_alm_app.py
```

The cockpit writes to `outputs/streamlit_goal1_advanced/` and can run either:

- ACTUS/AAL asset engine (live service)
- Deterministic proxy (fast, local, no ACTUS dependency at runtime)

## Configure Inputs

In the cockpit, upload or edit the input tables with these columns:

- Allocation: `asset_class`, `weight`
- Bonds: `contract_id`, `notional`, `coupon_rate`, `maturity_years`, `currency`
- Active cohorts: `cohort_id`, `age`, `count`, `gross_salary`, `savings_capital`, `gender`
- Retiree cohorts: `cohort_id`, `age`, `count`, `annual_pension`, `retirement_capital`, `gender`

## Analyze Funding Ratio

- Stage-1 baseline: `funding_ratio_trajectory.csv`
- Full ALM: `full_alm_funding_ratio_trajectory.csv`
- Cockpit: KPI cards and the funding-ratio chart

## Analyze Liquidity

- Use `annual_cashflows.csv` and `net_cashflow.csv`
- Structural net cashflow is the primary liquidity KPI

## Run Stress Lab

In the cockpit, the Stress Lab runs five presets in deterministic proxy mode
for speed. ACTUS and stochastic modes are disabled in the lab by design.

## Run Stochastic Rate Sensitivity

Standalone example:

```bash
python3 examples/stage2d_stochastic.py
```

Cockpit sidecar: enable stochastic in the Run tab. Results are written to
`outputs/streamlit_goal1_advanced/stochastic_sidecar/`.

## Export and Review Results

- CSV outputs: use `outputs/.../*.csv`
- Plots: use `outputs/.../plots/*.png`
- All exports are written outside the protected Stage-1 output directory.

## Typical Analyst Workflow

1. Run the Stage-1 baseline to verify deterministic reference outputs.
2. Run Full ALM reporting to integrate ACTUS assets with BVG liabilities.
3. Use the cockpit to configure inputs and visualize funding and liquidity.
4. Run stress presets for scenario comparison.
5. Run stochastic rate sensitivity for diagnostic distributions.
6. Export CSVs and plots for thesis reporting.
