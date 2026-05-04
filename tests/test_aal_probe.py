"""Tests for the required AAL import helper."""

import awesome_actus_lib

from pk_alm.actus_asset_engine.aal_probe import get_aal_module


def test_get_aal_module_returns_required_aal_package():
    assert get_aal_module() is awesome_actus_lib


def test_required_aal_module_exposes_needed_symbols():
    module = get_aal_module()
    assert hasattr(module, "PAM")
    assert hasattr(module, "STK")
    assert hasattr(module, "CSH")
    assert hasattr(module, "Portfolio")
    assert hasattr(module, "PublicActusService")
