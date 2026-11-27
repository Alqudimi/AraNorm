"""Stable structural contracts shared by the public processing surfaces.

The contracts in this module intentionally use :class:`typing.Protocol` so
applications can provide their own callbacks without inheriting AraNorm
classes.  Runtime implementations remain in their existing modules to keep
imports lightweight and backwards compatible.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from aranorm.core.pipeline import NormalizationResult


@runtime_checkable
class ProgressCallbackProtocol(Protocol):
    """Structural callback contract for bounded and batch processing.

    A callback receives one lifecycle event before processing, one event per
    input item, and a final event regardless of normal completion or failure.
    """

    def on_start(self, total: int) -> None:
        """Signal the beginning of a processing stream."""

    def on_item(self, index: int, text: str, success: bool) -> None:
        """Signal completion of one input item."""

    def on_finish(self) -> None:
        """Signal the end of a processing stream."""


class CancellationToken:
    """Thread-safe cooperative cancellation signal for batch operations.

    Cancellation is observed between input items and at safe batch boundaries;
    AraNorm never forcefully interrupts a worker thread already executing a
    processor.
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation for the associated operation."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """Raise the public cancellation error when cancellation was requested."""
        if self.is_cancelled:
            from aranorm.exceptions import ProcessingCancelledError

            raise ProcessingCancelledError("Processing was cancelled cooperatively")


ErrorHandler = Callable[[int, str, Exception], Optional[str]]
"""Convert a failed item to fallback text, or return ``None`` to skip it."""


@dataclass(frozen=True)
class BatchProcessingPolicy:
    """Explicit policy for item failures during batch processing.

    ``fail_fast`` preserves the strict default and raises the first error.
    ``collect`` processes the complete input and raises one
    :class:`~aranorm.exceptions.BatchProcessingError` containing all failures.
    ``skip`` tolerates failures and yields only successful or fallback results.
    The existing ``on_error`` callback remains the compatible mechanism for
    supplying fallback text; this policy only controls what happens when the
    original and fallback processing both fail.
    """

    mode: Literal["fail_fast", "collect", "skip"] = "fail_fast"

    def __post_init__(self) -> None:
        if self.mode not in {"fail_fast", "collect", "skip"}:
            raise ValueError("mode must be one of: fail_fast, collect, skip")


BeforeProcessHook = Callable[[str], str]
AfterProcessHook = Callable[["NormalizationResult"], None]
ProcessErrorHook = Callable[[str, Exception], None]


@dataclass(frozen=True)
class BatchRetryPolicy:
    """Validated settings for bounded retry operations.

    The policy is intentionally independent from :class:`BatchProcessingPolicy`:
    it controls retry mechanics while the latter controls item-failure
    handling.  ``fail_fast`` is not represented here because retry requires a
    complete failure set from the initial pass.
    """

    max_retries: int = 3
    batch_size: int = 32
    n_workers: int = 1

    def __post_init__(self) -> None:
        for name, value in (
            ("max_retries", self.max_retries),
            ("batch_size", self.batch_size),
            ("n_workers", self.n_workers),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer")
        if not 0 <= self.max_retries <= 10:
            raise ValueError("max_retries must be between 0 and 10")
        if self.batch_size < 1:
            raise ValueError("batch_size must be positive")
        if self.n_workers < 1:
            raise ValueError("n_workers must be positive")

    def to_dict(self) -> Dict[str, int]:
        """Return a defensive JSON-serializable representation."""
        return {
            "max_retries": self.max_retries,
            "batch_size": self.batch_size,
            "n_workers": self.n_workers,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchRetryPolicy":
        """Create a policy from a strict mapping without retaining aliases."""
        if not isinstance(data, dict):
            raise TypeError("retry_policy must be a dictionary")
        valid_fields = {"max_retries", "batch_size", "n_workers"}
        unknown = sorted(set(data) - valid_fields)
        if unknown:
            raise ValueError("Unknown BatchRetryPolicy field(s): " + ", ".join(unknown))
        return cls(**dict(data))


@dataclass(frozen=True)
class BatchRetryReport:
    """Outcome of a bounded-retry batch processing pass.

    ``results`` contains only the items that eventually produced a
    :class:`~aranorm.core.pipeline.NormalizationResult`; ``failed_indices``
    are the original zero-based input positions that never succeeded. The
    ``retry_report`` summary makes the number of extra attempts observable
    for monitoring dashboards without leaking input text.
    """

    results: List[Any] = field(default_factory=list)
    failed_indices: List[int] = field(default_factory=list)
    retry_report: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable defensive representation.

        Result objects are serialised through their own ``to_dict`` when
        available; failed entries keep only their index so input text is
        never leaked into the report.
        """
        return {
            "results": [item.to_dict() if hasattr(item, "to_dict") else item for item in self.results],
            "failed_indices": list(self.failed_indices),
            "retry_report": {
                "total_inputs": self.retry_report.get("total_inputs"),
                "max_retries": self.retry_report.get("max_retries"),
                "retry_attempts": self.retry_report.get("retry_attempts"),
                "recovered_count": self.retry_report.get("recovered_count"),
            },
        }


@dataclass(frozen=True)
class PipelineHooks:
    """Optional extension points around one-item processing.

    Hooks are deliberately observational or text-to-text: they do not replace
    the pipeline and are never required for normal operation. Exceptions from
    an ``after_process`` hook are treated as processing failures; exceptions
    from ``on_error`` are suppressed so the original failure remains visible.
    """

    before_process: Optional[BeforeProcessHook] = None
    after_process: Optional[AfterProcessHook] = None
    on_error: Optional[ProcessErrorHook] = None
