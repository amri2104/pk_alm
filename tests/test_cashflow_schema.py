import math

import pandas as pd
import pytest
from pk_alm.cashflows.schema import (
    CASHFLOW_COLUMNS,
    VALID_SOURCES,
    CashflowRecord,
    cashflow_records_to_dataframe,
    validate_cashflow_dataframe,
)


# ---------------------------------------------------------------------------
# A. Standard positive inflow record
# ---------------------------------------------------------------------------


def test_record_positive_inflow():
    r = CashflowRecord(
        contractId="ACT_40",
        time="2026-12-31",
        type="PR",
        payoff=59275.0,
        nominalValue=1_200_000.0,
        currency="CHF",
        source="BVG",
    )
    assert r.contractId == "ACT_40"
    assert r.time == pd.Timestamp("2026-12-31")
    assert isinstance(r.time, pd.Timestamp)
    assert r.type == "PR"
    assert r.payoff == 59275.0
    assert r.payoff > 0
    assert r.nominalValue == 1_200_000.0
    assert r.currency == "CHF"
    assert r.source == "BVG"
    assert list(r.to_dict().keys()) == list(CASHFLOW_COLUMNS)


# ---------------------------------------------------------------------------
# B. Standard negative outflow record
# ---------------------------------------------------------------------------


def test_record_negative_outflow():
    r = CashflowRecord(
        contractId="RET_70",
        time="2026-12-31",
        type="RP",
        payoff=-150_000.0,
        nominalValue=2_250_000.0,
        currency="CHF",
        source="BVG",
    )
    assert r.payoff < 0
    assert r.source == "BVG"
    d = r.to_dict()
    assert d["payoff"] == -150_000.0
    assert list(d.keys()) == list(CASHFLOW_COLUMNS)


# ---------------------------------------------------------------------------
# C. Zero-payoff state update
# ---------------------------------------------------------------------------


def test_record_zero_payoff_state_update():
    r = CashflowRecord(
        contractId="RET_70",
        time="2026-12-31",
        type="PV",
        payoff=0.0,
        nominalValue=2_136_960.0,
        currency="CHF",
        source="BVG",
    )
    assert r.payoff == 0.0
    assert r.nominalValue == 2_136_960.0


# ---------------------------------------------------------------------------
# D. Defaults
# ---------------------------------------------------------------------------


def test_record_defaults():
    r = CashflowRecord(
        contractId="ACT_40",
        time="2026-12-31",
        type="PR",
        payoff=100.0,
    )
    assert r.nominalValue == 0.0
    assert r.currency == "CHF"
    assert r.source == "BVG"


# ---------------------------------------------------------------------------
# E. Frozen immutability
# ---------------------------------------------------------------------------


def test_record_is_frozen():
    r = CashflowRecord(
        contractId="ACT_40", time="2026-12-31", type="PR", payoff=100.0
    )
    with pytest.raises(Exception):
        r.payoff = 1.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# F. Two-record DataFrame
# ---------------------------------------------------------------------------


def test_dataframe_two_records():
    inflow = CashflowRecord(
        contractId="ACT_40",
        time="2026-12-31",
        type="PR",
        payoff=59275.0,
        nominalValue=1_200_000.0,
    )
    outflow = CashflowRecord(
        contractId="RET_70",
        time="2026-12-31",
        type="RP",
        payoff=-150_000.0,
        nominalValue=2_250_000.0,
    )
    df = cashflow_records_to_dataframe([inflow, outflow])

    assert df.shape == (2, len(CASHFLOW_COLUMNS))
    assert list(df.columns) == list(CASHFLOW_COLUMNS)
    assert df.loc[0, "payoff"] == 59275.0
    assert df.loc[1, "payoff"] == -150_000.0
    # Net cashflow = 59275 + (-150000) = -90725
    assert df["payoff"].sum() == pytest.approx(-90_725.0)


# ---------------------------------------------------------------------------
# G. Empty list conversion
# ---------------------------------------------------------------------------


def test_dataframe_empty_input():
    df = cashflow_records_to_dataframe([])
    assert df.empty
    assert list(df.columns) == list(CASHFLOW_COLUMNS)


def test_dataframe_empty_tuple_input():
    df = cashflow_records_to_dataframe(())
    assert df.empty
    assert list(df.columns) == list(CASHFLOW_COLUMNS)


# ---------------------------------------------------------------------------
# H. Valid DataFrame validation
# ---------------------------------------------------------------------------


def test_validate_valid_dataframe():
    records = [
        CashflowRecord(
            contractId="ACT_40", time="2026-12-31", type="PR", payoff=59275.0
        ),
        CashflowRecord(
            contractId="RET_70", time="2026-12-31", type="RP", payoff=-150_000.0
        ),
    ]
    df = cashflow_records_to_dataframe(records)
    assert validate_cashflow_dataframe(df) is True


def test_validate_empty_dataframe():
    df = cashflow_records_to_dataframe([])
    assert validate_cashflow_dataframe(df) is True


# ---------------------------------------------------------------------------
# I. Invalid CashflowRecord tests
# ---------------------------------------------------------------------------


_BASE = dict(
    contractId="ACT_40", time="2026-12-31", type="PR", payoff=100.0
)


def _make(**overrides):
    """Construct a CashflowRecord starting from a valid base."""
    args = {**_BASE, **overrides}
    return CashflowRecord(**args)


def test_invalid_contract_id_empty():
    with pytest.raises(ValueError):
        _make(contractId="")


def test_invalid_contract_id_whitespace():
    with pytest.raises(ValueError):
        _make(contractId="   ")


def test_invalid_time_none():
    with pytest.raises(ValueError):
        _make(time=None)


def test_invalid_time_string():
    with pytest.raises(ValueError):
        _make(time="not-a-date")


def test_invalid_type_empty():
    with pytest.raises(ValueError):
        _make(type="")


def test_invalid_type_whitespace():
    with pytest.raises(ValueError):
        _make(type="   ")


def test_invalid_payoff_nan():
    with pytest.raises(ValueError):
        _make(payoff=float("nan"))


def test_invalid_payoff_bool():
    with pytest.raises(ValueError):
        _make(payoff=True)


def test_invalid_nominal_nan():
    with pytest.raises(ValueError):
        _make(nominalValue=float("nan"))


def test_invalid_nominal_bool():
    with pytest.raises(ValueError):
        _make(nominalValue=True)


def test_invalid_nominal_negative():
    with pytest.raises(ValueError):
        _make(nominalValue=-1.0)


def test_invalid_currency_empty():
    with pytest.raises(ValueError):
        _make(currency="")


def test_invalid_currency_whitespace():
    with pytest.raises(ValueError):
        _make(currency="   ")


def test_invalid_source():
    with pytest.raises(ValueError):
        _make(source="UNKNOWN")


# ---------------------------------------------------------------------------
# J. Invalid records-to-DataFrame input
# ---------------------------------------------------------------------------


def test_records_to_df_none_raises():
    with pytest.raises(TypeError):
        cashflow_records_to_dataframe(None)  # type: ignore[arg-type]


def test_records_to_df_string_raises():
    with pytest.raises(TypeError):
        cashflow_records_to_dataframe("not records")  # type: ignore[arg-type]


def test_records_to_df_mixed_with_string_raises():
    valid = _make()
    with pytest.raises(TypeError):
        cashflow_records_to_dataframe([valid, "bad item"])  # type: ignore[list-item]


def test_records_to_df_dict_item_raises():
    with pytest.raises(TypeError):
        cashflow_records_to_dataframe([{"not": "a CashflowRecord"}])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# K. Invalid DataFrame validation
# ---------------------------------------------------------------------------


def test_validate_none_raises_type_error():
    with pytest.raises(TypeError):
        validate_cashflow_dataframe(None)  # type: ignore[arg-type]


def test_validate_string_raises_type_error():
    with pytest.raises(TypeError):
        validate_cashflow_dataframe("not a dataframe")  # type: ignore[arg-type]


def _valid_df():
    return cashflow_records_to_dataframe([_make()])


def test_validate_missing_column_raises():
    df = _valid_df().drop(columns=["payoff"])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_cashflow_dataframe(df)


def test_validate_wrong_column_order_raises():
    df = _valid_df()
    reordered = df[list(reversed(CASHFLOW_COLUMNS))]
    with pytest.raises(ValueError, match="columns must be in order"):
        validate_cashflow_dataframe(reordered)


def _set_value(df, column, value):
    """Set a column to a single value while keeping it object-dtype safe."""
    df[column] = pd.Series([value], dtype=object)
    return df


def test_validate_contract_id_none():
    df = _valid_df()
    df = _set_value(df, "contractId", None)
    with pytest.raises(ValueError, match="contractId"):
        validate_cashflow_dataframe(df)


def test_validate_contract_id_empty():
    df = _valid_df()
    df = _set_value(df, "contractId", "")
    with pytest.raises(ValueError, match="contractId"):
        validate_cashflow_dataframe(df)


def test_validate_contract_id_whitespace():
    df = _valid_df()
    df = _set_value(df, "contractId", "   ")
    with pytest.raises(ValueError, match="contractId"):
        validate_cashflow_dataframe(df)


def test_validate_time_none():
    df = _valid_df()
    df = _set_value(df, "time", None)
    with pytest.raises(ValueError, match="time"):
        validate_cashflow_dataframe(df)


def test_validate_time_invalid_string():
    df = _valid_df()
    df = _set_value(df, "time", "not-a-date")
    with pytest.raises(ValueError, match="time"):
        validate_cashflow_dataframe(df)


def test_validate_type_none():
    df = _valid_df()
    df = _set_value(df, "type", None)
    with pytest.raises(ValueError, match="type"):
        validate_cashflow_dataframe(df)


def test_validate_type_empty():
    df = _valid_df()
    df = _set_value(df, "type", "")
    with pytest.raises(ValueError, match="type"):
        validate_cashflow_dataframe(df)


def test_validate_payoff_nan():
    df = _valid_df()
    df = _set_value(df, "payoff", math.nan)
    with pytest.raises(ValueError, match="payoff"):
        validate_cashflow_dataframe(df)


def test_validate_payoff_bool():
    df = _valid_df()
    df = _set_value(df, "payoff", True)
    with pytest.raises(ValueError, match="payoff"):
        validate_cashflow_dataframe(df)


def test_validate_nominal_nan():
    df = _valid_df()
    df = _set_value(df, "nominalValue", math.nan)
    with pytest.raises(ValueError, match="nominalValue"):
        validate_cashflow_dataframe(df)


def test_validate_nominal_bool():
    df = _valid_df()
    df = _set_value(df, "nominalValue", True)
    with pytest.raises(ValueError, match="nominalValue"):
        validate_cashflow_dataframe(df)


def test_validate_nominal_negative():
    df = _valid_df()
    df = _set_value(df, "nominalValue", -1.0)
    with pytest.raises(ValueError, match="nominalValue"):
        validate_cashflow_dataframe(df)


def test_validate_currency_none():
    df = _valid_df()
    df = _set_value(df, "currency", None)
    with pytest.raises(ValueError, match="currency"):
        validate_cashflow_dataframe(df)


def test_validate_currency_empty():
    df = _valid_df()
    df = _set_value(df, "currency", "")
    with pytest.raises(ValueError, match="currency"):
        validate_cashflow_dataframe(df)


def test_validate_invalid_source():
    df = _valid_df()
    df = _set_value(df, "source", "UNKNOWN")
    with pytest.raises(ValueError, match="source"):
        validate_cashflow_dataframe(df)


def test_valid_sources_constant():
    assert VALID_SOURCES == ("BVG", "ACTUS", "MANUAL")
