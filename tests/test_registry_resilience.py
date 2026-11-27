"""Resilience contracts for processor plugin discovery."""

import pytest

from aranorm import Processor, ProcessorRegistry


class ReportProcessor(Processor):
    name = "report"

    def process(self, text: str, context=None) -> str:
        return text


class FakeEntryPoint:
    def __init__(self, name: str, loaded: object, value: str = "") -> None:
        self.name = name
        self.value = value
        self._loaded = loaded

    def load(self) -> object:
        if isinstance(self._loaded, Exception):
            raise self._loaded
        return self._loaded


class FakeEntryPoints:
    def __init__(self, entries: list[FakeEntryPoint]) -> None:
        self.entries = entries

    def select(self, *, group: str) -> list[FakeEntryPoint]:
        assert group == "aranorm.processors"
        return self.entries


def test_discovery_report_is_deterministic_and_serializable(monkeypatch: pytest.MonkeyPatch) -> None:
    from aranorm.core import registry as registry_module

    monkeypatch.setattr(
        registry_module.metadata,
        "entry_points",
        lambda: FakeEntryPoints(
            [
                FakeEntryPoint("zeta", ReportProcessor, "zeta:Processor"),
                FakeEntryPoint("alpha", ReportProcessor, "alpha:Processor"),
            ]
        ),
    )

    report = ProcessorRegistry().discover_report()

    assert report.discovered == ("alpha", "zeta")
    assert report.failures == ()
    assert report.to_dict()["discovered"] == ["alpha", "zeta"]


def test_discovery_report_isolates_invalid_and_duplicate_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    from aranorm.core import registry as registry_module

    monkeypatch.setattr(
        registry_module.metadata,
        "entry_points",
        lambda: FakeEntryPoints(
            [
                FakeEntryPoint("plugin", ReportProcessor, "a:Processor"),
                FakeEntryPoint("plugin", ReportProcessor, "b:Processor"),
                FakeEntryPoint("broken", object, "broken:object"),
            ]
        ),
    )

    registry = ProcessorRegistry()
    report = registry.discover_report()

    assert report.discovered == ("plugin",)
    assert registry.names() == ["plugin"]
    assert {failure.name for failure in report.failures} == {"broken", "plugin"}
    assert all(failure.error_type for failure in report.failures)


def test_discovery_report_strict_duplicate_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    from aranorm.core import registry as registry_module

    monkeypatch.setattr(
        registry_module.metadata,
        "entry_points",
        lambda: FakeEntryPoints(
            [
                FakeEntryPoint("plugin", ReportProcessor, "a:Processor"),
                FakeEntryPoint("plugin", ReportProcessor, "b:Processor"),
            ]
        ),
    )

    with pytest.raises(ValueError, match="duplicate"):
        ProcessorRegistry().discover_report(strict=True)
