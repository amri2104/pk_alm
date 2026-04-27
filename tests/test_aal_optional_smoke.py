import pytest

from pk_alm.adapters.aal_probe import check_aal_availability, get_aal_module


def _skip_if_aal_missing():
    return pytest.importorskip("awesome_actus_lib")


def test_optional_aal_import_gateway_smoke():
    _skip_if_aal_missing()

    module = get_aal_module()
    public_attrs = [name for name in dir(module) if not name.startswith("_")]

    assert module is not None
    assert public_attrs
    assert check_aal_availability().is_available is True


def test_optional_aal_public_attribute_listing_is_non_brittle():
    _skip_if_aal_missing()

    module = get_aal_module()
    public_attrs = [name for name in dir(module) if not name.startswith("_")]

    assert isinstance(public_attrs, list)
