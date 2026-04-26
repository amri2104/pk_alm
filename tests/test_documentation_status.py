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
    assert "582 passed" in text


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
    assert "582 passed" in combined
    for outdated in (
        "No funding ratio logic",
        "Asset-side modelling is not yet implemented",
        "No assets/funding ratio yet",
    ):
        assert outdated not in combined
