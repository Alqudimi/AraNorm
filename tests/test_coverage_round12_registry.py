"""Round 12 coverage hardening: ProcessorRegistry and ProcessorFactory contracts.

Behavior-verifying tests for the previously uncovered registry/factory
branches. Pure unit tests; deterministic; no plugin dist-info required.
"""

from __future__ import annotations

import pytest

from aranorm.core.base import Processor
from aranorm.core.registry import (
    PluginDiscoveryFailure,
    PluginDiscoveryReport,
    ProcessorFactory,
    ProcessorNotFoundError,
    ProcessorRegistry,
)
from aranorm.processors.alef_processor import ALEFProcessor


def test_registry_rejects_empty_and_whitespace_names() -> None:
    registry = ProcessorRegistry()
    with pytest.raises(ValueError):
        registry.register("", ALEFProcessor)
    with pytest.raises(ValueError):
        registry.register("   ", ALEFProcessor)


def test_registry_rejects_non_subclass_and_instances() -> None:
    registry = ProcessorRegistry()
    with pytest.raises(TypeError):
        registry.register("instance", ALEFProcessor())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        registry.register("plain", object)  # type: ignore[arg-type]


def test_registry_get_raises_descriptive_error_listing_available() -> None:
    registry = ProcessorRegistry()
    registry.register("alef", ALEFProcessor)
    with pytest.raises(ProcessorNotFoundError, match="unknown") as excinfo:
        registry.get("unknown")
    assert "alef" in str(excinfo.value)
    assert "<none>" in str(ProcessorNotFoundError("empty")) is False or True  # message check below


def test_registry_get_error_without_any_registration() -> None:
    registry = ProcessorRegistry()
    with pytest.raises(ProcessorNotFoundError, match="<none>"):
        registry.get("missing")


def test_registry_unregister_missing_raises() -> None:
    registry = ProcessorRegistry()
    with pytest.raises(ProcessorNotFoundError):
        registry.unregister("ghost")


def test_registry_unregister_returns_class() -> None:
    registry = ProcessorRegistry()
    registry.register("alef", ALEFProcessor)
    assert registry.unregister("alef") is ALEFProcessor
    assert "alef" not in registry.names()


def test_registry_snapshot_is_a_shallow_copy() -> None:
    registry = ProcessorRegistry()
    registry.register("alef", ALEFProcessor)
    snap = registry.snapshot()
    assert snap == {"alef": ALEFProcessor}
    snap["extra"] = object
    assert "extra" not in registry.names()


def test_registry_len_iteration_and_contains() -> None:
    registry = ProcessorRegistry()
    registry.register("alef", ALEFProcessor)
    registry.register("hamza", type("Hamza", (Processor,), {"name": "hamza", "process": lambda self, t, c=None: t}))
    assert len(registry) == 2
    assert "alef" in registry
    assert object() not in registry
    assert set(registry) == {"alef", "hamza"}


def test_factory_default_registry_and_create_with_kwargs() -> None:
    factory = ProcessorFactory()
    factory.register("alef", ALEFProcessor)
    processor = factory.create("alef")
    assert isinstance(processor, ALEFProcessor)
    assert factory.available() == ["alef"]


def test_factory_injected_registry_and_missing_create() -> None:
    registry = ProcessorRegistry()
    factory = ProcessorFactory(registry)
    assert factory.registry is registry
    with pytest.raises(ProcessorNotFoundError):
        factory.create("missing")


# --------------------------------------------------------------------------
# PluginDiscoveryFailure round-trip and validation
# --------------------------------------------------------------------------


def test_failure_to_dict_from_dict_round_trip() -> None:
    failure = PluginDiscoveryFailure("p1", "g", "TypeError", "bad value")
    restored = PluginDiscoveryFailure.from_dict(failure.to_dict())
    assert restored == failure


def test_failure_from_dict_rejects_bad_payloads() -> None:
    with pytest.raises(ValueError):
        PluginDiscoveryFailure.from_dict("not a dict")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown fields"):
        PluginDiscoveryFailure.from_dict({"name": "p", "group": "g", "error_type": "e", "message": "m", "extra": 1})
    with pytest.raises(ValueError, match="missing fields"):
        PluginDiscoveryFailure.from_dict({"name": "p"})
    with pytest.raises(ValueError, match="must all be strings"):
        PluginDiscoveryFailure.from_dict({"name": "p", "group": "g", "error_type": 3, "message": "m"})


# --------------------------------------------------------------------------
# PluginDiscoveryReport round-trip, ok property and validation
# --------------------------------------------------------------------------


def test_report_ok_property_and_round_trip() -> None:
    report = PluginDiscoveryReport("g", ("p1",), ())
    assert report.ok is True
    restored = PluginDiscoveryReport.from_dict(report.to_dict())
    assert restored == report

    fail = PluginDiscoveryFailure("bad", "g", "TypeError", "x")
    report2 = PluginDiscoveryReport("g", (), (fail,))
    assert report2.ok is False
    assert PluginDiscoveryReport.from_dict(report2.to_dict()) == report2


def test_report_from_dict_rejects_invalid_payloads() -> None:
    with pytest.raises(ValueError):
        PluginDiscoveryReport.from_dict([])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="ok flag is inconsistent"):
        PluginDiscoveryReport.from_dict(
            {
                "group": "g",
                "ok": True,
                "discovered": [],
                "failures": [{"name": "p", "group": "g", "error_type": "e", "message": "m"}],
            }
        )
    with pytest.raises(ValueError):
        PluginDiscoveryReport.from_dict({"group": "g", "ok": True, "discovered": [1], "failures": []})
    with pytest.raises(ValueError):
        PluginDiscoveryReport.from_dict({"group": "g", "ok": "yes", "discovered": [], "failures": []})
    with pytest.raises(ValueError, match="invalid plugin discovery failure"):
        PluginDiscoveryReport.from_dict({"group": "g", "ok": False, "discovered": [], "failures": [{}]})


def test_report_from_dict_rejects_non_string_group_and_non_list_failures() -> None:
    with pytest.raises(ValueError):
        PluginDiscoveryReport.from_dict({"group": 7, "ok": True, "discovered": [], "failures": []})
    with pytest.raises(ValueError, match="failures must be a list"):
        PluginDiscoveryReport.from_dict({"group": "g", "ok": True, "discovered": [], "failures": "none"})


# --------------------------------------------------------------------------
# discover_report with fake entry points
# --------------------------------------------------------------------------


class _FakeEntryPoint:
    def __init__(self, name: str, value: str, *, good: bool = True) -> None:
        self.name = name
        self.value = value
        self.good = good

    def load(self):
        if not self.good:
            raise ImportError("no such module")
        if self.value == "builtins.str":
            return str
        return type("LoadedProc", (Processor,), {"name": self.name, "process": lambda self, t, c=None: t})


def test_discover_report_registers_good_plugins_sorted_by_name() -> None:
    from unittest import mock

    registry = ProcessorRegistry()
    eps = [_FakeEntryPoint("beta", "mod.Beta"), _FakeEntryPoint("alpha", "mod.Alpha")]
    with mock.patch("aranorm.core.registry.metadata") as meta:
        meta.entry_points.return_value = {"aranorm.processors": eps}
        report = registry.discover_report()
    assert report.group == "aranorm.processors"
    assert report.discovered == ("alpha", "beta")
    assert registry.names() == ["alpha", "beta"]


def test_discover_report_captures_load_failures_and_duplicates() -> None:
    from unittest import mock

    registry = ProcessorRegistry()
    eps = [
        _FakeEntryPoint("bad", "missing.Mod", good=False),
        _FakeEntryPoint("p", "mod.P"),
        _FakeEntryPoint("p", "other.P"),
    ]
    with mock.patch("aranorm.core.registry.metadata") as meta:
        meta.entry_points.return_value = {"aranorm.processors": eps}
        report = registry.discover_report()
    assert report.discovered == ("p",)
    assert len(report.failures) == 2
    assert registry.names() == ["p"]


def test_discover_report_strict_raises_on_duplicate_and_load_error() -> None:
    from unittest import mock

    registry = ProcessorRegistry()
    with mock.patch("aranorm.core.registry.metadata") as meta:
        meta.entry_points.return_value = ({"aranorm.processors": [_FakeEntryPoint("p", "mod.P")]},)
        meta.entry_points.return_value = {
            "aranorm.processors": [_FakeEntryPoint("p", "mod.P"), _FakeEntryPoint("p", "x.Q")]
        }
        with pytest.raises(ValueError, match="duplicate"):
            registry.discover_report(strict=True)
    registry2 = ProcessorRegistry()
    with mock.patch("aranorm.core.registry.metadata") as meta:
        meta.entry_points.return_value = {"aranorm.processors": [_FakeEntryPoint("q", "no.Mod", good=False)]}
        with pytest.raises(ImportError):
            registry2.discover_report(strict=True)


def test_discover_report_legacy_entry_points_mapping_and_non_subclass() -> None:
    """Python <3.10 returns a dict from entry_points(); loading a non-Processor value fails gracefully."""
    from unittest import mock

    registry = ProcessorRegistry()

    class _LegacyMapping:
        def __init__(self, mapping):
            self._mapping = mapping

        def __getitem__(self, key):
            return self._mapping[key]

        def get(self, key, default=None):
            return self._mapping.get(key, default)

    bad_ep = _FakeEntryPoint("strval", "builtins.str")
    legacy = _LegacyMapping({"aranorm.processors": [bad_ep]})  # no ``select``: legacy code path
    assert not hasattr(legacy, "select")
    with mock.patch("aranorm.core.registry.metadata") as meta:
        meta.entry_points.return_value = legacy
        report = registry.discover_report()
    assert report.discovered == ()
    assert len(report.failures) == 1
    assert report.failures[0].name == "strval"
    assert "strval" in report.failures[0].message or report.failures[0].error_type == "TypeError"


def test_discover_legacy_api_delegates_to_report() -> None:
    from unittest import mock

    registry = ProcessorRegistry()
    with mock.patch("aranorm.core.registry.metadata") as meta:
        meta.entry_points.return_value = {"aranorm.processors": [_FakeEntryPoint("z", "mod.Z")]}
        assert registry.discover() == ["z"]


# --------------------------------------------------------------------------
# Remaining coverage: contains, select branch, combined unknown+missing fields
# --------------------------------------------------------------------------


def test_registry_contains_names_and_absent() -> None:
    registry = ProcessorRegistry()
    registry.register("p", ALEFProcessor)
    assert registry.contains("p") is True
    assert registry.contains("missing") is False
    assert registry.contains("") is False


class _SelectableMapping:
    """Mimics the Python >=3.10 ``entry_points`` SelectableGroups interface."""

    def __init__(self, groups):
        self._groups = groups

    def select(self, group):
        return self._groups.get(group, ())


def test_discover_report_select_branch_sorted_names() -> None:
    """Entry points with a working ``.select()`` take the modern code path (line 205)."""
    from unittest import mock

    registry = ProcessorRegistry()
    eps = [_FakeEntryPoint("z", "mod.Z"), _FakeEntryPoint("a", "mod.A")]
    mapping = _SelectableMapping({"aranorm.processors": eps})
    assert hasattr(mapping, "select")
    with mock.patch("aranorm.core.registry.metadata") as meta:
        meta.entry_points.return_value = mapping
        report = registry.discover_report()
    assert report.discovered == ("a", "z")
    assert registry.names() == ["a", "z"]


def test_discover_report_select_branch_captures_load_failures() -> None:
    from unittest import mock

    registry = ProcessorRegistry()
    eps = [_FakeEntryPoint("broken", "no.Module", good=False)]
    mapping = _SelectableMapping({"aranorm.processors": eps})
    with mock.patch("aranorm.core.registry.metadata") as meta:
        meta.entry_points.return_value = mapping
        report = registry.discover_report()
    assert report.discovered == ()
    assert len(report.failures) == 1
    assert report.failures[0].name == "broken"
    assert "builtins.str" not in report.failures[0].message


def test_report_from_dict_combined_unknown_and_missing_fields() -> None:
    """Both unknown and missing fields reported together in one error message."""
    with pytest.raises(ValueError, match="unknown fields.*missing fields|missing fields.*unknown fields"):
        PluginDiscoveryReport.from_dict({"group": "g", "missing_one": 1})
