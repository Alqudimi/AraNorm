"""Registry contract and concurrency tests."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from aranorm import Processor, ProcessorRegistry
from aranorm.exceptions import ProcessorNotFoundError


class DemoProcessor(Processor):
    name = "demo"

    def process(self, text: str, context=None) -> str:
        return text


def test_registry_rejects_non_processor_classes() -> None:
    registry = ProcessorRegistry()
    with pytest.raises(TypeError, match="Processor subclass"):
        registry.register("invalid", object)  # type: ignore[arg-type]


def test_registry_snapshot_is_independent() -> None:
    registry = ProcessorRegistry()
    registry.register("demo", DemoProcessor)

    snapshot = registry.snapshot()
    snapshot.clear()

    assert registry.names() == ["demo"]


def test_registry_unregister_returns_class_and_reports_missing() -> None:
    registry = ProcessorRegistry()
    registry.register("demo", DemoProcessor)

    assert registry.unregister("demo") is DemoProcessor
    with pytest.raises(ProcessorNotFoundError):
        registry.unregister("demo")


def test_registry_supports_concurrent_reads_and_writes() -> None:
    registry = ProcessorRegistry()

    def register(index: int) -> None:
        registry.register(f"demo-{index}", DemoProcessor)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(register, range(100)))

    assert len(registry) == 100
    assert registry.contains("demo-42")
    assert len(list(registry)) == 100


class FakeEntryPoint:
    def __init__(self, name: str, loaded: object) -> None:
        self.name = name
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


def test_registry_discovers_valid_entry_points(monkeypatch: pytest.MonkeyPatch) -> None:
    from aranorm.core import registry as registry_module

    monkeypatch.setattr(
        registry_module.metadata,
        "entry_points",
        lambda: FakeEntryPoints([FakeEntryPoint("plugin", DemoProcessor)]),
    )
    registry = ProcessorRegistry()

    assert registry.discover() == ["plugin"]
    assert registry.get("plugin") is DemoProcessor


def test_registry_skips_invalid_entry_points_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from aranorm.core import registry as registry_module

    monkeypatch.setattr(
        registry_module.metadata,
        "entry_points",
        lambda: FakeEntryPoints([FakeEntryPoint("valid", DemoProcessor), FakeEntryPoint("invalid", object)]),
    )
    registry = ProcessorRegistry()

    assert registry.discover() == ["valid"]
    assert registry.names() == ["valid"]


def test_registry_discovery_strict_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from aranorm.core import registry as registry_module

    monkeypatch.setattr(
        registry_module.metadata,
        "entry_points",
        lambda: FakeEntryPoints([FakeEntryPoint("broken", RuntimeError("broken plugin"))]),
    )
    with pytest.raises(RuntimeError, match="broken plugin"):
        ProcessorRegistry().discover(strict=True)
