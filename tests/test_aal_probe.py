import importlib
from types import ModuleType, SimpleNamespace

import pytest

from pk_alm.adapters import aal_probe
from pk_alm.adapters.aal_probe import (
    AAL_DISTRIBUTION_NAMES,
    AAL_MODULE_NAME,
    AALAvailability,
    _detect_aal_version,
    check_aal_availability,
    get_aal_module,
    require_aal_available,
)


def _availability_available() -> AALAvailability:
    return AALAvailability(
        True,
        AAL_MODULE_NAME,
        AAL_DISTRIBUTION_NAMES,
        "1.0.12",
        None,
    )


def _availability_unavailable() -> AALAvailability:
    return AALAvailability(
        False,
        AAL_MODULE_NAME,
        AAL_DISTRIBUTION_NAMES,
        None,
        "No module named 'awesome_actus_lib'",
    )


def test_availability_dataclass_available_to_dict_order():
    availability = _availability_available()

    assert availability.is_available is True
    assert availability.module_name == "awesome_actus_lib"
    assert availability.distribution_names == (
        "awesome_actus_lib",
        "awesome-actus-lib",
    )
    assert availability.version == "1.0.12"
    assert availability.import_error is None
    assert list(availability.to_dict().keys()) == [
        "is_available",
        "module_name",
        "distribution_names",
        "version",
        "import_error",
    ]


def test_availability_dataclass_unavailable_to_dict_order():
    availability = _availability_unavailable()

    assert availability.is_available is False
    assert availability.version is None
    assert "awesome_actus_lib" in str(availability.import_error)
    assert list(availability.to_dict().keys()) == [
        "is_available",
        "module_name",
        "distribution_names",
        "version",
        "import_error",
    ]


@pytest.mark.parametrize("bad", [None, 1, "True"])
def test_availability_rejects_invalid_is_available(bad):
    with pytest.raises(TypeError):
        AALAvailability(
            bad,
            AAL_MODULE_NAME,
            AAL_DISTRIBUTION_NAMES,
            None,
            None,
        )


@pytest.mark.parametrize("bad", ["", "   "])
def test_availability_rejects_empty_module_name(bad):
    with pytest.raises(ValueError):
        AALAvailability(False, bad, AAL_DISTRIBUTION_NAMES, None, None)


def test_availability_rejects_non_string_module_name():
    with pytest.raises(TypeError):
        AALAvailability(False, 123, AAL_DISTRIBUTION_NAMES, None, None)


@pytest.mark.parametrize("bad", [None, [], ["awesome_actus_lib"]])
def test_availability_rejects_non_tuple_distribution_names(bad):
    with pytest.raises(TypeError):
        AALAvailability(False, AAL_MODULE_NAME, bad, None, None)


def test_availability_rejects_empty_distribution_names():
    with pytest.raises(ValueError):
        AALAvailability(False, AAL_MODULE_NAME, (), None, None)


@pytest.mark.parametrize(
    "bad",
    [
        ("awesome_actus_lib", ""),
        ("awesome_actus_lib", "   "),
        ("awesome_actus_lib", 123),
    ],
)
def test_availability_rejects_invalid_distribution_name_item(bad):
    with pytest.raises((TypeError, ValueError)):
        AALAvailability(False, AAL_MODULE_NAME, bad, None, None)


def test_availability_rejects_non_string_version():
    with pytest.raises(TypeError):
        AALAvailability(False, AAL_MODULE_NAME, AAL_DISTRIBUTION_NAMES, 1, None)


def test_availability_rejects_non_string_import_error():
    with pytest.raises(TypeError):
        AALAvailability(False, AAL_MODULE_NAME, AAL_DISTRIBUTION_NAMES, None, 1)


def test_availability_rejects_available_with_import_error():
    with pytest.raises(ValueError):
        AALAvailability(
            True,
            AAL_MODULE_NAME,
            AAL_DISTRIBUTION_NAMES,
            "1.0.12",
            "unexpected",
        )


def test_detect_aal_version_first_distribution_succeeds(monkeypatch):
    def fake_version(name: str) -> str:
        assert name == "awesome_actus_lib"
        return "1.0.12"

    monkeypatch.setattr(aal_probe.importlib.metadata, "version", fake_version)

    assert _detect_aal_version() == "1.0.12"


def test_detect_aal_version_second_distribution_fallback_succeeds(monkeypatch):
    calls = []

    def fake_version(name: str) -> str:
        calls.append(name)
        if name == "awesome_actus_lib":
            raise aal_probe.importlib.metadata.PackageNotFoundError
        return "1.0.12"

    monkeypatch.setattr(aal_probe.importlib.metadata, "version", fake_version)

    assert _detect_aal_version() == "1.0.12"
    assert calls == ["awesome_actus_lib", "awesome-actus-lib"]


def test_detect_aal_version_all_metadata_missing(monkeypatch):
    def fake_version(name: str) -> str:
        raise aal_probe.importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(aal_probe.importlib.metadata, "version", fake_version)

    assert _detect_aal_version() is None


def test_check_aal_availability_import_success_with_version(monkeypatch):
    dummy = SimpleNamespace(__name__=AAL_MODULE_NAME)

    def fake_import_module(name: str):
        assert name == AAL_MODULE_NAME
        return dummy

    monkeypatch.setattr(aal_probe.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(
        aal_probe.importlib.metadata,
        "version",
        lambda name: "1.0.12",
    )

    availability = check_aal_availability()

    assert availability.is_available is True
    assert availability.version == "1.0.12"
    assert availability.import_error is None


def test_check_aal_availability_import_success_without_metadata(monkeypatch):
    dummy = SimpleNamespace(__name__=AAL_MODULE_NAME)

    def fake_import_module(name: str):
        assert name == AAL_MODULE_NAME
        return dummy

    def fake_version(name: str) -> str:
        raise aal_probe.importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(aal_probe.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(aal_probe.importlib.metadata, "version", fake_version)

    availability = check_aal_availability()

    assert availability.is_available is True
    assert availability.version is None
    assert availability.import_error is None


def test_check_aal_availability_import_failure(monkeypatch):
    def fake_import_module(name: str):
        raise ModuleNotFoundError("No module named 'awesome_actus_lib'")

    monkeypatch.setattr(aal_probe.importlib, "import_module", fake_import_module)

    availability = check_aal_availability()

    assert availability.is_available is False
    assert availability.version is None
    assert "awesome_actus_lib" in str(availability.import_error)


def test_require_aal_available_success(monkeypatch):
    expected = _availability_available()
    monkeypatch.setattr(aal_probe, "check_aal_availability", lambda: expected)

    assert require_aal_available() is expected


def test_require_aal_available_failure(monkeypatch):
    monkeypatch.setattr(
        aal_probe,
        "check_aal_availability",
        lambda: _availability_unavailable(),
    )

    with pytest.raises(ImportError) as excinfo:
        require_aal_available()

    message = str(excinfo.value)
    assert "optional" in message
    assert "pip install awesome-actus-lib" in message
    assert "Stage-1 baseline" in message
    assert "do not require AAL" in message


def test_get_aal_module_returns_dummy_module_through_gateway(monkeypatch):
    dummy = ModuleType(AAL_MODULE_NAME)
    gateway_calls = []

    def fake_require() -> AALAvailability:
        gateway_calls.append("called")
        return _availability_available()

    def fake_import_module(name: str) -> ModuleType:
        assert name == AAL_MODULE_NAME
        return dummy

    monkeypatch.setattr(aal_probe, "require_aal_available", fake_require)
    monkeypatch.setattr(aal_probe.importlib, "import_module", fake_import_module)

    assert get_aal_module() is dummy
    assert gateway_calls == ["called"]


def test_importing_aal_probe_does_not_require_aal_installed():
    module = importlib.import_module("pk_alm.adapters.aal_probe")

    assert module.AAL_MODULE_NAME == "awesome_actus_lib"
