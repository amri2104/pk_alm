"""Benchmark and plausibility tables for Full ALM scenario outputs.

This module prepares comparison tables only. It does not fetch data and does
not embed empirical claims as defaults. Reference values are caller-provided.
"""

from __future__ import annotations

import math
import numbers
from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from pk_alm.alm_analytics_engine.alm_kpis import build_alm_kpi_summary
from pk_alm.alm_analytics_engine.analytics_result import ALMAnalyticsResult
from pk_alm.bvg_liability_engine.pension_logic.valuation import validate_valuation_dataframe
from pk_alm.reporting.full_alm_export import reject_protected_stage1_output_dir

BENCHMARK_PLAUSIBILITY_COLUMNS = (
    "metric",
    "model_value",
    "reference_value",
    "difference",
    "unit",
    "note",
)


def _validate_mapping(
    value: Mapping[str, object] | None,
    name: str,
) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping, got {type(value).__name__}")
    for key in value:
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{name} keys must be non-empty strings")
    return value


def _coerce_optional_float(value: object, name: str) -> float | None:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric or None, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        return None
    return fval


def _coerce_analytics_result(value: object) -> ALMAnalyticsResult:
    if isinstance(value, ALMAnalyticsResult):
        return value
    nested = getattr(value, "alm_analytics_result", None)
    if isinstance(nested, ALMAnalyticsResult):
        return nested
    raise TypeError(
        "result must be ALMAnalyticsResult or expose an alm_analytics_result"
    )


def _derive_model_values(
    result: ALMAnalyticsResult,
) -> dict[str, float]:
    summary = build_alm_kpi_summary(result)
    valuation_snapshots = result.inputs.valuation_snapshots
    validate_valuation_dataframe(valuation_snapshots)
    if valuation_snapshots.empty:
        raise ValueError("valuation_snapshots must not be empty")

    technical_rate = float(valuation_snapshots.iloc[0]["technical_interest_rate"])
    return {
        "final_funding_ratio_percent": summary.final_funding_ratio_percent,
        "minimum_funding_ratio_percent": summary.minimum_funding_ratio_percent,
        "technical_interest_rate_percent": technical_rate * 100.0,
    }


def _default_unit(metric: str) -> str:
    return "%" if metric.endswith("_percent") else ""


def build_benchmark_plausibility_table(
    result: object,
    *,
    reference_values: Mapping[str, float] | None = None,
    model_values: Mapping[str, float | None] | None = None,
    units: Mapping[str, str] | None = None,
    notes: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Build a benchmark/plausibility comparison table.

    Available model values are derived from existing scenario outputs. Extra
    model values, such as conversion rates or asset-allocation shares, must be
    supplied explicitly by the caller.
    """
    analytics_result = _coerce_analytics_result(result)

    refs = _validate_mapping(reference_values, "reference_values")
    extras = _validate_mapping(model_values, "model_values")
    unit_map = _validate_mapping(units, "units")
    note_map = _validate_mapping(notes, "notes")

    derived_model_values: dict[str, float | None] = _derive_model_values(
        analytics_result
    )
    for metric, value in extras.items():
        derived_model_values[metric] = _coerce_optional_float(
            value,
            f"model_values[{metric!r}]",
        )

    metrics = sorted(set(derived_model_values) | set(refs))
    rows: list[dict[str, object]] = []
    for metric in metrics:
        model_value = _coerce_optional_float(
            derived_model_values.get(metric),
            f"model_value[{metric!r}]",
        )
        reference_value = _coerce_optional_float(
            refs.get(metric),
            f"reference_values[{metric!r}]",
        )
        difference = (
            model_value - reference_value
            if model_value is not None and reference_value is not None
            else pd.NA
        )

        unit_value = unit_map.get(metric, _default_unit(metric))
        if not isinstance(unit_value, str):
            raise TypeError(f"units[{metric!r}] must be str")
        note_value = note_map.get(metric, "")
        if not isinstance(note_value, str):
            raise TypeError(f"notes[{metric!r}] must be str")

        rows.append(
            {
                "metric": metric,
                "model_value": model_value if model_value is not None else pd.NA,
                "reference_value": (
                    reference_value if reference_value is not None else pd.NA
                ),
                "difference": difference,
                "unit": unit_value,
                "note": note_value,
            }
        )

    return pd.DataFrame(rows, columns=list(BENCHMARK_PLAUSIBILITY_COLUMNS))


def export_benchmark_plausibility(
    result: object,
    output_dir: str | Path,
    *,
    reference_values: Mapping[str, float] | None = None,
    model_values: Mapping[str, float | None] | None = None,
    units: Mapping[str, str] | None = None,
    notes: Mapping[str, str] | None = None,
) -> Path:
    """Write ``benchmark_plausibility.csv`` and verify it can be read back."""
    out_path = reject_protected_stage1_output_dir(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    table = build_benchmark_plausibility_table(
        result,
        reference_values=reference_values,
        model_values=model_values,
        units=units,
        notes=notes,
    )
    output_path = out_path / "benchmark_plausibility.csv"
    table.to_csv(output_path, index=False)

    roundtrip = pd.read_csv(output_path)
    if list(roundtrip.columns) != list(BENCHMARK_PLAUSIBILITY_COLUMNS):
        raise RuntimeError(
            "benchmark CSV roundtrip column mismatch: "
            f"{list(roundtrip.columns)} != {list(BENCHMARK_PLAUSIBILITY_COLUMNS)}"
        )
    if len(roundtrip) != len(table):
        raise RuntimeError(
            f"benchmark CSV roundtrip row-count mismatch: "
            f"{len(roundtrip)} != {len(table)}"
        )
    return output_path
