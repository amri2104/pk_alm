"""Tests for Stage 2 salary dynamics (BAUPLAN — all skipped until Sprint 10).

These tests pin the Stage-2 salary-dynamics contract before implementation.
Each test is currently skipped via ``pytest.mark.skip``. Sprint 10 will
remove the skip markers and fill in the assertion bodies.

The set of test names below is final; new test names may be added during
implementation, but no test name in this file should be removed.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Stage 2 Bauplan: implementation deferred")


class TestApplySalaryGrowthToActiveCohort:
    def test_zero_growth_returns_equivalent_cohort(self) -> None:
        """g=0 must produce a cohort with the same gross_salary_per_person."""
        ...

    def test_positive_growth_scales_gross_salary_only(self) -> None:
        """g>0 scales gross_salary by (1+g); other fields unchanged."""
        ...

    def test_age_count_capital_pass_through(self) -> None:
        """age, count, capital_active_per_person, cohort_id pass through."""
        ...

    def test_input_cohort_not_mutated(self) -> None:
        """Original cohort instance is not mutated."""
        ...

    def test_negative_growth_rate_raises_value_error(self) -> None:
        """g<0 must raise ValueError (deflation rejected in Stage 2)."""
        ...

    def test_growth_above_max_permitted_raises_value_error(self) -> None:
        """g > MAX_PERMITTED_SALARY_GROWTH_RATE raises ValueError."""
        ...

    def test_nan_growth_rate_raises_value_error(self) -> None:
        """NaN growth_rate raises ValueError."""
        ...

    def test_bool_growth_rate_raises_type_error(self) -> None:
        """Bool growth_rate raises TypeError."""
        ...

    def test_non_active_cohort_input_raises_type_error(self) -> None:
        """Non-ActiveCohort input raises TypeError."""
        ...

    def test_manually_checkable_numeric_example(self) -> None:
        """Manually checkable: salary 60000 * 1.015 = 60900.0."""
        ...


class TestApplySalaryGrowthToPortfolio:
    def test_zero_growth_preserves_portfolio_state(self) -> None:
        """g=0 returns a portfolio with identical active/retired cohorts."""
        ...

    def test_positive_growth_scales_all_active_cohorts_uniformly(self) -> None:
        """All active cohorts get the same multiplicative scaling."""
        ...

    def test_retired_cohorts_unchanged(self) -> None:
        """Retired cohorts pass through (pension indexation out of scope)."""
        ...

    def test_projection_year_unchanged(self) -> None:
        """Salary growth does not advance projection_year."""
        ...

    def test_input_portfolio_not_mutated(self) -> None:
        """Original portfolio instance is not mutated."""
        ...

    def test_invalid_portfolio_input_raises_type_error(self) -> None:
        """Non-BVGPortfolioState input raises TypeError."""
        ...

    def test_invalid_growth_rate_raises_value_error(self) -> None:
        """Out-of-range or NaN growth_rate raises ValueError."""
        ...
