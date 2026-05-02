"""Tests for AAL/ACTUS asset portfolio specs and builders."""

import math

import pandas as pd
import pytest

from pk_alm.adapters.aal_asset_portfolio import (
    AALAssetContractSpec,
    CSHSpec,
    DEFAULT_AAL_ASSET_CONTRACT_SPECS,
    PAMSpec,
    STKSpec,
    build_aal_cash_contracts_from_specs,
    build_aal_pam_contracts_from_specs,
    build_aal_portfolio_from_specs,
    build_aal_stk_contracts_from_specs,
    get_default_aal_asset_contract_specs,
    validate_aal_asset_contract_specs,
)
from pk_alm.adapters.aal_probe import get_aal_module
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

    def __len__(self):
        return len(self.contracts)

    def to_dict(self):
        return [contract.to_dict() for contract in self.contracts]


class _FakeAALModule:
    PAM = _FakePAM
    STK = _FakeSTK
    CSH = _FakeCSH
    Portfolio = _FakePortfolio


def _custom_specs():
    return (
        PAMSpec(
            contract_id="CUSTOM_PAM_1",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
            currency="CHF",
        ),
        STKSpec(
            contract_id="CUSTOM_STK_1",
            start_year=2026,
            divestment_year=2030,
            quantity=1_000.0,
            price_at_purchase=100.0,
            price_at_termination=116.985856,
            currency="CHF",
            dividend_yield=0.025,
            market_value_growth=0.04,
        ),
        CSHSpec(
            contract_id="CUSTOM_CSH_1",
            start_year=2026,
            nominal_value=50_000.0,
            currency="CHF",
        ),
    )


def test_compatibility_base_is_not_instantiable():
    with pytest.raises(TypeError):
        AALAssetContractSpec()


def test_default_portfolio_specs_are_non_empty_and_use_new_spec_types():
    specs = get_default_aal_asset_contract_specs()
    assert specs
    assert specs == DEFAULT_AAL_ASSET_CONTRACT_SPECS
    assert all(isinstance(spec, AALAssetContractSpec) for spec in specs)
    assert sum(isinstance(spec, PAMSpec) for spec in specs) == 5
    assert sum(isinstance(spec, STKSpec) for spec in specs) == 3
    assert sum(isinstance(spec, CSHSpec) for spec in specs) == 1


def test_default_portfolio_specs_have_unique_ids_one_currency_and_five_million_total():
    specs = get_default_aal_asset_contract_specs()
    contract_ids = [spec.contract_id for spec in specs]
    assert len(contract_ids) == len(set(contract_ids))
    assert {spec.currency for spec in specs} == {"CHF"}
    total_exposure = sum(spec.nominal_value for spec in specs)
    assert total_exposure == pytest.approx(5_000_000.0)


def test_default_stk_quantities_and_terminal_prices_are_precomputed():
    specs = {
        spec.contract_id: spec
        for spec in get_default_aal_asset_contract_specs()
        if isinstance(spec, STKSpec)
    }
    equity = specs["AAL_STK_EQUITY_PROXY"]
    real_estate = specs["AAL_STK_REAL_ESTATE_PROXY"]
    alternatives = specs["AAL_STK_ALTERNATIVES_PROXY"]

    assert equity.quantity == pytest.approx(15_500.0)
    assert real_estate.quantity == pytest.approx(11_500.0)
    assert alternatives.quantity == pytest.approx(5_000.0)
    assert equity.price_at_termination == pytest.approx(100.0 * (1.04**12))
    assert real_estate.price_at_termination == pytest.approx(100.0 * (1.02**12))
    assert alternatives.price_at_termination == pytest.approx(100.0 * (1.03**12))


def test_contract_type_properties():
    pam, stk, csh = _custom_specs()
    assert pam.contract_type == "PAM"
    assert stk.contract_type == "STK"
    assert csh.contract_type == "CSH"


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_invalid_contract_id_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        PAMSpec(
            contract_id=bad,
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        )


@pytest.mark.parametrize("bad", [True, None, "2026", 1.5])
def test_invalid_start_year_type_rejected(bad):
    with pytest.raises(TypeError):
        PAMSpec("BAD", bad, 2028, 100_000.0, 0.02)


@pytest.mark.parametrize("maturity_year", [2025, 2026])
def test_pam_maturity_year_must_be_after_start_year(maturity_year):
    with pytest.raises(ValueError):
        PAMSpec("BAD", 2026, maturity_year, 100_000.0, 0.02)


@pytest.mark.parametrize("bad", [False, None, "2028", 1.5])
def test_invalid_maturity_year_type_rejected(bad):
    with pytest.raises(TypeError):
        PAMSpec("BAD", 2026, bad, 100_000.0, 0.02)


@pytest.mark.parametrize("bad", [True, None, "100000", math.nan, 0.0, -1.0])
def test_invalid_nominal_value_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        PAMSpec("BAD", 2026, 2028, bad, 0.02)


@pytest.mark.parametrize("bad", [False, None, "0.02", math.nan, -0.01])
def test_invalid_coupon_rate_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        PAMSpec("BAD", 2026, 2028, 100_000.0, bad)


@pytest.mark.parametrize("bad", ["", "   ", None, 123, "chf", "CH", "CH1"])
def test_invalid_currency_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        PAMSpec("BAD", 2026, 2028, 100_000.0, 0.02, currency=bad)


def test_stk_validation_and_nominal_value_property():
    spec = STKSpec(
        "STK",
        2026,
        2030,
        quantity=1_500.0,
        price_at_purchase=100.0,
        price_at_termination=120.0,
        dividend_yield=0.02,
        market_value_growth=0.03,
    )
    assert spec.nominal_value == pytest.approx(150_000.0)


@pytest.mark.parametrize("divestment_year", [2025, 2026])
def test_stk_divestment_year_must_be_after_start_year(divestment_year):
    with pytest.raises(ValueError):
        STKSpec("BAD", 2026, divestment_year, 1.0, 100.0, 100.0)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("quantity", 0.0),
        ("quantity", -1.0),
        ("price_at_purchase", 0.0),
        ("price_at_purchase", -1.0),
        ("price_at_termination", 0.0),
        ("price_at_termination", -1.0),
        ("dividend_yield", -0.01),
        ("market_value_growth", -1.0),
        ("market_value_growth", math.nan),
    ],
)
def test_invalid_stk_numeric_fields_rejected(field, bad):
    kwargs = {
        "contract_id": "BAD",
        "start_year": 2026,
        "divestment_year": 2030,
        "quantity": 1_000.0,
        "price_at_purchase": 100.0,
        "price_at_termination": 110.0,
        "dividend_yield": 0.0,
        "market_value_growth": 0.02,
    }
    kwargs[field] = bad
    with pytest.raises((TypeError, ValueError)):
        STKSpec(**kwargs)


@pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, "1000"])
def test_invalid_csh_nominal_value_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        CSHSpec("BAD", 2026, bad)


@pytest.mark.parametrize("bad", [-0.01, math.nan, "0.01"])
def test_invalid_csh_assumed_return_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        CSHSpec("BAD", 2026, 100_000.0, assumed_return=bad)


def test_empty_portfolio_specs_rejected():
    with pytest.raises(ValueError):
        validate_aal_asset_contract_specs(())


def test_non_spec_item_rejected():
    with pytest.raises(TypeError):
        validate_aal_asset_contract_specs([_custom_specs()[0], "not a spec"])


def test_duplicate_contract_ids_rejected_across_types():
    with pytest.raises(ValueError):
        validate_aal_asset_contract_specs(
            [
                PAMSpec("DUP", 2026, 2028, 100_000.0, 0.02),
                CSHSpec("DUP", 2026, 50_000.0),
            ]
        )


def test_mixed_currency_rejected_for_stage1_portfolio_analytics():
    with pytest.raises(ValueError):
        validate_aal_asset_contract_specs(
            [
                PAMSpec("CHF_PAM", 2026, 2028, 100_000.0, 0.02),
                CSHSpec("EUR_CSH", 2026, 50_000.0, currency="EUR"),
            ]
        )


def test_pam_terms_are_mapped_from_specs_with_fake_module():
    contracts = build_aal_pam_contracts_from_specs(_FakeAALModule, _custom_specs())
    terms = [contract.to_dict() for contract in contracts]

    assert len(terms) == 1
    assert terms[0]["contractID"] == "CUSTOM_PAM_1"
    assert terms[0]["contractDealDate"] == "2026-01-01T00:00:00"
    assert terms[0]["initialExchangeDate"] == "2026-01-01T00:00:00"
    assert terms[0]["statusDate"] == "2026-01-01T00:00:00"
    assert terms[0]["maturityDate"] == "2028-12-31T00:00:00"
    assert terms[0]["notionalPrincipal"] == 100_000.0
    assert terms[0]["nominalInterestRate"] == 0.02
    assert terms[0]["cycleOfInterestPayment"] == "P1YL1"
    assert terms[0]["cycleAnchorDateOfInterestPayment"] == "2027-01-01T00:00:00"
    assert terms[0]["currency"] == "CHF"


def test_stk_and_cash_contracts_are_mapped_from_specs_with_fake_module():
    stk_contracts = build_aal_stk_contracts_from_specs(_FakeAALModule, _custom_specs())
    cash_contracts = build_aal_cash_contracts_from_specs(_FakeAALModule, _custom_specs())

    stk_terms = stk_contracts[0].to_dict()
    cash_terms = cash_contracts[0].to_dict()

    assert stk_terms["contractID"] == "CUSTOM_STK_1"
    assert stk_terms["contractType"] == "STK"
    assert stk_terms["terminationDate"] == "2030-12-31T00:00:00"
    assert stk_terms["priceAtTerminationDate"] == pytest.approx(116.985856)
    assert stk_terms["cycleOfDividend"] == "P1YL1"
    assert cash_terms["contractID"] == "CUSTOM_CSH_1"
    assert cash_terms["contractType"] == "CSH"
    assert cash_terms["notionalPrincipal"] == 50_000.0


def test_aal_portfolio_can_be_constructed_with_fake_module_from_pam_subset():
    portfolio = build_aal_portfolio_from_specs(_FakeAALModule, _custom_specs())
    assert len(portfolio) == 3
    assert [term["contractID"] for term in portfolio.to_dict()] == [
        "CUSTOM_PAM_1",
        "CUSTOM_STK_1",
        "CUSTOM_CSH_1",
    ]


def test_real_aal_contracts_can_be_constructed_from_specs():
    module = get_aal_module()
    specs = _custom_specs()
    pam_contracts = build_aal_pam_contracts_from_specs(module, specs)
    stk_contracts = build_aal_stk_contracts_from_specs(module, specs)
    cash_contracts = build_aal_cash_contracts_from_specs(module, specs)
    assert [contract.to_dict()["contractID"] for contract in pam_contracts] == [
        "CUSTOM_PAM_1",
    ]
    assert [contract.to_dict()["contractID"] for contract in stk_contracts] == [
        "CUSTOM_STK_1",
    ]
    assert [contract.to_dict()["contractID"] for contract in cash_contracts] == [
        "CUSTOM_CSH_1",
    ]


def test_real_aal_portfolio_can_be_constructed_from_pam_subset():
    module = get_aal_module()
    portfolio = build_aal_portfolio_from_specs(module, _custom_specs())
    assert len(portfolio) == 3


def test_stage1_baseline_unchanged_by_portfolio_construction():
    before = run_stage1_baseline(output_dir=None)
    module = get_aal_module()
    build_aal_portfolio_from_specs(module, _custom_specs())
    after = run_stage1_baseline(output_dir=None)

    assert before.engine_result.portfolio_states == after.engine_result.portfolio_states
    pd.testing.assert_frame_equal(before.engine_result.cashflows, after.engine_result.cashflows)
    pd.testing.assert_frame_equal(before.annual_cashflows, after.annual_cashflows)
