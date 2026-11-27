"""Registry and factory support for custom processors."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from importlib import metadata
from typing import Dict, Iterable, Iterator, List, Optional, Tuple, Type, TypeVar, cast

from aranorm.core.base import Processor
from aranorm.exceptions import ProcessorNotFoundError

ProcessorType = TypeVar("ProcessorType", bound=Processor)


@dataclass(frozen=True)
class PluginDiscoveryFailure:
    """A non-fatal plugin discovery failure with sanitized diagnostics."""

    name: str
    group: str
    error_type: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        """Return a JSON-compatible diagnostic dictionary."""
        return {
            "name": self.name,
            "group": self.group,
            "error_type": self.error_type,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "PluginDiscoveryFailure":
        """Restore a failure from a validated JSON-compatible mapping."""
        if not isinstance(payload, dict):
            raise ValueError("plugin failure payload must be an object")
        expected = {"name", "group", "error_type", "message"}
        fields = set(payload)
        if fields != expected:
            unknown = sorted(fields - expected)
            missing = sorted(expected - fields)
            details = []
            if unknown:
                details.append("unknown fields: " + ", ".join(unknown))
            if missing:
                details.append("missing fields: " + ", ".join(missing))
            raise ValueError("invalid plugin failure payload (" + "; ".join(details) + ")")
        if not all(isinstance(payload[field], str) for field in expected):
            raise ValueError("plugin failure fields must all be strings")
        return cls(
            name=payload["name"],
            group=payload["group"],
            error_type=payload["error_type"],
            message=payload["message"],
        )


@dataclass(frozen=True)
class PluginDiscoveryReport:
    """Deterministic result of an entry-point discovery attempt."""

    group: str
    discovered: Tuple[str, ...]
    failures: Tuple[PluginDiscoveryFailure, ...]

    @property
    def ok(self) -> bool:
        """Return whether every candidate was loaded successfully."""
        return not self.failures

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-compatible report without plugin objects."""
        return {
            "group": self.group,
            "ok": self.ok,
            "discovered": list(self.discovered),
            "failures": [failure.to_dict() for failure in self.failures],
        }

    @classmethod
    def from_dict(cls, payload: object) -> "PluginDiscoveryReport":
        """Restore a report from a validated JSON-compatible mapping."""
        if not isinstance(payload, dict):
            raise ValueError("plugin discovery report payload must be an object")
        expected = {"group", "ok", "discovered", "failures"}
        fields = set(payload)
        if fields != expected:
            unknown = sorted(fields - expected)
            missing = sorted(expected - fields)
            details = []
            if unknown:
                details.append("unknown fields: " + ", ".join(unknown))
            if missing:
                details.append("missing fields: " + ", ".join(missing))
            raise ValueError("invalid plugin discovery report payload (" + "; ".join(details) + ")")

        group = payload["group"]
        ok = payload["ok"]
        discovered = payload["discovered"]
        failures = payload["failures"]
        if not isinstance(group, str) or not isinstance(ok, bool):
            raise ValueError("plugin discovery report group must be a string and ok must be boolean")
        if not isinstance(discovered, (list, tuple)) or not all(isinstance(name, str) for name in discovered):
            raise ValueError("plugin discovery report discovered must be a list of strings")
        if not isinstance(failures, (list, tuple)):
            raise ValueError("plugin discovery report failures must be a list")
        restored_failures = []
        for failure in failures:
            try:
                restored_failures.append(PluginDiscoveryFailure.from_dict(failure))
            except ValueError as error:
                raise ValueError("invalid plugin discovery failure in report") from error
        if ok != (not restored_failures):
            raise ValueError("plugin discovery report ok flag is inconsistent with failures")
        return cls(group=group, discovered=tuple(discovered), failures=tuple(restored_failures))


class ProcessorRegistry:
    """Named registry for processor classes.

    Example
    -------
    >>> registry = ProcessorRegistry()
    >>> registry.register("my_proc", MyProcessor)
    >>> registry.names()
    ['my_proc']
    """

    def __init__(self) -> None:
        self._processors: Dict[str, Type[Processor]] = {}
        self._lock = threading.RLock()

    def register(self, name: str, processor: Type[Processor]) -> None:
        """Register a processor class under a stable name.

        Parameters
        ----------
        name:
            Unique, non-empty identifier for the processor.
        processor:
            A class (not an instance) that subclasses :class:`Processor`.
        """
        if not name.strip():
            raise ValueError("processor name cannot be empty")
        if not isinstance(processor, type) or not issubclass(processor, Processor):
            raise TypeError("processor must be a Processor subclass")
        with self._lock:
            self._processors[name] = processor

    def get(self, name: str) -> Type[Processor]:
        """Return a registered class or raise a descriptive error.

        Parameters
        ----------
        name:
            Processor name as given to :meth:`register`.

        Raises
        ------
        ProcessorNotFoundError
            When *name* is not registered.
        """
        try:
            with self._lock:
                return self._processors[name]
        except KeyError as error:
            available = ", ".join(self.names()) or "<none>"
            raise ProcessorNotFoundError(f"processor '{name}' is not registered. " f"Available: {available}") from error

    def names(self) -> List[str]:
        """Return all registered processor names in alphabetical order."""
        with self._lock:
            return sorted(self._processors)

    def contains(self, name: str) -> bool:
        """Return *True* when *name* is registered."""
        with self._lock:
            return name in self._processors

    def unregister(self, name: str) -> Type[Processor]:
        """Remove and return a registered processor class."""
        with self._lock:
            try:
                return self._processors.pop(name)
            except KeyError as error:
                raise ProcessorNotFoundError(f"processor '{name}' is not registered") from error

    def snapshot(self) -> Dict[str, Type[Processor]]:
        """Return a shallow copy of the registry for introspection."""
        with self._lock:
            return dict(self._processors)

    def discover_report(self, group: str = "aranorm.processors", *, strict: bool = False) -> PluginDiscoveryReport:
        """Discover plugins and return deterministic success/failure diagnostics.

        Discovery candidates are sorted by entry-point name and value. Duplicate
        names are reported and ignored after the first deterministic candidate.
        With ``strict=True`` the original loading error, or an explicit duplicate
        error, is raised immediately.
        """
        entry_points = cast(object, metadata.entry_points())
        if hasattr(entry_points, "select"):
            selected = cast(Iterable[metadata.EntryPoint], entry_points.select(group=group))
        else:
            legacy = cast(Dict[str, Iterable[metadata.EntryPoint]], entry_points)
            selected = legacy.get(group, ())

        candidates = sorted(
            list(selected),
            key=lambda entry_point: (
                str(getattr(entry_point, "name", "<unknown>")),
                str(getattr(entry_point, "value", "")),
            ),
        )
        discovered = set()
        failures: List[PluginDiscoveryFailure] = []

        for entry_point in candidates:
            name = str(getattr(entry_point, "name", "<unknown>"))
            if name in discovered:
                error = ValueError(f"duplicate plugin entry point '{name}'")
                if strict:
                    raise error
                failures.append(PluginDiscoveryFailure(name, group, type(error).__name__, str(error)))
                continue
            try:
                loaded = entry_point.load()
                if not isinstance(loaded, type) or not issubclass(loaded, Processor):
                    raise TypeError(f"entry point '{name}' must expose a Processor subclass")
                self.register(name, loaded)
            except Exception as error:  # noqa: BLE001
                if strict:
                    raise
                failures.append(PluginDiscoveryFailure(name, group, type(error).__name__, str(error)))
                continue
            discovered.add(name)

        ordered_failures = tuple(
            sorted(
                failures,
                key=lambda failure: (failure.name, failure.error_type, failure.message),
            )
        )
        return PluginDiscoveryReport(group, tuple(sorted(discovered)), ordered_failures)

    def discover(self, group: str = "aranorm.processors", *, strict: bool = False) -> List[str]:
        """Discover and register plugins, preserving the legacy list API.

        Loading failures are skipped by default and raised in strict mode. For
        machine-readable diagnostics use :meth:`discover_report`.
        """
        return list(self.discover_report(group, strict=strict).discovered)

    def __len__(self) -> int:
        with self._lock:
            return len(self._processors)

    def __iter__(self) -> Iterator[str]:
        return iter(self.names())

    def __contains__(self, name: object) -> bool:
        with self._lock:
            return name in self._processors


class ProcessorFactory:
    """Factory facade backed by a :class:`ProcessorRegistry`.

    Example
    -------
    >>> factory = ProcessorFactory()
    >>> factory.register("alef", ALEFProcessor)
    >>> proc = factory.create("alef")
    >>> proc.process("إبراهيم")
    'ابراهيم'
    """

    def __init__(self, registry: Optional[ProcessorRegistry] = None) -> None:
        self.registry: ProcessorRegistry = registry if registry is not None else ProcessorRegistry()

    def register(self, name: str, processor: Type[Processor]) -> None:
        """Register a processor class.

        Parameters
        ----------
        name:
            Unique identifier.
        processor:
            :class:`Processor` subclass to register.
        """
        self.registry.register(name, processor)

    def create(self, name: str, **kwargs: object) -> Processor:
        """Instantiate a registered processor.

        Parameters
        ----------
        name:
            Registered processor name.
        **kwargs:
            Constructor arguments forwarded to the processor class.
        """
        return self.registry.get(name)(**kwargs)

    def available(self) -> List[str]:
        """Return all registered processor names."""
        return self.registry.names()
