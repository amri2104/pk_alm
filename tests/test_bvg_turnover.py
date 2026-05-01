import math

import pytest

from pk_alm.bvg.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.turnover import (
    MAX_PERMITTED_TURNOVER_RATE,
    TurnoverResult,
    apply_turnover_to_active_cohort,
    apply_turnover_to_portfolio,
)


def _active(count: int = 10) -> ActiveCohort:
    return ActiveCohort("ACT", 40, count, 80_000.0, 120_000.0)


def test_zero_rate_returns_same_cohort_no_record_and_no_departures() -> None:
    cohort = _active()
    surviving, record, residual, departed = apply_turnover_to_active_cohort(
        cohort, 0.0, "2026-12-31"
    )
    assert surviving == cohort
    assert record is None
    assert residual == 0.0
    assert departed == 0


def test_turnover_uses_floor_rounding_and_negative_ex_cashflow() -> None:
    surviving, record, residual, departed = apply_turnover_to_active_cohort(
        _active(10), 0.25, "2026-12-31"
    )
    assert surviving is not None
    assert surviving.count == 8
    assert departed == 2
    assert residual == pytest.approx(0.5)
    assert record is not None
    assert record.type == "EX"
    assert record.source == "BVG"
    assert record.payoff == pytest.approx(-240_000.0)
    assert record.nominalValue == pytest.approx(240_000.0)


def test_full_permitted_turnover_can_remove_half_cohort() -> None:
    surviving, record, residual, departed = apply_turnover_to_active_cohort(
        _active(2), MAX_PERMITTED_TURNOVER_RATE, "2026-12-31"
    )
    assert surviving is not None
    assert surviving.count == 1
    assert departed == 1
    assert residual == 0.0
    assert record is not None


@pytest.mark.parametrize("bad_rate", [True, math.nan, -0.01, 0.51])
def test_invalid_turnover_rate_raises(bad_rate: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        apply_turnover_to_active_cohort(_active(), bad_rate, "2026-12-31")


def test_apply_turnover_to_portfolio_tracks_person_exits_and_retirees_pass_through() -> None:
    portfolio = BVGPortfolioState(
        active_cohorts=(_active(10), ActiveCohort("ACT2", 50, 5, 70_000.0, 80_000.0)),
        retired_cohorts=(RetiredCohort("RET", 70, 3, 30_000.0, 400_000.0),),
    )
    result = apply_turnover_to_portfolio(portfolio, 0.2, "2026-12-31")
    assert isinstance(result, TurnoverResult)
    assert result.exited_count == 3
    assert result.rounding_residual_count == 0.0
    assert [c.count for c in result.portfolio_state.active_cohorts] == [8, 4]
    assert result.portfolio_state.retired_cohorts == portfolio.retired_cohorts
    assert len(result.cashflow_records) == 2


def test_turnover_result_rejects_invalid_exited_count() -> None:
    portfolio = BVGPortfolioState()
    with pytest.raises(TypeError):
        TurnoverResult(portfolio, (), 0.0, True)
