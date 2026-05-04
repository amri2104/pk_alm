import pandas as pd
from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort, RetiredCohort
from pk_alm.bvg_liability_engine.domain_models.portfolio import BVGPortfolioState
from pk_alm.bvg_liability_engine.orchestration.config_enhanced import EnhancedBVGConfig
from pk_alm.bvg_liability_engine.orchestration.engine_enhanced import run_bvg_engine_enhanced, calculate_retiree_pv

def run_tests():
    # Setup initial state
    initial_active = ActiveCohort("A1", 45, 100, 80000.0, 50000.0, gender="mixed")
    initial_retired = RetiredCohort("R1", 70, 50, 20000.0, 300000.0, gender="mixed")
    portfolio = BVGPortfolioState(0, (initial_active,), (initial_retired,))
    
    config = EnhancedBVGConfig(
        start_year=2024,
        projection_horizon=20, # Long horizon
        new_entrants_per_year=0,
        active_mortality_mode="expected",
        retiree_mortality_mode="expected",
        withdrawal_rate=0.02
    )

    # Scenario 1: No-new-entrant run declines over long horizon
    _, _, _, pop_dev = run_bvg_engine_enhanced(portfolio, config)
    final_count = pop_dev.iloc[-1]["total_count"]
    initial_count = pop_dev.iloc[0]["total_count"]
    if final_count < initial_count:
        print("Scenario 1 (No-new-entrant run declines over long horizon): PASS")
    else:
        print("Scenario 1: FAIL")

    # Scenario 2: New-entrant run stabilizes member count / liability development directionally
    config_ne = EnhancedBVGConfig.from_dict(config.__dict__)
    config_ne.new_entrants_per_year = 5
    _, _, _, pop_dev_ne = run_bvg_engine_enhanced(portfolio, config_ne)
    final_count_ne = pop_dev_ne.iloc[-1]["total_count"]
    if final_count_ne > final_count:
        print("Scenario 2 (New-entrant run stabilizes member count): PASS")
    else:
        print("Scenario 2: FAIL")

    # Scenario 3: Mortality reduces expected retiree PV versus mortality-off valuation
    config_off = EnhancedBVGConfig.from_dict(config.__dict__)
    config_off.retiree_mortality_mode = "off"
    
    pv_on = calculate_retiree_pv(initial_retired, config)
    pv_off = calculate_retiree_pv(initial_retired, config_off)
    if pv_on < pv_off:
        print("Scenario 3 (Mortality reduces expected retiree PV): PASS")
    else:
        print("Scenario 3: FAIL")

    # Scenario 4: Retiree PV annuity-due test (first payment undiscounted)
    # Using hand calculation: 1 payment now (t=0) + ...
    # If mortality is off, PV = sum(20000 / (1+r)^t)
    r = config_off.technical_interest_rate
    expected_hand_calc = 50 * sum(20000.0 / ((1 + r)**t) for t in range(120 - 70 + 1))
    if abs(pv_off - expected_hand_calc) < 1e-5:
        print("Scenario 4 (Retiree PV annuity-due test): PASS")
    else:
        print(f"Scenario 4: FAIL (Expected: {expected_hand_calc}, Got: {pv_off})")

if __name__ == "__main__":
    run_tests()
