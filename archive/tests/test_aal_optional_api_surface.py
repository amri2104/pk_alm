import pytest

from pk_alm.adapters.aal_introspection import (
    format_aal_api_surface_report,
    inspect_aal_api_surface,
)


def _skip_if_aal_missing():
    return pytest.importorskip("awesome_actus_lib")


def test_real_aal_api_surface_can_be_inspected_if_installed():
    _skip_if_aal_missing()

    snapshot = inspect_aal_api_surface()
    report = format_aal_api_surface_report(snapshot)

    assert snapshot.is_available is True
    assert snapshot.module_name == "awesome_actus_lib"
    assert isinstance(snapshot.top_level_public_names, tuple)
    assert isinstance(report, str)
    assert report


def test_real_aal_api_surface_has_some_public_surface_if_installed():
    _skip_if_aal_missing()

    snapshot = inspect_aal_api_surface()

    assert snapshot.top_level_public_names or snapshot.public_submodules
