"""Tests for the ACTUS-native AAL Asset Engine."""

import pandas as pd
import pytest

from pk_alm.actus_asset_engine import aal_engine
from pk_alm.actus_asset_engine.aal_asset_portfolio import (
    get_default_aal_asset_contract_configs,
    make_pam_contract_config,
)
from pk_alm.actus_asset_engine.aal_engine import (
    AALAssetEngineResult,
    run_aal_asset_engine,
)
from pk_alm.actus_asset_engine.contract_config import AALContractConfig
from pk_alm.actus_asset_engine.risk_factors import AALRiskFactorSet
from pk_alm.actus_asset_engine.simulation_settings import AALSimulationSettings
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe


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

    def to_dict(self):
        return [contract.to_dict() for contract in self.contracts]


class _FakePublicActusService:
    last_risk_factors = "unset"

    def generateEvents(self, *, portfolio, riskFactors=None):
        type(self).last_risk_factors = riskFactors
        events = []
        for contract in portfolio.contracts:
            terms = contract.to_dict()
            contract_id = terms["contractID"]
            contract_type = terms["contractType"]
            notional = float(terms["notionalPrincipal"])
            if contract_type == "PAM":
                if "initialExchangeDate" in terms:
                    events.append(
                        {
                            "contractId": contract_id,
                            "time": terms["initialExchangeDate"],
                            "type": "IED",
                            "payoff": -notional,
                            "nominalValue": notional,
                            "currency": terms["currency"],
                        }
                    )
                maturity = terms["maturityDate"]
                events.append(
                    {
                        "contractId": contract_id,
                        "time": maturity,
                        "type": "IP",
                        "payoff": notional * float(terms["nominalInterestRate"]),
                        "nominalValue": notional,
                        "currency": terms["currency"],
                    }
                )
                events.append(
                    {
                        "contractId": contract_id,
                        "time": maturity,
                        "type": "MD",
                        "payoff": notional,
                        "nominalValue": 0.0,
                        "currency": terms["currency"],
                    }
                )
            elif contract_type == "STK":
                events.append(
                    {
                        "contractId": contract_id,
                        "time": terms["terminationDate"],
                        "type": "TD",
                        "payoff": terms["quantity"] * terms["priceAtTerminationDate"],
                        "nominalValue": 0.0,
                        "currency": terms["currency"],
                    }
                )
        return events


class _FakeAALModule:
    PAM = _FakePAM
    STK = _FakeSTK
    CSH = _FakeCSH
    Portfolio = _FakePortfolio
    PublicActusService = _FakePublicActusService


class _RiskFactor:
    marketObjectCode = "CHF_LIBOR"

    def to_json(self):
        return {
            "marketObjectCode": self.marketObjectCode,
            "data": [{"time": "2026-01-01", "value": 0.01}],
        }


def _patch_fake_aal(monkeypatch) -> None:
    monkeypatch.setattr(aal_engine, "get_aal_module", lambda: _FakeAALModule)
    monkeypatch.setattr(aal_engine, "_detect_aal_version", lambda: "fake-1.0")
    _FakePublicActusService.last_risk_factors = "unset"


def _settings(
    *,
    start: str = "2026-01-01T00:00:00",
    end: str = "2038-12-31T00:00:00",
    cutoff: str = "from_status_date",
) -> AALSimulationSettings:
    return AALSimulationSettings(
        analysis_date=start,
        event_start_date=start,
        event_end_date=end,
        cashflow_cutoff_mode=cutoff,  # type: ignore[arg-type]
    )


def _current_bond() -> tuple[AALContractConfig, ...]:
    return (
        make_pam_contract_config(
            contract_id="ENGINE_PAM_1",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        ),
    )


def _existing_bond() -> tuple[AALContractConfig, ...]:
    terms = dict(_current_bond()[0].terms)
    terms.update(
        {
            "contractDealDate": "2021-01-01T00:00:00",
            "initialExchangeDate": "2021-01-01T00:00:00",
            "statusDate": "2026-01-01T00:00:00",
        }
    )
    return (AALContractConfig("PAM", terms),)


def test_engine_returns_expanded_result_and_schema_valid_cashflows(monkeypatch):
    _patch_fake_aal(monkeypatch)

    result = run_aal_asset_engine(
        contracts=_current_bond(),
        settings=_settings(end="2029-12-31T00:00:00"),
    )

    assert isinstance(result, AALAssetEngineResult)
    assert validate_cashflow_dataframe(result.cashflows) is True
    assert list(result.cashflows.columns) == list(CASHFLOW_COLUMNS)
    assert result.aal_version == "fake-1.0"
    assert result.generation_mode == "aal"
    assert not result.event_summary.empty
    assert not result.event_coverage_report.empty
    assert result.risk_factor_report.empty
    assert isinstance(result.limitation_report, pd.DataFrame)


def test_engine_uses_default_contract_configs_when_contracts_none(monkeypatch):
    _patch_fake_aal(monkeypatch)

    result = run_aal_asset_engine(settings=_settings())

    assert result.contracts == tuple(get_default_aal_asset_contract_configs())


def test_engine_passes_risk_factors_to_public_actus_service(monkeypatch):
    _patch_fake_aal(monkeypatch)
    risk_factor = _RiskFactor()

    result = run_aal_asset_engine(
        contracts=_current_bond(),
        risk_factors=AALRiskFactorSet((risk_factor,)),
        settings=_settings(end="2029-12-31T00:00:00"),
    )

    assert _FakePublicActusService.last_risk_factors == (risk_factor,)
    assert result.risk_factor_report.iloc[0]["marketObjectCode"] == "CHF_LIBOR"


def test_engine_passes_none_when_no_risk_factors(monkeypatch):
    _patch_fake_aal(monkeypatch)

    run_aal_asset_engine(
        contracts=_current_bond(),
        settings=_settings(end="2029-12-31T00:00:00"),
    )

    assert _FakePublicActusService.last_risk_factors is None


def test_existing_bond_excludes_historical_initial_exchange_by_default(monkeypatch):
    _patch_fake_aal(monkeypatch)

    result = run_aal_asset_engine(
        contracts=_existing_bond(),
        settings=_settings(end="2029-12-31T00:00:00"),
    )

    assert set(result.cashflows["type"]) == {"IP", "MD"}
    assert result.cashflows["time"].min() >= pd.Timestamp("2026-01-01")


def test_new_purchase_keeps_initial_exchange_on_status_date(monkeypatch):
    _patch_fake_aal(monkeypatch)

    result = run_aal_asset_engine(
        contracts=_current_bond(),
        settings=_settings(end="2029-12-31T00:00:00"),
    )

    assert "IED" in set(result.cashflows["type"])
    ied = result.cashflows.loc[result.cashflows["type"].eq("IED")].iloc[0]
    assert ied["time"] == pd.Timestamp("2026-01-01")


def test_all_events_keeps_historical_events_but_applies_end_date(monkeypatch):
    _patch_fake_aal(monkeypatch)

    result = run_aal_asset_engine(
        contracts=_existing_bond(),
        settings=_settings(end="2026-12-31T00:00:00", cutoff="all_events"),
    )

    assert set(result.cashflows["type"]) == {"IED"}
    assert result.cashflows.iloc[0]["time"] == pd.Timestamp("2021-01-01")


def test_engine_rejects_invalid_risk_factor(monkeypatch):
    _patch_fake_aal(monkeypatch)

    with pytest.raises(ValueError, match="marketObjectCode"):
        run_aal_asset_engine(
            contracts=_current_bond(),
            risk_factors=(object(),),
            settings=_settings(),
        )


def test_engine_wraps_service_failures(monkeypatch):
    class _BadService:
        def generateEvents(self, *, portfolio, riskFactors=None):
            raise RuntimeError("service down")

    class _BadModule(_FakeAALModule):
        PublicActusService = _BadService

    monkeypatch.setattr(aal_engine, "get_aal_module", lambda: _BadModule)

    with pytest.raises(RuntimeError, match="PublicActusService failed"):
        run_aal_asset_engine(contracts=_current_bond(), settings=_settings())
