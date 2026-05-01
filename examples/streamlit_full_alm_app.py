"""Minimal Streamlit prototype for the Full ALM reporting workflow.

Run with:

    python3 -m streamlit run examples/streamlit_full_alm_app.py

The module is import-safe: importing it does not execute the workflow. The
workflow only runs after a user presses the run button in the Streamlit UI.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pk_alm.reporting.full_alm_export import FULL_ALM_EXPORT_FILENAMES
from pk_alm.reporting.plots import FULL_ALM_PLOT_FILENAMES
from pk_alm.workflows.full_alm_workflow import (
    run_full_alm_reporting_workflow,
    summarize_generated_outputs,
)

DEFAULT_OUTPUT_DIR = Path("outputs/full_alm_streamlit")
GENERATION_MODES = ("aal", "fallback")
BENCHMARK_COLUMNS = ("metric", "reference_value", "model_value", "unit", "note")

CSV_DESCRIPTIONS = {
    "kpi_summary": "Headline ALM KPIs.",
    "annual_cashflows": "Annual liquidity table.",
    "cashflow_by_source": "Annual payoff totals split by source.",
    "net_cashflow": "Plot-ready net and structural net cashflow table.",
    "combined_cashflows": "Combined canonical CashflowRecord table.",
    "funding_ratio_trajectory": "Funding-ratio trajectory by projection year.",
}

PLOT_DESCRIPTIONS = {
    "funding_ratio_trajectory": "Funding-ratio percent by projection year.",
    "net_cashflow": "Annual net and structural net cashflows.",
    "cashflow_by_source": "Annual payoff totals by source.",
    "assets_vs_liabilities": "Assets and Stage-1 liability proxy.",
}


def _get_streamlit() -> Any:
    import streamlit as st

    return st


def _expected_output_paths(output_dir: str | Path) -> dict[str, dict[str, Path]]:
    root = Path(output_dir)
    return {
        "csv": {
            key: root / filename
            for key, filename in FULL_ALM_EXPORT_FILENAMES.items()
        },
        "png": {
            key: root / "plots" / filename
            for key, filename in FULL_ALM_PLOT_FILENAMES.items()
        },
        "benchmark": {
            "benchmark_plausibility": root / "benchmark_plausibility.csv"
        },
    }


def _existing_output_summary(output_dir: str | Path) -> dict[str, object] | None:
    paths = _expected_output_paths(output_dir)
    csv_paths = tuple(paths["csv"].values())
    png_paths = tuple(paths["png"].values())
    benchmark_path = paths["benchmark"]["benchmark_plausibility"]

    if not all(path.exists() for path in csv_paths + png_paths):
        return None

    benchmark_paths = (benchmark_path,) if benchmark_path.exists() else ()
    return {
        "output_dir": Path(output_dir).resolve(),
        "generation_mode": "existing files",
        "csv_count": len(csv_paths),
        "png_count": len(png_paths),
        "benchmark_available": bool(benchmark_paths),
        "total_generated_files": len(csv_paths) + len(png_paths) + len(benchmark_paths),
    }


def _empty_benchmark_frame() -> pd.DataFrame:
    return pd.DataFrame([{column: "" for column in BENCHMARK_COLUMNS}])


def _optional_float(value: object) -> float | None:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _benchmark_inputs_from_editor(
    frame: pd.DataFrame,
) -> tuple[dict[str, float] | None, dict[str, float] | None, dict[str, str] | None, dict[str, str] | None]:
    reference_values: dict[str, float] = {}
    model_values: dict[str, float] = {}
    units: dict[str, str] = {}
    notes: dict[str, str] = {}

    if not isinstance(frame, pd.DataFrame):
        return None, None, None, None

    for _, row in frame.iterrows():
        metric = str(row.get("metric", "")).strip()
        if not metric:
            continue

        reference_value = _optional_float(row.get("reference_value"))
        model_value = _optional_float(row.get("model_value"))
        unit = str(row.get("unit", "")).strip()
        note = str(row.get("note", "")).strip()

        if reference_value is not None:
            reference_values[metric] = reference_value
        if model_value is not None:
            model_values[metric] = model_value
        if unit:
            units[metric] = unit
        if note:
            notes[metric] = note

    return (
        reference_values or None,
        model_values or None,
        units or None,
        notes or None,
    )


def _store_existing_files_in_session(st: Any, output_dir: Path) -> None:
    summary = _existing_output_summary(output_dir)
    if summary is None:
        st.session_state["workflow_completed"] = False
        st.session_state["latest_output_dir"] = str(output_dir)
        st.session_state["generated_summary"] = None
        return
    st.session_state["workflow_completed"] = True
    st.session_state["latest_output_dir"] = str(output_dir)
    st.session_state["generated_summary"] = summary


def _render_outputs(st: Any, output_dir: Path) -> None:
    paths = _expected_output_paths(output_dir)
    kpi_path = paths["csv"]["kpi_summary"]
    if not kpi_path.exists():
        st.info("No complete Full ALM output package is available yet.")
        return

    st.subheader("KPI Summary")
    st.dataframe(pd.read_csv(kpi_path), use_container_width=True)

    st.subheader("Generated CSV Tables")
    csv_tabs = st.tabs([key.replace("_", " ").title() for key in paths["csv"]])
    for tab, (key, path) in zip(csv_tabs, paths["csv"].items(), strict=True):
        with tab:
            st.caption(CSV_DESCRIPTIONS[key])
            st.dataframe(pd.read_csv(path), use_container_width=True)

    st.subheader("Generated PNG Plots")
    for key, path in paths["png"].items():
        if path.exists():
            st.caption(PLOT_DESCRIPTIONS[key])
            st.image(str(path))

    benchmark_path = paths["benchmark"]["benchmark_plausibility"]
    if benchmark_path.exists():
        st.subheader("Benchmark Plausibility")
        st.dataframe(pd.read_csv(benchmark_path), use_container_width=True)


def main() -> None:
    st = _get_streamlit()

    st.set_page_config(page_title="Full ALM Reporting Prototype", layout="wide")
    st.title("Full ALM Reporting Prototype")
    st.caption(
        "Prototype UI for existing reporting outputs. It does not add model "
        "logic or production pension fund assumptions."
    )

    if "workflow_completed" not in st.session_state:
        st.session_state["workflow_completed"] = False
        st.session_state["latest_output_dir"] = str(DEFAULT_OUTPUT_DIR)
        st.session_state["generated_summary"] = None

    with st.sidebar:
        st.header("Run Settings")
        generation_mode = st.selectbox(
            "Generation mode",
            GENERATION_MODES,
            index=0,
            help='Use "fallback" only explicitly for offline comparison.',
        )
        output_dir_text = st.text_input(
            "Output directory",
            value=st.session_state.get("latest_output_dir", str(DEFAULT_OUTPUT_DIR)),
        )
        output_dir = Path(output_dir_text)

        st.subheader("Benchmark Inputs")
        benchmark_frame = st.data_editor(
            _empty_benchmark_frame(),
            num_rows="dynamic",
            use_container_width=True,
            key="benchmark_editor",
        )

        run_clicked = st.button("Run Full ALM Workflow", type="primary")
        reload_clicked = st.button("Reload Existing Outputs")

    if run_clicked:
        (
            reference_values,
            model_values,
            units,
            notes,
        ) = _benchmark_inputs_from_editor(benchmark_frame)
        with st.spinner("Running Full ALM reporting workflow..."):
            try:
                result = run_full_alm_reporting_workflow(
                    output_dir,
                    generation_mode=generation_mode,
                    benchmark_reference_values=reference_values,
                    benchmark_model_values=model_values,
                    benchmark_units=units,
                    benchmark_notes=notes,
                )
            except Exception as exc:
                st.session_state["workflow_completed"] = False
                st.session_state["latest_output_dir"] = str(output_dir)
                st.session_state["generated_summary"] = None
                st.error(f"Workflow failed: {exc}")
            else:
                st.session_state["workflow_completed"] = True
                st.session_state["latest_output_dir"] = str(result.output_dir)
                st.session_state["generated_summary"] = summarize_generated_outputs(
                    result
                )
                st.success("Workflow completed.")

    if reload_clicked:
        _store_existing_files_in_session(st, output_dir)

    if (
        not st.session_state.get("workflow_completed")
        and not run_clicked
        and not reload_clicked
    ):
        _store_existing_files_in_session(st, output_dir)

    summary = st.session_state.get("generated_summary")
    if summary:
        st.subheader("Generated Output Summary")
        st.write(summary)

    st.info(
        'AAL mode is the strategic asset path. Fallback mode is explicit '
        "offline/comparison support only; the app does not silently fall back."
    )

    if st.session_state.get("workflow_completed"):
        _render_outputs(st, Path(st.session_state["latest_output_dir"]))
    else:
        st.info("Run the workflow or reload an existing output directory.")


if __name__ == "__main__":
    main()
