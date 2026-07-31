"""Registry and factory support for custom processors."""

from __future__ import annotations

from typing import Dict, Iterator, List, Optional, Type, TypeVar

from aranorm.core.base import Processor
from aranorm.exceptions import ProcessorNotFoundError

ProcessorType = TypeVar("ProcessorType", bound=Processor)


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
            return self._processors[name]
        except KeyError as error:
            available = ", ".join(sorted(self._processors)) or "<none>"
            raise ProcessorNotFoundError(
                f"processor '{name}' is not registered. "
                f"Available: {available}"
            ) from error

    def names(self) -> List[str]:
        """Return all registered processor names in alphabetical order."""
        return sorted(self._processors)

    def contains(self, name: str) -> bool:
        """Return *True* when *name* is registered."""
        return name in self._processors

    def __len__(self) -> int:
        return len(self._processors)

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._processors))

    def __contains__(self, name: object) -> bool:
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
        self.registry: ProcessorRegistry = registry or ProcessorRegistry()

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
