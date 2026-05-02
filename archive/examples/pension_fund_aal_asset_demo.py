"""Manual-run script: combined pension fund cashflow view (BVG + AAL/ACTUS).

This script demonstrates the shared CashflowRecord schema as the integration
contract between BVG liability cashflows and AAL/ACTUS asset-boundary
fallback cashflows. No network service is called; the ACTUS cashflows come
from the offline AAL asset boundary fallback.

Importing this module is a no-op. The demo only runs when this file is
executed directly:

    python examples/pension_fund_aal_asset_demo.py
"""

from pk_alm.scenarios.aal_asset_demo import run_pension_fund_aal_asset_demo

if __name__ == "__main__":
    result = run_pension_fund_aal_asset_demo()

    bvg_rows = len(result.baseline_result.engine_result.cashflows)
    aal_rows = len(result.aal_cashflows)
    combined_rows = len(result.combined_cashflows)
    sources = sorted(result.combined_cashflows["source"].unique().tolist())

    print("=== Pension Fund AAL Asset Demo ===")
    print(f"BVG cashflow rows        : {bvg_rows}")
    print(f"AAL/ACTUS cashflow rows  : {aal_rows}")
    print(f"Combined cashflow rows   : {combined_rows}")
    print(f"Sources in combined      : {sources}")
    print()
    print("Annual net cashflow (combined BVG + AAL/ACTUS):")
    for _, row in result.combined_annual_cashflows.iterrows():
        year = int(row["reporting_year"])
        net = float(row["net_cashflow"])
        struct = float(row["structural_net_cashflow"])
        print(f"  {year}: net = {net:>12,.0f}  structural = {struct:>12,.0f}")
    print()
    struct_yr = result.combined_liquidity_inflection_year_structural
    net_yr = result.combined_liquidity_inflection_year_net
    print(f"Structural inflection yr : {struct_yr}")
    print(f"Net inflection year      : {net_yr}")
    print()
    print("Note: no network/service call is made by default.")
    print("      AAL/ACTUS cashflows use the offline asset boundary fallback.")
