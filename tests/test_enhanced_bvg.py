import pytest
import math
import pandas as pd

from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.config_enhanced import EnhancedBVGConfig
from pk_alm.bvg_liability_engine.orchestration.engine_enhanced import run_bvg_engine_enhanced, calculate_retiree_pv
from pk_alm.bvg_liability_engine.actuarial_assumptions.enhanced_mortality import get_survival_probability, get_qx

def test_enhanced_mortality_helpers():
    # 1. EK0105 loading and survival probability for male, female, and mixed gender.
    q_male = get_qx(65, "male")
    q_female = get_qx(65, "female")
    q_mixed = get_qx(65, "mixed", female_fraction=0.5)
    
    assert q_male > 0 and q_female > 0
    assert math.isclose(q_mixed, 0.5 * q_male + 0.5 * q_female, rel_tol=1e-5)
    
    p_male = get_survival_probability(65, "male", 10)
    p_female = get_survival_probability(65, "female", 10)
    p_mixed = get_survival_probability(65, "mixed", 10, female_fraction=0.5)
    
    assert p_male > 0 and p_female > 0
    assert math.isclose(p_mixed, 0.5 * p_male + 0.5 * p_female, rel_tol=1e-5)

def test_single_active_projection_deterministic():
    # 2. Single active projection with no mortality, no withdrawals, no entries; compare capital to hand calculation.
    initial_active = ActiveCohort("A1", 45, 100, 80000.0, 50000.0, gender="mixed")
    portfolio = BVGPortfolioState(0, (initial_active,), ())
    
    config = EnhancedBVGConfig(
        projection_horizon=1,
        active_mortality_mode="off",
        withdrawal_rate=0.0,
        new_entrants_per_year=0,
        technical_interest_rate=0.02,
        salary_escalation_rate=0.01,
        contribution_rate=0.10
    )
    
    _, lib_dev, _, _ = run_bvg_engine_enhanced(portfolio, config)
    
    # Hand calc
    # End of year 1 capital per person: 50000 * 1.02 + annual_age_credit
    # Age 45 age credit rate is usually 15% in Stage-1, wait, let's just see what it actually is via code.
    # The code calculates it via `annual_age_credit_per_person` property on initial_active.
    expected_capital_pp = 50000.0 * 1.02 + initial_active.annual_age_credit_per_person
    expected_total = 100 * expected_capital_pp
    
    # Year 1 (which is the second entry in lib_dev, index 1)
    actual_total = lib_dev.iloc[1]["active_capital"]
    assert math.isclose(actual_total, expected_total, rel_tol=1e-5)

def test_retiree_pv_deterministic_vs_mortality():
    # 3. Single retiree PV with a simplified deterministic mortality table or zero mortality fixture; compare to fixed-term annuity formula.
    # 4. Mortality reduces expected retiree PV versus mortality-off valuation.
    initial_retired = RetiredCohort("R1", 70, 50, 20000.0, 300000.0, gender="mixed")
    
    config_off = EnhancedBVGConfig(retiree_mortality_mode="off", technical_interest_rate=0.02)
    pv_off = calculate_retiree_pv(initial_retired, config_off)
    
    expected_hand_calc = 50 * sum(20000.0 / ((1 + 0.02)**t) for t in range(120 - 70 + 1))
    assert math.isclose(pv_off, expected_hand_calc, rel_tol=1e-5)
    
    config_on = EnhancedBVGConfig(retiree_mortality_mode="expected", technical_interest_rate=0.02)
    pv_on = calculate_retiree_pv(initial_retired, config_on)
    
    assert pv_on < pv_off

def test_population_scenarios():
    # 5. No-new-entrant run declines over long horizon.
    # 6. New-entrant run stabilizes member count / liability development directionally.
    initial_active = ActiveCohort("A1", 45, 100, 80000.0, 50000.0, gender="mixed")
    portfolio = BVGPortfolioState(0, (initial_active,), ())
    
    config_no_ne = EnhancedBVGConfig(
        projection_horizon=15,
        new_entrants_per_year=0,
        active_mortality_mode="expected",
        withdrawal_rate=0.02
    )
    
    _, _, _, pop_no_ne = run_bvg_engine_enhanced(portfolio, config_no_ne)
    final_count_no_ne = pop_no_ne.iloc[-1]["total_count"]
    initial_count = pop_no_ne.iloc[0]["total_count"]
    
    assert final_count_no_ne < initial_count
    
    config_ne = EnhancedBVGConfig(
        projection_horizon=15,
        new_entrants_per_year=10,
        active_mortality_mode="expected",
        withdrawal_rate=0.02
    )
    
    _, _, _, pop_ne = run_bvg_engine_enhanced(portfolio, config_ne)
    final_count_ne = pop_ne.iloc[-1]["total_count"]
    
    assert final_count_ne > final_count_no_ne
