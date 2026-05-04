"""CSV export helpers for Full ALM scenario results.

The reporting layer is deliberately split into two steps:

- ``export_full_alm_result(...)`` writes an already computed
  :class:`FullALMScenarioResult`.
- ``export_full_alm_results(...)`` is a convenience wrapper that computes the
  scenario first and then delegates to ``export_full_alm_result(...)``.

Neither function catches AAL failures or switches generation modes. Offline
the wrapper always uses the live AAL path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pk_alm.alm_analytics_engine.alm_kpis import (
    ALMKPISummary,
    alm_kpi_summary_to_dataframe,
    build_alm_kpi_summary,
    build_cashflow_by_source_plot_table,
    build_net_cashflow_plot_table,
)
from pk_alm.alm_analytics_engine.cashflows import validate_annual_cashflow_dataframe
from pk_alm.alm_analytics_engine.funding import validate_funding_ratio_dataframe
from pk_alm.cashflows.schema import validate_cashflow_dataframe
from pk_alm.scenarios.full_alm_scenario import (
    FullALMScenarioResult,
    run_full_alm_scenario,
)

FULL_ALM_EXPORT_FILENAMES: dict[str, str] = {
    "kpi_summary": "full_alm_kpi_summary.csv",
    "annual_cashflows": "full_alm_annual_cashflows.csv",
    "cashflow_by_source": "full_alm_cashflow_by_source.csv",
    "net_cashflow": "full_alm_net_cashflow.csv",
    "combined_cashflows": "full_alm_combined_cashflows.csv",
    "funding_ratio_trajectory": "full_alm_funding_ratio_trajectory.csv",
}


@dataclass(frozen=True)
class FullALMExportResult:
    """Result of exporting a Full ALM scenario reporting package."""

    output_dir: Path
    output_paths: dict[str, Path]
    scenario_result: FullALMScenarioResult
    kpi_summary: ALMKPISummary
    kpi_summary_df: pd.DataFrame
    cashflow_by_source: pd.DataFrame
    net_cashflow: pd.DataFrame

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            raise TypeError(
                f"output_dir must be Path, got {type(self.output_dir).__name__}"
            )
        if not isinstance(self.output_paths, dict):
            raise TypeError(
                f"output_paths must be dict, got {type(self.output_paths).__name__}"
            )
        expected_keys = set(FULL_ALM_EXPORT_FILENAMES)
        if set(self.output_paths) != expected_keys:
            raise ValueError(
                f"output_paths keys must be {sorted(expected_keys)}, "
                f"got {sorted(self.output_paths)}"
            )
        for key, path in self.output_paths.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("output_paths keys must be non-empty strings")
            if not isinstance(path, Path):
                raise TypeError(
                    f"output_paths[{key!r}] must be Path, "
                    f"got {type(path).__name__}"
                )

        if not isinstance(self.scenario_result, FullALMScenarioResult):
            raise TypeError(
                "scenario_result must be FullALMScenarioResult, got "
                f"{type(self.scenario_result).__name__}"
            )
        if not isinstance(self.kpi_summary, ALMKPISummary):
            raise TypeError(
                f"kpi_summary must be ALMKPISummary, "
                f"got {type(self.kpi_summary).__name__}"
            )
        for fname in ("kpi_summary_df", "cashflow_by_source", "net_cashflow"):
            value = getattr(self, fname)
            if not isinstance(value, pd.DataFrame):
                raise TypeError(
                    f"{fname} must be a pandas DataFrame, "
                    f"got {type(value).__name__}"
                )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _protected_stage1_dirs() -> tuple[Path, ...]:
    candidates = (
        Path.cwd() / "outputs" / "stage1_baseline",
        _repo_root() / "outputs" / "stage1_baseline",
    )
    resolved: list[Path] = []
    for candidate in candidates:
        path = candidate.resolve(strict=False)
        if path not in resolved:
            resolved.append(path)
    return tuple(resolved)


def reject_protected_stage1_output_dir(output_dir: str | Path) -> Path:
    """Return a resolved Path after rejecting protected Stage-1 targets."""
    path = Path(output_dir)
    resolved = path.resolve(strict=False)
    for protected in _protected_stage1_dirs():
        if _is_relative_to(resolved, protected):
            raise ValueError(
                "Full ALM reporting outputs must not be written to "
                f"the protected Stage-1 output directory: {protected}"
            )
    return resolved


def _write_csv_and_verify(df: pd.DataFrame, path: Path) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"df must be a pandas DataFrame, got {type(df).__name__}")
    df.to_csv(path, index=False)
    roundtrip = pd.read_csv(path)
    if list(roundtrip.columns) != list(df.columns):
        raise RuntimeError(
            f"CSV roundtrip column mismatch for {path}: "
            f"{list(roundtrip.columns)} != {list(df.columns)}"
        )
    if len(roundtrip) != len(df):
        raise RuntimeError(
            f"CSV roundtrip row-count mismatch for {path}: "
            f"{len(roundtrip)} != {len(df)}"
        )


def export_full_alm_result(
    result: FullALMScenarioResult,
    output_dir: str | Path,
) -> FullALMExportResult:
    """Export an already computed Full ALM scenario result to CSV files."""
    if not isinstance(result, FullALMScenarioResult):
        raise TypeError(
            f"result must be FullALMScenarioResult, got {type(result).__name__}"
        )

    out_path = reject_protected_stage1_output_dir(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    kpi_summary = build_alm_kpi_summary(result)
    kpi_summary_df = alm_kpi_summary_to_dataframe(kpi_summary)
    cashflow_by_source = build_cashflow_by_source_plot_table(
        result.combined_cashflows
    )
    net_cashflow = build_net_cashflow_plot_table(result.annual_cashflows)

    validate_annual_cashflow_dataframe(result.annual_cashflows)
    validate_cashflow_dataframe(result.combined_cashflows)
    validate_funding_ratio_dataframe(result.stage1_result.funding_ratio_trajectory)

    dataframes = {
        "kpi_summary": kpi_summary_df,
        "annual_cashflows": result.annual_cashflows,
        "cashflow_by_source": cashflow_by_source,
        "net_cashflow": net_cashflow,
        "combined_cashflows": result.combined_cashflows,
        "funding_ratio_trajectory": result.stage1_result.funding_ratio_trajectory,
    }

    output_paths = {
        key: out_path / filename
        for key, filename in FULL_ALM_EXPORT_FILENAMES.items()
    }
    for key, df in dataframes.items():
        _write_csv_and_verify(df, output_paths[key])

    return FullALMExportResult(
        output_dir=out_path,
        output_paths=output_paths,
        scenario_result=result,
        kpi_summary=kpi_summary,
        kpi_summary_df=kpi_summary_df,
        cashflow_by_source=cashflow_by_source,
        net_cashflow=net_cashflow,
    )


def export_full_alm_results(
    output_dir: str | Path,
    **scenario_kwargs: object,
) -> FullALMExportResult:
    """Run a Full ALM scenario and export the resulting reporting package."""
    out_path = reject_protected_stage1_output_dir(output_dir)
    result = run_full_alm_scenario(**scenario_kwargs)
    return export_full_alm_result(result, out_path)
