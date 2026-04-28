"""Tests for the AAL Asset Engine v1 (Sprint 7A.4).

Coverage strategy:
- Always-run tests cover fallback mode, mapper edge cases, no-silent-fallback
  behaviour, and Stage-1 no-side-effects.
- AAL-required tests use ``pytest.importorskip("awesome_actus_lib")`` and
  skip on RuntimeError when the ACTUS service endpoint is unreachable —
  the engine itself still raises a clean RuntimeError, no silent fallback.
"""

import os
from pathlib import Path

import pandas as pd
import pytest

from pk_alm.adapters.aal_asset_portfolio import (
    AALAssetContractSpec,
    DEFAULT_AAL_ASSET_CONTRACT_SPECS,
    get_default_aal_asset_contract_specs,
)
from pk_alm.adapters.aal_probe import AAL_DISTRIBUTION_NAMES, AAL_MODULE_NAME, AALAvailability
from pk_alm.adapters.actus_adapter import (
    aal_events_to_cashflow_dataframe,
)
from pk_alm.assets import aal_engine
from pk_alm.assets.aal_engine import (
    VALID_GENERATION_MODES,
    AALAssetEngineResult,
    run_aal_asset_engine,
)
from pk_alm.cashflows.schema import (
    CASHFLOW_COLUMNS,
    validate_cashflow_dataframe,
)
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline

_OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "stage1_baseline"


def _custom_specs() -> tuple[AALAssetContractSpec, ...]:
    return (
        AALAssetContractSpec(
            contract_id="ENGINE_PAM_1",
            start_year=2026,
            maturity_year=2028,
            nominal_value=100_000.0,
            coupon_rate=0.02,
        ),
    )


def _force_aal_unavailable(monkeypatch) -> None:
    fake = AALAvailability(
        is_available=False,
        module_name=AAL_MODULE_NAME,
        distribution_names=AAL_DISTRIBUTION_NAMES,
        version=None,
        import_error="simulated absence for test",
    )
    monkeypatch.setattr(aal_engine, "check_aal_availability", lambda: fake)


# ---------------------------------------------------------------------------
# A. Fallback mode (always run)
# ---------------------------------------------------------------------------


def test_fallback_mode_returns_schema_valid_cashflows():
    result = run_aal_asset_engine(generation_mode="fallback")
    assert isinstance(result, AALAssetEngineResult)
    assert validate_cashflow_dataframe(result.cashflows) is True
    assert list(result.cashflows.columns) == list(CASHFLOW_COLUMNS)


def test_fallback_result_generation_mode_is_fallback():
    result = run_aal_asset_engine(generation_mode="fallback")
    assert result.generation_mode == "fallback"


def test_fallback_cashflows_have_source_actus():
    result = run_aal_asset_engine(generation_mode="fallback")
    assert (result.cashflows["source"] == "ACTUS").all()


def test_fallback_uses_default_specs_when_specs_none():
    result = run_aal_asset_engine(generation_mode="fallback")
    assert result.contracts == tuple(DEFAULT_AAL_ASSET_CONTRACT_SPECS)


def test_fallback_accepts_custom_specs():
    specs = _custom_specs()
    result = run_aal_asset_engine(specs=specs, generation_mode="fallback")
    assert result.contracts == specs
    assert (result.cashflows["contractId"] == "ENGINE_PAM_1").all()


def test_fallback_notes_mention_actus_fixtures_and_no_aal_event_generation():
    result = run_aal_asset_engine(generation_mode="fallback")
    joined = " | ".join(result.notes)
    assert "fallback" in joined.lower()
    assert "ACTUS" in joined
    assert "AAL was not used" in joined


# ---------------------------------------------------------------------------
# B. Generation-mode and spec validation
# ---------------------------------------------------------------------------


def test_engine_rejects_invalid_generation_mode():
    with pytest.raises(ValueError):
        run_aal_asset_engine(generation_mode="silent")


def test_engine_rejects_empty_specs():
    with pytest.raises(ValueError):
        run_aal_asset_engine(specs=[], generation_mode="fallback")


def test_engine_rejects_non_spec_items():
    with pytest.raises(TypeError):
        run_aal_asset_engine(specs=[{"contract_id": "BAD"}], generation_mode="fallback")  # type: ignore[list-item]


def test_valid_generation_modes_constant():
    assert set(VALID_GENERATION_MODES) == {"aal", "fallback"}


# ---------------------------------------------------------------------------
# C. AAL mode — no silent fallback
# ---------------------------------------------------------------------------


def test_aal_mode_raises_import_error_when_aal_absent(monkeypatch):
    _force_aal_unavailable(monkeypatch)
    with pytest.raises(ImportError):
        run_aal_asset_engine(generation_mode="aal")


def test_aal_mode_does_not_silently_fall_back_on_aal_absence(monkeypatch):
    _force_aal_unavailable(monkeypatch)
    with pytest.raises(ImportError) as excinfo:
        run_aal_asset_engine(generation_mode="aal")
    # The error message must point the user at the explicit fallback path,
    # not silently use it.
    msg = str(excinfo.value)
    assert "fallback" in msg.lower()
    assert "awesome-actus-lib" in msg or "awesome_actus_lib" in msg


def test_default_generation_mode_is_aal():
    # Default mode is the AAL strategic path; must require AAL.
    import inspect

    sig = inspect.signature(run_aal_asset_engine)
    assert sig.parameters["generation_mode"].default == "aal"


# ---------------------------------------------------------------------------
# D. AAL events mapper (synthetic, no AAL needed)
# ---------------------------------------------------------------------------


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
    # default currency applied
    assert df.iloc[0]["currency"] == "CHF"
    # default nominal value applied
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


# ---------------------------------------------------------------------------
# E. Result dataclass invariants
# ---------------------------------------------------------------------------


def _good_result_kwargs() -> dict:
    result = run_aal_asset_engine(generation_mode="fallback")
    return {
        "cashflows": result.cashflows,
        "contracts": result.contracts,
        "generation_mode": result.generation_mode,
        "aal_available": result.aal_available,
        "aal_version": result.aal_version,
        "notes": result.notes,
    }


def test_result_dataclass_rejects_non_actus_source_rows():
    kwargs = _good_result_kwargs()
    bad = kwargs["cashflows"].copy()
    bad.loc[0, "source"] = "BVG"
    kwargs["cashflows"] = bad
    with pytest.raises(ValueError):
        AALAssetEngineResult(**kwargs)


def test_result_dataclass_rejects_invalid_generation_mode():
    kwargs = _good_result_kwargs()
    kwargs["generation_mode"] = "silent"
    with pytest.raises(ValueError):
        AALAssetEngineResult(**kwargs)


def test_result_dataclass_rejects_non_dataframe_cashflows():
    kwargs = _good_result_kwargs()
    kwargs["cashflows"] = "not a dataframe"
    with pytest.raises(TypeError):
        AALAssetEngineResult(**kwargs)


# ---------------------------------------------------------------------------
# F. Stage-1 no-side-effect
# ---------------------------------------------------------------------------


def test_engine_does_not_modify_stage1_baseline_outputs():
    before = run_stage1_baseline(output_dir=None)
    run_aal_asset_engine(generation_mode="fallback")
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


def test_stage1_output_csv_files_not_modified_by_engine():
    if not _OUTPUTS_DIR.exists():
        pytest.skip("outputs/stage1_baseline/ does not exist")
    csv_files = list(_OUTPUTS_DIR.glob("*.csv"))
    assert csv_files, "expected CSV files in outputs/stage1_baseline/"

    mtimes_before = {f: os.path.getmtime(f) for f in csv_files}
    run_aal_asset_engine(generation_mode="fallback")
    # also exercise the no-AAL aal-mode path which must raise rather than write
    try:
        run_aal_asset_engine(generation_mode="aal")
    except (ImportError, RuntimeError):
        pass
    mtimes_after = {f: os.path.getmtime(f) for f in csv_files}
    assert mtimes_before == mtimes_after


# ---------------------------------------------------------------------------
# G. AAL-required tests (skip if AAL absent or service unreachable)
# ---------------------------------------------------------------------------


def test_aal_mode_runs_against_real_aal_or_skips_with_clear_reason():
    pytest.importorskip("awesome_actus_lib")
    try:
        result = run_aal_asset_engine(generation_mode="aal")
    except RuntimeError as exc:
        pytest.skip(f"AAL service path unreachable in this env: {exc}")

    assert result.generation_mode == "aal"
    assert result.aal_available is True
    assert validate_cashflow_dataframe(result.cashflows) is True
    assert (result.cashflows["source"] == "ACTUS").all()


def test_aal_mode_uses_provided_specs_or_skips_with_clear_reason():
    pytest.importorskip("awesome_actus_lib")
    specs = _custom_specs()
    try:
        result = run_aal_asset_engine(specs=specs, generation_mode="aal")
    except RuntimeError as exc:
        pytest.skip(f"AAL service path unreachable in this env: {exc}")

    assert result.contracts == specs
    assert validate_cashflow_dataframe(result.cashflows) is True


def test_aal_mode_default_specs_or_skips_with_clear_reason():
    pytest.importorskip("awesome_actus_lib")
    try:
        result = run_aal_asset_engine(generation_mode="aal")
    except RuntimeError as exc:
        pytest.skip(f"AAL service path unreachable in this env: {exc}")

    assert result.contracts == tuple(get_default_aal_asset_contract_specs())
