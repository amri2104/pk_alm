from dataclasses import dataclass

from pk_alm.bvg.formulas import (
    calculate_age_credit,
    calculate_coordinated_salary,
    get_age_credit_rate,
)


@dataclass
class ActiveCohort:
    """A group of active BVG members with the same age and salary profile."""

    cohort_id: str
    age: int
    count: int
    gross_salary_per_person: float
    capital_active_per_person: float

    def __post_init__(self) -> None:
        if not isinstance(self.cohort_id, str) or not self.cohort_id.strip():
            raise ValueError("cohort_id must be a non-empty, non-whitespace string")
        if self.age < 0:
            raise ValueError(f"age must be >= 0, got {self.age}")
        if self.count < 0:
            raise ValueError(f"count must be >= 0, got {self.count}")
        if self.gross_salary_per_person < 0:
            raise ValueError(
                f"gross_salary_per_person must be >= 0, got {self.gross_salary_per_person}"
            )
        if self.capital_active_per_person < 0:
            raise ValueError(
                f"capital_active_per_person must be >= 0, got {self.capital_active_per_person}"
            )

    @property
    def coordinated_salary_per_person(self) -> float:
        return calculate_coordinated_salary(self.gross_salary_per_person)

    @property
    def age_credit_rate(self) -> float:
        return get_age_credit_rate(self.age)

    @property
    def annual_age_credit_per_person(self) -> float:
        return calculate_age_credit(self.coordinated_salary_per_person, self.age)

    @property
    def total_capital_active(self) -> float:
        return self.count * self.capital_active_per_person

    @property
    def annual_salary_total(self) -> float:
        return self.count * self.gross_salary_per_person

    @property
    def annual_age_credit_total(self) -> float:
        return self.count * self.annual_age_credit_per_person


@dataclass
class RetiredCohort:
    """A group of retired BVG members with the same pension and capital profile."""

    cohort_id: str
    age: int
    count: int
    annual_pension_per_person: float
    capital_rente_per_person: float

    def __post_init__(self) -> None:
        if not isinstance(self.cohort_id, str) or not self.cohort_id.strip():
            raise ValueError("cohort_id must be a non-empty, non-whitespace string")
        if self.age < 0:
            raise ValueError(f"age must be >= 0, got {self.age}")
        if self.count < 0:
            raise ValueError(f"count must be >= 0, got {self.count}")
        if self.annual_pension_per_person < 0:
            raise ValueError(
                f"annual_pension_per_person must be >= 0, got {self.annual_pension_per_person}"
            )
        if self.capital_rente_per_person < 0:
            raise ValueError(
                f"capital_rente_per_person must be >= 0, got {self.capital_rente_per_person}"
            )

    @property
    def annual_pension_total(self) -> float:
        return self.count * self.annual_pension_per_person

    @property
    def total_capital_rente(self) -> float:
        return self.count * self.capital_rente_per_person
