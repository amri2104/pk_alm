"""Import tests for the three-engine package layout."""


def test_new_bvg_liability_engine_import_paths():
    from pk_alm.bvg_liability_engine.domain_models.cohorts import ActiveCohort
    from pk_alm.bvg_liability_engine.orchestration.engine import run_bvg_engine

    assert ActiveCohort.__name__ == "ActiveCohort"
    assert callable(run_bvg_engine)


def test_new_actus_asset_engine_import_paths():
    from pk_alm.actus_asset_engine.aal_engine import AALAssetEngineResult
    from pk_alm.actus_asset_engine.aal_asset_portfolio import PAMSpec

    assert AALAssetEngineResult.__name__ == "AALAssetEngineResult"
    assert PAMSpec.__name__ == "PAMSpec"


def test_new_alm_analytics_engine_import_paths():
    from pk_alm.alm_analytics_engine import funding
    from pk_alm.alm_analytics_engine.cashflows import summarize_cashflows_by_year

    assert hasattr(funding, "build_funding_ratio_trajectory")
    assert callable(summarize_cashflows_by_year)


def test_legacy_engine_packages_are_removed_from_active_tree():
    import importlib.util

    assert importlib.util.find_spec("pk_alm.bvg") is None
    assert importlib.util.find_spec("pk_alm.assets") is None
    assert importlib.util.find_spec("pk_alm.analytics") is None
    assert importlib.util.find_spec("pk_alm.adapters") is None
