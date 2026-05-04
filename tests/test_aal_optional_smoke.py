"""Smoke tests for the required AAL dependency."""

from pk_alm.actus_asset_engine.aal_probe import get_aal_module


def test_aal_dependency_is_importable():
    module = get_aal_module()
    assert module.__name__ == "awesome_actus_lib"


def test_public_actus_service_is_constructible():
    module = get_aal_module()
    service = module.PublicActusService()
    assert hasattr(service, "generateEvents")
