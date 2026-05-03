"""Aggregation helpers for Stage-2D stochastic ALM outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from pk_alm.analytics.cashflows import (
    find_liquidity_inflection_year,
    summarize_cashflows_by_year,
)
from pk_alm.analytics.distributional import (
    compute_percentiles,
    compute_underfunding_probability,
    compute_var_es,
)
from pk_alm.analytics.funding import build_funding_ratio_trajectory
from pk_alm.assets.deterministic import build_deterministic_asset_trajectory
from pk_alm.bvg.engine_stage2d import Stage2DEngineResult
from pk_alm.bvg.valuation_dynamic import value_portfolio_states_dynamic

FUNDING_RATIO_PERCENTILE_COLUMNS = (
    "projection_year",
    "p5",
    "p25",
    "p50",
    "p75",
    "p95",
)

FUNDING_RATIO_SUMMARY_COLUMNS = (
    "final_p5",
    "final_p50",
    "final_p95",
    "VaR_5",
    "ES_5",
    "P_underfunding",
)

LIQUIDITY_INFLECTION_COLUMNS = (
    "year",
    "count",
    "probability",
)

RATE_PATHS_SUMMARY_COLUMNS = (
    "projection_year",
    "active_mean",
    "active_p5",
    "active_p95",
    "technical_mean",
    "technical_p5",
    "technical_p95",
)

MC_METADATA_COLUMNS = (
    "scenario_id",
    "model_active",
    "model_technical",
    "n_paths",
    "seed",
    "model_active_params",
    "model_technical_params",
    "runtime_s",
)


@dataclass(frozen=True)
class Stage2DAggregationResult:
    """Five aggregated Stage-2D output tables."""

    funding_ratio_percentiles: pd.DataFrame
    funding_ratio_summary: pd.DataFrame
    liquidity_inflection_distribution: pd.DataFrame
    rate_paths_summary: pd.DataFrame
    mc_metadata: pd.DataFrame

    def __post_init__(self) -> None:
        validate_funding_ratio_percentiles(self.funding_ratio_percentiles)
        validate_funding_ratio_summary(self.funding_ratio_summary)
        validate_liquidity_inflection_distribution(
            self.liquidity_inflection_distribution
        )
        validate_rate_paths_summary(self.rate_paths_summary)
        validate_mc_metadata(self.mc_metadata)


def aggregate_stage2d_outputs(
    *,
    engine_result: Stage2DEngineResult,
    rate_paths_technical: np.ndarray,
    scenario_id: str,
    model_technical: str,
    seed: int,
    model_active_params: dict[str, object],
    model_technical_params: dict[str, object],
    runtime_s: float,
    start_year: int,
    valuation_terminal_age: int,
    target_funding_ratio: float,
    annual_asset_return: float,
) -> Stage2DAggregationResult:
    """Aggregate path-level Stage-2D outputs into the public CSV tables."""
    if not isinstance(engine_result, Stage2DEngineResult):
        raise TypeError("engine_result must be Stage2DEngineResult")
    technical_paths = _validate_technical_paths(
        rate_paths_technical,
        engine_result.n_paths,
        engine_result.horizon_years + 1,
    )

    funding_ratio_percent_paths: list[np.ndarray] = []
    funding_ratio_decimal_paths: list[np.ndarray] = []
    inflection_years: list[int] = []

    for path_result in engine_result.path_results:
        valuation_snapshots = value_portfolio_states_dynamic(
            path_result.portfolio_states,
            tuple(float(v) for v in technical_paths[path_result.path_index]),
            valuation_terminal_age,
        )
        annual_cashflows = summarize_cashflows_by_year(path_result.cashflows)
        asset_snapshots = build_deterministic_asset_trajectory(
            valuation_snapshots,
            annual_cashflows,
            target_funding_ratio=target_funding_ratio,
            annual_return_rate=annual_asset_return,
            start_year=start_year,
        )
        funding_ratio = build_funding_ratio_trajectory(
            asset_snapshots,
            valuation_snapshots,
        )
        funding_ratio_percent_paths.append(
            funding_ratio["funding_ratio_percent"].to_numpy(dtype=float)
        )
        funding_ratio_decimal_paths.append(
            funding_ratio["funding_ratio"].to_numpy(dtype=float)
        )
        inflection = find_liquidity_inflection_year(
            annual_cashflows,
            use_structural=True,
        )
        inflection_years.append(-1 if inflection is None else int(inflection))

    percent_matrix = np.vstack(funding_ratio_percent_paths)
    decimal_matrix = np.vstack(funding_ratio_decimal_paths)

    funding_ratio_percentiles = _build_funding_ratio_percentiles(percent_matrix)
    funding_ratio_summary = _build_funding_ratio_summary(
        percent_matrix,
        decimal_matrix,
    )
    liquidity_inflection_distribution = _build_liquidity_inflection_distribution(
        inflection_years,
        engine_result.n_paths,
    )
    rate_paths_summary = _build_rate_paths_summary(
        engine_result.rate_paths_active,
        technical_paths,
    )
    mc_metadata = _build_mc_metadata(
        scenario_id=scenario_id,
        model_active=engine_result.model_active,
        model_technical=model_technical,
        n_paths=engine_result.n_paths,
        seed=seed,
        model_active_params=model_active_params,
        model_technical_params=model_technical_params,
        runtime_s=runtime_s,
    )
    return Stage2DAggregationResult(
        funding_ratio_percentiles=funding_ratio_percentiles,
        funding_ratio_summary=funding_ratio_summary,
        liquidity_inflection_distribution=liquidity_inflection_distribution,
        rate_paths_summary=rate_paths_summary,
        mc_metadata=mc_metadata,
    )


def _build_funding_ratio_percentiles(percent_matrix: np.ndarray) -> pd.DataFrame:
    percentiles = compute_percentiles(percent_matrix, axis=0)
    rows = {
        "projection_year": list(range(percent_matrix.shape[1])),
        **{name: values for name, values in percentiles.items()},
    }
    df = pd.DataFrame(rows, columns=list(FUNDING_RATIO_PERCENTILE_COLUMNS))
    validate_funding_ratio_percentiles(df)
    return df


def _build_funding_ratio_summary(
    percent_matrix: np.ndarray,
    decimal_matrix: np.ndarray,
) -> pd.DataFrame:
    final_values = percent_matrix[:, -1]
    final_percentiles = compute_percentiles(final_values, axis=0)
    var_5, es_5 = compute_var_es(final_values, alpha=0.05)
    df = pd.DataFrame(
        [
            {
                "final_p5": float(final_percentiles["p5"]),
                "final_p50": float(final_percentiles["p50"]),
                "final_p95": float(final_percentiles["p95"]),
                "VaR_5": var_5,
                "ES_5": es_5,
                "P_underfunding": compute_underfunding_probability(decimal_matrix),
            }
        ],
        columns=list(FUNDING_RATIO_SUMMARY_COLUMNS),
    )
    validate_funding_ratio_summary(df)
    return df


def _build_liquidity_inflection_distribution(
    inflection_years: list[int],
    n_paths: int,
) -> pd.DataFrame:
    values, counts = np.unique(np.asarray(inflection_years, dtype=int), return_counts=True)
    rows = [
        {
            "year": int(year),
            "count": int(count),
            "probability": float(count / n_paths),
        }
        for year, count in zip(values, counts)
    ]
    df = pd.DataFrame(rows, columns=list(LIQUIDITY_INFLECTION_COLUMNS))
    validate_liquidity_inflection_distribution(df)
    return df


def _build_rate_paths_summary(
    active_paths: np.ndarray,
    technical_paths: np.ndarray,
) -> pd.DataFrame:
    if active_paths.shape[1] == 0:
        active_for_snapshots = np.zeros((active_paths.shape[0], 1), dtype=float)
    else:
        active_for_snapshots = np.column_stack([active_paths, active_paths[:, -1]])
    rows: list[dict[str, object]] = []
    for projection_year in range(technical_paths.shape[1]):
        active_values = active_for_snapshots[:, projection_year]
        technical_values = technical_paths[:, projection_year]
        rows.append(
            {
                "projection_year": projection_year,
                "active_mean": float(np.mean(active_values)),
                "active_p5": float(np.percentile(active_values, 5)),
                "active_p95": float(np.percentile(active_values, 95)),
                "technical_mean": float(np.mean(technical_values)),
                "technical_p5": float(np.percentile(technical_values, 5)),
                "technical_p95": float(np.percentile(technical_values, 95)),
            }
        )
    df = pd.DataFrame(rows, columns=list(RATE_PATHS_SUMMARY_COLUMNS))
    validate_rate_paths_summary(df)
    return df


def _build_mc_metadata(
    *,
    scenario_id: str,
    model_active: str,
    model_technical: str,
    n_paths: int,
    seed: int,
    model_active_params: dict[str, object],
    model_technical_params: dict[str, object],
    runtime_s: float,
) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "scenario_id": scenario_id,
                "model_active": model_active,
                "model_technical": model_technical,
                "n_paths": n_paths,
                "seed": seed,
                "model_active_params": json.dumps(
                    model_active_params,
                    sort_keys=True,
                ),
                "model_technical_params": json.dumps(
                    model_technical_params,
                    sort_keys=True,
                ),
                "runtime_s": runtime_s,
            }
        ],
        columns=list(MC_METADATA_COLUMNS),
    )
    validate_mc_metadata(df)
    return df


def validate_funding_ratio_percentiles(df: pd.DataFrame) -> bool:
    _validate_columns(df, FUNDING_RATIO_PERCENTILE_COLUMNS, "funding_ratio_percentiles")
    _validate_no_missing(df, "funding_ratio_percentiles")
    return True


def validate_funding_ratio_summary(df: pd.DataFrame) -> bool:
    _validate_columns(df, FUNDING_RATIO_SUMMARY_COLUMNS, "funding_ratio_summary")
    _validate_no_missing(df, "funding_ratio_summary")
    if len(df) != 1:
        raise ValueError("funding_ratio_summary must contain exactly one row")
    probability = float(df.iloc[0]["P_underfunding"])
    if probability < 0.0 or probability > 1.0:
        raise ValueError("P_underfunding must be in [0, 1]")
    return True


def validate_liquidity_inflection_distribution(df: pd.DataFrame) -> bool:
    _validate_columns(
        df,
        LIQUIDITY_INFLECTION_COLUMNS,
        "liquidity_inflection_distribution",
    )
    _validate_no_missing(df, "liquidity_inflection_distribution")
    total_probability = float(df["probability"].sum()) if not df.empty else 0.0
    if not np.isclose(total_probability, 1.0):
        raise ValueError("liquidity inflection probabilities must sum to 1")
    return True


def validate_rate_paths_summary(df: pd.DataFrame) -> bool:
    _validate_columns(df, RATE_PATHS_SUMMARY_COLUMNS, "rate_paths_summary")
    _validate_no_missing(df, "rate_paths_summary")
    return True


def validate_mc_metadata(df: pd.DataFrame) -> bool:
    _validate_columns(df, MC_METADATA_COLUMNS, "mc_metadata")
    _validate_no_missing(df, "mc_metadata")
    if len(df) != 1:
        raise ValueError("mc_metadata must contain exactly one row")
    return True


def _validate_technical_paths(
    value: object,
    n_paths: int,
    n_snapshots: int,
) -> np.ndarray:
    if not isinstance(value, np.ndarray):
        raise TypeError("rate_paths_technical must be numpy.ndarray")
    try:
        arr = value.astype(float, copy=False)
    except (TypeError, ValueError) as exc:
        raise TypeError("rate_paths_technical must contain numeric values") from exc
    if arr.shape != (n_paths, n_snapshots):
        raise ValueError(
            "rate_paths_technical shape must be "
            f"({n_paths}, {n_snapshots}), got {arr.shape}"
        )
    if np.isnan(arr).any():
        raise ValueError("rate_paths_technical must not contain NaN")
    if np.any(arr < 0.0):
        raise ValueError("rate_paths_technical must be >= 0")
    return arr


def _validate_columns(df: object, columns: tuple[str, ...], name: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be DataFrame")
    if list(df.columns) != list(columns):
        raise ValueError(f"{name} columns must be {list(columns)}")


def _validate_no_missing(df: pd.DataFrame, name: str) -> None:
    if df.isna().any().any():
        raise ValueError(f"{name} must not contain missing values")
