"""Matplotlib plot generation for Full ALM reporting outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from pk_alm.analytics.alm_kpis import (
    CASHFLOW_BY_SOURCE_PLOT_COLUMNS,
    NET_CASHFLOW_PLOT_COLUMNS,
)
from pk_alm.analytics.funding import validate_funding_ratio_dataframe
from pk_alm.reporting.full_alm_export import reject_protected_stage1_output_dir

FULL_ALM_PLOT_FILENAMES: dict[str, str] = {
    "funding_ratio_trajectory": "funding_ratio_trajectory.png",
    "net_cashflow": "net_cashflow.png",
    "cashflow_by_source": "cashflow_by_source.png",
    "assets_vs_liabilities": "assets_vs_liabilities.png",
}


@dataclass(frozen=True)
class FullALMPlotExportResult:
    """Result of saving Full ALM plot PNG files."""

    output_dir: Path
    output_paths: dict[str, Path]

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            raise TypeError(
                f"output_dir must be Path, got {type(self.output_dir).__name__}"
            )
        if not isinstance(self.output_paths, dict):
            raise TypeError(
                f"output_paths must be dict, got {type(self.output_paths).__name__}"
            )
        expected_keys = set(FULL_ALM_PLOT_FILENAMES)
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


def _require_dataframe(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"{name} must be a pandas DataFrame, got {type(df).__name__}"
        )
    return df.copy(deep=True)


def _validate_exact_columns(
    df: pd.DataFrame,
    expected_columns: tuple[str, ...],
    name: str,
) -> None:
    missing = [c for c in expected_columns if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")
    if list(df.columns) != list(expected_columns):
        raise ValueError(
            f"{name} columns must be {list(expected_columns)}, "
            f"got {list(df.columns)}"
        )


def plot_funding_ratio_trajectory(
    funding_ratio_trajectory: pd.DataFrame,
) -> Figure:
    """Plot funding-ratio percent over projection years."""
    df = _require_dataframe(
        funding_ratio_trajectory,
        "funding_ratio_trajectory",
    )
    validate_funding_ratio_dataframe(df)
    df = df.sort_values("projection_year", ignore_index=True)

    fig, ax = plt.subplots()
    ax.plot(df["projection_year"], df["funding_ratio_percent"], marker="o")
    ax.set_title("Funding Ratio Trajectory")
    ax.set_xlabel("Projection year")
    ax.set_ylabel("Funding ratio (%)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_net_cashflow(net_cashflow: pd.DataFrame) -> Figure:
    """Plot net and structural net cashflow over reporting years."""
    df = _require_dataframe(net_cashflow, "net_cashflow")
    _validate_exact_columns(df, NET_CASHFLOW_PLOT_COLUMNS, "net_cashflow")
    df = df.sort_values("reporting_year", ignore_index=True)

    fig, ax = plt.subplots()
    ax.plot(df["reporting_year"], df["net_cashflow"], marker="o", label="Net")
    ax.plot(
        df["reporting_year"],
        df["structural_net_cashflow"],
        marker="o",
        label="Structural net",
    )
    ax.set_title("Net Cashflow")
    ax.set_xlabel("Reporting year")
    ax.set_ylabel("Cashflow")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_cashflow_by_source(cashflow_by_source: pd.DataFrame) -> Figure:
    """Plot annual payoff totals by cashflow source."""
    df = _require_dataframe(cashflow_by_source, "cashflow_by_source")
    _validate_exact_columns(
        df,
        CASHFLOW_BY_SOURCE_PLOT_COLUMNS,
        "cashflow_by_source",
    )
    df = df.sort_values(["reporting_year", "source"], ignore_index=True)

    fig, ax = plt.subplots()
    if not df.empty:
        pivot = df.pivot(
            index="reporting_year",
            columns="source",
            values="total_payoff",
        ).fillna(0.0)
        pivot.plot(ax=ax, marker="o")
    ax.set_title("Cashflow By Source")
    ax.set_xlabel("Reporting year")
    ax.set_ylabel("Total payoff")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_assets_vs_liabilities(
    funding_ratio_trajectory: pd.DataFrame,
) -> Figure:
    """Plot assets and Stage-1 liability proxy from the funding trajectory."""
    df = _require_dataframe(
        funding_ratio_trajectory,
        "funding_ratio_trajectory",
    )
    validate_funding_ratio_dataframe(df)
    df = df.sort_values("projection_year", ignore_index=True)

    fig, ax = plt.subplots()
    ax.plot(df["projection_year"], df["asset_value"], marker="o", label="Assets")
    ax.plot(
        df["projection_year"],
        df["total_stage1_liability"],
        marker="o",
        label="Stage-1 liability proxy",
    )
    ax.set_title("Assets vs Liabilities")
    ax.set_xlabel("Projection year")
    ax.set_ylabel("Value")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def _save_png(fig: Figure, path: Path) -> None:
    fig.savefig(path, format="png", bbox_inches="tight")
    plt.close(fig)
    if not path.exists() or path.stat().st_size <= 0:
        raise RuntimeError(f"plot was not written as a non-empty PNG: {path}")


def save_full_alm_plots(
    output_dir: str | Path,
    *,
    funding_ratio_trajectory: pd.DataFrame,
    cashflow_by_source: pd.DataFrame,
    net_cashflow: pd.DataFrame,
) -> FullALMPlotExportResult:
    """Save the standard Full ALM plot package as PNG files."""
    out_path = reject_protected_stage1_output_dir(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    output_paths = {
        key: out_path / filename for key, filename in FULL_ALM_PLOT_FILENAMES.items()
    }
    figures = {
        "funding_ratio_trajectory": plot_funding_ratio_trajectory(
            funding_ratio_trajectory
        ),
        "net_cashflow": plot_net_cashflow(net_cashflow),
        "cashflow_by_source": plot_cashflow_by_source(cashflow_by_source),
        "assets_vs_liabilities": plot_assets_vs_liabilities(
            funding_ratio_trajectory
        ),
    }

    for key, fig in figures.items():
        _save_png(fig, output_paths[key])

    return FullALMPlotExportResult(output_dir=out_path, output_paths=output_paths)
