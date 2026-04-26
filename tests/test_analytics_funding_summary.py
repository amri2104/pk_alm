import math

import pandas as pd
import pytest

from pk_alm.analytics.funding import FUNDING_RATIO_COLUMNS
from pk_alm.analytics.funding_summary import (
    FUNDING_SUMMARY_COLUMNS,
    FundingRatioSummary,
    funding_summary_to_dataframe,
    summarize_funding_ratio,
    validate_funding_summary_dataframe,
)


def _funding_trajectory(percentages, projection_years=None, currency="CHF"):
    if projection_years is None:
        projection_years = list(range(len(percentages)))
    rows = []
    for projection_year, percent in zip(projection_years, percentages):
        ratio = float(percent) / 100
        rows.append(
            {
                "projection_year": projection_year,
                "asset_value": ratio * 1000.0,
                "total_stage1_liability": 1000.0,
                "funding_ratio": ratio,
                "funding_ratio_percent": float(percent),
                "currency": currency,
            }
        )
    return pd.DataFrame(rows, columns=list(FUNDING_RATIO_COLUMNS))


def _standard_summary(**overrides):
    kwargs = dict(
        start_projection_year=0,
        end_projection_year=3,
        initial_funding_ratio_percent=107.6,
        final_funding_ratio_percent=101.0,
        minimum_funding_ratio_percent=95.0,
        minimum_funding_ratio_projection_year=2,
        maximum_funding_ratio_percent=107.6,
        maximum_funding_ratio_projection_year=0,
        target_funding_ratio_percent=107.6,
        years_below_100_percent=2,
        years_below_target_percent=3,
        ever_underfunded=True,
        final_underfunded=False,
        currency="CHF",
    )
    kwargs.update(overrides)
    return FundingRatioSummary(**kwargs)


# ---------------------------------------------------------------------------
# A. Standard summary
# ---------------------------------------------------------------------------


def test_standard_summary_values():
    summary = summarize_funding_ratio(
        _funding_trajectory([107.6, 99.0, 95.0, 101.0]),
        target_funding_ratio=1.076,
    )

    assert summary.start_projection_year == 0
    assert summary.end_projection_year == 3
    assert summary.initial_funding_ratio_percent == pytest.approx(107.6)
    assert summary.final_funding_ratio_percent == pytest.approx(101.0)
    assert summary.minimum_funding_ratio_percent == pytest.approx(95.0)
    assert summary.minimum_funding_ratio_projection_year == 2
    assert summary.maximum_funding_ratio_percent == pytest.approx(107.6)
    assert summary.maximum_funding_ratio_projection_year == 0
    assert summary.target_funding_ratio_percent == pytest.approx(107.6)
    assert summary.years_below_100_percent == 2
    assert summary.years_below_target_percent == 3
    assert summary.ever_underfunded is True
    assert summary.final_underfunded is False
    assert summary.currency == "CHF"


# ---------------------------------------------------------------------------
# B. Tie handling
# ---------------------------------------------------------------------------


def test_summary_ties_use_earliest_projection_year():
    summary = summarize_funding_ratio(
        _funding_trajectory([100.0, 95.0, 95.0, 110.0, 110.0]),
        target_funding_ratio=1.0,
    )

    assert summary.minimum_funding_ratio_percent == pytest.approx(95.0)
    assert summary.minimum_funding_ratio_projection_year == 1
    assert summary.maximum_funding_ratio_percent == pytest.approx(110.0)
    assert summary.maximum_funding_ratio_projection_year == 3


# ---------------------------------------------------------------------------
# C. No underfunding
# ---------------------------------------------------------------------------


def test_summary_no_underfunding():
    summary = summarize_funding_ratio(
        _funding_trajectory([110.0, 108.0, 109.0]),
        target_funding_ratio=1.076,
    )

    assert summary.years_below_100_percent == 0
    assert summary.ever_underfunded is False
    assert summary.final_underfunded is False


# ---------------------------------------------------------------------------
# D. Final underfunded
# ---------------------------------------------------------------------------


def test_summary_final_underfunded():
    summary = summarize_funding_ratio(
        _funding_trajectory([105.0, 98.0]),
        target_funding_ratio=1.076,
    )

    assert summary.ever_underfunded is True
    assert summary.final_underfunded is True


# ---------------------------------------------------------------------------
# E. Negative funding ratio values
# ---------------------------------------------------------------------------


def test_summary_allows_negative_funding_ratio_values():
    summary = summarize_funding_ratio(
        _funding_trajectory([50.0, -10.0, 20.0]),
        target_funding_ratio=1.0,
    )

    assert summary.minimum_funding_ratio_percent == pytest.approx(-10.0)
    assert summary.minimum_funding_ratio_projection_year == 1
    assert summary.years_below_100_percent == 3


def test_summary_threshold_tolerance_for_100_percent():
    summary = summarize_funding_ratio(
        _funding_trajectory([100.0, 99.9999999999]),
        target_funding_ratio=1.0,
    )

    assert summary.years_below_100_percent == 0
    assert summary.ever_underfunded is False
    assert summary.final_underfunded is False


def test_summary_threshold_tolerance_for_target_percent():
    summary = summarize_funding_ratio(
        _funding_trajectory([107.6, 107.5999999999]),
        target_funding_ratio=1.076,
    )

    assert summary.years_below_target_percent == 0


# ---------------------------------------------------------------------------
# F. DataFrame conversion
# ---------------------------------------------------------------------------


def test_funding_summary_to_dataframe_single_summary():
    df = funding_summary_to_dataframe(_standard_summary())

    assert df.shape == (1, len(FUNDING_SUMMARY_COLUMNS))
    assert list(df.columns) == list(FUNDING_SUMMARY_COLUMNS)
    assert validate_funding_summary_dataframe(df) is True


def test_funding_summary_to_dataframe_list_of_two():
    df = funding_summary_to_dataframe(
        [
            _standard_summary(),
            _standard_summary(
                start_projection_year=1,
                end_projection_year=4,
                maximum_funding_ratio_projection_year=1,
                minimum_funding_ratio_projection_year=3,
            ),
        ]
    )

    assert df.shape == (2, len(FUNDING_SUMMARY_COLUMNS))
    assert list(df.columns) == list(FUNDING_SUMMARY_COLUMNS)


def test_funding_summary_to_dataframe_empty_list():
    df = funding_summary_to_dataframe([])

    assert df.empty
    assert list(df.columns) == list(FUNDING_SUMMARY_COLUMNS)
    assert validate_funding_summary_dataframe(df) is True


def test_funding_summary_to_dataframe_rejects_wrong_item_type():
    with pytest.raises(TypeError):
        funding_summary_to_dataframe([object()])


@pytest.mark.parametrize("bad", [None, "x", {"summary": 1}])
def test_funding_summary_to_dataframe_rejects_wrong_input_type(bad):
    with pytest.raises(TypeError):
        funding_summary_to_dataframe(bad)


# ---------------------------------------------------------------------------
# G. Validate funding summary DataFrame
# ---------------------------------------------------------------------------


def test_validate_funding_summary_dataframe_valid_returns_true():
    df = funding_summary_to_dataframe(_standard_summary())
    assert validate_funding_summary_dataframe(df) is True


def test_validate_funding_summary_dataframe_empty_returns_true():
    df = pd.DataFrame(columns=list(FUNDING_SUMMARY_COLUMNS))
    assert validate_funding_summary_dataframe(df) is True


def test_validate_funding_summary_dataframe_rejects_non_dataframe():
    with pytest.raises(TypeError):
        validate_funding_summary_dataframe("not a df")


def test_validate_funding_summary_dataframe_rejects_missing_column():
    df = funding_summary_to_dataframe(_standard_summary()).drop(
        columns=["final_underfunded"]
    )
    with pytest.raises(ValueError):
        validate_funding_summary_dataframe(df)


def test_validate_funding_summary_dataframe_rejects_wrong_column_order():
    df = funding_summary_to_dataframe(_standard_summary())
    with pytest.raises(ValueError):
        validate_funding_summary_dataframe(df[list(reversed(FUNDING_SUMMARY_COLUMNS))])


def test_validate_funding_summary_dataframe_rejects_missing_value():
    df = funding_summary_to_dataframe(_standard_summary())
    df.loc[0, "currency"] = pd.NA
    with pytest.raises(ValueError):
        validate_funding_summary_dataframe(df)


def test_validate_funding_summary_dataframe_rejects_invalid_row_value():
    df = funding_summary_to_dataframe(_standard_summary())
    df.loc[0, "target_funding_ratio_percent"] = 0.0
    with pytest.raises(ValueError):
        validate_funding_summary_dataframe(df)


def test_summary_dataclass_rejects_year_count_above_horizon():
    with pytest.raises(ValueError):
        _standard_summary(years_below_100_percent=99)


def test_summary_dataclass_rejects_non_bool_flags():
    with pytest.raises(TypeError):
        _standard_summary(ever_underfunded=1)


# ---------------------------------------------------------------------------
# H. Invalid summarize inputs
# ---------------------------------------------------------------------------


def test_summarize_funding_ratio_rejects_non_dataframe():
    with pytest.raises(TypeError):
        summarize_funding_ratio("not a df", target_funding_ratio=1.076)


def test_summarize_funding_ratio_rejects_empty_trajectory():
    empty = pd.DataFrame(columns=list(FUNDING_RATIO_COLUMNS))
    with pytest.raises(ValueError):
        summarize_funding_ratio(empty, target_funding_ratio=1.076)


def test_summarize_funding_ratio_rejects_invalid_trajectory():
    with pytest.raises(ValueError):
        summarize_funding_ratio(
            pd.DataFrame({"foo": [1]}),
            target_funding_ratio=1.076,
        )


@pytest.mark.parametrize("bad", [True, None, "x", math.nan, 0.0, -1.0])
def test_summarize_funding_ratio_rejects_invalid_target_ratio(bad):
    with pytest.raises((TypeError, ValueError)):
        summarize_funding_ratio(
            _funding_trajectory([100.0]),
            target_funding_ratio=bad,
        )


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_summarize_funding_ratio_rejects_invalid_currency(bad):
    with pytest.raises(ValueError):
        summarize_funding_ratio(
            _funding_trajectory([100.0]),
            target_funding_ratio=1.0,
            currency=bad,
        )


# ---------------------------------------------------------------------------
# I. Projection year validation
# ---------------------------------------------------------------------------


def test_summarize_rejects_duplicated_projection_years():
    with pytest.raises(ValueError):
        summarize_funding_ratio(
            _funding_trajectory([100.0, 101.0], projection_years=[0, 0]),
            target_funding_ratio=1.0,
        )


def test_summarize_rejects_unsorted_projection_years():
    with pytest.raises(ValueError):
        summarize_funding_ratio(
            _funding_trajectory([101.0, 100.0], projection_years=[1, 0]),
            target_funding_ratio=1.0,
        )


def test_summarize_rejects_non_contiguous_projection_years():
    with pytest.raises(ValueError):
        summarize_funding_ratio(
            _funding_trajectory([100.0, 101.0], projection_years=[0, 2]),
            target_funding_ratio=1.0,
        )


# ---------------------------------------------------------------------------
# J. Immutability
# ---------------------------------------------------------------------------


def test_summarize_funding_ratio_does_not_mutate_input():
    trajectory = _funding_trajectory([107.6, 99.0, 95.0, 101.0])
    before = trajectory.copy(deep=True)

    summarize_funding_ratio(trajectory, target_funding_ratio=1.076)

    pd.testing.assert_frame_equal(trajectory, before)
