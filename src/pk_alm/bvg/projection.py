from pk_alm.bvg.cohorts import ActiveCohort, RetiredCohort


def project_active_cohort_one_year(
    cohort: ActiveCohort, interest_rate: float
) -> ActiveCohort:
    """Return a new ActiveCohort advanced by one year.

    Age credit is earned at the current age before ageing.
    Capital evolves as: capital * (1 + r) + age_credit.
    """
    if interest_rate <= -1:
        raise ValueError(f"interest_rate must be > -1, got {interest_rate}")

    new_capital = (
        cohort.capital_active_per_person * (1 + interest_rate)
        + cohort.annual_age_credit_per_person
    )

    return ActiveCohort(
        cohort_id=cohort.cohort_id,
        age=cohort.age + 1,
        count=cohort.count,
        gross_salary_per_person=cohort.gross_salary_per_person,
        capital_active_per_person=new_capital,
    )


def project_retired_cohort_one_year(
    cohort: RetiredCohort, interest_rate: float
) -> RetiredCohort:
    """Return a new RetiredCohort advanced by one year.

    Annuity-due convention: pension is paid at the start of the year,
    then the remaining capital accumulates with the technical interest rate.
    Capital evolves as: (capital - pension) * (1 + r), floored at 0.
    """
    if interest_rate <= -1:
        raise ValueError(f"interest_rate must be > -1, got {interest_rate}")

    new_capital = max(
        0.0,
        (cohort.capital_rente_per_person - cohort.annual_pension_per_person)
        * (1 + interest_rate),
    )

    return RetiredCohort(
        cohort_id=cohort.cohort_id,
        age=cohort.age + 1,
        count=cohort.count,
        annual_pension_per_person=cohort.annual_pension_per_person,
        capital_rente_per_person=new_capital,
    )
