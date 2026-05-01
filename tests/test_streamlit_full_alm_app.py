"""Tests for the Sprint 11 Streamlit Full ALM prototype."""

import runpy
from pathlib import Path

import pytest

from pk_alm.workflows import full_alm_workflow

_REPO_ROOT = Path(__file__).resolve().parent.parent
_APP_PATH = _REPO_ROOT / "examples" / "streamlit_full_alm_app.py"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _app_source() -> str:
    return _APP_PATH.read_text()


def test_streamlit_app_file_exists():
    assert _APP_PATH.exists()


def test_streamlit_app_import_safe_without_running_workflow(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("workflow must not run during import")

    monkeypatch.setattr(
        full_alm_workflow,
        "run_full_alm_reporting_workflow",
        fail_if_called,
    )

    namespace = runpy.run_path(str(_APP_PATH), run_name="not_main")

    assert "main" in namespace
    assert callable(namespace["main"])


def test_streamlit_app_calls_workflow_only_from_button_flow():
    text = _app_source()
    call = "run_full_alm_reporting_workflow("
    import_call = "import run_full_alm_reporting_workflow"
    call_positions = [
        idx
        for idx in range(len(text))
        if text.startswith(call, idx) and not text.startswith(import_call, idx)
    ]

    assert call_positions
    assert "run_clicked = st.button(" in text
    assert "if run_clicked:" in text
    assert all(pos > text.index("if run_clicked:") for pos in call_positions)


def test_streamlit_app_has_required_controls_and_session_state():
    text = _app_source()

    assert 'GENERATION_MODES = ("aal", "fallback")' in text
    assert "st.selectbox(" in text
    assert "st.text_input(" in text
    assert "st.data_editor(" in text
    assert "st.button(" in text
    assert "st.session_state" in text
    assert "workflow_completed" in text
    assert "latest_output_dir" in text
    assert "generated_summary" in text


def test_streamlit_app_uses_safe_default_output_dir():
    text = _app_source()

    assert 'DEFAULT_OUTPUT_DIR = Path("outputs/full_alm_streamlit")' in text
    assert "outputs/stage1_baseline" not in text


def test_pyproject_declares_streamlit_app_extra_only():
    text = _PYPROJECT.read_text()

    assert 'app = ["streamlit"]' in text
    assert '"streamlit",' not in text
    assert "streamlit" not in text.split("dev = [", 1)[1].split("]", 1)[0]


def test_optional_streamlit_apptest_initial_render_only():
    app_test_module = pytest.importorskip("streamlit.testing.v1")
    AppTest = app_test_module.AppTest

    app = AppTest.from_file(str(_APP_PATH)).run(timeout=10)

    assert not app.exception
    assert any("Full ALM Reporting Prototype" in title.value for title in app.title)
    assert app.selectbox
    assert app.text_input
    assert app.button
