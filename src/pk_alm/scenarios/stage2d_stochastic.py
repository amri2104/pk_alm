"""Stage 2D stochastic-rate scenario.

Stage 2D is parallel to Stage 2C. It keeps population dynamics, UWS,
mortality, asset returns, salary growth, turnover, and contributions
deterministic while making the active BVG minimum rate and technical
discount rate stochastic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from pk_alm.alm_analytics_engine.stochastic_aggregation import (
    LIQUIDITY_INFLECTION_COLUMNS,
    MC_METADATA_COLUMNS,
    RATE_PATHS_SUMMARY_COLUMNS,
    FUNDING_RATIO_PERCENTILE_COLUMNS,
    FUNDING_RATIO_SUMMARY_COLUMNS,
    Stage2DAggregationResult,
    aggregate_stage2d_outputs,
    validate_funding_ratio_percentiles,
    validate_funding_ratio_summary,
    validate_liquidity_inflection_distribution,
    validate_mc_metadata,
    validate_rate_paths_summary,
)
from pk_alm.bvg_liability_engine.assumptions import (
    BVGAssumptions,
    FlatRateCurve,
    MortalityAssumptions,
)
from pk_alm.bvg_liability_engine.orchestration.stochastic_runner import (
    BVGStochasticResult,
    run_stochastic_bvg_engine,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_dynamics import (
    EntryAssumptions,
    get_default_entry_assumptions,
)
from pk_alm.bvg_liability_engine.population_dynamics.entry_policies import (
    FixedEntryPolicy,
)
from pk_alm.scenarios.stage2c_dynamic_parameters import (
    build_default_initial_portfolio_stage2c,
)

ShortRateModel = Literal["vasicek", "cir", "ho_lee", "hull_white"]

STAGE2D_OUTPUT_FILENAMES: tuple[str, ...] = (
    "funding_ratio_percentiles.csv",
    "funding_ratio_summary.csv",
    "liquidity_inflection_distribution.csv",
    "rate_paths_summary.csv",
    "mc_metadata.csv",
)

DEFAULT_CURVE_TENORS: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 12.0)
DEFAULT_SPOT_RATES: tuple[float, ...] = (0.0176,) * len(DEFAULT_CURVE_TENORS)
DEFAULT_SHORT_RATE = 0.0176
DEFAULT_MEAN_REVERSION = 0.10
DEFAULT_VOLATILITY = 0.005

_INSTALL_MESSAGE = (
    "Stage 2D stochastic rates require the optional `stochastic_rates` package. "
    "Install it with `pip install -e ../stochastic_rates`."
)


@dataclass(frozen=True)
class Stage2DStochasticResult:
    """Frozen result container for one Stage-2D stochastic-rate run."""

    scenario_id: str
    engine_result: BVGStochasticResult
    rate_paths_technical: np.ndarray
    funding_ratio_percentiles: pd.DataFrame
    funding_ratio_summary: pd.DataFrame
    liquidity_inflection_distribution: pd.DataFrame
    rate_paths_summary: pd.DataFrame
    mc_metadata: pd.DataFrame
    output_dir: Path | None

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("scenario_id must be a non-empty string")
        if not isinstance(self.engine_result, BVGStochasticResult):
            raise TypeError("engine_result must be BVGStochasticResult")
        if not isinstance(self.rate_paths_technical, np.ndarray):
            raise TypeError("rate_paths_technical must be numpy.ndarray")
        expected_shape = (
            self.engine_result.n_paths,
            self.engine_result.horizon_years + 1,
        )
        if self.rate_paths_technical.shape != expected_shape:
            raise ValueError(
                f"rate_paths_technical shape must be {expected_shape}, "
                f"got {self.rate_paths_technical.shape}"
            )
        validate_funding_ratio_percentiles(self.funding_ratio_percentiles)
        validate_funding_ratio_summary(self.funding_ratio_summary)
        validate_liquidity_inflection_distribution(
            self.liquidity_inflection_distribution
        )
        validate_rate_paths_summary(self.rate_paths_summary)
        validate_mc_metadata(self.mc_metadata)
        if self.output_dir is not None and not isinstance(self.output_dir, Path):
            raise TypeError("output_dir must be Path or None")


def run_stage2d_stochastic(
    scenario_id: str = "stage2d_stochastic",
    horizon_years: int = 12,
    start_year: int = 2026,
    n_paths: int = 1000,
    seed: int = 42,
    model_active: ShortRateModel = "hull_white",
    model_technical: ShortRateModel = "hull_white",
    model_active_params: dict | None = None,
    model_technical_params: dict | None = None,
    retired_interest_rate: float = 0.0176,
    contribution_multiplier: float = 1.4,
    valuation_terminal_age: int = 90,
    target_funding_ratio: float = 1.076,
    annual_asset_return: float = 0.025,
    salary_growth_rate: float = 0.015,
    turnover_rate: float = 0.02,
    entry_assumptions: EntryAssumptions | None = None,
    conversion_rate: float = 0.068,
    output_dir: str | Path | None = "outputs/stage2d_stochastic",
) -> Stage2DStochasticResult:
    """Run the Stage-2D stochastic-rate scenario end to end."""
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ValueError("scenario_id must be a non-empty string")
    horizon = _validate_non_bool_int(horizon_years, "horizon_years")
    if horizon < 0:
        raise ValueError(f"horizon_years must be >= 0, got {horizon}")
    path_count = _validate_non_bool_int(n_paths, "n_paths")
    if path_count <= 0:
        raise ValueError(f"n_paths must be > 0, got {path_count}")
    seed_value = _validate_non_bool_int(seed, "seed")
    active_model_key = _validate_short_rate_model(model_active, "model_active")
    technical_model_key = _validate_short_rate_model(
        model_technical,
        "model_technical",
    )

    create_model, curve_calibrator = _load_stochastic_rates()
    active_params, active_metadata_params = _resolve_model_params(
        active_model_key,
        model_active_params if model_active_params is not None else {"sigma": 0.001},
        curve_calibrator,
    )
    technical_params, technical_metadata_params = _resolve_model_params(
        technical_model_key,
        model_technical_params,
        curve_calibrator,
    )

    rate_paths_active, rate_paths_technical = _simulate_rate_paths(
        create_model=create_model,
        model_active=active_model_key,
        model_technical=technical_model_key,
        active_params=active_params,
        technical_params=technical_params,
        horizon_years=horizon,
        n_paths=path_count,
        seed=seed_value,
    )

    initial_state = build_default_initial_portfolio_stage2c()
    resolved_entry = (
        entry_assumptions
        if entry_assumptions is not None
        else get_default_entry_assumptions()
    )
    base_assumptions = BVGAssumptions(
        start_year=start_year,
        horizon_years=horizon,
        retirement_age=65,
        valuation_terminal_age=valuation_terminal_age,
        active_crediting_rate=FlatRateCurve(0.0),  # overridden per path
        retired_interest_rate=FlatRateCurve(retired_interest_rate),
        technical_discount_rate=FlatRateCurve(retired_interest_rate),
        economic_discount_rate=FlatRateCurve(retired_interest_rate),
        salary_growth_rate=FlatRateCurve(salary_growth_rate),
        conversion_rate=FlatRateCurve(conversion_rate),
        turnover_rate=turnover_rate,
        capital_withdrawal_fraction=0.35,
        contribution_multiplier=contribution_multiplier,
        mortality=MortalityAssumptions(mode="off"),
        entry_policy=FixedEntryPolicy(resolved_entry),
    )
    engine_result = run_stochastic_bvg_engine(
        initial_state=initial_state,
        assumptions=base_assumptions,
        rate_paths_active=rate_paths_active,
        model_active=active_model_key,
    )

    aggregation = aggregate_stage2d_outputs(
        engine_result=engine_result,
        rate_paths_technical=rate_paths_technical,
        scenario_id=scenario_id,
        model_technical=technical_model_key,
        seed=seed_value,
        model_active_params=active_metadata_params,
        model_technical_params=technical_metadata_params,
        runtime_s=0.0,
        start_year=start_year,
        valuation_terminal_age=valuation_terminal_age,
        target_funding_ratio=target_funding_ratio,
        annual_asset_return=annual_asset_return,
    )

    resolved_output_dir: Path | None = None
    if output_dir is not None:
        resolved_output_dir = Path(output_dir)
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        outputs = _aggregation_outputs(aggregation)
        for filename in STAGE2D_OUTPUT_FILENAMES:
            outputs[filename].to_csv(resolved_output_dir / filename, index=False)

    return Stage2DStochasticResult(
        scenario_id=scenario_id,
        engine_result=engine_result,
        rate_paths_technical=rate_paths_technical.copy(),
        funding_ratio_percentiles=aggregation.funding_ratio_percentiles,
        funding_ratio_summary=aggregation.funding_ratio_summary,
        liquidity_inflection_distribution=(
            aggregation.liquidity_inflection_distribution
        ),
        rate_paths_summary=aggregation.rate_paths_summary,
        mc_metadata=aggregation.mc_metadata,
        output_dir=resolved_output_dir,
    )


def _load_stochastic_rates() -> tuple[Any, Any]:
    try:
        from stochastic_rates import CurveCalibrator, create_model
    except ImportError as exc:
        raise ImportError(_INSTALL_MESSAGE) from exc
    return create_model, CurveCalibrator


def _resolve_model_params(
    model: str,
    params: dict | None,
    curve_calibrator: Any,
) -> tuple[dict[str, object], dict[str, object]]:
    defaults = _default_model_params(model, curve_calibrator)
    provided = {} if params is None else dict(params)
    provided.pop("seed", None)
    resolved = {**defaults, **provided}
    metadata = _metadata_params(resolved)
    return resolved, metadata


def _default_model_params(model: str, curve_calibrator: Any) -> dict[str, object]:
    if model in ("vasicek", "cir"):
        return {
            "r0": DEFAULT_SHORT_RATE,
            "a": DEFAULT_MEAN_REVERSION,
            "b": DEFAULT_SHORT_RATE,
            "sigma": DEFAULT_VOLATILITY,
        }
    calibrator = curve_calibrator.from_market(
        DEFAULT_CURVE_TENORS,
        spot_rates=DEFAULT_SPOT_RATES,
    )
    if model == "ho_lee":
        return {
            "r0": DEFAULT_SHORT_RATE,
            "sigma": DEFAULT_VOLATILITY,
            "calibrator": calibrator,
        }
    if model == "hull_white":
        return {
            "r0": DEFAULT_SHORT_RATE,
            "a": DEFAULT_MEAN_REVERSION,
            "sigma": DEFAULT_VOLATILITY,
            "calibrator": calibrator,
        }
    raise ValueError(f"Unknown short-rate model: {model}")


def _simulate_rate_paths(
    *,
    create_model: Any,
    model_active: str,
    model_technical: str,
    active_params: dict[str, object],
    technical_params: dict[str, object],
    horizon_years: int,
    n_paths: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    active_model = create_model(model_active, **active_params, seed=seed)
    technical_model = create_model(model_technical, **technical_params, seed=seed)

    if horizon_years == 0:
        active_paths = np.empty((n_paths, 0), dtype=float)
        technical_paths = np.full((n_paths, 1), float(technical_model.r0), dtype=float)
    else:
        sim_active = active_model.simulate(
            T=float(horizon_years),
            M=horizon_years,
            I=n_paths,
        )
        sim_technical = technical_model.simulate(
            T=float(horizon_years),
            M=horizon_years,
            I=n_paths,
        )
        active_paths = sim_active.rates[1:, :].T
        technical_paths = sim_technical.rates.T

    return _floor_rates(active_paths), _floor_rates(technical_paths)


def _floor_rates(paths: np.ndarray) -> np.ndarray:
    arr = np.asarray(paths, dtype=float)
    if np.isnan(arr).any():
        raise ValueError("rate paths must not contain NaN")
    return np.maximum(arr, 0.0)


def _metadata_params(params: dict[str, object]) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for key, value in params.items():
        if key == "calibrator":
            metadata[key] = "default_flat_curve_or_custom_calibrator"
        else:
            metadata[key] = _jsonable_value(value)
    return metadata


def _jsonable_value(value: object) -> object:
    if isinstance(value, np.ndarray):
        return [_jsonable_value(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_jsonable_value(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _aggregation_outputs(
    aggregation: Stage2DAggregationResult,
) -> dict[str, pd.DataFrame]:
    return {
        "funding_ratio_percentiles.csv": aggregation.funding_ratio_percentiles,
        "funding_ratio_summary.csv": aggregation.funding_ratio_summary,
        "liquidity_inflection_distribution.csv": (
            aggregation.liquidity_inflection_distribution
        ),
        "rate_paths_summary.csv": aggregation.rate_paths_summary,
        "mc_metadata.csv": aggregation.mc_metadata,
    }


def _validate_short_rate_model(value: object, name: str) -> ShortRateModel:
    allowed = ("vasicek", "cir", "ho_lee", "hull_white")
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    key = value.lower().replace("-", "_").strip()
    if key == "holee":
        key = "ho_lee"
    if key == "hullwhite":
        key = "hull_white"
    if key not in allowed:
        raise ValueError(f"{name} must be one of {allowed}, got {value!r}")
    return key  # type: ignore[return-value]


def _validate_non_bool_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    return value


__all__ = [
    "FUNDING_RATIO_PERCENTILE_COLUMNS",
    "FUNDING_RATIO_SUMMARY_COLUMNS",
    "LIQUIDITY_INFLECTION_COLUMNS",
    "MC_METADATA_COLUMNS",
    "RATE_PATHS_SUMMARY_COLUMNS",
    "STAGE2D_OUTPUT_FILENAMES",
    "ShortRateModel",
    "Stage2DStochasticResult",
    "run_stage2d_stochastic",
]
