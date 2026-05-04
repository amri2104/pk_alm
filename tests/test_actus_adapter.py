import copy

import pandas as pd
import pytest

from pk_alm.actus_asset_engine.actus_adapter import (
    ACTUS_SOURCE,
    actus_event_to_cashflow_record,
    actus_events_to_cashflow_dataframe,
    actus_events_to_cashflow_records,
)
from pk_alm.cashflows.schema import (
    CASHFLOW_COLUMNS,
    CashflowRecord,
    validate_cashflow_dataframe,
)
from pk_alm.scenarios.stage1_baseline import run_stage1_baseline


# ---------------------------------------------------------------------------
# Event factories
# ---------------------------------------------------------------------------


def _standard_event(**overrides) -> dict:
    base = {
        "contract_id": "BOND_1",
        "event_date": "2026-12-31",
        "event_type": "IP",
        "payoff": 5000.0,
        "nominal_value": 100000.0,
        "currency": "CHF",
    }
    base.update(overrides)
    return base


def _coupon_event() -> dict:
    return {
        "contract_id": "BOND_1",
        "event_date": "2026-12-31",
        "event_type": "IP",
        "payoff": 5000.0,
        "nominal_value": 100000.0,
        "currency": "CHF",
    }


def _maturity_event() -> dict:
    return {
        "contract_id": "BOND_1",
        "event_date": "2030-12-31",
        "event_type": "MD",
        "payoff": 100000.0,
        "nominal_value": 100000.0,
        "currency": "CHF",
    }


# ---------------------------------------------------------------------------
# A. Single standard event
# ---------------------------------------------------------------------------


def test_single_standard_event_returns_cashflow_record():
    rec = actus_event_to_cashflow_record(_standard_event())

    assert isinstance(rec, CashflowRecord)
    assert rec.contractId == "BOND_1"
    assert rec.time == pd.Timestamp("2026-12-31")
    assert rec.type == "IP"
    assert rec.payoff == 5000.0
    assert rec.nominalValue == 100000.0
    assert rec.currency == "CHF"
    assert rec.source == "ACTUS"
    assert rec.source == ACTUS_SOURCE


# ---------------------------------------------------------------------------
# B. Defaults
# ---------------------------------------------------------------------------


def test_defaults_for_optional_keys():
    event = {
        "contract_id": "BOND_2",
        "event_date": "2027-06-30",
        "event_type": "IP",
        "payoff": 1234.5,
    }
    rec = actus_event_to_cashflow_record(event)

    assert rec.nominalValue == 0.0
    assert rec.currency == "CHF"
    assert rec.source == "ACTUS"


# ---------------------------------------------------------------------------
# C. Negative payoff
# ---------------------------------------------------------------------------


def test_negative_payoff_preserved_and_validates_via_shared_schema():
    event = _standard_event(payoff=-100000.0, event_type="MD")
    rec = actus_event_to_cashflow_record(event)

    assert rec.payoff == -100000.0
    assert rec.payoff < 0

    df = actus_events_to_cashflow_dataframe([event])
    assert validate_cashflow_dataframe(df) is True


# ---------------------------------------------------------------------------
# D. Multiple events to records
# ---------------------------------------------------------------------------


def test_multiple_events_to_records_preserves_order_and_source():
    events = [_coupon_event(), _maturity_event()]
    records = actus_events_to_cashflow_records(events)

    assert isinstance(records, tuple)
    assert len(records) == 2
    assert records[0].type == "IP"
    assert records[1].type == "MD"
    assert records[0].time == pd.Timestamp("2026-12-31")
    assert records[1].time == pd.Timestamp("2030-12-31")
    assert all(r.source == "ACTUS" for r in records)


# ---------------------------------------------------------------------------
# E. DataFrame conversion
# ---------------------------------------------------------------------------


def test_events_to_dataframe_columns_shape_and_validation():
    events = [_coupon_event(), _maturity_event()]
    df = actus_events_to_cashflow_dataframe(events)

    assert list(df.columns) == list(CASHFLOW_COLUMNS)
    assert df.shape == (2, 7)
    assert validate_cashflow_dataframe(df) is True
    assert (df["source"] == "ACTUS").all()


# ---------------------------------------------------------------------------
# F. Empty input
# ---------------------------------------------------------------------------


def test_empty_records_returns_empty_tuple():
    assert actus_events_to_cashflow_records([]) == ()
    assert actus_events_to_cashflow_records(()) == ()


def test_empty_dataframe_has_canonical_columns_and_validates():
    df = actus_events_to_cashflow_dataframe([])
    assert df.empty
    assert list(df.columns) == list(CASHFLOW_COLUMNS)
    assert validate_cashflow_dataframe(df) is True


# ---------------------------------------------------------------------------
# G. Invalid single event
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, "not a dict", 42, ["a", "b"], (1, 2)])
def test_non_dict_event_raises_type_error(bad):
    with pytest.raises(TypeError):
        actus_event_to_cashflow_record(bad)


@pytest.mark.parametrize(
    "missing",
    ["contract_id", "event_date", "event_type", "payoff"],
)
def test_missing_required_key_raises_value_error(missing):
    event = _standard_event()
    event.pop(missing)
    with pytest.raises(ValueError, match="missing required"):
        actus_event_to_cashflow_record(event)


def test_invalid_contract_id_empty_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(_standard_event(contract_id=""))


def test_invalid_contract_id_whitespace_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(_standard_event(contract_id="   "))


def test_invalid_event_date_unparsable_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(_standard_event(event_date="not-a-date"))


def test_invalid_event_date_none_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(_standard_event(event_date=None))


def test_invalid_event_type_empty_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(_standard_event(event_type=""))


def test_invalid_payoff_nan_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(_standard_event(payoff=float("nan")))


def test_invalid_payoff_bool_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(_standard_event(payoff=True))


def test_invalid_nominal_value_negative_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(_standard_event(nominal_value=-1.0))


def test_invalid_nominal_value_nan_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(
            _standard_event(nominal_value=float("nan"))
        )


def test_invalid_currency_empty_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(_standard_event(currency=""))


def test_invalid_currency_whitespace_propagates():
    with pytest.raises(ValueError):
        actus_event_to_cashflow_record(_standard_event(currency="   "))


# ---------------------------------------------------------------------------
# H. Invalid event collection
# ---------------------------------------------------------------------------


def test_records_none_raises_type_error():
    with pytest.raises(TypeError):
        actus_events_to_cashflow_records(None)


def test_records_string_raises_type_error():
    with pytest.raises(TypeError):
        actus_events_to_cashflow_records("x")


def test_dataframe_none_raises_type_error():
    with pytest.raises(TypeError):
        actus_events_to_cashflow_dataframe(None)


def test_dataframe_string_raises_type_error():
    with pytest.raises(TypeError):
        actus_events_to_cashflow_dataframe("x")


def test_records_non_dict_item_raises_type_error():
    with pytest.raises(TypeError):
        actus_events_to_cashflow_records([_standard_event(), "bad"])


def test_dataframe_non_dict_item_raises_type_error():
    with pytest.raises(TypeError):
        actus_events_to_cashflow_dataframe([_standard_event(), 42])


# ---------------------------------------------------------------------------
# I. No mutation
# ---------------------------------------------------------------------------


def test_no_mutation_of_input_dictionaries():
    coupon = _coupon_event()
    maturity = _maturity_event()
    coupon_before = copy.deepcopy(coupon)
    maturity_before = copy.deepcopy(maturity)

    actus_event_to_cashflow_record(coupon)
    actus_events_to_cashflow_records([coupon, maturity])
    actus_events_to_cashflow_dataframe([coupon, maturity])

    assert coupon == coupon_before
    assert maturity == maturity_before


def test_no_mutation_when_optional_keys_omitted():
    minimal = {
        "contract_id": "BOND_3",
        "event_date": "2028-06-30",
        "event_type": "IP",
        "payoff": 250.0,
    }
    minimal_before = copy.deepcopy(minimal)

    actus_event_to_cashflow_record(minimal)

    assert minimal == minimal_before
    assert "nominal_value" not in minimal
    assert "currency" not in minimal


# ---------------------------------------------------------------------------
# J. Schema integration smoke test
# ---------------------------------------------------------------------------


def test_actus_events_concatenated_with_bvg_passes_schema_validation():
    bvg_result = run_stage1_baseline(horizon_years=1, output_dir=None)
    bvg_df = bvg_result.engine_result.cashflows
    assert validate_cashflow_dataframe(bvg_df) is True

    actus_df = actus_events_to_cashflow_dataframe(
        [_coupon_event(), _maturity_event()]
    )

    combined = pd.concat([bvg_df, actus_df], ignore_index=True)

    assert validate_cashflow_dataframe(combined) is True
    assert set(combined["source"].unique()) == {"BVG", "ACTUS"}
    assert len(combined) == len(bvg_df) + len(actus_df)
