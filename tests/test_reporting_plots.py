"""Tests for Sprint 8 Full ALM plot generation."""

import pandas as pd
import pytest
from matplotlib.figure import Figure

from pk_alm.alm_analytics_engine.alm_kpis import (
    build_cashflow_by_source_plot_table,
    build_net_cashflow_plot_table,
)
from pk_alm.reporting.plots import (
    FULL_ALM_PLOT_FILENAMES,
    FullALMPlotExportResult,
    plot_assets_vs_liabilities,
    plot_cashflow_by_source,
    plot_funding_ratio_trajectory,
    plot_net_cashflow,
    save_full_alm_plots,
)
from pk_alm.scenarios.full_alm_scenario import run_full_alm_scenario


@pytest.fixture()
def plot_inputs():
    scenario = run_full_alm_scenario()
    return {
        "funding_ratio_trajectory": scenario.stage1_result.funding_ratio_trajectory,
        "cashflow_by_source": build_cashflow_by_source_plot_table(
            scenario.combined_cashflows
        ),
        "net_cashflow": build_net_cashflow_plot_table(scenario.annual_cashflows),
    }


def test_plot_functions_return_figures(plot_inputs):
    figures = [
        plot_funding_ratio_trajectory(plot_inputs["funding_ratio_trajectory"]),
        plot_net_cashflow(plot_inputs["net_cashflow"]),
        plot_cashflow_by_source(plot_inputs["cashflow_by_source"]),
        plot_assets_vs_liabilities(plot_inputs["funding_ratio_trajectory"]),
    ]

    assert all(isinstance(fig, Figure) for fig in figures)
    for fig in figures:
        fig.clf()


def test_save_full_alm_plots_writes_non_empty_pngs(tmp_path, plot_inputs):
    result = save_full_alm_plots(
        tmp_path,
        funding_ratio_trajectory=plot_inputs["funding_ratio_trajectory"],
        cashflow_by_source=plot_inputs["cashflow_by_source"],
        net_cashflow=plot_inputs["net_cashflow"],
    )

    assert isinstance(result, FullALMPlotExportResult)
    assert result.output_dir == tmp_path.resolve()
    assert set(result.output_paths) == set(FULL_ALM_PLOT_FILENAMES)

    for key, path in result.output_paths.items():
        assert path.exists(), key
        assert path.is_file(), key
        path.relative_to(tmp_path)
        assert path.suffix == ".png"
        assert path.name == FULL_ALM_PLOT_FILENAMES[key]
        assert path.stat().st_size > 0


def test_plot_functions_do_not_mutate_input_dataframes(tmp_path, plot_inputs):
    snapshots = {
        key: value.copy(deep=True)
        for key, value in plot_inputs.items()
    }

    save_full_alm_plots(
        tmp_path,
        funding_ratio_trajectory=plot_inputs["funding_ratio_trajectory"],
        cashflow_by_source=plot_inputs["cashflow_by_source"],
        net_cashflow=plot_inputs["net_cashflow"],
    )

    for key, expected in snapshots.items():
        pd.testing.assert_frame_equal(plot_inputs[key], expected)


def test_plot_functions_reject_reordered_plot_table_columns(plot_inputs):
    bad_net = plot_inputs["net_cashflow"].copy(deep=True)
    bad_net = bad_net[["net_cashflow"] + [c for c in bad_net.columns if c != "net_cashflow"]]

    with pytest.raises(ValueError):
        plot_net_cashflow(bad_net)
