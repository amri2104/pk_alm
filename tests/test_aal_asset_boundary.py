"""Tests for the generic AAL construction boundary."""

import pytest

from pk_alm.actus_asset_engine.aal_asset_boundary import (
    build_aal_contract,
    build_aal_contracts,
    build_aal_portfolio,
    build_aal_portfolio_from_configs,
)
from pk_alm.actus_asset_engine.aal_asset_portfolio import (
    make_csh_contract_config,
    make_pam_contract_config,
    make_stk_contract_config_from_nominal,
)


class _FakePAM:
    def __init__(self, **terms):
        self.terms = dict(terms)


class _FakeSTK:
    def __init__(self, **terms):
        self.terms = dict(terms)


class _FakeCSH:
    def __init__(self, **terms):
        self.terms = dict(terms)


class _FakePortfolio:
    def __init__(self, contracts):
        self.contracts = list(contracts)

    def __len__(self):
        return len(self.contracts)


class _FakeModule:
    PAM = _FakePAM
    STK = _FakeSTK
    CSH = _FakeCSH
    Portfolio = _FakePortfolio


def _configs():
    return (
        make_pam_contract_config(
            contract_id="PAM_1",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        ),
        make_stk_contract_config_from_nominal(
            contract_id="STK_1",
            start_year=2026,
            divestment_year=2030,
            nominal_value=200_000.0,
            dividend_yield=0.025,
            market_value_growth=0.04,
        ),
        make_csh_contract_config(
            contract_id="CSH_1",
            start_year=2026,
            nominal_value=50_000.0,
        ),
    )


def test_build_aal_contract_maps_config_type_to_module_class():
    config = _configs()[0]
    contract = build_aal_contract(_FakeModule, config)

    assert isinstance(contract, _FakePAM)
    assert contract.terms["contractID"] == "PAM_1"
    assert contract.terms["notionalPrincipal"] == 100_000.0


def test_build_aal_contracts_preserves_config_order():
    contracts = build_aal_contracts(_FakeModule, _configs())

    assert [type(contract) for contract in contracts] == [_FakePAM, _FakeSTK, _FakeCSH]


def test_build_aal_portfolio_wraps_existing_contract_objects():
    contracts = [object(), object()]
    portfolio = build_aal_portfolio(_FakeModule, contracts)

    assert len(portfolio) == 2
    assert portfolio.contracts == contracts


def test_build_aal_portfolio_from_configs_constructs_all_contracts():
    portfolio = build_aal_portfolio_from_configs(_FakeModule, _configs())

    assert len(portfolio) == 3
    assert [type(contract) for contract in portfolio.contracts] == [
        _FakePAM,
        _FakeSTK,
        _FakeCSH,
    ]


def test_unknown_contract_type_is_rejected():
    config = make_csh_contract_config(
        contract_id="CSH_BAD",
        start_year=2026,
        nominal_value=50_000.0,
    )
    hacked = type(config)(
        contract_type="XYZ",
        terms=dict(config.terms),
    )

    with pytest.raises(ValueError, match="no contract class"):
        build_aal_contract(_FakeModule, hacked)
