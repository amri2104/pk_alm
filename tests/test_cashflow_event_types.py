"""Tests for the cashflow event-type contract and sign-rule validation."""

from __future__ import annotations

import pandas as pd
import pytest

from pk_alm.cashflows.event_types import (
    ACTUS_EVENT_TYPES,
    BVG_EVENT_TYPES,
    EX,
    EXPECTED_PAYOFF_SIGNS,
    IED,
    IN,
    IP,
    KA,
    MD,
    PR,
    RP,
    TD,
    expected_sign,
    is_known_event_type,
)
from pk_alm.cashflows.schema import (
    CASHFLOW_COLUMNS,
    CashflowRecord,
    cashflow_records_to_dataframe,
    validate_cashflow_dataframe,
)


def test_bvg_constants_match_codes() -> None:
    assert PR == "PR"
    assert RP == "RP"
    assert KA == "KA"
    assert EX == "EX"
    assert IN == "IN"


def test_actus_constants_match_codes() -> None:
    assert IED == "IED"
    assert IP == "IP"
    assert MD == "MD"
    assert TD == "TD"


def test_bvg_event_types_set_complete() -> None:
    assert set(BVG_EVENT_TYPES) == {PR, RP, KA, EX, IN}


def test_actus_event_types_set_complete() -> None:
    assert set(ACTUS_EVENT_TYPES) == {IED, IP, MD, TD}


def test_expected_signs_cover_every_event_type() -> None:
    expected = set(BVG_EVENT_TYPES) | set(ACTUS_EVENT_TYPES)
    assert set(EXPECTED_PAYOFF_SIGNS) == expected


def test_expected_signs_values() -> None:
    assert EXPECTED_PAYOFF_SIGNS[PR] == "non_negative"
    assert EXPECTED_PAYOFF_SIGNS[IN] == "non_negative"
    assert EXPECTED_PAYOFF_SIGNS[RP] == "non_positive"
    assert EXPECTED_PAYOFF_SIGNS[KA] == "non_positive"
    assert EXPECTED_PAYOFF_SIGNS[EX] == "non_positive"
    for code in (IED, IP, MD, TD):
        assert EXPECTED_PAYOFF_SIGNS[code] == "any"


def test_is_known_event_type() -> None:
    assert is_known_event_type(PR) is True
    assert is_known_event_type("ZZ") is False


def test_expected_sign_default_any() -> None:
    assert expected_sign(PR) == "non_negative"
    assert expected_sign("ZZ") == "any"


def _make_df(records: list[CashflowRecord]) -> pd.DataFrame:
    return cashflow_records_to_dataframe(records)


def test_validate_with_sign_check_accepts_valid_pr() -> None:
    df = _make_df(
        [
            CashflowRecord(
                contractId="A1",
                time=pd.Timestamp("2026-01-01"),
                type=PR,
                payoff=100.0,
                nominalValue=0.0,
                source="BVG",
            )
        ]
    )
    assert validate_cashflow_dataframe(df, check_event_type_signs=True) is True


def test_validate_with_sign_check_rejects_negative_pr() -> None:
    df = _make_df(
        [
            CashflowRecord(
                contractId="A1",
                time=pd.Timestamp("2026-01-01"),
                type=PR,
                payoff=-100.0,
                source="BVG",
            )
        ]
    )
    with pytest.raises(ValueError, match="non-negative payoff"):
        validate_cashflow_dataframe(df, check_event_type_signs=True)


def test_validate_with_sign_check_rejects_positive_rp() -> None:
    df = _make_df(
        [
            CashflowRecord(
                contractId="R1",
                time=pd.Timestamp("2026-01-01"),
                type=RP,
                payoff=50.0,
                source="BVG",
            )
        ]
    )
    with pytest.raises(ValueError, match="non-positive payoff"):
        validate_cashflow_dataframe(df, check_event_type_signs=True)


def test_validate_with_sign_check_rejects_unknown_event_type() -> None:
    df = _make_df(
        [
            CashflowRecord(
                contractId="X1",
                time=pd.Timestamp("2026-01-01"),
                type="ZZ",
                payoff=0.0,
                source="MANUAL",
            )
        ]
    )
    with pytest.raises(ValueError, match="unknown event type"):
        validate_cashflow_dataframe(df, check_event_type_signs=True)


def test_validate_default_does_not_check_signs() -> None:
    df = _make_df(
        [
            CashflowRecord(
                contractId="A1",
                time=pd.Timestamp("2026-01-01"),
                type=PR,
                payoff=-100.0,
                source="BVG",
            )
        ]
    )
    assert validate_cashflow_dataframe(df) is True


def test_schema_columns_unchanged() -> None:
    assert CASHFLOW_COLUMNS == (
        "contractId",
        "time",
        "type",
        "payoff",
        "nominalValue",
        "currency",
        "source",
    )
