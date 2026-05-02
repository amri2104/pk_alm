from dataclasses import FrozenInstanceError
import math

import pandas as pd
import pytest

from pk_alm.scenarios.stage1_baseline import run_stage1_baseline
from pk_alm.time_grid import (
    TIME_GRID_COLUMNS,
    TimeGridStep,
    annual_rate_to_periodic_rate,
    build_time_grid,
    normalize_frequency,
    periods_per_year,
    split_annual_amount,
    time_grid_to_dataframe,
    validate_time_grid_dataframe,
)


# ---------------------------------------------------------------------------
# A. Frequency helpers
# ---------------------------------------------------------------------------


def test_normalize_frequency_accepts_supported_values():
    assert normalize_frequency("annual") == "ANNUAL"
    assert normalize_frequency("ANNUAL") == "ANNUAL"
    assert normalize_frequency(" monthly ") == "MONTHLY"


def test_normalize_frequency_rejects_invalid_string():
    with pytest.raises(ValueError):
        normalize_frequency("weekly")


def test_normalize_frequency_rejects_non_string():
    with pytest.raises(TypeError):
        normalize_frequency(None)  # type: ignore[arg-type]


def test_periods_per_year():
    assert periods_per_year("ANNUAL") == 1
    assert periods_per_year("MONTHLY") == 12


# ---------------------------------------------------------------------------
# B. Rate and amount helpers
# ---------------------------------------------------------------------------


def test_annual_rate_to_periodic_rate_annual_returns_same_rate():
    assert annual_rate_to_periodic_rate(0.03, "ANNUAL") == pytest.approx(0.03)


def test_annual_rate_to_periodic_rate_monthly_compounds_effectively():
    expected = (1.0 + 0.03) ** (1.0 / 12.0) - 1.0

    assert annual_rate_to_periodic_rate(0.03, "MONTHLY") == pytest.approx(expected)


@pytest.mark.parametrize("bad", [True, None, "0.03", math.nan, -1.0, -1.2])
def test_annual_rate_to_periodic_rate_rejects_invalid_rates(bad):
    with pytest.raises((TypeError, ValueError)):
        annual_rate_to_periodic_rate(bad, "MONTHLY")  # type: ignore[arg-type]


def test_split_annual_amount_annual_returns_single_amount():
    assert split_annual_amount(1200.0, "ANNUAL") == (1200.0,)


def test_split_annual_amount_monthly_returns_equal_parts():
    parts = split_annual_amount(1200.0, "MONTHLY")

    assert len(parts) == 12
    assert parts == pytest.approx(tuple(100.0 for _ in range(12)))
    assert sum(parts) == pytest.approx(1200.0)


def test_split_annual_amount_allows_negative_and_zero_amounts():
    assert split_annual_amount(-1200.0, "MONTHLY") == pytest.approx(
        tuple(-100.0 for _ in range(12))
    )
    assert split_annual_amount(0.0, "MONTHLY") == pytest.approx(
        tuple(0.0 for _ in range(12))
    )


@pytest.mark.parametrize("bad", [True, None, "1200", math.nan])
def test_split_annual_amount_rejects_invalid_amounts(bad):
    with pytest.raises((TypeError, ValueError)):
        split_annual_amount(bad, "MONTHLY")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# C. Build grids
# ---------------------------------------------------------------------------


def test_build_annual_grid():
    grid = build_time_grid(start_year=2026, horizon_years=2, frequency="ANNUAL")

    assert len(grid) == 2
    assert tuple(step.event_date for step in grid) == (
        pd.Timestamp("2026-12-31"),
        pd.Timestamp("2027-12-31"),
    )
    assert tuple(step.projection_year for step in grid) == (1, 2)
    assert tuple(step.reporting_year for step in grid) == (2026, 2027)
    assert tuple(step.period_in_year for step in grid) == (1, 1)
    assert tuple(step.step_index for step in grid) == (0, 1)


def test_build_monthly_grid():
    grid = build_time_grid(start_year=2026, horizon_years=1, frequency="MONTHLY")

    assert len(grid) == 12
    assert grid[0].event_date == pd.Timestamp("2026-01-31")
    assert grid[-1].event_date == pd.Timestamp("2026-12-31")
    assert tuple(step.period_in_year for step in grid) == tuple(range(1, 13))
    assert set(step.projection_year for step in grid) == {1}
    assert set(step.reporting_year for step in grid) == {2026}
    assert tuple(step.step_index for step in grid) == tuple(range(12))


def test_build_monthly_grid_leap_year_february():
    grid = build_time_grid(start_year=2028, horizon_years=1, frequency="MONTHLY")

    assert grid[1].event_date == pd.Timestamp("2028-02-29")


def test_horizon_zero_returns_empty_tuple():
    assert build_time_grid(start_year=2026, horizon_years=0, frequency="ANNUAL") == ()
    assert build_time_grid(start_year=2026, horizon_years=0, frequency="MONTHLY") == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start_year": True, "horizon_years": 1},
        {"start_year": -1, "horizon_years": 1},
        {"start_year": 2026, "horizon_years": True},
        {"start_year": 2026, "horizon_years": -1},
    ],
)
def test_build_time_grid_rejects_invalid_year_inputs(kwargs):
    with pytest.raises((TypeError, ValueError)):
        build_time_grid(**kwargs)


# ---------------------------------------------------------------------------
# D. DataFrame conversion and validation
# ---------------------------------------------------------------------------


def test_time_grid_to_dataframe_and_validate_annual_grid():
    grid = build_time_grid(start_year=2026, horizon_years=2, frequency="ANNUAL")
    df = time_grid_to_dataframe(grid)

    assert list(df.columns) == list(TIME_GRID_COLUMNS)
    assert validate_time_grid_dataframe(df) is True


def test_time_grid_to_dataframe_and_validate_monthly_grid():
    grid = build_time_grid(start_year=2026, horizon_years=1, frequency="MONTHLY")
    df = time_grid_to_dataframe(grid)

    assert list(df.columns) == list(TIME_GRID_COLUMNS)
    assert validate_time_grid_dataframe(df) is True


def test_time_grid_to_dataframe_empty_returns_exact_columns():
    df = time_grid_to_dataframe([])

    assert list(df.columns) == list(TIME_GRID_COLUMNS)
    assert df.empty
    assert validate_time_grid_dataframe(df) is True


def test_time_grid_to_dataframe_rejects_wrong_input_type():
    with pytest.raises(TypeError):
        time_grid_to_dataframe("not steps")


def test_time_grid_to_dataframe_rejects_wrong_item_type():
    with pytest.raises(TypeError):
        time_grid_to_dataframe([object()])


def _valid_time_grid_df() -> pd.DataFrame:
    return time_grid_to_dataframe(
        build_time_grid(start_year=2026, horizon_years=2, frequency="ANNUAL")
    )


def test_validate_time_grid_dataframe_rejects_non_dataframe():
    with pytest.raises(TypeError):
        validate_time_grid_dataframe("not a df")  # type: ignore[arg-type]


def test_validate_time_grid_dataframe_rejects_missing_column():
    df = _valid_time_grid_df().drop(columns=["event_date"])

    with pytest.raises(ValueError):
        validate_time_grid_dataframe(df)


def test_validate_time_grid_dataframe_rejects_wrong_column_order():
    df = _valid_time_grid_df()

    with pytest.raises(ValueError):
        validate_time_grid_dataframe(df[list(reversed(TIME_GRID_COLUMNS))])


def test_validate_time_grid_dataframe_rejects_missing_values():
    df = _valid_time_grid_df()
    df.loc[0, "event_date"] = pd.NaT

    with pytest.raises(ValueError):
        validate_time_grid_dataframe(df)


def test_validate_time_grid_dataframe_rejects_bad_frequency():
    df = _valid_time_grid_df()
    df.loc[0, "frequency"] = "WEEKLY"

    with pytest.raises(ValueError):
        validate_time_grid_dataframe(df)


def test_validate_time_grid_dataframe_rejects_non_contiguous_step_index():
    df = _valid_time_grid_df()
    df.loc[1, "step_index"] = 2

    with pytest.raises(ValueError):
        validate_time_grid_dataframe(df)


def test_validate_time_grid_dataframe_rejects_non_monotonic_event_date():
    df = _valid_time_grid_df()
    df.loc[1, "event_date"] = pd.Timestamp("2025-12-31")

    with pytest.raises(ValueError):
        validate_time_grid_dataframe(df)


# ---------------------------------------------------------------------------
# E. Dataclass validation
# ---------------------------------------------------------------------------


def test_time_grid_step_normalizes_frequency_and_event_date():
    step = TimeGridStep(
        frequency=" monthly ",
        step_index=0,
        projection_year=1,
        reporting_year=2026,
        period_in_year=1,
        event_date="2026-01-31",
    )

    assert step.frequency == "MONTHLY"
    assert step.event_date == pd.Timestamp("2026-01-31")
    assert list(step.to_dict().keys()) == list(TIME_GRID_COLUMNS)


def test_time_grid_step_rejects_invalid_frequency():
    with pytest.raises(ValueError):
        TimeGridStep("WEEKLY", 0, 1, 2026, 1, "2026-01-31")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"step_index": True},
        {"step_index": -1},
        {"projection_year": True},
        {"projection_year": 0},
        {"reporting_year": True},
        {"reporting_year": -1},
        {"period_in_year": True},
    ],
)
def test_time_grid_step_rejects_invalid_int_fields(kwargs):
    values = {
        "frequency": "MONTHLY",
        "step_index": 0,
        "projection_year": 1,
        "reporting_year": 2026,
        "period_in_year": 1,
        "event_date": "2026-01-31",
    }
    values.update(kwargs)

    with pytest.raises((TypeError, ValueError)):
        TimeGridStep(**values)


@pytest.mark.parametrize(
    "frequency,period",
    [
        ("ANNUAL", 2),
        ("MONTHLY", 0),
        ("MONTHLY", 13),
    ],
)
def test_time_grid_step_rejects_invalid_period_in_year(frequency, period):
    with pytest.raises(ValueError):
        TimeGridStep(frequency, 0, 1, 2026, period, "2026-01-31")


@pytest.mark.parametrize("bad", [None, pd.NaT, "not-a-date"])
def test_time_grid_step_rejects_invalid_event_date(bad):
    with pytest.raises(ValueError):
        TimeGridStep("MONTHLY", 0, 1, 2026, 1, bad)


def test_time_grid_step_is_frozen():
    step = TimeGridStep("ANNUAL", 0, 1, 2026, 1, "2026-12-31")

    with pytest.raises(FrozenInstanceError):
        step.step_index = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# F. No integration side effects
# ---------------------------------------------------------------------------


def test_time_grid_helpers_do_not_change_stage1_baseline_outputs():
    before = run_stage1_baseline(output_dir=None)

    build_time_grid(start_year=2026, horizon_years=2, frequency="ANNUAL")
    monthly_df = time_grid_to_dataframe(
        build_time_grid(start_year=2026, horizon_years=1, frequency="MONTHLY")
    )
    assert validate_time_grid_dataframe(monthly_df) is True

    after = run_stage1_baseline(output_dir=None)

    pd.testing.assert_frame_equal(
        before.engine_result.cashflows,
        after.engine_result.cashflows,
    )
    pd.testing.assert_frame_equal(before.annual_cashflows, after.annual_cashflows)
    pd.testing.assert_frame_equal(
        before.funding_ratio_trajectory,
        after.funding_ratio_trajectory,
    )
