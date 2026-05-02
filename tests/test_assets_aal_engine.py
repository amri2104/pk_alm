"""Tests for the required live-path AAL Asset Engine."""

import os
from pathlib import Path

import pandas as pd
import pytest

from pk_alm.adapters.aal_asset_portfolio import (
    AALAssetContractSpec,
    CSHSpec,
    DEFAULT_AAL_ASSET_CONTRACT_SPECS,
    PAMSpec,
    STKSpec,
    get_default_aal_asset_contract_specs,
)
from pk_alm.adapters.actus_adapter import aal_events_to_cashflow_dataframe
from pk_alm.assets import aal_engine
from pk_alm.assets.aal_engine import AALAssetEngineResult, run_aal_asset_engine
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline

_OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "stage1_baseline"


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


class _FakePublicActusService:
    serverURL = "https://example.invalid"

    def generateEvents(self, *, portfolio):
        events = []
        for contract in portfolio.contracts:
            terms = contract.to_dict()
            contract_id = terms["contractID"]
            contract_type = terms["contractType"]
            notional = float(terms["notionalPrincipal"])
            if contract_type == "PAM":
                coupon_rate = float(terms["nominalInterestRate"])
                maturity = terms["maturityDate"]
                events.append(
                    {
                        "contractId": contract_id,
                        "time": maturity,
                        "type": "IP",
                        "payoff": notional * coupon_rate,
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


def _custom_specs() -> tuple[AALAssetContractSpec, ...]:
    return (
        PAMSpec(
            contract_id="ENGINE_PAM_1",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        ),
    )


def _mixed_specs() -> tuple[AALAssetContractSpec, ...]:
    return (
        PAMSpec("ENGINE_PAM_1", 2026, 2028, 100_000.0, 0.02),
        STKSpec(
            "ENGINE_STK_1",
            2026,
            2030,
            quantity=1_000.0,
            price_at_purchase=100.0,
            price_at_termination=116.985856,
            dividend_yield=0.025,
            market_value_growth=0.04,
        ),
        CSHSpec(
            "ENGINE_CSH_1",
            2026,
            50_000.0,
            assumed_return=0.01,
        ),
    )


def _patch_fake_aal(monkeypatch) -> None:
    monkeypatch.setattr(aal_engine, "get_aal_module", lambda: _FakeAALModule)
    monkeypatch.setattr(aal_engine, "_detect_aal_version", lambda: "fake-1.0")


def test_engine_returns_schema_valid_cashflows(monkeypatch):
    _patch_fake_aal(monkeypatch)
    result = run_aal_asset_engine()
    assert isinstance(result, AALAssetEngineResult)
    assert validate_cashflow_dataframe(result.cashflows) is True
    assert list(result.cashflows.columns) == list(CASHFLOW_COLUMNS)


def test_result_records_required_live_aal_path(monkeypatch):
    _patch_fake_aal(monkeypatch)
    result = run_aal_asset_engine()
    assert result.generation_mode == "aal"
    assert result.aal_available is True
    assert result.aal_version == "fake-1.0"
    assert "PublicActusService" in " | ".join(result.notes)


def test_engine_uses_default_specs_when_specs_none(monkeypatch):
    _patch_fake_aal(monkeypatch)
    result = run_aal_asset_engine()
    assert result.contracts == tuple(DEFAULT_AAL_ASSET_CONTRACT_SPECS)


def test_engine_accepts_custom_specs(monkeypatch):
    _patch_fake_aal(monkeypatch)
    specs = _custom_specs()
    result = run_aal_asset_engine(specs=specs)
    assert result.contracts == specs
    assert set(result.cashflows["contractId"]) == {"ENGINE_PAM_1"}


def test_engine_dispatches_mixed_specs_and_synthesizes_proxy_cashflows(monkeypatch):
    _patch_fake_aal(monkeypatch)
    result = run_aal_asset_engine(specs=_mixed_specs(), horizon_years=3)

    sources = set(result.cashflows["source"])
    assert sources == {"ACTUS", "ACTUS_PROXY"}
    assert set(result.cashflows.loc[result.cashflows["source"] == "ACTUS", "type"]) == {
        "IP",
        "MD",
        "TD",
    }
    proxy = result.cashflows[result.cashflows["source"] == "ACTUS_PROXY"]
    assert set(proxy["type"]) == {"DV", "IP"}
    assert len(proxy[proxy["type"] == "DV"]) == 4
    assert len(proxy[proxy["contractId"] == "ENGINE_CSH_1"]) == 3
    first_dv = proxy[
        (proxy["contractId"] == "ENGINE_STK_1") & (proxy["type"] == "DV")
    ].iloc[0]
    assert first_dv["time"] == pd.Timestamp("2027-01-01T00:00:00")
    assert first_dv["payoff"] == pytest.approx(0.025 * 100_000.0 * 1.04)
    assert "Processed specs: 1 PAM, 1 STK, 1 CSH" in " | ".join(result.notes)
    assert "ACTUS_PROXY events: 7" in " | ".join(result.notes)


def test_engine_rejects_empty_specs(monkeypatch):
    _patch_fake_aal(monkeypatch)
    with pytest.raises(ValueError):
        run_aal_asset_engine(specs=[])


def test_engine_rejects_non_spec_items(monkeypatch):
    _patch_fake_aal(monkeypatch)
    with pytest.raises(TypeError):
        run_aal_asset_engine(specs=[{"contract_id": "BAD"}])  # type: ignore[list-item]


def test_engine_wraps_contract_construction_failures(monkeypatch):
    class _BadModule(_FakeAALModule):
        class PAM:  # noqa: N801
            def __init__(self, **terms):
                raise ValueError("bad pam")

    monkeypatch.setattr(aal_engine, "get_aal_module", lambda: _BadModule)
    with pytest.raises(RuntimeError, match="AAL contract or Portfolio construction"):
        run_aal_asset_engine(specs=_custom_specs())


def test_engine_wraps_service_failures(monkeypatch):
    class _BadService:
        def generateEvents(self, *, portfolio):
            raise RuntimeError("service down")

    class _BadServiceModule(_FakeAALModule):
        PublicActusService = _BadService

    monkeypatch.setattr(aal_engine, "get_aal_module", lambda: _BadServiceModule)
    with pytest.raises(RuntimeError, match="PublicActusService failed"):
        run_aal_asset_engine(specs=_custom_specs())


def test_engine_wraps_mapping_failures(monkeypatch):
    class _BadMappingService:
        def generateEvents(self, *, portfolio):
            return [{"contractID": "BROKEN"}]

    class _BadMappingModule(_FakeAALModule):
        PublicActusService = _BadMappingService

    monkeypatch.setattr(aal_engine, "get_aal_module", lambda: _BadMappingModule)
    with pytest.raises(RuntimeError, match="event mapping"):
        run_aal_asset_engine(specs=_custom_specs())


def test_engine_raises_if_server_and_proxy_both_emit_stk_dv(monkeypatch):
    class _DividendService:
        def generateEvents(self, *, portfolio):
            return [
                {
                    "contractId": "ENGINE_STK_1",
                    "time": "2027-01-01T00:00:00",
                    "type": "DV",
                    "payoff": 1_000.0,
                    "nominalValue": 100_000.0,
                    "currency": "CHF",
                }
            ]

    class _DividendModule(_FakeAALModule):
        PublicActusService = _DividendService

    monkeypatch.setattr(aal_engine, "get_aal_module", lambda: _DividendModule)
    with pytest.raises(RuntimeError, match="double-counting guard"):
        run_aal_asset_engine(specs=_mixed_specs())


def test_synthetic_aal_dict_event_maps_to_schema():
    event = {
        "contractID": "BOND_X",
        "eventDate": "2027-12-31",
        "eventType": "IP",
        "payoff": 2000.0,
        "nominalValue": 100000.0,
        "currency": "CHF",
    }
    df = aal_events_to_cashflow_dataframe(event)
    assert validate_cashflow_dataframe(df) is True
    assert len(df) == 1
    assert df.iloc[0]["contractId"] == "BOND_X"
    assert df.iloc[0]["type"] == "IP"
    assert df.iloc[0]["payoff"] == pytest.approx(2000.0)
    assert df.iloc[0]["source"] == "ACTUS"


def test_synthetic_aal_list_of_dicts_maps_to_schema():
    events = [
        {
            "contractID": "B1",
            "eventDate": "2027-12-31",
            "eventType": "IP",
            "payoff": 1500.0,
        },
        {
            "contractID": "B1",
            "eventDate": "2028-12-31",
            "eventType": "MD",
            "payoff": 75000.0,
        },
    ]
    df = aal_events_to_cashflow_dataframe(events)
    assert validate_cashflow_dataframe(df) is True
    assert len(df) == 2
    assert (df["source"] == "ACTUS").all()


def test_synthetic_aal_dataframe_camelcase_keys_maps_to_schema():
    df_in = pd.DataFrame(
        [
            {
                "contractID": "B2",
                "eventDate": "2027-12-31",
                "eventType": "IP",
                "payoff": 1000.0,
                "nominalValue": 50000.0,
                "currency": "CHF",
            }
        ]
    )
    df = aal_events_to_cashflow_dataframe(df_in)
    assert validate_cashflow_dataframe(df) is True
    assert df.iloc[0]["contractId"] == "B2"
    assert df.iloc[0]["nominalValue"] == pytest.approx(50000.0)


def test_synthetic_aal_dataframe_snakecase_keys_maps_to_schema():
    df_in = pd.DataFrame(
        [
            {
                "contract_id": "B3",
                "event_date": "2027-12-31",
                "event_type": "IP",
                "payoff": 500.0,
            }
        ]
    )
    df = aal_events_to_cashflow_dataframe(df_in)
    assert validate_cashflow_dataframe(df) is True
    assert df.iloc[0]["contractId"] == "B3"
    assert df.iloc[0]["currency"] == "CHF"
    assert df.iloc[0]["nominalValue"] == pytest.approx(0.0)


def test_aal_events_mapper_extracts_events_df_attribute():
    class _Wrapper:
        def __init__(self, df):
            self.events_df = df

    wrapper = _Wrapper(
        pd.DataFrame(
            [
                {
                    "contractID": "B4",
                    "eventDate": "2027-12-31",
                    "eventType": "IP",
                    "payoff": 100.0,
                }
            ]
        )
    )
    df = aal_events_to_cashflow_dataframe(wrapper)
    assert validate_cashflow_dataframe(df) is True
    assert df.iloc[0]["contractId"] == "B4"


def test_aal_events_mapper_rejects_unknown_shape():
    with pytest.raises(TypeError):
        aal_events_to_cashflow_dataframe(42)


def test_aal_events_mapper_rejects_event_with_missing_required_keys():
    with pytest.raises(ValueError):
        aal_events_to_cashflow_dataframe(
            {"contractID": "B5", "eventDate": "2027-12-31", "eventType": "IP"}
        )


def test_aal_events_mapper_rejects_non_dict_inside_list():
    with pytest.raises(TypeError):
        aal_events_to_cashflow_dataframe([42])


def test_aal_events_mapper_default_currency_can_be_overridden():
    df = aal_events_to_cashflow_dataframe(
        {
            "contractID": "B6",
            "eventDate": "2027-12-31",
            "eventType": "IP",
            "payoff": 100.0,
        },
        default_currency="USD",
    )
    assert df.iloc[0]["currency"] == "USD"


def _good_result_kwargs(monkeypatch) -> dict:
    _patch_fake_aal(monkeypatch)
    result = run_aal_asset_engine(specs=_custom_specs())
    return {
        "cashflows": result.cashflows,
        "contracts": result.contracts,
        "aal_version": result.aal_version,
        "notes": result.notes,
    }


def test_result_dataclass_rejects_non_asset_source_rows(monkeypatch):
    kwargs = _good_result_kwargs(monkeypatch)
    bad = kwargs["cashflows"].copy()
    bad.loc[0, "source"] = "BVG"
    kwargs["cashflows"] = bad
    with pytest.raises(ValueError):
        AALAssetEngineResult(**kwargs)


def test_result_dataclass_accepts_actus_proxy_source_rows(monkeypatch):
    kwargs = _good_result_kwargs(monkeypatch)
    proxy = kwargs["cashflows"].copy()
    proxy.loc[0, "source"] = "ACTUS_PROXY"
    kwargs["cashflows"] = proxy
    assert AALAssetEngineResult(**kwargs).cashflows.iloc[0]["source"] == "ACTUS_PROXY"


def test_result_dataclass_rejects_invalid_fixed_generation_mode(monkeypatch):
    kwargs = _good_result_kwargs(monkeypatch)
    kwargs["generation_mode"] = "fallback"
    with pytest.raises(ValueError):
        AALAssetEngineResult(**kwargs)


def test_result_dataclass_rejects_false_aal_available(monkeypatch):
    kwargs = _good_result_kwargs(monkeypatch)
    kwargs["aal_available"] = False
    with pytest.raises(ValueError):
        AALAssetEngineResult(**kwargs)


def test_result_dataclass_rejects_non_dataframe_cashflows(monkeypatch):
    kwargs = _good_result_kwargs(monkeypatch)
    kwargs["cashflows"] = "not a dataframe"
    with pytest.raises(TypeError):
        AALAssetEngineResult(**kwargs)


def test_engine_does_not_modify_stage1_baseline_outputs(monkeypatch):
    _patch_fake_aal(monkeypatch)
    before = run_stage1_baseline(output_dir=None)
    run_aal_asset_engine(specs=_custom_specs())
    after = run_stage1_baseline(output_dir=None)
    pd.testing.assert_frame_equal(before.engine_result.cashflows, after.engine_result.cashflows)
    pd.testing.assert_frame_equal(before.annual_cashflows, after.annual_cashflows)
    pd.testing.assert_frame_equal(
        before.funding_ratio_trajectory,
        after.funding_ratio_trajectory,
    )


def test_stage1_output_csv_files_not_modified_by_engine(monkeypatch):
    _patch_fake_aal(monkeypatch)
    if not _OUTPUTS_DIR.exists():
        pytest.skip("outputs/stage1_baseline/ does not exist")
    csv_files = list(_OUTPUTS_DIR.glob("*.csv"))
    assert csv_files, "expected CSV files in outputs/stage1_baseline/"

    mtimes_before = {f: os.path.getmtime(f) for f in csv_files}
    run_aal_asset_engine(specs=_custom_specs())
    mtimes_after = {f: os.path.getmtime(f) for f in csv_files}
    assert mtimes_before == mtimes_after


def test_required_aal_default_specs_can_run_against_live_service():
    result = run_aal_asset_engine(specs=tuple(get_default_aal_asset_contract_specs()))
    assert result.generation_mode == "aal"
    assert result.aal_available is True
    assert validate_cashflow_dataframe(result.cashflows) is True
    assert set(result.cashflows["source"]).issubset({"ACTUS", "ACTUS_PROXY"})
    assert "ACTUS_PROXY" in set(result.cashflows["source"])
