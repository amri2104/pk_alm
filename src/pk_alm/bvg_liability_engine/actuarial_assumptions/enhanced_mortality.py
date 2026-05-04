from __future__ import annotations

from pk_alm.bvg_liability_engine.actuarial_assumptions.mortality import (
    load_ek0105_table, EKM_0105, EKF_0105, survival_factor
)

_MALE_TABLE = None
_FEMALE_TABLE = None

def _get_tables():
    global _MALE_TABLE, _FEMALE_TABLE
    if _MALE_TABLE is None:
        _MALE_TABLE = load_ek0105_table(EKM_0105)
    if _FEMALE_TABLE is None:
        _FEMALE_TABLE = load_ek0105_table(EKF_0105)
    return _MALE_TABLE, _FEMALE_TABLE

def get_survival_probability(age: int, gender: str, years: int, female_fraction: float = 0.5) -> float:
    male_table, female_table = _get_tables()
    if gender == "male":
        return survival_factor(male_table, age, years)
    elif gender == "female":
        return survival_factor(female_table, age, years)
    elif gender == "mixed":
        p_male = survival_factor(male_table, age, years)
        p_female = survival_factor(female_table, age, years)
        return female_fraction * p_female + (1 - female_fraction) * p_male
    else:
        raise ValueError(f"Unknown gender: {gender}")

def get_qx(age: int, gender: str, female_fraction: float = 0.5) -> float:
    male_table, female_table = _get_tables()
    if age > male_table.max_age:
        return 1.0
    if gender == "male":
        return male_table.qx(age)
    elif gender == "female":
        return female_table.qx(age)
    elif gender == "mixed":
        # The prompt instructed: "Mixed-gender survival - Compute it as a weighted average of the male and female survival probabilities, not by blending the mortality rates (qx) directly."
        # However, for a 1-year qx, the survival probability is px = 1 - qx.
        # So p_mixed = f * p_female + (1-f) * p_male
        # qx_mixed = 1 - p_mixed = 1 - (f * (1-q_female) + (1-f) * (1-q_male)) = f*q_female + (1-f)*q_male.
        # So for 1-year it's mathematically equivalent to blending qx.
        p_male = male_table.px(age)
        p_female = female_table.px(age)
        p_mixed = female_fraction * p_female + (1 - female_fraction) * p_male
        return 1.0 - p_mixed
    else:
        raise ValueError(f"Unknown gender: {gender}")
