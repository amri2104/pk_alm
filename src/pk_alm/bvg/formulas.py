# BVG 2024 parameters
ENTRY_THRESHOLD = 22050.0
COORDINATION_DEDUCTION = 25725.0
MAX_AHV_SALARY = 88200.0
MIN_COORDINATED_SALARY = 3675.0
MAX_COORDINATED_SALARY = 62475.0

# (lower_age_inclusive, upper_age_inclusive, credit_rate)
AGE_CREDIT_RATES = [
    (0, 24, 0.00),
    (25, 34, 0.07),
    (35, 44, 0.10),
    (45, 54, 0.15),
    (55, 64, 0.18),
    (65, float("inf"), 0.00),
]


def calculate_coordinated_salary(gross_salary: float) -> float:
    """BVG coordinated salary: insured portion of gross salary after deductions.

    Returns 0 if below the entry threshold. Once above the threshold the minimum
    coordinated salary (3675 CHF) applies even when gross minus deduction is negative,
    because the member is insured.
    """
    if gross_salary < 0:
        raise ValueError(f"gross_salary must be >= 0, got {gross_salary}")
    if gross_salary < ENTRY_THRESHOLD:
        return 0.0
    coord = min(gross_salary, MAX_AHV_SALARY) - COORDINATION_DEDUCTION
    coord = max(coord, MIN_COORDINATED_SALARY)
    return min(coord, MAX_COORDINATED_SALARY)


def get_age_credit_rate(age: int) -> float:
    """BVG age-dependent savings credit rate (Altersgutschrift rate).

    Brackets are inclusive on both ends: [lower, upper].
    """
    if age < 0:
        raise ValueError(f"age must be >= 0, got {age}")
    for lower, upper, rate in AGE_CREDIT_RATES:
        if lower <= age <= upper:
            return rate
    return 0.0


def calculate_age_credit(coordinated_salary: float, age: int) -> float:
    """Annual BVG savings credit: coordinated_salary * age_credit_rate."""
    if coordinated_salary < 0:
        raise ValueError(f"coordinated_salary must be >= 0, got {coordinated_salary}")
    if age < 0:
        raise ValueError(f"age must be >= 0, got {age}")
    return coordinated_salary * get_age_credit_rate(age)


def calculate_annuity_immediate(n_years: int, interest_rate: float) -> float:
    """Present value of an annuity-immediate: payments at end of each period.

    Formula: (1 - (1+r)^-n) / r, or n when r == 0.
    """
    if n_years <= 0:
        raise ValueError(f"n_years must be > 0, got {n_years}")
    if interest_rate <= -1:
        raise ValueError(f"interest_rate must be > -1, got {interest_rate}")
    if interest_rate == 0.0:
        return float(n_years)
    return (1 - (1 + interest_rate) ** (-n_years)) / interest_rate


def calculate_annuity_due(n_years: int, interest_rate: float) -> float:
    """Present value of an annuity-due: payments at start of each period.

    Formula: annuity_immediate * (1 + r).
    """
    if n_years <= 0:
        raise ValueError(f"n_years must be > 0, got {n_years}")
    if interest_rate <= -1:
        raise ValueError(f"interest_rate must be > -1, got {interest_rate}")
    return calculate_annuity_immediate(n_years, interest_rate) * (1 + interest_rate)


def calculate_retiree_pv(
    annual_pension: float, n_years: int, interest_rate: float
) -> float:
    """Present value of future pension payments using annuity-due convention.

    Pension fund pays at the start of each period, so annuity-due applies.
    """
    if annual_pension < 0:
        raise ValueError(f"annual_pension must be >= 0, got {annual_pension}")
    if n_years <= 0:
        raise ValueError(f"n_years must be > 0, got {n_years}")
    if interest_rate <= -1:
        raise ValueError(f"interest_rate must be > -1, got {interest_rate}")
    return annual_pension * calculate_annuity_due(n_years, interest_rate)


def calculate_pensionierungsverlust(retiree_pv: float, capital_rente: float) -> float:
    """Retirement conversion loss: excess of retiree PV over annuity-financed capital.

    Reported as a KPI / P&L effect. Not added to V(t) if retiree PV already
    reflects the full pension obligation (avoids double-counting).
    """
    return retiree_pv - capital_rente
