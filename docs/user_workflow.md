# User Workflow

This page describes the small analyst-facing Full ALM reporting workflow.
It is a scriptable workflow, not a dashboard.

## Run

From an installed or editable local checkout:

```bash
python examples/full_alm_reporting_workflow.py
```

The example writes to `outputs/full_alm_scenario/` and uses
`generation_mode="fallback"` explicitly so it can run offline. The strategic
main asset path remains `generation_mode="aal"` when AAL and its service path
are available.

## Review Outputs

1. Open `full_alm_kpi_summary.csv` for headline funding and cashflow KPIs.
2. Inspect `plots/funding_ratio_trajectory.png` for the funding-ratio path.
3. Inspect `plots/net_cashflow.png` for annual net and structural net
   cashflows.
4. Inspect `plots/cashflow_by_source.png` to separate BVG and ACTUS/AAL
   cashflow contributions.
5. Optionally provide reference values to create `benchmark_plausibility.csv`.

Full ALM workflow outputs are separate reporting artifacts. They do not
replace or mutate the protected Stage-1 files in `outputs/stage1_baseline/`.

## Streamlit Prototype

An optional Streamlit prototype can display the same workflow outputs:

```bash
pip install -e ".[app]"
python3 -m streamlit run examples/streamlit_full_alm_app.py
```

Use `pip install -e ".[app,aal]"` when the UI should run the AAL asset-engine
path. The prototype writes to `outputs/full_alm_streamlit/` by default and is
only a UI layer over the existing workflow.
