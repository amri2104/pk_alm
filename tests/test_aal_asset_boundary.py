"""Tests for AAL asset construction helpers."""

import pandas as pd

from pk_alm.actus_asset_engine.aal_asset_boundary import (
    DEFAULT_PAM_CONTRACT_ID,
    DEFAULT_PAM_COUPON_RATE,
    DEFAULT_PAM_CURRENCY,
    DEFAULT_PAM_MATURITY_YEAR,
    DEFAULT_PAM_NOMINAL_VALUE,
    DEFAULT_PAM_START_YEAR,
    build_aal_cash_contract,
    build_aal_pam_contract,
    build_aal_portfolio,
    build_aal_stk_contract,
)
from pk_alm.actus_asset_engine.aal_asset_portfolio import CSHSpec, STKSpec
from pk_alm.actus_asset_engine.aal_probe import get_aal_module
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline


class _FakePAM:
    def __init__(self, **terms):
        self.terms = dict(terms)

    def to_dict(self):
        return {**self.terms, "contractType": "PAM"}


class _FakeSTK:
    def __init__(self, **terms):
        self.terms = dict(terms)

    def to_dict(self):
        return {**self.terms, "contractType": "STK"}


class _FakeCSH:
    def __init__(self, **terms):
        self.terms = dict(terms)

    def to_dict(self):
        return {**self.terms, "contractType": "CSH"}


class _FakePortfolio:
    def __init__(self, contracts):
        self.contracts = list(contracts)
        self.contract_df = pd.DataFrame(
            [contract.to_dict() for contract in self.contracts]
        )

    def __len__(self):
        return len(self.contracts)

    def to_dict(self):
        return [contract.to_dict() for contract in self.contracts]


class _FakeAALModule:
    PAM = _FakePAM
    STK = _FakeSTK
    CSH = _FakeCSH
    Portfolio = _FakePortfolio


def _stk_spec(dividend_yield=0.025):
    return STKSpec(
        contract_id="CUSTOM_STK",
        start_year=2026,
        divestment_year=2030,
        quantity=1_000.0,
        price_at_purchase=100.0,
        price_at_termination=116.985856,
        dividend_yield=dividend_yield,
        market_value_growth=0.04,
    )


def test_pam_contract_uses_default_terms_with_fake_module():
    pam = build_aal_pam_contract(_FakeAALModule)
    terms = pam.to_dict()
    assert terms["contractID"] == DEFAULT_PAM_CONTRACT_ID
    assert terms["contractDealDate"] == f"{DEFAULT_PAM_START_YEAR}-01-01T00:00:00"
    assert terms["initialExchangeDate"] == f"{DEFAULT_PAM_START_YEAR}-01-01T00:00:00"
    assert terms["maturityDate"] == f"{DEFAULT_PAM_MATURITY_YEAR}-12-31T00:00:00"
    assert terms["notionalPrincipal"] == DEFAULT_PAM_NOMINAL_VALUE
    assert terms["nominalInterestRate"] == DEFAULT_PAM_COUPON_RATE
    assert terms["cycleOfInterestPayment"] == "P1YL1"
    assert terms["cycleAnchorDateOfInterestPayment"] == "2027-01-01T00:00:00"
    assert terms["currency"] == DEFAULT_PAM_CURRENCY
    assert terms["contractType"] == "PAM"


def test_pam_contract_accepts_custom_terms_with_fake_module():
    pam = build_aal_pam_contract(
        _FakeAALModule,
        contract_id="CUSTOM_PAM",
        start_year=2027,
        maturity_year=2031,
        nominal_value=250_000.0,
        coupon_rate=0.031,
        coupon_cycle="P6ML1",
        coupon_anchor_date="2027-07-01T00:00:00",
        currency="CHF",
    )
    terms = pam.to_dict()
    assert terms["contractID"] == "CUSTOM_PAM"
    assert terms["contractDealDate"] == "2027-01-01T00:00:00"
    assert terms["maturityDate"] == "2031-12-31T00:00:00"
    assert terms["notionalPrincipal"] == 250_000.0
    assert terms["nominalInterestRate"] == 0.031
    assert terms["cycleOfInterestPayment"] == "P6ML1"
    assert terms["cycleAnchorDateOfInterestPayment"] == "2027-07-01T00:00:00"


def test_stk_contract_maps_required_terms_and_group_6_with_fake_module():
    stk = build_aal_stk_contract(_FakeAALModule, _stk_spec())
    terms = stk.to_dict()
    assert terms["contractID"] == "CUSTOM_STK"
    assert terms["contractRole"] == "RPA"
    assert terms["contractDealDate"] == "2026-01-01T00:00:00"
    assert terms["purchaseDate"] == "2026-01-01T00:00:00"
    assert terms["statusDate"] == "2026-01-01T00:00:00"
    assert terms["quantity"] == 1_000.0
    assert terms["priceAtPurchaseDate"] == 100.0
    assert terms["notionalPrincipal"] == 100_000.0
    assert terms["terminationDate"] == "2030-12-31T00:00:00"
    assert terms["priceAtTerminationDate"] == 116.985856
    assert terms["contractType"] == "STK"


def test_stk_contract_populates_dividend_group_only_when_yield_positive():
    with_dividend = build_aal_stk_contract(_FakeAALModule, _stk_spec(0.025)).to_dict()
    without_dividend = build_aal_stk_contract(_FakeAALModule, _stk_spec(0.0)).to_dict()

    assert with_dividend["cycleOfDividend"] == "P1YL1"
    assert with_dividend["cycleAnchorDateOfDividend"] == "2027-01-01T00:00:00"
    assert with_dividend["nextDividendPaymentAmount"] == 2_500.0
    assert "cycleOfDividend" not in without_dividend
    assert "cycleAnchorDateOfDividend" not in without_dividend
    assert "nextDividendPaymentAmount" not in without_dividend


def test_csh_contract_maps_minimal_required_terms_with_fake_module():
    csh = build_aal_cash_contract(
        _FakeAALModule,
        CSHSpec("CUSTOM_CSH", 2026, 50_000.0),
    )
    terms = csh.to_dict()
    assert terms == {
        "contractID": "CUSTOM_CSH",
        "contractRole": "RPA",
        "creatorID": "PK_ALM",
        "currency": "CHF",
        "notionalPrincipal": 50_000.0,
        "statusDate": "2026-01-01T00:00:00",
        "contractType": "CSH",
    }


def test_portfolio_wraps_contracts_with_fake_module():
    pam = build_aal_pam_contract(_FakeAALModule)
    portfolio = build_aal_portfolio(_FakeAALModule, [pam])
    assert len(portfolio) == 1
    assert portfolio.to_dict() == [pam.to_dict()]
    assert list(portfolio.contract_df["contractID"]) == [DEFAULT_PAM_CONTRACT_ID]


def test_real_aal_pam_contract_can_be_constructed():
    module = get_aal_module()
    pam = build_aal_pam_contract(module)
    terms = pam.to_dict()
    assert terms["contractID"] == DEFAULT_PAM_CONTRACT_ID
    assert terms["contractType"] == "PAM"
    assert terms["currency"] == DEFAULT_PAM_CURRENCY


def test_real_aal_stk_and_csh_contracts_can_be_constructed():
    module = get_aal_module()
    stk = build_aal_stk_contract(module, _stk_spec())
    csh = build_aal_cash_contract(module, CSHSpec("REAL_CSH", 2026, 50_000.0))
    assert stk.to_dict()["contractID"] == "CUSTOM_STK"
    assert stk.to_dict()["contractType"] == "STK"
    assert csh.to_dict()["contractID"] == "REAL_CSH"
    assert csh.to_dict()["contractType"] == "CSH"


def test_real_aal_portfolio_accepts_pam_contract():
    module = get_aal_module()
    pam = build_aal_pam_contract(module)
    portfolio = build_aal_portfolio(module, [pam])
    assert len(portfolio) == 1
    assert list(portfolio.contract_df["contractID"]) == [DEFAULT_PAM_CONTRACT_ID]


def test_aal_asset_boundary_does_not_change_stage1_baseline_outputs():
    before = run_stage1_baseline(output_dir=None)
    module = get_aal_module()
    pam = build_aal_pam_contract(module)
    build_aal_portfolio(module, [pam])
    after = run_stage1_baseline(output_dir=None)

    pd.testing.assert_frame_equal(
        before.engine_result.cashflows,
        after.engine_result.cashflows,
    )
    pd.testing.assert_frame_equal(before.annual_cashflows, after.annual_cashflows)
    pd.testing.assert_frame_equal(
        before.funding_ratio_trajectory,
        after.funding_ratio_trajectory,
    )
