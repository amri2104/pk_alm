"""Goal-1 Streamlit dashboard workflow dispatcher.

This module is intentionally a thin orchestration layer. It does not add
model logic; it selects an existing frozen stage/scenario/workflow function,
injects the Streamlit-specific output directory, and reloads generated CSV/PNG
artifacts for display.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import EntryAssumptions

MODE_CORE = "core"
MODE_FULL_ALM_ACTUS = "full_alm_actus"
MODE_POPULATION = "population"
MODE_MORTALITY = "mortality"
MODE_DYNAMIC_PARAMETERS = "dynamic_parameters"
MODE_STOCHASTIC_RATES = "stochastic_rates"

STREAMLIT_OUTPUT_DIRS: dict[str, Path] = {
    MODE_CORE: Path("outputs/streamlit_core"),
    MODE_FULL_ALM_ACTUS: Path("outputs/streamlit_full_alm_actus"),
    MODE_POPULATION: Path("outputs/streamlit_population"),
    MODE_MORTALITY: Path("outputs/streamlit_mortality"),
    MODE_DYNAMIC_PARAMETERS: Path("outputs/streamlit_dynamic_parameters"),
    MODE_STOCHASTIC_RATES: Path("outputs/streamlit_stochastic"),
}

PROTECTED_OUTPUT_DIRS: tuple[Path, ...] = (
    Path("outputs/stage1_baseline"),
    Path("outputs/stage2a_population"),
    Path("outputs/stage2b_mortality"),
    Path("outputs/stage2c_dynamic_parameters"),
    Path("outputs/stage2d_stochastic"),
)

MODE_METADATA: dict[str, dict[str, object]] = {
    MODE_CORE: {
        "label": "Core Baseline",
        "description": "Protected-style deterministic Stage-1 baseline output.",
    },
    MODE_FULL_ALM_ACTUS: {
        "label": "Full ALM with ACTUS",
        "description": "Integrated BVG plus live AAL/ACTUS asset workflow.",
    },
    MODE_POPULATION: {
        "label": "Population",
        "description": "Stage 2A population dynamics layer.",
    },
    MODE_MORTALITY: {
        "label": "Mortality",
        "description": "Stage 2B educational mortality layer.",
    },
    MODE_DYNAMIC_PARAMETERS: {
        "label": "Dynamic Parameters",
        "description": "Stage 2C dynamic UWS, BVG interest, and discount paths.",
    },
    MODE_STOCHASTIC_RATES: {
        "label": "Stochastic Rates",
        "description": "Stage 2D stochastic active and technical rates.",
    },
}

_CSV_KEY_HINTS = (
    "kpi",
    "summary",
    "cashflow",
    "valuation",
    "funding",
    "demographic",
    "mortality",
    "parameter",
    "stochastic",
    "rate",
)


@dataclass(frozen=True)
class StageAppRunResult:
    """Result returned by the Streamlit stage dispatcher."""

    mode_id: str
    label: str
    output_dir: Path
    result: object
    csv_outputs: dict[str, pd.DataFrame]
    plot_outputs: tuple[Path, ...]
    summary: dict[str, object]

    def __post_init__(self) -> None:
        if self.mode_id not in MODE_METADATA:
            raise ValueError(f"unknown mode_id: {self.mode_id!r}")
        if not isinstance(self.output_dir, Path):
            raise TypeError("output_dir must be Path")
        if not isinstance(self.csv_outputs, dict):
            raise TypeError("csv_outputs must be dict")
        if not isinstance(self.plot_outputs, tuple):
            raise TypeError("plot_outputs must be tuple")
        if not isinstance(self.summary, dict):
            raise TypeError("summary must be dict")


def run_stage(mode_id: str, **kwargs: object) -> StageAppRunResult:
    """Run one Goal-1 dashboard mode and load its generated outputs."""
    resolved_mode = _validate_mode_id(mode_id)
    if "output_dir" in kwargs:
        raise ValueError("run_stage owns output_dir; do not pass output_dir")

    output_dir = STREAMLIT_OUTPUT_DIRS[resolved_mode]
    _reject_protected_output_dir(output_dir)

    runner_kwargs = _prepare_runner_kwargs(resolved_mode, kwargs)
    runner = _load_runner(resolved_mode)
    if resolved_mode == MODE_FULL_ALM_ACTUS:
        raw_result = runner(output_dir, **runner_kwargs)
    else:
        raw_result = runner(**runner_kwargs, output_dir=output_dir)

    csv_outputs = load_generated_csv_outputs(output_dir)
    plot_outputs = load_generated_plot_outputs(output_dir)
    summary = summarize_available_outputs(output_dir)
    label = str(MODE_METADATA[resolved_mode]["label"])
    return StageAppRunResult(
        mode_id=resolved_mode,
        label=label,
        output_dir=output_dir,
        result=raw_result,
        csv_outputs=csv_outputs,
        plot_outputs=plot_outputs,
        summary=summary,
    )


def load_generated_csv_outputs(output_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load generated CSV files below ``output_dir`` keyed by relative path."""
    root = Path(output_dir)
    if not root.exists():
        return {}
    outputs: dict[str, pd.DataFrame] = {}
    for path in sorted(root.rglob("*.csv")):
        if path.is_file():
            outputs[path.relative_to(root).as_posix()] = pd.read_csv(path)
    return outputs


def load_generated_plot_outputs(output_dir: str | Path) -> tuple[Path, ...]:
    """Return generated PNG plots below ``output_dir``."""
    root = Path(output_dir)
    if not root.exists():
        return ()
    return tuple(path for path in sorted(root.rglob("*.png")) if path.is_file())


def summarize_available_outputs(output_dir: str | Path) -> dict[str, object]:
    """Summarize generated CSV/PNG artifacts for dashboard display."""
    root = Path(output_dir)
    csv_names = tuple(
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*.csv"))
        if path.is_file()
    ) if root.exists() else ()
    png_names = tuple(
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*.png"))
        if path.is_file()
    ) if root.exists() else ()
    key_tables = tuple(
        name
        for name in csv_names
        if any(hint in name.lower() for hint in _CSV_KEY_HINTS)
    )
    return {
        "output_dir": root,
        "csv_count": len(csv_names),
        "png_count": len(png_names),
        "csv_names": csv_names,
        "png_names": png_names,
        "key_tables": key_tables,
    }


def _prepare_runner_kwargs(
    mode_id: str,
    kwargs: dict[str, object],
) -> dict[str, object]:
    prepared = dict(kwargs)
    entry_count = prepared.pop("entry_count_per_year", None)
    if entry_count is not None:
        if "entry_assumptions" in prepared:
            raise ValueError(
                "pass either entry_count_per_year or entry_assumptions, not both"
            )
        prepared["entry_assumptions"] = EntryAssumptions(
            entry_count_per_year=_validate_int(entry_count, "entry_count_per_year")
        )
    return prepared


def _load_runner(mode_id: str) -> Callable[..., object]:
    if mode_id == MODE_CORE:
        from pk_alm.scenarios.stage1_baseline import run_stage1_baseline

        return run_stage1_baseline
    if mode_id == MODE_FULL_ALM_ACTUS:
        from pk_alm.workflows.full_alm_workflow import (
            run_full_alm_reporting_workflow,
        )

        return run_full_alm_reporting_workflow
    if mode_id == MODE_POPULATION:
        from pk_alm.scenarios.stage2_baseline import run_stage2_baseline

        return run_stage2_baseline
    if mode_id == MODE_MORTALITY:
        from pk_alm.scenarios.stage2b_mortality import run_stage2b_mortality

        return run_stage2b_mortality
    if mode_id == MODE_DYNAMIC_PARAMETERS:
        from pk_alm.scenarios.stage2c_dynamic_parameters import (
            run_stage2c_dynamic_parameters,
        )

        return run_stage2c_dynamic_parameters
    if mode_id == MODE_STOCHASTIC_RATES:
        from pk_alm.scenarios.stage2d_stochastic import run_stage2d_stochastic

        return run_stage2d_stochastic
    raise ValueError(f"unknown mode_id: {mode_id!r}")


def _validate_mode_id(mode_id: object) -> str:
    if not isinstance(mode_id, str):
        raise TypeError("mode_id must be str")
    value = mode_id.strip()
    if value not in MODE_METADATA:
        raise ValueError(
            f"unknown mode_id {mode_id!r}; expected one of {tuple(MODE_METADATA)}"
        )
    return value


def _validate_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


def _reject_protected_output_dir(output_dir: str | Path) -> None:
    resolved = Path(output_dir).resolve(strict=False)
    for protected in PROTECTED_OUTPUT_DIRS:
        protected_resolved = protected.resolve(strict=False)
        try:
            resolved.relative_to(protected_resolved)
        except ValueError:
            continue
        raise ValueError(f"Streamlit outputs must not target {protected}")


__all__ = [
    "MODE_CORE",
    "MODE_DYNAMIC_PARAMETERS",
    "MODE_FULL_ALM_ACTUS",
    "MODE_METADATA",
    "MODE_MORTALITY",
    "MODE_POPULATION",
    "MODE_STOCHASTIC_RATES",
    "PROTECTED_OUTPUT_DIRS",
    "STREAMLIT_OUTPUT_DIRS",
    "StageAppRunResult",
    "load_generated_csv_outputs",
    "load_generated_plot_outputs",
    "run_stage",
    "summarize_available_outputs",
]
