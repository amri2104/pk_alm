"""Tests for the AAL/ACTUS asset portfolio helpers (Sprint 7A.3)."""

import math

import pandas as pd
import pytest

from pk_alm.adapters.aal_asset_boundary import probe_aal_asset_boundary
from pk_alm.adapters.aal_asset_portfolio import (
    AALAssetContractSpec,
    DEFAULT_AAL_ASSET_CONTRACT_SPECS,
    build_aal_asset_portfolio_fallback_cashflows,
    build_aal_pam_contracts_from_specs,
    build_aal_portfolio_from_specs,
    get_default_aal_asset_contract_specs,
    validate_aal_asset_contract_specs,
)
from pk_alm.adapters.actus_fixtures import build_fixed_rate_bond_cashflow_dataframe
from pk_alm.analytics.cashflows import summarize_cashflows_by_year
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline


class _FakePAM:
    def __init__(self, **terms):
        self.terms = dict(terms)

    def to_dict(self):
        return {**self.terms, "contractType": "PAM"}


class _FakePortfolio:
    def __init__(self, contracts):
        self.contracts = list(contracts)

    def __len__(self):
        return len(self.contracts)

    def to_dict(self):
        return [contract.to_dict() for contract in self.contracts]


class _FakeAALModule:
    PAM = _FakePAM
    Portfolio = _FakePortfolio


def _custom_specs() -> tuple[AALAssetContractSpec, ...]:
    return (
        AALAssetContractSpec(
            contract_id="CUSTOM_PAM_1",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
            currency="CHF",
        ),
        AALAssetContractSpec(
            contract_id="CUSTOM_PAM_2",
            start_year=2027,
            maturity_year=2030,
            nominal_value=250_000.0,
            coupon_rate=0.035,
            currency="CHF",
        ),
    )


def _skip_if_aal_missing():
    return pytest.importorskip("awesome_actus_lib")


# ---------------------------------------------------------------------------
# A. Default specs
# ---------------------------------------------------------------------------


def test_default_portfolio_specs_are_non_empty():
    specs = get_default_aal_asset_contract_specs()
    assert specs
    assert specs == DEFAULT_AAL_ASSET_CONTRACT_SPECS
    assert all(isinstance(spec, AALAssetContractSpec) for spec in specs)


def test_default_portfolio_specs_have_unique_ids_one_currency_and_no_purchase():
    specs = get_default_aal_asset_contract_specs()
    contract_ids = [spec.contract_id for spec in specs]
    assert len(contract_ids) == len(set(contract_ids))
    assert {spec.currency for spec in specs} == {"CHF"}
    assert all(spec.include_purchase_event is False for spec in specs)


# ---------------------------------------------------------------------------
# B. Spec validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_invalid_contract_id_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        AALAssetContractSpec(
            contract_id=bad,
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        )


@pytest.mark.parametrize("bad", [True, None, "2026", 1.5])
def test_invalid_start_year_type_rejected(bad):
    with pytest.raises(TypeError):
        AALAssetContractSpec(
            contract_id="BAD",
            start_year=bad,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        )


@pytest.mark.parametrize("maturity_year", [2025, 2026])
def test_maturity_year_must_be_after_start_year(maturity_year):
    with pytest.raises(ValueError):
        AALAssetContractSpec(
            contract_id="BAD",
            start_year=2026,
            maturity_year=maturity_year,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        )


@pytest.mark.parametrize("bad", [False, None, "2028", 1.5])
def test_invalid_maturity_year_type_rejected(bad):
    with pytest.raises(TypeError):
        AALAssetContractSpec(
            contract_id="BAD",
            start_year=2026,
            maturity_year=bad,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        )


@pytest.mark.parametrize("bad", [True, None, "100000", math.nan, 0.0, -1.0])
def test_invalid_nominal_value_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        AALAssetContractSpec(
            contract_id="BAD",
            start_year=2026,
            maturity_year=2028,
            nominal_value=bad,
            coupon_rate=0.02,
        )


@pytest.mark.parametrize("bad", [False, None, "0.02", math.nan, -0.01])
def test_invalid_coupon_rate_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        AALAssetContractSpec(
            contract_id="BAD",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=bad,
        )


@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_invalid_currency_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        AALAssetContractSpec(
            contract_id="BAD",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
            currency=bad,
        )


@pytest.mark.parametrize("bad", [None, 0, 1, "True"])
def test_invalid_include_purchase_event_rejected(bad):
    with pytest.raises(TypeError):
        AALAssetContractSpec(
            contract_id="BAD",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
            include_purchase_event=bad,
        )


def test_empty_portfolio_specs_rejected():
    with pytest.raises(ValueError):
        validate_aal_asset_contract_specs(())


def test_non_spec_item_rejected():
    with pytest.raises(TypeError):
        validate_aal_asset_contract_specs([_custom_specs()[0], "not a spec"])


def test_duplicate_contract_ids_rejected():
    with pytest.raises(ValueError):
        validate_aal_asset_contract_specs(
            [
                AALAssetContractSpec("DUP", 2026, 2028, 100_000.0, 0.02),
                AALAssetContractSpec("DUP", 2027, 2029, 200_000.0, 0.03),
            ]
        )


def test_mixed_currency_rejected_for_stage1_portfolio_analytics():
    with pytest.raises(ValueError):
        validate_aal_asset_contract_specs(
            [
                AALAssetContractSpec("CHF_PAM", 2026, 2028, 100_000.0, 0.02),
                AALAssetContractSpec(
                    "EUR_PAM",
                    2026,
                    2029,
                    100_000.0,
                    0.02,
                    currency="EUR",
                ),
            ]
        )


# ---------------------------------------------------------------------------
# C. Fallback cashflows
# ---------------------------------------------------------------------------


def test_fallback_portfolio_cashflows_validate_with_schema():
    df = build_aal_asset_portfolio_fallback_cashflows()
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == list(CASHFLOW_COLUMNS)
    assert validate_cashflow_dataframe(df) is True


def test_fallback_portfolio_cashflows_source_is_always_actus():
    df = build_aal_asset_portfolio_fallback_cashflows()
    assert not df.empty
    assert (df["source"] == "ACTUS").all()


def test_fallback_portfolio_cashflows_have_multiple_contract_ids():
    specs = get_default_aal_asset_contract_specs()
    df = build_aal_asset_portfolio_fallback_cashflows(specs)
    assert set(df["contractId"]) == {spec.contract_id for spec in specs}


def test_fallback_portfolio_row_count_equals_sum_of_individual_contract_rows():
    specs = _custom_specs()
    portfolio = build_aal_asset_portfolio_fallback_cashflows(specs)
    expected = sum(
        len(
            build_fixed_rate_bond_cashflow_dataframe(
                contract_id=spec.contract_id,
                start_year=spec.start_year,
                maturity_year=spec.maturity_year,
                nominal_value=spec.nominal_value,
                annual_coupon_rate=spec.coupon_rate,
                currency=spec.currency,
                include_purchase_event=spec.include_purchase_event,
            )
        )
        for spec in specs
    )
    assert len(portfolio) == expected


def test_annual_cashflow_summary_is_not_empty_and_consistent():
    specs = _custom_specs()
    portfolio = build_aal_asset_portfolio_fallback_cashflows(specs)
    annual = summarize_cashflows_by_year(portfolio)
    assert not annual.empty

    expected_by_year: dict[int, float] = {}
    for spec in specs:
        df = build_fixed_rate_bond_cashflow_dataframe(
            contract_id=spec.contract_id,
            start_year=spec.start_year,
            maturity_year=spec.maturity_year,
            nominal_value=spec.nominal_value,
            annual_coupon_rate=spec.coupon_rate,
            currency=spec.currency,
            include_purchase_event=spec.include_purchase_event,
        )
        individual_annual = summarize_cashflows_by_year(df)
        for _, row in individual_annual.iterrows():
            year = int(row["reporting_year"])
            expected_by_year[year] = expected_by_year.get(year, 0.0) + float(
                row["net_cashflow"]
            )

    actual_by_year = {
        int(row["reporting_year"]): float(row["net_cashflow"])
        for _, row in annual.iterrows()
    }
    assert actual_by_year == pytest.approx(expected_by_year)


def test_include_purchase_event_true_produces_ied_outflow():
    spec = AALAssetContractSpec(
        contract_id="PURCHASED_PAM",
        start_year=2026,
        maturity_year=2028,
        nominal_value=50_000.0,
        coupon_rate=0.02,
        include_purchase_event=True,
    )
    df = build_aal_asset_portfolio_fallback_cashflows([spec])
    ied = df[df["type"] == "IED"]
    assert len(ied) == 1
    assert ied.iloc[0]["payoff"] == pytest.approx(-50_000.0)
    assert ied.iloc[0]["contractId"] == "PURCHASED_PAM"


# ---------------------------------------------------------------------------
# D. AAL object construction
# ---------------------------------------------------------------------------


def test_dynamic_aal_terms_are_mapped_from_specs_with_fake_module():
    specs = _custom_specs()
    contracts = build_aal_pam_contracts_from_specs(_FakeAALModule, specs)
    terms = [contract.to_dict() for contract in contracts]

    assert [term["contractID"] for term in terms] == ["CUSTOM_PAM_1", "CUSTOM_PAM_2"]
    assert [term["contractDealDate"] for term in terms] == [
        "2026-01-01T00:00:00",
        "2027-01-01T00:00:00",
    ]
    assert [term["initialExchangeDate"] for term in terms] == [
        "2026-01-01T00:00:00",
        "2027-01-01T00:00:00",
    ]
    assert [term["statusDate"] for term in terms] == [
        "2026-01-01T00:00:00",
        "2027-01-01T00:00:00",
    ]
    assert [term["maturityDate"] for term in terms] == [
        "2028-12-31T00:00:00",
        "2030-12-31T00:00:00",
    ]
    assert [term["notionalPrincipal"] for term in terms] == [100_000.0, 250_000.0]
    assert [term["nominalInterestRate"] for term in terms] == [0.02, 0.035]
    assert [term["currency"] for term in terms] == ["CHF", "CHF"]


def test_aal_portfolio_can_be_constructed_with_fake_module():
    specs = _custom_specs()
    portfolio = build_aal_portfolio_from_specs(_FakeAALModule, specs)
    assert len(portfolio) == 2
    assert [term["contractID"] for term in portfolio.to_dict()] == [
        "CUSTOM_PAM_1",
        "CUSTOM_PAM_2",
    ]


def test_multiple_pam_contracts_can_be_constructed_if_aal_installed():
    module = _skip_if_aal_missing()
    contracts = build_aal_pam_contracts_from_specs(module, _custom_specs())
    assert len(contracts) == 2
    assert [contract.to_dict()["contractID"] for contract in contracts] == [
        "CUSTOM_PAM_1",
        "CUSTOM_PAM_2",
    ]


def test_aal_portfolio_can_be_constructed_from_specs_if_aal_installed():
    module = _skip_if_aal_missing()
    portfolio = build_aal_portfolio_from_specs(module, _custom_specs())
    assert len(portfolio) == 2


# ---------------------------------------------------------------------------
# E. No network / Stage-1 no-side-effect
# ---------------------------------------------------------------------------


def test_no_service_generation_attempted_by_default():
    probe = probe_aal_asset_boundary()
    assert probe.service_generation_attempted is False


def test_asset_portfolio_helpers_do_not_change_stage1_baseline_outputs():
    before = run_stage1_baseline(output_dir=None)

    build_aal_asset_portfolio_fallback_cashflows()
    build_aal_pam_contracts_from_specs(_FakeAALModule)
    build_aal_portfolio_from_specs(_FakeAALModule)

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
