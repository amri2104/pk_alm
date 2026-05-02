"""Tests for Sprint 8 benchmark/plausibility preparation."""

import pandas as pd
import pytest

from pk_alm.reporting.benchmark import (
    BENCHMARK_PLAUSIBILITY_COLUMNS,
    build_benchmark_plausibility_table,
    export_benchmark_plausibility,
)
from pk_alm.scenarios.full_alm_scenario import run_full_alm_scenario


@pytest.fixture()
def full_alm_scenario():
    return run_full_alm_scenario()


def test_benchmark_table_has_stable_columns(full_alm_scenario):
    table = build_benchmark_plausibility_table(
        full_alm_scenario,
        reference_values={
            "final_funding_ratio_percent": 100.0,
            "minimum_funding_ratio_percent": 100.0,
            "technical_interest_rate_percent": 1.76,
        },
    )

    assert list(table.columns) == list(BENCHMARK_PLAUSIBILITY_COLUMNS)
    assert set(table["metric"]) >= {
        "final_funding_ratio_percent",
        "minimum_funding_ratio_percent",
        "technical_interest_rate_percent",
    }


def test_benchmark_difference_uses_caller_provided_references(full_alm_scenario):
    table = build_benchmark_plausibility_table(
        full_alm_scenario,
        reference_values={"technical_interest_rate_percent": 2.0},
        notes={"technical_interest_rate_percent": "caller reference"},
    )

    row = table.loc[
        table["metric"] == "technical_interest_rate_percent"
    ].iloc[0]
    assert row["model_value"] == pytest.approx(1.76)
    assert row["reference_value"] == pytest.approx(2.0)
    assert row["difference"] == pytest.approx(-0.24)
    assert row["unit"] == "%"
    assert row["note"] == "caller reference"


def test_benchmark_accepts_caller_supplied_model_values(full_alm_scenario):
    table = build_benchmark_plausibility_table(
        full_alm_scenario,
        reference_values={"conversion_rate_percent": 6.8},
        model_values={"conversion_rate_percent": 6.8},
        units={"conversion_rate_percent": "%"},
        notes={"conversion_rate_percent": "explicit caller value"},
    )

    row = table.loc[table["metric"] == "conversion_rate_percent"].iloc[0]
    assert row["model_value"] == pytest.approx(6.8)
    assert row["reference_value"] == pytest.approx(6.8)
    assert row["difference"] == pytest.approx(0.0)
    assert row["note"] == "explicit caller value"


def test_benchmark_without_references_adds_no_empirical_claims(full_alm_scenario):
    table = build_benchmark_plausibility_table(full_alm_scenario)

    assert set(table["metric"]) == {
        "final_funding_ratio_percent",
        "minimum_funding_ratio_percent",
        "technical_interest_rate_percent",
    }
    assert table["reference_value"].isna().all()
    assert table["difference"].isna().all()


def test_export_benchmark_plausibility_writes_readable_csv(
    tmp_path,
    full_alm_scenario,
):
    path = export_benchmark_plausibility(
        full_alm_scenario,
        tmp_path,
        reference_values={
            "final_funding_ratio_percent": 100.0,
            "minimum_funding_ratio_percent": 100.0,
        },
    )

    assert path.exists()
    assert path.name == "benchmark_plausibility.csv"
    path.relative_to(tmp_path)

    roundtrip = pd.read_csv(path)
    assert list(roundtrip.columns) == list(BENCHMARK_PLAUSIBILITY_COLUMNS)
    assert not roundtrip.empty


def test_benchmark_rejects_bool_reference_value(full_alm_scenario):
    with pytest.raises(TypeError):
        build_benchmark_plausibility_table(
            full_alm_scenario,
            reference_values={"final_funding_ratio_percent": True},
        )
