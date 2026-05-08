"""Tests for ACTUS-native AAL asset portfolio configs."""

import pytest

from pk_alm.actus_asset_engine.aal_asset_portfolio import (
    DEFAULT_AAL_ASSET_CONTRACT_CONFIGS,
    get_default_aal_asset_contract_configs,
    make_csh_contract_config,
    make_pam_contract_config,
    make_stk_contract_config_from_nominal,
    validate_aal_contract_configs,
)
from pk_alm.actus_asset_engine.contract_config import AALContractConfig


class _FakeContract:
    contract_type = "GEN"

    def __init__(self, **terms):
        self.terms = dict(terms)

    def to_dict(self):
        return dict(self.terms)


class _FakePAM(_FakeContract):
    contract_type = "PAM"

    def to_dict(self):
        return {**self.terms, "contractType": "PAM"}


class _FakeSTK(_FakeContract):
    contract_type = "STK"

    def to_dict(self):
        return {**self.terms, "contractType": "STK"}


class _FakeCSH(_FakeContract):
    contract_type = "CSH"

    def to_dict(self):
        return {**self.terms, "contractType": "CSH"}


class _FakePortfolio:
    def __init__(self, contracts):
        self.contracts = list(contracts)

    def __len__(self):
        return len(self.contracts)


class _FakeAALModule:
    PAM = _FakePAM
    STK = _FakeSTK
    CSH = _FakeCSH
    Portfolio = _FakePortfolio


def test_contract_config_requires_core_actus_terms():
    with pytest.raises(ValueError, match="missing required ACTUS terms"):
        AALContractConfig("PAM", {"contractID": "BOND"})


def test_contract_config_normalizes_type_and_exposes_properties():
    config = make_pam_contract_config(
        contract_id="BOND_1",
        start_year=2026,
        maturity_year=2028,
        nominal_value=100_000.0,
        coupon_rate=0.02,
        currency="CHF",
        label="Test bond",
    )

    assert config.contract_type == "PAM"
    assert config.contract_id == "BOND_1"
    assert config.currency == "CHF"
    assert config.status_date.year == 2026
    assert config.label == "Test bond"


def test_default_portfolio_configs_are_explicit_actus_contracts():
    configs = get_default_aal_asset_contract_configs()

    assert configs == DEFAULT_AAL_ASSET_CONTRACT_CONFIGS
    assert all(isinstance(config, AALContractConfig) for config in configs)
    assert sum(config.contract_type == "PAM" for config in configs) == 5
    assert sum(config.contract_type == "STK" for config in configs) == 3
    assert sum(config.contract_type == "CSH" for config in configs) == 1
    assert {config.currency for config in configs} == {"CHF"}

    total_notional = sum(
        float(config.terms.get("notionalPrincipal", 0.0)) for config in configs
    )
    assert total_notional == pytest.approx(5_000_000.0)


def test_default_stk_prices_are_precomputed_from_growth():
    configs = {
        config.contract_id: config
        for config in get_default_aal_asset_contract_configs()
        if config.contract_type == "STK"
    }

    equity = configs["AAL_STK_EQUITY_PROXY"]
    real_estate = configs["AAL_STK_REAL_ESTATE_PROXY"]
    alternatives = configs["AAL_STK_ALTERNATIVES_PROXY"]

    assert equity.terms["quantity"] == pytest.approx(15_500.0)
    assert real_estate.terms["quantity"] == pytest.approx(11_500.0)
    assert alternatives.terms["quantity"] == pytest.approx(5_000.0)
    assert equity.terms["priceAtTerminationDate"] == pytest.approx(100.0 * (1.04**12))
    assert real_estate.terms["priceAtTerminationDate"] == pytest.approx(
        100.0 * (1.02**12)
    )


def test_validation_rejects_empty_duplicate_and_mixed_currency_configs():
    pam = make_pam_contract_config(
        contract_id="DUP",
        start_year=2026,
        maturity_year=2028,
        nominal_value=100_000.0,
        coupon_rate=0.02,
    )
    csh = make_csh_contract_config(
        contract_id="DUP",
        start_year=2026,
        nominal_value=50_000.0,
    )
    eur = make_csh_contract_config(
        contract_id="EUR_CASH",
        start_year=2026,
        nominal_value=10_000.0,
        currency="EUR",
    )

    with pytest.raises(ValueError, match="must not be empty"):
        validate_aal_contract_configs(())
    with pytest.raises(ValueError, match="duplicate contractID"):
        validate_aal_contract_configs((pam, csh))
    with pytest.raises(ValueError, match="mixed currencies"):
        validate_aal_contract_configs((pam, eur))


def test_config_helpers_map_to_actus_terms():
    pam = make_pam_contract_config(
        contract_id="CUSTOM_PAM",
        start_year=2026,
        maturity_year=2029,
        nominal_value=100_000.0,
        coupon_rate=0.015,
    )
    stk = make_stk_contract_config_from_nominal(
        contract_id="CUSTOM_STK",
        start_year=2026,
        divestment_year=2030,
        nominal_value=200_000.0,
        dividend_yield=0.025,
        market_value_growth=0.04,
    )
    csh = make_csh_contract_config(
        contract_id="CUSTOM_CSH",
        start_year=2026,
        nominal_value=50_000.0,
    )

    assert pam.terms["contractDealDate"] == "2026-01-01T00:00:00"
    assert pam.terms["initialExchangeDate"] == "2026-01-01T00:00:00"
    assert pam.terms["maturityDate"] == "2029-12-31T00:00:00"
    assert stk.terms["purchaseDate"] == "2026-01-01T00:00:00"
    assert stk.terms["terminationDate"] == "2030-12-31T00:00:00"
    assert stk.terms["nextDividendPaymentAmount"] == pytest.approx(5_000.0)
    assert csh.terms["notionalPrincipal"] == 50_000.0
