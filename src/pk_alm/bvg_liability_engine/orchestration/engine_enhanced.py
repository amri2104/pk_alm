"""Repo-native Enhanced BVG Liability Engine."""

from __future__ import annotations

import math
import pandas as pd
from typing import Tuple

from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.cashflows.schema import CashflowRecord
from pk_alm.bvg_liability_engine.orchestration.config_enhanced import EnhancedBVGConfig
from pk_alm.bvg_liability_engine.actuarial_assumptions.enhanced_mortality import get_survival_probability, get_qx

def calculate_retiree_pv(cohort: RetiredCohort, config: EnhancedBVGConfig) -> float:
    """Calculate the present value of a retired cohort's pensions."""
    pv_per_person = 0.0
    horizon = 120 - cohort.age
    if horizon < 0:
        horizon = 0
        
    if config.retiree_mortality_mode == "off":
        for t in range(horizon + 1):
            pv_per_person += cohort.annual_pension_per_person / ((1 + config.technical_interest_rate)**t)
    else:
        for t in range(horizon + 1):
            prob = get_survival_probability(cohort.age, cohort.gender, t, config.female_fraction)
            pv_per_person += (cohort.annual_pension_per_person * prob) / ((1 + config.technical_interest_rate)**t)
            
    return cohort.count * pv_per_person


def run_bvg_engine_enhanced(
    initial_state: BVGPortfolioState,
    config: EnhancedBVGConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame, tuple[CashflowRecord, ...], pd.DataFrame]:
    
    current_state = initial_state
    
    cashflows_list = []
    cf_records = []
    liability_list = []
    population_list = []
    
    for step in range(config.projection_horizon):
        year = config.start_year + step
        event_date = pd.Timestamp(f"{year}-12-31")
        
        # 1. Report starting population & liability
        active_count = sum(c.count for c in current_state.active_cohorts)
        retired_count = sum(c.count for c in current_state.retired_cohorts)
        population_list.append({
            "year": year,
            "active_count": active_count,
            "retired_count": retired_count,
            "total_count": active_count + retired_count
        })
        
        active_capital = sum(c.total_capital_active for c in current_state.active_cohorts)
        retiree_pv = sum(calculate_retiree_pv(c, config) for c in current_state.retired_cohorts)
        liability_list.append({
            "year": year,
            "active_capital": active_capital,
            "retiree_pv": retiree_pv,
            "total_liabilities": active_capital + retiree_pv
        })
        
        # Track annual expected cashflows
        contributions_received = 0.0
        pensions_paid = 0.0
        withdrawals_paid = 0.0
        
        next_active_cohorts = []
        next_retired_cohorts = []
        
        # 2. PR / Contributions from Active Cohorts
        for cohort in current_state.active_cohorts:
            # Stage 1 defines contributions as contribution_rate * gross_salary * count (using age_credit rate is another way, but config has contribution_rate)
            # Actually, let's just use the config.contribution_rate * gross_salary
            contrib = cohort.count * cohort.gross_salary_per_person * config.contribution_rate
            contributions_received += contrib
            cf_records.append(CashflowRecord(
                contractId=cohort.cohort_id,
                time=event_date,
                type="PR",
                payoff=contrib,
                nominalValue=contrib,
                currency="CHF",
                source="BVG"
            ))
            
        # 3. RP / Pensions from Retired Cohorts
        for cohort in current_state.retired_cohorts:
            # Expected pension payment
            if config.retiree_mortality_mode == "expected":
                survival_prob = get_survival_probability(cohort.age, cohort.gender, 1, config.female_fraction)
                # First payment at start of year is fully paid. Wait, is it annuity-due? 
                # If they survive the year, they get paid for the year, or they get paid at the start?
                # Annuity-due means payment is at start. So full payment for the current cohort count.
                # Actually, the prompt says expected annual pension payments.
                # We'll just pay the expected amount based on start count, or survival? Let's pay full for current alive.
                # Wait, "mortality reduces expected retiree PV". The cashflow is just current count * annual_pension if paid at start of year.
                expected_pension = cohort.count * cohort.annual_pension_per_person
            else:
                expected_pension = cohort.count * cohort.annual_pension_per_person
            
            pensions_paid += expected_pension
            # Canonical representation: pensions paid are outflows (negative)
            cf_records.append(CashflowRecord(
                contractId=cohort.cohort_id,
                time=event_date,
                type="RP",
                payoff=-expected_pension,
                nominalValue=expected_pension,
                currency="CHF",
                source="BVG"
            ))
            
        # 4. Active Decrements (Mortality & Turnover)
        for cohort in current_state.active_cohorts:
            count = cohort.count
            expected_deaths = 0.0
            departing_deaths_int = 0
            
            if config.active_mortality_mode == "expected":
                qx = get_qx(cohort.age, cohort.gender, config.female_fraction)
                expected_deaths = count * qx
                if config.decrement_mode == "expected":
                    departing_deaths_int = math.floor(expected_deaths)
                else:
                    departing_deaths_int = math.floor(expected_deaths)
                    
            count_after_death = count - departing_deaths_int
            
            expected_withdrawals = count_after_death * config.withdrawal_rate
            departing_withdrawals_int = math.floor(expected_withdrawals)
            count_after_turnover = count_after_death - departing_withdrawals_int
            
            # Expected cashflow for withdrawals
            withdrawal_amount = expected_withdrawals * cohort.capital_active_per_person
            withdrawals_paid += withdrawal_amount
            
            if expected_withdrawals > 0:
                cf_records.append(CashflowRecord(
                    contractId=cohort.cohort_id,
                    time=event_date,
                    type="EX",
                    payoff=-withdrawal_amount,
                    nominalValue=withdrawal_amount,
                    currency="CHF",
                    source="BVG"
                ))
            
            if count_after_turnover > 0:
                next_active_cohorts.append(ActiveCohort(
                    cohort_id=cohort.cohort_id,
                    age=cohort.age, # updated in projection
                    count=count_after_turnover,
                    gross_salary_per_person=cohort.gross_salary_per_person,
                    capital_active_per_person=cohort.capital_active_per_person,
                    gender=cohort.gender
                ))

        # 5. Retiree Decrements (Mortality)
        for cohort in current_state.retired_cohorts:
            count = cohort.count
            departing_deaths_int = 0
            if config.retiree_mortality_mode == "expected":
                qx = get_qx(cohort.age, cohort.gender, config.female_fraction)
                expected_deaths = count * qx
                departing_deaths_int = math.floor(expected_deaths)
            
            count_after_death = count - departing_deaths_int
            if count_after_death > 0:
                next_retired_cohorts.append(RetiredCohort(
                    cohort_id=cohort.cohort_id,
                    age=cohort.age,
                    count=count_after_death,
                    annual_pension_per_person=cohort.annual_pension_per_person,
                    capital_rente_per_person=cohort.capital_rente_per_person,
                    gender=cohort.gender
                ))
                
        # 6. Projection & Salary Growth
        projected_active = []
        for cohort in next_active_cohorts:
            # Interest credit + age credit
            new_capital = (cohort.capital_active_per_person * (1 + config.technical_interest_rate) + 
                           cohort.annual_age_credit_per_person)
            new_salary = cohort.gross_salary_per_person * (1 + config.salary_escalation_rate)
            projected_active.append(ActiveCohort(
                cohort_id=cohort.cohort_id,
                age=cohort.age + 1,
                count=cohort.count,
                gross_salary_per_person=new_salary,
                capital_active_per_person=new_capital,
                gender=cohort.gender
            ))
            
        projected_retired = []
        for cohort in next_retired_cohorts:
            new_capital = cohort.capital_rente_per_person * (1 + config.technical_interest_rate) - cohort.annual_pension_per_person
            if new_capital < 0:
                new_capital = 0.0
            projected_retired.append(RetiredCohort(
                cohort_id=cohort.cohort_id,
                age=cohort.age + 1,
                count=cohort.count,
                annual_pension_per_person=cohort.annual_pension_per_person,
                capital_rente_per_person=new_capital,
                gender=cohort.gender
            ))
            
        # 7. Retirement Transitions
        final_active = []
        for cohort in projected_active:
            if cohort.age >= config.retirement_age:
                # Retire this cohort
                # No capital withdrawal fraction in simplified config, assume 0 for now or use standard
                pension = cohort.capital_active_per_person * config.conversion_rate
                projected_retired.append(RetiredCohort(
                    cohort_id=f"{cohort.cohort_id}_ret",
                    age=cohort.age,
                    count=cohort.count,
                    annual_pension_per_person=pension,
                    capital_rente_per_person=cohort.capital_active_per_person,
                    gender=cohort.gender
                ))
            else:
                final_active.append(cohort)
                
        # 8. New Entrants
        if config.new_entrants_per_year > 0:
            final_active.append(ActiveCohort(
                cohort_id=f"NE_{year}",
                age=config.entry_age,
                count=config.new_entrants_per_year,
                gross_salary_per_person=config.entry_salary,
                capital_active_per_person=0.0, # Start with 0 capital
                gender="mixed"
            ))
            
        current_state = BVGPortfolioState(
            projection_year=current_state.projection_year + 1,
            active_cohorts=tuple(final_active),
            retired_cohorts=tuple(projected_retired)
        )
        
        # Cashflow Summary (Note: pensions_paid and withdrawals_paid are treated as magnitudes here,
        # but in net_cashflow they are subtracted from contributions_received)
        net_cashflow = contributions_received - pensions_paid - withdrawals_paid
        cashflows_list.append({
            "year": year,
            "contributions_received": contributions_received,
            "pensions_paid": pensions_paid,
            "withdrawals_paid": withdrawals_paid,
            "net_cashflow": net_cashflow
        })

    # Final year state
    year = config.start_year + config.projection_horizon
    active_count = sum(c.count for c in current_state.active_cohorts)
    retired_count = sum(c.count for c in current_state.retired_cohorts)
    population_list.append({
        "year": year,
        "active_count": active_count,
        "retired_count": retired_count,
        "total_count": active_count + retired_count
    })
    
    active_capital = sum(c.total_capital_active for c in current_state.active_cohorts)
    retiree_pv = sum(calculate_retiree_pv(c, config) for c in current_state.retired_cohorts)
    liability_list.append({
        "year": year,
        "active_capital": active_capital,
        "retiree_pv": retiree_pv,
        "total_liabilities": active_capital + retiree_pv
    })

    return (
        pd.DataFrame(cashflows_list),
        pd.DataFrame(liability_list),
        tuple(cf_records),
        pd.DataFrame(population_list)
    )
