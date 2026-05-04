import math

import pandas as pd
import pytest

from pk_alm.bvg_liability_engine.domain_models.cohorts import RetiredCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.pension_logic.valuation import VALUATION_COLUMNS, value_portfolio_states
from pk_alm.bvg_liability_engine.pension_logic.valuation_dynamic import value_portfolio_states_dynamic


RATE = 0.0176


def _retired_state(projection_year: int = 0) -> BVGPortfolioState:
    return BVGPortfolioState(
        projection_year=projection_year,
        retired_cohorts=(
            RetiredCohort(
                cohort_id="RET_70",
                age=70,
                count=5,
                annual_pension_per_person=30_000.0,
                capital_rente_per_person=450_000.0,
            ),
        ),
    )


def test_scalar_input_reproduces_standard_valuation() -> None:
    states = (_retired_state(0), _retired_state(1))
    standard = value_portfolio_states(states, RATE)
    dynamic = value_portfolio_states_dynamic(states, RATE)
    pd.testing.assert_frame_equal(dynamic, standard)


def test_constant_sequence_reproduces_scalar_input() -> None:
    states = (_retired_state(0), _retired_state(1), _retired_state(2))
    scalar = value_portfolio_states_dynamic(states, RATE)
    sequence = value_portfolio_states_dynamic(states, (RATE, RATE, RATE))
    pd.testing.assert_frame_equal(sequence, scalar)


def test_short_sequence_forward_fills_discount_rate() -> None:
    states = (_retired_state(0), _retired_state(1), _retired_state(2))
    df = value_portfolio_states_dynamic(states, (0.02, 0.01))
    assert list(df["technical_interest_rate"]) == pytest.approx([0.02, 0.01, 0.01])


def test_falling_discount_rate_increases_pv_for_same_pension_path() -> None:
    states = (_retired_state(0), _retired_state(1))
    flat = value_portfolio_states_dynamic(states, (0.03, 0.03))
    falling = value_portfolio_states_dynamic(states, (0.03, 0.01))
    assert falling.iloc[1]["retiree_obligation_pv"] > flat.iloc[1][
        "retiree_obligation_pv"
    ]


def test_dynamic_valuation_schema_matches_stage2a_schema() -> None:
    df = value_portfolio_states_dynamic((_retired_state(),), RATE)
    assert list(df.columns) == list(VALUATION_COLUMNS)


@pytest.mark.parametrize("bad_rate", [True, math.nan, -0.01])
def test_bool_nan_and_negative_rates_are_rejected(bad_rate: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        value_portfolio_states_dynamic((_retired_state(),), bad_rate)
