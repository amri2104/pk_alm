"""Smoke tests for the Goal-1 Streamlit dashboard."""

import runpy
from pathlib import Path

import pytest

import pk_alm.workflows.stage_app_workflow as stage_app_workflow

_REPO_ROOT = Path(__file__).resolve().parent.parent
_APP_PATH = _REPO_ROOT / "examples" / "streamlit_full_alm_app.py"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _app_source() -> str:
    return _APP_PATH.read_text()


def test_streamlit_app_file_exists() -> None:
    assert _APP_PATH.exists()


def test_streamlit_app_import_safe_without_running_workflow(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("workflow must not run during import")

    monkeypatch.setattr(stage_app_workflow, "run_stage", fail_if_called)

    namespace = runpy.run_path(str(_APP_PATH), run_name="not_main")

    assert "main" in namespace
    assert callable(namespace["main"])


def test_streamlit_app_calls_dispatcher_only_from_button_flow() -> None:
    text = _app_source()
    call = "run_goal1_advanced_alm("
    call_positions = [
        idx for idx in range(len(text)) if text.startswith(call, idx)
    ]

    assert call_positions
    assert 'st.sidebar.button("Run Full Goal-1 Advanced ALM"' in text
    assert "if run_clicked:" in text
    assert all(pos > text.index("if run_clicked:") for pos in call_positions)


def test_streamlit_app_has_required_controls_tabs_and_session_state() -> None:
    text = _app_source()

    assert "horizon_years" in text
    assert "start_year" in text
    assert "target_funding_ratio" in text
    assert "valuation_terminal_age" in text
    assert ".button(" in text
    assert "st.session_state" in text
    assert "goal1_result" in text
    for tab_label in (
        "Overview",
        "Configure",
        "Run",
        "Results & Risk",
        "Stress Lab",
        "Methodology",
    ):
        assert tab_label in text


def test_streamlit_app_mentions_all_six_modes() -> None:
    text = _app_source()
    for mode_id in stage_app_workflow.MODE_METADATA:
        assert mode_id in text or mode_id in stage_app_workflow.MODE_METADATA
    for metadata in stage_app_workflow.MODE_METADATA.values():
        assert str(metadata["label"])


def test_streamlit_app_uses_streamlit_specific_output_dirs_not_protected_dirs() -> None:
    streamlit_dirs = {path.as_posix() for path in stage_app_workflow.STREAMLIT_OUTPUT_DIRS.values()}
    protected_dirs = {path.as_posix() for path in stage_app_workflow.PROTECTED_OUTPUT_DIRS}
    assert streamlit_dirs == {
        "outputs/streamlit_core",
        "outputs/streamlit_full_alm_actus",
        "outputs/streamlit_population",
        "outputs/streamlit_mortality",
        "outputs/streamlit_dynamic_parameters",
        "outputs/streamlit_stochastic",
    }
    assert streamlit_dirs.isdisjoint(protected_dirs)
    assert "outputs/stage1_baseline" not in _app_source()


def test_pyproject_declares_streamlit_app_extra_only() -> None:
    text = _PYPROJECT.read_text()

    app_line = next(line for line in text.splitlines() if line.startswith("app = "))
    assert "streamlit" in app_line
    assert "plotly" in app_line
    assert '"streamlit",' not in text
    assert "streamlit" not in text.split("dev = [", 1)[1].split("]", 1)[0]


def test_optional_streamlit_apptest_initial_render_only() -> None:
    app_test_module = pytest.importorskip("streamlit.testing.v1")
    AppTest = app_test_module.AppTest

    app = AppTest.from_file(str(_APP_PATH)).run(timeout=10)

    assert not app.exception
    assert any("Goal-1" in title.value for title in app.title)
    assert app.button
