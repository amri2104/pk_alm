import inspect

from pk_alm.actus_asset_engine.aal_probe import get_aal_module


def _minimal_pam_terms() -> dict:
    return {
        "contractDealDate": "2026-01-01T00:00:00",
        "contractID": "AAL_PAM_1",
        "contractRole": "RPA",
        "counterpartyID": "COUNTERPARTY_1",
        "creatorID": "PK_ALM",
        "currency": "CHF",
        "dayCountConvention": "30E360",
        "initialExchangeDate": "2026-01-01T00:00:00",
        "maturityDate": "2028-12-31T00:00:00",
        "nominalInterestRate": 0.02,
        "notionalPrincipal": 100000.0,
        "statusDate": "2026-01-01T00:00:00",
    }


def _minimal_pam_contract(module):
    return module.PAM(**_minimal_pam_terms())


def test_real_aal_module_is_loaded_through_gateway():
    module = get_aal_module()
    assert get_aal_module() is module


def test_real_aal_pam_contract_can_be_constructed():
    module = get_aal_module()

    contract = _minimal_pam_contract(module)
    contract_terms = contract.to_dict()

    assert contract_terms["contractID"] == "AAL_PAM_1"
    assert contract_terms["contractType"] == "PAM"
    assert contract_terms["currency"] == "CHF"
    assert contract_terms["nominalInterestRate"] == "0.02"
    assert contract_terms["notionalPrincipal"] == "100000.0"


def test_real_aal_portfolio_accepts_pam_contract():
    module = get_aal_module()
    contract = _minimal_pam_contract(module)

    portfolio = module.Portfolio([contract])

    assert len(portfolio) == 1
    assert portfolio.to_dict() == [contract.to_dict()]
    assert list(portfolio.contract_df["contractID"]) == ["AAL_PAM_1"]
    assert list(portfolio.contract_df["contractType"]) == ["PAM"]


def test_real_aal_event_generation_api_is_service_backed():
    module = get_aal_module()

    service = module.PublicActusService()
    signature = inspect.signature(service.generateEvents)

    assert hasattr(service, "serverURL")
    assert "/eventsBatch" in inspect.getsource(service.generateEvents)
    assert "portfolio" in signature.parameters
