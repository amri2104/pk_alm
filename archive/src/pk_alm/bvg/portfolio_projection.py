from pk_alm.bvg.portfolio import BVGPortfolioState
from pk_alm.bvg.projection import (
    project_active_cohort_one_year,
    project_retired_cohort_one_year,
)


def project_portfolio_one_year(
    portfolio: BVGPortfolioState,
    active_interest_rate: float,
    retiree_interest_rate: float,
) -> BVGPortfolioState:
    """Return a new BVGPortfolioState advanced by one year.

    Each active cohort is projected with active_interest_rate.
    Each retired cohort is projected with retiree_interest_rate.
    The two rates are kept separate because active savings capital
    and retiree reserve capital may use different assumptions later.
    """
    if not isinstance(portfolio, BVGPortfolioState):
        raise TypeError(
            f"portfolio must be a BVGPortfolioState, got {type(portfolio).__name__}"
        )
    if active_interest_rate <= -1:
        raise ValueError(
            f"active_interest_rate must be > -1, got {active_interest_rate}"
        )
    if retiree_interest_rate <= -1:
        raise ValueError(
            f"retiree_interest_rate must be > -1, got {retiree_interest_rate}"
        )

    projected_active = tuple(
        project_active_cohort_one_year(c, active_interest_rate)
        for c in portfolio.active_cohorts
    )
    projected_retired = tuple(
        project_retired_cohort_one_year(c, retiree_interest_rate)
        for c in portfolio.retired_cohorts
    )

    return BVGPortfolioState(
        projection_year=portfolio.projection_year + 1,
        active_cohorts=projected_active,
        retired_cohorts=projected_retired,
    )
