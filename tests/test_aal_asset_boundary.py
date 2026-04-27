"""Tests for the AAL asset boundary module (Sprint 7A.1).

Coverage strategy:
- All fallback tests run unconditionally (no AAL required).
- AAL-specific construction tests are skipped when AAL is absent.
- Probe tests verify offline-only behaviour in both AAL-absent and
  AAL-present environments.
- A Stage-1 no-side-effect test confirms the boundary does not touch
  run_stage1_baseline(...) outputs.
"""

import pandas as pd
import pytest

from pk_alm.adapters.aal_asset_boundary import (
    AALAssetBoundaryProbeResult,
    DEFAULT_PAM_CONTRACT_ID,
    DEFAULT_PAM_COUPON_RATE,
    DEFAULT_PAM_CURRENCY,
    DEFAULT_PAM_MATURITY_YEAR,
    DEFAULT_PAM_NOMINAL_VALUE,
    DEFAULT_PAM_START_YEAR,
    build_aal_pam_contract,
    build_aal_portfolio,
    get_aal_asset_boundary_fallback_cashflows,
    probe_aal_asset_boundary,
)
from pk_alm.cashflows.schema import CASHFLOW_COLUMNS, validate_cashflow_dataframe
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline


# ---------------------------------------------------------------------------
# Skip helper
# ---------------------------------------------------------------------------


def _skip_if_aal_missing():
    return pytest.importorskip("awesome_actus_lib")


# ---------------------------------------------------------------------------
# A. Offline fallback — always runs
# ---------------------------------------------------------------------------


def test_fallback_returns_dataframe():
    df = get_aal_asset_boundary_fallback_cashflows()
    assert isinstance(df, pd.DataFrame)


def test_fallback_passes_schema_validation():
    df = get_aal_asset_boundary_fallback_cashflows()
    assert validate_cashflow_dataframe(df) is True


def test_fallback_columns_are_canonical():
    df = get_aal_asset_boundary_fallback_cashflows()
    assert list(df.columns) == list(CASHFLOW_COLUMNS)


def test_fallback_source_is_always_actus():
    df = get_aal_asset_boundary_fallback_cashflows()
    assert not df.empty
    assert (df["source"] == "ACTUS").all()


def test_fallback_uses_default_contract_id():
    df = get_aal_asset_boundary_fallback_cashflows()
    assert (df["contractId"] == DEFAULT_PAM_CONTRACT_ID).all()


def test_fallback_uses_default_currency():
    df = get_aal_asset_boundary_fallback_cashflows()
    assert (df["currency"] == DEFAULT_PAM_CURRENCY).all()


def test_fallback_default_row_count():
    # Default: start 2026, maturity 2028, no purchase event.
    # Produces: IP 2027, IP 2028, MD 2028 = 3 rows.
    df = get_aal_asset_boundary_fallback_cashflows()
    assert len(df) == 3


def test_fallback_includes_coupon_and_maturity_event_types():
    df = get_aal_asset_boundary_fallback_cashflows()
    types = set(df["type"])
    assert "IP" in types
    assert "MD" in types


def test_fallback_with_purchase_event_adds_ied_row():
    df = get_aal_asset_boundary_fallback_cashflows(include_purchase_event=True)
    assert len(df) == 4
    ied_rows = df[df["type"] == "IED"]
    assert len(ied_rows) == 1
    assert ied_rows.iloc[0]["payoff"] == pytest.approx(-DEFAULT_PAM_NOMINAL_VALUE)


def test_fallback_custom_parameters():
    df = get_aal_asset_boundary_fallback_cashflows(
        contract_id="CUSTOM_BOND",
        start_year=2028,
        maturity_year=2030,
        nominal_value=200_000.0,
        annual_coupon_rate=0.03,
        currency="CHF",
    )
    assert validate_cashflow_dataframe(df) is True
    assert (df["contractId"] == "CUSTOM_BOND").all()
    coupon_rows = df[df["type"] == "IP"]
    for payoff in coupon_rows["payoff"]:
        assert payoff == pytest.approx(200_000.0 * 0.03)


def test_fallback_does_not_require_aal():
    # This test documents that the fallback works regardless of AAL presence.
    # It succeeds even when awesome_actus_lib is not installed.
    df = get_aal_asset_boundary_fallback_cashflows()
    assert not df.empty


# ---------------------------------------------------------------------------
# B. Probe result dataclass
# ---------------------------------------------------------------------------


def test_probe_result_valid_aal_absent():
    result = AALAssetBoundaryProbeResult(
        aal_available=False,
        pam_constructed=False,
        portfolio_constructed=False,
        service_generation_attempted=False,
        fallback_used=True,
    )
    assert result.aal_available is False
    assert result.fallback_used is True
    assert result.service_generation_attempted is False


def test_probe_result_valid_aal_present():
    result = AALAssetBoundaryProbeResult(
        aal_available=True,
        pam_constructed=True,
        portfolio_constructed=True,
        service_generation_attempted=False,
        fallback_used=False,
    )
    assert result.aal_available is True
    assert result.pam_constructed is True
    assert result.portfolio_constructed is True


def test_probe_result_to_dict_has_all_five_keys():
    result = AALAssetBoundaryProbeResult(
        aal_available=False,
        pam_constructed=False,
        portfolio_constructed=False,
        service_generation_attempted=False,
        fallback_used=True,
    )
    d = result.to_dict()
    expected_keys = {
        "aal_available",
        "pam_constructed",
        "portfolio_constructed",
        "service_generation_attempted",
        "fallback_used",
    }
    assert set(d.keys()) == expected_keys


def test_probe_result_rejects_bool_false_for_non_bool_type():
    with pytest.raises(TypeError):
        AALAssetBoundaryProbeResult(
            aal_available="yes",  # type: ignore[arg-type]
            pam_constructed=False,
            portfolio_constructed=False,
            service_generation_attempted=False,
            fallback_used=True,
        )


def test_probe_result_rejects_service_generation_attempted_true():
    with pytest.raises(ValueError):
        AALAssetBoundaryProbeResult(
            aal_available=True,
            pam_constructed=True,
            portfolio_constructed=True,
            service_generation_attempted=True,  # must always be False
            fallback_used=False,
        )


def test_probe_result_rejects_pam_constructed_true_when_aal_unavailable():
    with pytest.raises(ValueError):
        AALAssetBoundaryProbeResult(
            aal_available=False,
            pam_constructed=True,  # impossible without AAL
            portfolio_constructed=False,
            service_generation_attempted=False,
            fallback_used=True,
        )


def test_probe_result_rejects_portfolio_constructed_true_when_aal_unavailable():
    with pytest.raises(ValueError):
        AALAssetBoundaryProbeResult(
            aal_available=False,
            pam_constructed=False,
            portfolio_constructed=True,  # impossible without AAL
            service_generation_attempted=False,
            fallback_used=True,
        )


# ---------------------------------------------------------------------------
# C. Probe function — offline behaviour (always runs)
# ---------------------------------------------------------------------------


def test_probe_never_attempts_service_generation():
    result = probe_aal_asset_boundary()
    assert result.service_generation_attempted is False


def test_probe_reports_fallback_used_when_aal_absent(monkeypatch):
    # Force AAL to appear unavailable regardless of the real environment.
    import importlib
    from pk_alm.adapters import aal_probe

    original_import = importlib.import_module

    def _raise_import_error(name, *args, **kwargs):
        if name == "awesome_actus_lib":
            raise ImportError("simulated AAL absence")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", _raise_import_error)

    # Re-run the probe with the patched import.
    from pk_alm.adapters.aal_asset_boundary import probe_aal_asset_boundary as _probe

    # We need to also patch check_aal_availability to use the monkeypatched import.
    # Since check_aal_availability calls importlib.import_module, monkeypatching
    # importlib.import_module is sufficient.
    from pk_alm.adapters.aal_probe import check_aal_availability as _check
    from pk_alm.adapters import aal_probe as _aal_probe_mod

    original_check = _aal_probe_mod.check_aal_availability

    def _fake_check():
        from pk_alm.adapters.aal_probe import AALAvailability, AAL_MODULE_NAME, AAL_DISTRIBUTION_NAMES
        return AALAvailability(
            is_available=False,
            module_name=AAL_MODULE_NAME,
            distribution_names=AAL_DISTRIBUTION_NAMES,
            version=None,
            import_error="simulated absence",
        )

    monkeypatch.setattr(
        "pk_alm.adapters.aal_asset_boundary.check_aal_availability",
        _fake_check,
    )

    result = _probe()
    assert result.aal_available is False
    assert result.fallback_used is True
    assert result.pam_constructed is False
    assert result.portfolio_constructed is False
    assert result.service_generation_attempted is False


# ---------------------------------------------------------------------------
# D. AAL-specific construction tests — skip when AAL absent
# ---------------------------------------------------------------------------


def test_pam_contract_can_be_constructed_if_aal_installed():
    module = _skip_if_aal_missing()
    pam = build_aal_pam_contract(module)
    terms = pam.to_dict()
    assert terms["contractID"] == DEFAULT_PAM_CONTRACT_ID
    assert terms["contractType"] == "PAM"
    assert terms["currency"] == DEFAULT_PAM_CURRENCY


def test_pam_contract_custom_id_if_aal_installed():
    module = _skip_if_aal_missing()
    pam = build_aal_pam_contract(module, contract_id="CUSTOM_PAM")
    assert pam.to_dict()["contractID"] == "CUSTOM_PAM"


def test_portfolio_accepts_pam_contract_if_aal_installed():
    module = _skip_if_aal_missing()
    pam = build_aal_pam_contract(module)
    portfolio = build_aal_portfolio(module, [pam])
    assert len(portfolio) == 1
    assert portfolio.to_dict() == [pam.to_dict()]


def test_probe_reports_aal_available_and_constructed_if_installed():
    _skip_if_aal_missing()
    result = probe_aal_asset_boundary()
    assert result.aal_available is True
    assert result.pam_constructed is True
    assert result.portfolio_constructed is True
    assert result.service_generation_attempted is False
    assert result.fallback_used is False


# ---------------------------------------------------------------------------
# E. No network calls by default
# ---------------------------------------------------------------------------


def test_probe_service_generation_attempted_is_always_false():
    # By design, service_generation_attempted is always False.
    # The dataclass validator also enforces this as a hard constraint.
    result = probe_aal_asset_boundary()
    assert result.service_generation_attempted is False


def test_probe_result_dataclass_enforces_no_service_generation():
    # Demonstrate that a result claiming service generation occurred is invalid.
    with pytest.raises(ValueError):
        AALAssetBoundaryProbeResult(
            aal_available=True,
            pam_constructed=True,
            portfolio_constructed=True,
            service_generation_attempted=True,
            fallback_used=False,
        )


# ---------------------------------------------------------------------------
# F. Stage-1 baseline no-side-effect
# ---------------------------------------------------------------------------


def test_aal_asset_boundary_does_not_change_stage1_baseline_outputs():
    before = run_stage1_baseline(output_dir=None)

    # Run all boundary operations between the two baseline calls.
    get_aal_asset_boundary_fallback_cashflows()
    probe_aal_asset_boundary()

    after = run_stage1_baseline(output_dir=None)

    pd.testing.assert_frame_equal(
        before.engine_result.cashflows,
        after.engine_result.cashflows,
    )
    pd.testing.assert_frame_equal(
        before.annual_cashflows,
        after.annual_cashflows,
    )
    pd.testing.assert_frame_equal(
        before.funding_ratio_trajectory,
        after.funding_ratio_trajectory,
    )
