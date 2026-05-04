"""Reporting helpers for Full ALM scenario outputs."""

_BENCHMARK_EXPORTS = {
    "BENCHMARK_PLAUSIBILITY_COLUMNS",
    "build_benchmark_plausibility_table",
    "export_benchmark_plausibility",
}

_FULL_ALM_EXPORTS = {
    "FULL_ALM_EXPORT_FILENAMES",
    "FullALMExportResult",
    "export_full_alm_result",
    "export_full_alm_results",
}

_PLOT_EXPORTS = {
    "FULL_ALM_PLOT_FILENAMES",
    "FullALMPlotExportResult",
    "plot_assets_vs_liabilities",
    "plot_cashflow_by_source",
    "plot_funding_ratio_trajectory",
    "plot_net_cashflow",
    "save_full_alm_plots",
}


def __getattr__(name: str) -> object:
    if name in _BENCHMARK_EXPORTS:
        from pk_alm.reporting import benchmark

        return getattr(benchmark, name)
    if name in _FULL_ALM_EXPORTS:
        from pk_alm.reporting import full_alm_export

        return getattr(full_alm_export, name)
    if name in _PLOT_EXPORTS:
        from pk_alm.reporting import plots

        return getattr(plots, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "BENCHMARK_PLAUSIBILITY_COLUMNS",
    "FULL_ALM_EXPORT_FILENAMES",
    "FULL_ALM_PLOT_FILENAMES",
    "FullALMExportResult",
    "FullALMPlotExportResult",
    "build_benchmark_plausibility_table",
    "export_benchmark_plausibility",
    "export_full_alm_result",
    "export_full_alm_results",
    "plot_assets_vs_liabilities",
    "plot_cashflow_by_source",
    "plot_funding_ratio_trajectory",
    "plot_net_cashflow",
    "save_full_alm_plots",
]
