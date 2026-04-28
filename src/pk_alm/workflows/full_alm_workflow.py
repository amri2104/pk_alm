"""Scriptable Full ALM reporting workflow.

This module is an orchestration layer for analysts. It delegates scenario
calculation, CSV export, plot generation, and benchmark preparation to the
existing scenario and reporting modules. It does not add model logic or
financial assumptions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pk_alm.reporting.benchmark import export_benchmark_plausibility
from pk_alm.reporting.full_alm_export import (
    FULL_ALM_EXPORT_FILENAMES,
    FullALMExportResult,
    export_full_alm_results,
)
from pk_alm.reporting.plots import (
    FULL_ALM_PLOT_FILENAMES,
    FullALMPlotExportResult,
    save_full_alm_plots,
)

_GENERATED_FILE_KEYS = ("csv", "png", "benchmark")
_SUMMARY_KEYS = (
    "output_dir",
    "generation_mode",
    "csv_count",
    "png_count",
    "benchmark_available",
    "total_generated_files",
)


@dataclass(frozen=True)
class FullALMWorkflowResult:
    """Result container for the Full ALM user-facing reporting workflow."""

    output_dir: Path
    export_result: FullALMExportResult
    plot_result: FullALMPlotExportResult
    benchmark_path: Path | None
    generated_files: dict[str, tuple[Path, ...]]
    generation_mode: str

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            raise TypeError(
                f"output_dir must be Path, got {type(self.output_dir).__name__}"
            )
        if not isinstance(self.export_result, FullALMExportResult):
            raise TypeError(
                f"export_result must be FullALMExportResult, "
                f"got {type(self.export_result).__name__}"
            )
        if not isinstance(self.plot_result, FullALMPlotExportResult):
            raise TypeError(
                f"plot_result must be FullALMPlotExportResult, "
                f"got {type(self.plot_result).__name__}"
            )
        if self.benchmark_path is not None and not isinstance(
            self.benchmark_path, Path
        ):
            raise TypeError(
                f"benchmark_path must be Path or None, "
                f"got {type(self.benchmark_path).__name__}"
            )
        if not isinstance(self.generated_files, dict):
            raise TypeError(
                f"generated_files must be dict, "
                f"got {type(self.generated_files).__name__}"
            )
        if tuple(self.generated_files.keys()) != _GENERATED_FILE_KEYS:
            raise ValueError(
                f"generated_files keys must be {_GENERATED_FILE_KEYS}, "
                f"got {tuple(self.generated_files.keys())}"
            )
        for key, paths in self.generated_files.items():
            if not isinstance(paths, tuple):
                raise TypeError(
                    f"generated_files[{key!r}] must be tuple, "
                    f"got {type(paths).__name__}"
                )
            for path in paths:
                if not isinstance(path, Path):
                    raise TypeError(
                        f"generated_files[{key!r}] entries must be Path, "
                        f"got {type(path).__name__}"
                    )
        if self.benchmark_path is None and self.generated_files["benchmark"]:
            raise ValueError(
                "generated_files['benchmark'] must be empty when "
                "benchmark_path is None"
            )
        if self.benchmark_path is not None and self.generated_files[
            "benchmark"
        ] != (self.benchmark_path,):
            raise ValueError(
                "generated_files['benchmark'] must contain benchmark_path"
            )
        if not isinstance(self.generation_mode, str) or not self.generation_mode:
            raise ValueError("generation_mode must be a non-empty string")
        if self.generation_mode != self.export_result.scenario_result.generation_mode:
            raise ValueError(
                "generation_mode must match the exported scenario result "
                f"({self.generation_mode!r} != "
                f"{self.export_result.scenario_result.generation_mode!r})"
            )


def _should_export_benchmark(
    benchmark_reference_values: Mapping[str, float] | None,
    benchmark_model_values: Mapping[str, float | None] | None,
) -> bool:
    return bool(benchmark_reference_values) or bool(benchmark_model_values)


def _build_generated_files(
    export_result: FullALMExportResult,
    plot_result: FullALMPlotExportResult,
    benchmark_path: Path | None,
) -> dict[str, tuple[Path, ...]]:
    csv_paths = tuple(
        export_result.output_paths[key] for key in FULL_ALM_EXPORT_FILENAMES
    )
    png_paths = tuple(
        plot_result.output_paths[key] for key in FULL_ALM_PLOT_FILENAMES
    )
    benchmark_paths = () if benchmark_path is None else (benchmark_path,)
    return {
        "csv": csv_paths,
        "png": png_paths,
        "benchmark": benchmark_paths,
    }


def run_full_alm_reporting_workflow(
    output_dir: str | Path,
    *,
    generation_mode: str = "aal",
    benchmark_reference_values: Mapping[str, float] | None = None,
    benchmark_model_values: Mapping[str, float | None] | None = None,
    benchmark_units: Mapping[str, str] | None = None,
    benchmark_notes: Mapping[str, str] | None = None,
    **scenario_kwargs: object,
) -> FullALMWorkflowResult:
    """Run the scriptable Full ALM reporting workflow.

    The default generation mode remains ``"aal"``. Offline fallback must be
    requested explicitly by passing ``generation_mode="fallback"``.
    """
    export_result = export_full_alm_results(
        output_dir,
        generation_mode=generation_mode,
        **scenario_kwargs,
    )

    plot_result = save_full_alm_plots(
        export_result.output_dir / "plots",
        funding_ratio_trajectory=(
            export_result.scenario_result.stage1_result.funding_ratio_trajectory
        ),
        cashflow_by_source=export_result.cashflow_by_source,
        net_cashflow=export_result.net_cashflow,
    )

    benchmark_path: Path | None = None
    if _should_export_benchmark(
        benchmark_reference_values,
        benchmark_model_values,
    ):
        benchmark_path = export_benchmark_plausibility(
            export_result.scenario_result,
            export_result.output_dir,
            reference_values=benchmark_reference_values,
            model_values=benchmark_model_values,
            units=benchmark_units,
            notes=benchmark_notes,
        )

    return FullALMWorkflowResult(
        output_dir=export_result.output_dir,
        export_result=export_result,
        plot_result=plot_result,
        benchmark_path=benchmark_path,
        generated_files=_build_generated_files(
            export_result,
            plot_result,
            benchmark_path,
        ),
        generation_mode=generation_mode,
    )


def summarize_generated_outputs(
    workflow_result: FullALMWorkflowResult,
) -> dict[str, object]:
    """Return a compact user-facing summary of generated workflow outputs."""
    if not isinstance(workflow_result, FullALMWorkflowResult):
        raise TypeError(
            "workflow_result must be FullALMWorkflowResult, got "
            f"{type(workflow_result).__name__}"
        )

    csv_count = len(workflow_result.generated_files["csv"])
    png_count = len(workflow_result.generated_files["png"])
    benchmark_count = len(workflow_result.generated_files["benchmark"])
    summary = {
        "output_dir": workflow_result.output_dir,
        "generation_mode": workflow_result.generation_mode,
        "csv_count": csv_count,
        "png_count": png_count,
        "benchmark_available": benchmark_count == 1,
        "total_generated_files": csv_count + png_count + benchmark_count,
    }
    return {key: summary[key] for key in _SUMMARY_KEYS}
