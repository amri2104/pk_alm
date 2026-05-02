import types
from types import SimpleNamespace

import pytest

from pk_alm.adapters import aal_introspection
from pk_alm.adapters.aal_introspection import (
    AALAPISurfaceSnapshot,
    _discover_public_submodules,
    _filter_candidate_symbols,
    _public_names,
    format_aal_api_surface_report,
    inspect_aal_api_surface,
)
from pk_alm.adapters.aal_probe import (
    AAL_DISTRIBUTION_NAMES,
    AAL_MODULE_NAME,
    AALAvailability,
)


def _available_snapshot() -> AALAPISurfaceSnapshot:
    return AALAPISurfaceSnapshot(
        is_available=True,
        version="1.0.12",
        module_name=AAL_MODULE_NAME,
        top_level_public_names=("ContractModel", "PAM", "Portfolio"),
        public_submodules=("analysis", "events"),
        candidate_contract_symbols=("ContractModel",),
        candidate_portfolio_symbols=("Portfolio",),
        candidate_event_symbols=("events",),
        candidate_analysis_symbols=("analysis",),
        candidate_actus_type_symbols=("PAM",),
        notes=("introspection only",),
    )


def _unavailable_snapshot() -> AALAPISurfaceSnapshot:
    return AALAPISurfaceSnapshot(
        is_available=False,
        version=None,
        module_name=AAL_MODULE_NAME,
        top_level_public_names=(),
        public_submodules=(),
        candidate_contract_symbols=(),
        candidate_portfolio_symbols=(),
        candidate_event_symbols=(),
        candidate_analysis_symbols=(),
        candidate_actus_type_symbols=(),
        notes=("AAL is unavailable",),
    )


def test_snapshot_dataclass_standard_available_to_dict_order():
    snapshot = _available_snapshot()

    assert snapshot.is_available is True
    assert snapshot.version == "1.0.12"
    assert snapshot.module_name == "awesome_actus_lib"
    assert snapshot.candidate_contract_symbols == ("ContractModel",)
    assert list(snapshot.to_dict().keys()) == [
        "is_available",
        "version",
        "module_name",
        "top_level_public_names",
        "public_submodules",
        "candidate_contract_symbols",
        "candidate_portfolio_symbols",
        "candidate_event_symbols",
        "candidate_analysis_symbols",
        "candidate_actus_type_symbols",
        "notes",
    ]


def test_snapshot_dataclass_standard_unavailable():
    snapshot = _unavailable_snapshot()

    assert snapshot.is_available is False
    assert snapshot.version is None
    assert snapshot.top_level_public_names == ()
    assert snapshot.notes == ("AAL is unavailable",)


@pytest.mark.parametrize("bad", [None, 1, "True"])
def test_snapshot_rejects_invalid_is_available(bad):
    kwargs = _available_snapshot().to_dict()
    kwargs["is_available"] = bad
    with pytest.raises(TypeError):
        AALAPISurfaceSnapshot(**kwargs)


def test_snapshot_rejects_invalid_version():
    kwargs = _available_snapshot().to_dict()
    kwargs["version"] = 123
    with pytest.raises(TypeError):
        AALAPISurfaceSnapshot(**kwargs)


@pytest.mark.parametrize("bad", ["", "   "])
def test_snapshot_rejects_empty_module_name(bad):
    kwargs = _available_snapshot().to_dict()
    kwargs["module_name"] = bad
    with pytest.raises(ValueError):
        AALAPISurfaceSnapshot(**kwargs)


def test_snapshot_rejects_non_string_module_name():
    kwargs = _available_snapshot().to_dict()
    kwargs["module_name"] = 123
    with pytest.raises(TypeError):
        AALAPISurfaceSnapshot(**kwargs)


@pytest.mark.parametrize(
    "field_name",
    [
        "top_level_public_names",
        "public_submodules",
        "candidate_contract_symbols",
        "candidate_portfolio_symbols",
        "candidate_event_symbols",
        "candidate_analysis_symbols",
        "candidate_actus_type_symbols",
        "notes",
    ],
)
def test_snapshot_rejects_tuple_field_not_tuple(field_name):
    kwargs = _available_snapshot().to_dict()
    kwargs[field_name] = ["not", "tuple"]
    with pytest.raises(TypeError):
        AALAPISurfaceSnapshot(**kwargs)


@pytest.mark.parametrize(
    "field_name",
    [
        "top_level_public_names",
        "public_submodules",
        "candidate_contract_symbols",
        "candidate_portfolio_symbols",
        "candidate_event_symbols",
        "candidate_analysis_symbols",
        "candidate_actus_type_symbols",
        "notes",
    ],
)
def test_snapshot_rejects_tuple_field_non_string_item(field_name):
    kwargs = _available_snapshot().to_dict()
    kwargs[field_name] = ("ok", 123)
    with pytest.raises(TypeError):
        AALAPISurfaceSnapshot(**kwargs)


def test_public_names_excludes_private_and_sorts():
    obj = SimpleNamespace(Zeta=1, Alpha=2, _private=3)

    assert _public_names(obj) == ("Alpha", "Zeta")


def test_public_names_failure_returns_empty_tuple():
    class BadDir:
        def __dir__(self):
            raise RuntimeError("boom")

    assert _public_names(BadDir()) == ()


def test_discover_public_submodules_filters_private_and_sorts(monkeypatch):
    module = types.ModuleType("dummy_package")
    module.__path__ = ["dummy"]

    def fake_iter_modules(path):
        assert path == ["dummy"]
        return [
            SimpleNamespace(name="events"),
            SimpleNamespace(name="_private"),
            SimpleNamespace(name="analysis"),
        ]

    monkeypatch.setattr(aal_introspection.pkgutil, "iter_modules", fake_iter_modules)

    assert _discover_public_submodules(module) == ("analysis", "events")


def test_discover_public_submodules_without_path_returns_empty_tuple():
    module = types.ModuleType("dummy_module")

    assert _discover_public_submodules(module) == ()


def test_discover_public_submodules_failure_returns_empty_tuple(monkeypatch):
    module = types.ModuleType("dummy_package")
    module.__path__ = ["dummy"]

    def fake_iter_modules(path):
        raise RuntimeError("boom")

    monkeypatch.setattr(aal_introspection.pkgutil, "iter_modules", fake_iter_modules)

    assert _discover_public_submodules(module) == ()


def test_filter_candidate_symbols_case_insensitive_preserves_sorted_order():
    names = (
        "AnalysisTool",
        "ContractModel",
        "EventSchedule",
        "LiquidityView",
        "PAM",
        "Portfolio",
        "SomethingElse",
    )

    assert _filter_candidate_symbols(names, ("contract",)) == ("ContractModel",)
    assert _filter_candidate_symbols(names, ("portfolio",)) == ("Portfolio",)
    assert _filter_candidate_symbols(names, ("event", "schedule")) == (
        "EventSchedule",
    )
    assert _filter_candidate_symbols(names, ("liquidity", "value")) == (
        "LiquidityView",
    )
    assert _filter_candidate_symbols(names, ("pam",)) == ("PAM",)


def test_inspect_aal_api_surface_unavailable(monkeypatch):
    availability = AALAvailability(
        False,
        AAL_MODULE_NAME,
        AAL_DISTRIBUTION_NAMES,
        None,
        "missing",
    )
    monkeypatch.setattr(
        aal_introspection,
        "check_aal_availability",
        lambda: availability,
    )

    snapshot = inspect_aal_api_surface()

    assert snapshot.is_available is False
    assert snapshot.version is None
    assert snapshot.module_name == AAL_MODULE_NAME
    assert snapshot.top_level_public_names == ()
    assert snapshot.public_submodules == ()
    assert "not installed" in " ".join(snapshot.notes)


def test_inspect_aal_api_surface_available_detects_candidates(monkeypatch):
    availability = AALAvailability(
        True,
        AAL_MODULE_NAME,
        AAL_DISTRIBUTION_NAMES,
        "1.0.12",
        None,
    )
    dummy_module = types.ModuleType(AAL_MODULE_NAME)

    monkeypatch.setattr(
        aal_introspection,
        "check_aal_availability",
        lambda: availability,
    )
    monkeypatch.setattr(aal_introspection, "get_aal_module", lambda: dummy_module)
    monkeypatch.setattr(
        aal_introspection,
        "_public_names",
        lambda module: (
            "AnalysisTool",
            "ContractModel",
            "EventSchedule",
            "PAM",
            "Portfolio",
        ),
    )
    monkeypatch.setattr(
        aal_introspection,
        "_discover_public_submodules",
        lambda module: ("cashflow", "terms"),
    )

    snapshot = inspect_aal_api_surface()

    assert snapshot.is_available is True
    assert snapshot.version == "1.0.12"
    assert snapshot.top_level_public_names == (
        "AnalysisTool",
        "ContractModel",
        "EventSchedule",
        "PAM",
        "Portfolio",
    )
    assert snapshot.public_submodules == ("cashflow", "terms")
    assert snapshot.candidate_contract_symbols == ("ContractModel", "terms")
    assert snapshot.candidate_portfolio_symbols == ("Portfolio",)
    assert snapshot.candidate_event_symbols == ("EventSchedule", "cashflow")
    assert snapshot.candidate_analysis_symbols == ("AnalysisTool",)
    assert snapshot.candidate_actus_type_symbols == ("PAM",)
    assert "cashflows" in " ".join(snapshot.notes)


def test_format_aal_api_surface_report_available_contains_key_sections():
    report = format_aal_api_surface_report(_available_snapshot())

    assert "AAL API Surface Report" in report
    assert "availability: available" in report
    assert "version: 1.0.12" in report
    assert "candidate_contract_symbols" in report
    assert "candidate_portfolio_symbols" in report
    assert "candidate_event_symbols" in report
    assert "candidate_analysis_symbols" in report
    assert "candidate_actus_type_symbols" in report
    assert "notes:" in report


def test_format_aal_api_surface_report_unavailable_says_optional():
    report = format_aal_api_surface_report(_unavailable_snapshot())

    assert "availability: unavailable" in report
    assert "optional" in report
    assert "unknown" in report
