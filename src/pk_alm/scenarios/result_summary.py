"""Scenario-level result summary for Stage-1 baseline runs."""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass

import pandas as pd

from pk_alm.analytics.cashflows import validate_annual_cashflow_dataframe
from pk_alm.analytics.funding import validate_funding_ratio_dataframe
from pk_alm.analytics.funding_summary import validate_funding_summary_dataframe
from pk_alm.assets.deterministic import validate_asset_dataframe
from pk_alm.bvg.valuation import validate_valuation_dataframe

SCENARIO_RESULT_COLUMNS = (
    "scenario_id",
    "horizon_years",
    "start_year",
    "end_year",
    "initial_total_stage1_liability",
    "final_total_stage1_liability",
    "initial_asset_value",
    "final_asset_value",
    "initial_funding_ratio_percent",
    "final_funding_ratio_percent",
    "minimum_funding_ratio_percent",
    "minimum_funding_ratio_year",
    "maximum_funding_ratio_percent",
    "maximum_funding_ratio_year",
    "years_below_100_percent",
    "years_below_target_percent",
    "ever_underfunded",
    "final_underfunded",
    "liquidity_inflection_year_structural",
    "liquidity_inflection_year_net",
    "currency",
)

_MONETARY_FIELDS = (
    "initial_total_stage1_liability",
    "final_total_stage1_liability",
    "initial_asset_value",
    "final_asset_value",
)
_FUNDING_PERCENT_FIELDS = (
    "initial_funding_ratio_percent",
    "final_funding_ratio_percent",
    "minimum_funding_ratio_percent",
    "maximum_funding_ratio_percent",
)
_OPTIONAL_INFLECTION_FIELDS = (
    "liquidity_inflection_year_structural",
    "liquidity_inflection_year_net",
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_non_bool_int(
    value: object, name: str, *, min_value: int | None = None
) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def _validate_non_bool_real(
    value: object,
    name: str,
    *,
    min_value: float | None = None,
    allow_equal_min: bool = True,
) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    fval = float(value)
    if math.isnan(fval):
        raise ValueError(f"{name} must not be NaN")
    if min_value is not None:
        if allow_equal_min:
            if fval < min_value:
                raise ValueError(f"{name} must be >= {min_value}, got {fval}")
        else:
            if fval <= min_value:
                raise ValueError(f"{name} must be > {min_value}, got {fval}")
    return fval


def _validate_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _coerce_integer_like(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        fval = float(value)
        if math.isnan(fval):
            raise ValueError(f"{name} must not be NaN")
        if not fval.is_integer():
            raise ValueError(f"{name} must be integer-like, got {value!r}")
        return int(fval)
    raise TypeError(f"{name} must be integer-like, got {type(value).__name__}")


def _normalize_optional_inflection_year(value: object, name: str) -> int | None:
    if isinstance(value, bool):
        raise TypeError(f"{name} must not be bool")
    if value is None:
        return None
    if pd.isna(value):
        return None
    return _coerce_integer_like(value, name)


def _validate_bool(value: object, name: str) -> bool:
    if pd.api.types.is_bool(value):
        return bool(value)
    raise TypeError(f"{name} must be bool, got {type(value).__name__}")


# ---------------------------------------------------------------------------
# Summary container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioResultSummary:
    """One-row scenario-level Stage-1 result summary."""

    scenario_id: str
    horizon_years: int
    start_year: int
    end_year: int
    initial_total_stage1_liability: float
    final_total_stage1_liability: float
    initial_asset_value: float
    final_asset_value: float
    initial_funding_ratio_percent: float
    final_funding_ratio_percent: float
    minimum_funding_ratio_percent: float
    minimum_funding_ratio_year: int
    maximum_funding_ratio_percent: float
    maximum_funding_ratio_year: int
    years_below_100_percent: int
    years_below_target_percent: int
    ever_underfunded: bool
    final_underfunded: bool
    liquidity_inflection_year_structural: int | None
    liquidity_inflection_year_net: int | None
    currency: str = "CHF"

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.scenario_id, "scenario_id")

        horizon = _validate_non_bool_int(
            self.horizon_years, "horizon_years", min_value=0
        )
        start = _validate_non_bool_int(self.start_year, "start_year", min_value=0)
        end = _validate_non_bool_int(self.end_year, "end_year", min_value=0)
        if horizon > 0 and end < start:
            raise ValueError(
                f"end_year must be >= start_year when horizon_years > 0 "
                f"({end} < {start})"
            )

        for fname in _MONETARY_FIELDS:
            min_value = 0.0 if fname.endswith("liability") else None
            _validate_non_bool_real(
                getattr(self, fname),
                fname,
                min_value=min_value,
                allow_equal_min=False,
            )

        for fname in _FUNDING_PERCENT_FIELDS:
            _validate_non_bool_real(getattr(self, fname), fname)

        _validate_non_bool_int(
            self.minimum_funding_ratio_year,
            "minimum_funding_ratio_year",
            min_value=0,
        )
        _validate_non_bool_int(
            self.maximum_funding_ratio_year,
            "maximum_funding_ratio_year",
            min_value=0,
        )
        _validate_non_bool_int(
            self.years_below_100_percent,
            "years_below_100_percent",
            min_value=0,
        )
        _validate_non_bool_int(
            self.years_below_target_percent,
            "years_below_target_percent",
            min_value=0,
        )

        _validate_bool(self.ever_underfunded, "ever_underfunded")
        _validate_bool(self.final_underfunded, "final_underfunded")

        _normalize_optional_inflection_year(
            self.liquidity_inflection_year_structural,
            "liquidity_inflection_year_structural",
        )
        _normalize_optional_inflection_year(
            self.liquidity_inflection_year_net,
            "liquidity_inflection_year_net",
        )
        _validate_non_empty_string(self.currency, "currency")

    def to_dict(self) -> dict[str, object]:
        return {col: getattr(self, col) for col in SCENARIO_RESULT_COLUMNS}


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_scenario_result_summary(
    *,
    scenario_id: str,
    valuation_snapshots: pd.DataFrame,
    annual_cashflows: pd.DataFrame,
    asset_snapshots: pd.DataFrame,
    funding_ratio_trajectory: pd.DataFrame,
    funding_summary: pd.DataFrame,
    liquidity_inflection_year_structural: int | None,
    liquidity_inflection_year_net: int | None,
    currency: str = "CHF",
) -> ScenarioResultSummary:
    """Build one scenario-level result summary from validated Stage-1 outputs."""
    scenario = _validate_non_empty_string(scenario_id, "scenario_id")
    cur = _validate_non_empty_string(currency, "currency")

    if not isinstance(valuation_snapshots, pd.DataFrame):
        raise TypeError(
            f"valuation_snapshots must be a pandas DataFrame, "
            f"got {type(valuation_snapshots).__name__}"
        )
    validate_valuation_dataframe(valuation_snapshots)
    if valuation_snapshots.empty:
        raise ValueError("valuation_snapshots must not be empty")

    if not isinstance(annual_cashflows, pd.DataFrame):
        raise TypeError(
            f"annual_cashflows must be a pandas DataFrame, "
            f"got {type(annual_cashflows).__name__}"
        )
    validate_annual_cashflow_dataframe(annual_cashflows)

    if not isinstance(asset_snapshots, pd.DataFrame):
        raise TypeError(
            f"asset_snapshots must be a pandas DataFrame, "
            f"got {type(asset_snapshots).__name__}"
        )
    validate_asset_dataframe(asset_snapshots)
    if asset_snapshots.empty:
        raise ValueError("asset_snapshots must not be empty")

    if not isinstance(funding_ratio_trajectory, pd.DataFrame):
        raise TypeError(
            f"funding_ratio_trajectory must be a pandas DataFrame, "
            f"got {type(funding_ratio_trajectory).__name__}"
        )
    validate_funding_ratio_dataframe(funding_ratio_trajectory)
    if funding_ratio_trajectory.empty:
        raise ValueError("funding_ratio_trajectory must not be empty")

    if not isinstance(funding_summary, pd.DataFrame):
        raise TypeError(
            f"funding_summary must be a pandas DataFrame, "
            f"got {type(funding_summary).__name__}"
        )
    validate_funding_summary_dataframe(funding_summary)
    if funding_summary.empty:
        raise ValueError("funding_summary must not be empty")
    if len(funding_summary) != 1:
        raise ValueError(
            f"funding_summary must have exactly one row, got {len(funding_summary)}"
        )

    inflection_structural = _normalize_optional_inflection_year(
        liquidity_inflection_year_structural,
        "liquidity_inflection_year_structural",
    )
    inflection_net = _normalize_optional_inflection_year(
        liquidity_inflection_year_net,
        "liquidity_inflection_year_net",
    )

    horizon_years = len(valuation_snapshots) - 1
    if horizon_years == 0:
        if not annual_cashflows.empty:
            raise ValueError("annual_cashflows must be empty when horizon_years == 0")
        start_year = 0
        end_year = 0
    else:
        if annual_cashflows.empty:
            raise ValueError("annual_cashflows must not be empty when horizon_years > 0")
        if len(annual_cashflows) != horizon_years:
            raise ValueError(
                "annual_cashflows row count must equal horizon_years "
                f"({len(annual_cashflows)} != {horizon_years})"
            )
        reporting_years = [
            _coerce_integer_like(y, "annual_cashflows.reporting_year")
            for y in annual_cashflows["reporting_year"]
        ]
        if len(set(reporting_years)) != len(reporting_years):
            raise ValueError("annual_cashflows reporting_year values must be unique")
        if reporting_years != sorted(reporting_years):
            raise ValueError(
                "annual_cashflows reporting_year values must be sorted ascending"
            )
        expected_years = list(
            range(reporting_years[0], reporting_years[0] + len(reporting_years))
        )
        if reporting_years != expected_years:
            raise ValueError(
                "annual_cashflows reporting_year values must be contiguous"
            )
        start_year = reporting_years[0]
        end_year = reporting_years[-1]
        if end_year < start_year:
            raise ValueError("end_year must be >= start_year")

    funding_summary_row = funding_summary.iloc[0]

    return ScenarioResultSummary(
        scenario_id=scenario,
        horizon_years=horizon_years,
        start_year=start_year,
        end_year=end_year,
        initial_total_stage1_liability=float(
            valuation_snapshots.iloc[0]["total_stage1_liability"]
        ),
        final_total_stage1_liability=float(
            valuation_snapshots.iloc[-1]["total_stage1_liability"]
        ),
        initial_asset_value=float(asset_snapshots.iloc[0]["closing_asset_value"]),
        final_asset_value=float(asset_snapshots.iloc[-1]["closing_asset_value"]),
        initial_funding_ratio_percent=float(
            funding_ratio_trajectory.iloc[0]["funding_ratio_percent"]
        ),
        final_funding_ratio_percent=float(
            funding_ratio_trajectory.iloc[-1]["funding_ratio_percent"]
        ),
        minimum_funding_ratio_percent=float(
            funding_summary_row["minimum_funding_ratio_percent"]
        ),
        minimum_funding_ratio_year=_coerce_integer_like(
            funding_summary_row["minimum_funding_ratio_year"],
            "minimum_funding_ratio_year",
        ),
        maximum_funding_ratio_percent=float(
            funding_summary_row["maximum_funding_ratio_percent"]
        ),
        maximum_funding_ratio_year=_coerce_integer_like(
            funding_summary_row["maximum_funding_ratio_year"],
            "maximum_funding_ratio_year",
        ),
        years_below_100_percent=_coerce_integer_like(
            funding_summary_row["years_below_100_percent"],
            "years_below_100_percent",
        ),
        years_below_target_percent=_coerce_integer_like(
            funding_summary_row["years_below_target_percent"],
            "years_below_target_percent",
        ),
        ever_underfunded=_validate_bool(
            funding_summary_row["ever_underfunded"], "ever_underfunded"
        ),
        final_underfunded=_validate_bool(
            funding_summary_row["final_underfunded"], "final_underfunded"
        ),
        liquidity_inflection_year_structural=inflection_structural,
        liquidity_inflection_year_net=inflection_net,
        currency=cur,
    )


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------


def scenario_result_summary_to_dataframe(
    summary: ScenarioResultSummary | list | tuple,
) -> pd.DataFrame:
    """Convert one or more scenario summaries to a DataFrame."""
    if isinstance(summary, ScenarioResultSummary):
        summaries = [summary]
    elif isinstance(summary, (list, tuple)):
        summaries = list(summary)
    else:
        raise TypeError(
            "summary must be ScenarioResultSummary, list, or tuple, "
            f"got {type(summary).__name__}"
        )

    for i, item in enumerate(summaries):
        if not isinstance(item, ScenarioResultSummary):
            raise TypeError(
                f"summary[{i}] must be ScenarioResultSummary, "
                f"got {type(item).__name__}"
            )

    return pd.DataFrame(
        [item.to_dict() for item in summaries],
        columns=list(SCENARIO_RESULT_COLUMNS),
    )


def validate_scenario_result_dataframe(df: pd.DataFrame) -> bool:
    """Validate a scenario-level result summary DataFrame."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            f"df must be a pandas DataFrame, got {type(df).__name__}"
        )

    missing = [c for c in SCENARIO_RESULT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")

    if list(df.columns) != list(SCENARIO_RESULT_COLUMNS):
        raise ValueError(
            f"columns must be in order {list(SCENARIO_RESULT_COLUMNS)}, "
            f"got {list(df.columns)}"
        )

    if df.empty:
        return True

    required_columns = [
        c for c in SCENARIO_RESULT_COLUMNS if c not in _OPTIONAL_INFLECTION_FIELDS
    ]
    if df[required_columns].isna().any().any():
        raise ValueError(
            "required columns must not contain NaN/None/NaT/pd.NA"
        )

    for _, row in df.iterrows():
        ScenarioResultSummary(
            scenario_id=row["scenario_id"],
            horizon_years=_coerce_integer_like(row["horizon_years"], "horizon_years"),
            start_year=_coerce_integer_like(row["start_year"], "start_year"),
            end_year=_coerce_integer_like(row["end_year"], "end_year"),
            initial_total_stage1_liability=row["initial_total_stage1_liability"],
            final_total_stage1_liability=row["final_total_stage1_liability"],
            initial_asset_value=row["initial_asset_value"],
            final_asset_value=row["final_asset_value"],
            initial_funding_ratio_percent=row["initial_funding_ratio_percent"],
            final_funding_ratio_percent=row["final_funding_ratio_percent"],
            minimum_funding_ratio_percent=row["minimum_funding_ratio_percent"],
            minimum_funding_ratio_year=_coerce_integer_like(
                row["minimum_funding_ratio_year"], "minimum_funding_ratio_year"
            ),
            maximum_funding_ratio_percent=row["maximum_funding_ratio_percent"],
            maximum_funding_ratio_year=_coerce_integer_like(
                row["maximum_funding_ratio_year"], "maximum_funding_ratio_year"
            ),
            years_below_100_percent=_coerce_integer_like(
                row["years_below_100_percent"], "years_below_100_percent"
            ),
            years_below_target_percent=_coerce_integer_like(
                row["years_below_target_percent"], "years_below_target_percent"
            ),
            ever_underfunded=_validate_bool(
                row["ever_underfunded"], "ever_underfunded"
            ),
            final_underfunded=_validate_bool(
                row["final_underfunded"], "final_underfunded"
            ),
            liquidity_inflection_year_structural=_normalize_optional_inflection_year(
                row["liquidity_inflection_year_structural"],
                "liquidity_inflection_year_structural",
            ),
            liquidity_inflection_year_net=_normalize_optional_inflection_year(
                row["liquidity_inflection_year_net"],
                "liquidity_inflection_year_net",
            ),
            currency=row["currency"],
        )

    return True
