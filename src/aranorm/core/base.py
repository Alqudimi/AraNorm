"""Abstractions shared by all processors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ProcessorContext:
    """Mutable metadata bag passed through every stage of a pipeline.

    Attributes
    ----------
    applied_steps:
        Ordered list of processor names that have run.
    metadata:
        Free-form key/value store for inter-processor communication.

    Example
    -------
    >>> ctx = ProcessorContext()
    >>> ctx.record("alef_normalizer")
    >>> ctx.applied_steps
    ['alef_normalizer']
    """

    applied_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    _trace_enabled: bool = field(default=False, repr=False)
    _trace: List[Tuple[str, str]] = field(default_factory=list, repr=False)

    def record(self, step: str) -> None:
        """Append *step* to :attr:`applied_steps` if not already present.

        Duplicate recording is silently ignored so processors can call this
        method unconditionally without checking for previous execution.

        Parameters
        ----------
        step:
            A human-readable processor/stage identifier.
        """
        if step not in self.applied_steps:
            self.applied_steps.append(step)
        if self._trace_enabled:
            self._trace.append((step, "record"))

    def enable_trace(self) -> None:
        """Opt in to detailed ``(step, action)`` recording for this context.

        Tracing is explicitly opt-in: when disabled (the default), the trace
        list stays empty and no additional bookkeeping affects processing.
        """
        self._trace_enabled = True

    def steps_trace(self) -> List[Tuple[str, str]]:
        """Return a copy of the recorded ``(step, action)`` trace.

        Returns an empty list when tracing was never enabled, keeping the
        contract stable for callers that never opt in.
        """
        return [(step, action) for step, action in self._trace]

    def record_always(self, step: str) -> None:
        """Append *step* even if it was already recorded.

        Useful for processors that are allowed to run multiple times in the
        same pipeline pass (e.g. repeated-whitespace cleanup after each stage).

        Parameters
        ----------
        step:
            A human-readable processor/stage identifier.
        """
        self.applied_steps.append(step)
        if self._trace_enabled:
            self._trace.append((step, "record_always"))

    def set(self, key: str, value: Any) -> None:
        """Store *value* in the metadata dict under *key*.

        Parameters
        ----------
        key:
            Metadata key.
        value:
            Any JSON-serialisable value.
        """
        self.metadata[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a metadata value by *key*.

        Parameters
        ----------
        key:
            Metadata key.
        default:
            Returned when *key* is absent (default *None*).
        """
        return self.metadata.get(key, default)

    def merge(self, other: "ProcessorContext") -> None:
        """Merge *other* context into this one.

        Applied steps from *other* are appended (without duplicates).
        Metadata keys from *other* overwrite keys in this context.

        Parameters
        ----------
        other:
            Another :class:`ProcessorContext` whose data should be merged in.
        """
        for step in other.applied_steps:
            self.record(step)
        self.metadata.update(other.metadata)
        if self._trace_enabled and other._trace_enabled:
            self._trace.extend((step, "merge") for step, _ in other.steps_trace())


class Processor(ABC):
    """Minimal interface that every text processor must implement.

    Subclasses should define a unique :attr:`name` class attribute used
    for logging, registry keys, and the :attr:`~ProcessorContext.applied_steps`
    list.
    """

    name: str = "processor"

    @abstractmethod
    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Transform *text* and optionally update *context*.

        Parameters
        ----------
        text:
            Input string to transform.
        context:
            Optional mutable context shared across the pipeline stages.

        Returns
        -------
        str
            The transformed text.
        """

    def _record(self, context: Optional[ProcessorContext]) -> None:
        """Record this processor's :attr:`name` in *context* when provided."""
        if context is not None:
            context.record(self.name)
