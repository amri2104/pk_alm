from __future__ import annotations

from dataclasses import dataclass, field

from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort


@dataclass(frozen=True)
class BVGPortfolioState:
    """Immutable snapshot of a BVG fund's cohort population at one point in time.

    Accepts lists or tuples for cohort collections; always stores them as tuples.
    Does not project, accumulate, or emit cashflows.
    """

    projection_year: int = 0
    active_cohorts: tuple[ActiveCohort, ...] = field(default_factory=tuple)
    retired_cohorts: tuple[RetiredCohort, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.projection_year < 0:
            raise ValueError(
                f"projection_year must be >= 0, got {self.projection_year}"
            )

        # Coerce lists → tuples (frozen dataclass requires object.__setattr__)
        if self.active_cohorts is None:
            raise ValueError("active_cohorts must not be None")
        if self.retired_cohorts is None:
            raise ValueError("retired_cohorts must not be None")

        object.__setattr__(self, "active_cohorts", tuple(self.active_cohorts))
        object.__setattr__(self, "retired_cohorts", tuple(self.retired_cohorts))

        # Type checks
        for i, c in enumerate(self.active_cohorts):
            if not isinstance(c, ActiveCohort):
                raise TypeError(
                    f"active_cohorts[{i}] must be ActiveCohort, got {type(c).__name__}"
                )
        for i, c in enumerate(self.retired_cohorts):
            if not isinstance(c, RetiredCohort):
                raise TypeError(
                    f"retired_cohorts[{i}] must be RetiredCohort, got {type(c).__name__}"
                )

        # Unique cohort IDs across both collections
        all_ids = [c.cohort_id for c in self.active_cohorts] + [
            c.cohort_id for c in self.retired_cohorts
        ]
        seen: set[str] = set()
        for cid in all_ids:
            if cid in seen:
                raise ValueError(f"duplicate cohort_id: '{cid}'")
            seen.add(cid)

    # --- member counts ---

    @property
    def active_count_total(self) -> int:
        return sum(c.count for c in self.active_cohorts)

    @property
    def retired_count_total(self) -> int:
        return sum(c.count for c in self.retired_cohorts)

    @property
    def member_count_total(self) -> int:
        return self.active_count_total + self.retired_count_total

    # --- capital ---

    @property
    def total_capital_active(self) -> float:
        return sum(c.total_capital_active for c in self.active_cohorts)

    @property
    def total_capital_rente(self) -> float:
        return sum(c.total_capital_rente for c in self.retired_cohorts)

    @property
    def total_capital(self) -> float:
        return self.total_capital_active + self.total_capital_rente

    # --- salary / credit / pension flows ---

    @property
    def annual_salary_total(self) -> float:
        return sum(c.annual_salary_total for c in self.active_cohorts)

    @property
    def annual_age_credit_total(self) -> float:
        return sum(c.annual_age_credit_total for c in self.active_cohorts)

    @property
    def annual_pension_total(self) -> float:
        return sum(c.annual_pension_total for c in self.retired_cohorts)

    # --- identifiers ---

    @property
    def cohort_ids(self) -> tuple[str, ...]:
        return tuple(c.cohort_id for c in self.active_cohorts) + tuple(
            c.cohort_id for c in self.retired_cohorts
        )
