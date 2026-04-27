from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PROGRESS_DOC = REPO_ROOT / "docs" / "implementation_progress.md"
PIPELINE_DOC = REPO_ROOT / "docs" / "stage1_pipeline.md"
OUTPUTS_DOC = REPO_ROOT / "docs" / "stage1_outputs.md"
README = REPO_ROOT / "README.md"


def test_progress_doc_exists():
    assert PROGRESS_DOC.exists()


def test_pipeline_and_outputs_docs_exist():
    assert PIPELINE_DOC.exists()
    assert OUTPUTS_DOC.exists()


def test_readme_mentions_example_script():
    assert "examples/stage1_baseline.py" in README.read_text()


def test_readme_links_implementation_progress():
    text = README.read_text()
    assert "docs/implementation_progress.md" in text
    assert "docs/stage1_outputs.md" in text


def test_progress_doc_mentions_first_and_last_sprint_and_test_count():
    text = PROGRESS_DOC.read_text()
    assert "Sprint 1A" in text
    assert "Sprint 3A" in text
    assert "Sprint 3B" in text
    assert "Sprint 3C" in text
    assert "Sprint 3D" in text
    assert "Sprint 3E" in text
    assert "Sprint 4A" in text
    assert "Sprint 4B" in text
    assert "Sprint 4C" in text
    assert "Sprint 5A" in text
    assert "718 passed, 2 skipped" in text


def test_pipeline_doc_mentions_key_functions():
    text = PIPELINE_DOC.read_text()
    assert "run_bvg_engine" in text
    assert "value_portfolio_states" in text
    assert "summarize_cashflows_by_year" in text
    assert "build_deterministic_asset_trajectory" in text
    assert "build_funding_ratio_trajectory" in text
    assert "summarize_funding_ratio" in text
    assert "find_liquidity_inflection_year" in text
    assert "build_scenario_result_summary" in text
    assert "scenario_summary.csv" in text

    combined = "\n".join(
        [
            README.read_text(),
            PROGRESS_DOC.read_text(),
            PIPELINE_DOC.read_text(),
            OUTPUTS_DOC.read_text(),
        ]
    )
    assert "scenario_summary.csv" in combined
    assert "actus_adapter.py" in combined
    assert "actus_fixtures.py" in combined
    assert "asset_overlay.py" in combined
    assert "aal_probe.py" in combined
    assert "718 passed, 2 skipped" in combined
    for outdated in (
        "No funding ratio logic",
        "Asset-side modelling is not yet implemented",
        "No assets/funding ratio yet",
        "full ACTUS integration exists",
        "ACTUS/AAL is wired into the default Stage-1 baseline",
        "AAL is installed",
        "AAL is used in the Stage-1 baseline",
        "real AAL cashflow generation exists",
        "AAL is required",
        "AAL is wired into the default Stage-1 baseline",
    ):
        assert outdated not in combined


def test_docs_use_renamed_projection_year_fields():
    combined = "\n".join(
        [
            PROGRESS_DOC.read_text(),
            PIPELINE_DOC.read_text(),
            OUTPUTS_DOC.read_text(),
        ]
    )
    assert "minimum_funding_ratio_projection_year" in combined
    assert "maximum_funding_ratio_projection_year" in combined


def test_docs_do_not_use_old_ambiguous_year_field_names():
    combined = "\n".join(
        [
            README.read_text(),
            PROGRESS_DOC.read_text(),
            PIPELINE_DOC.read_text(),
            OUTPUTS_DOC.read_text(),
        ]
    )
    # The old, ambiguous bare names must not appear in any doc. The renamed
    # form `..._projection_year` is allowed; substring search is safe because
    # "minimum_funding_ratio_year" is not a substring of
    # "minimum_funding_ratio_projection_year".
    assert "minimum_funding_ratio_year" not in combined
    assert "maximum_funding_ratio_year" not in combined
