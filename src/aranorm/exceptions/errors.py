"""Domain-specific exceptions raised by AraNorm."""

from typing import Optional


class AraNormError(Exception):
    """Base class for all AraNorm errors."""


class NormalizationError(AraNormError):
    """Raised when a processor cannot normalize input."""


class DialectDetectionError(AraNormError):
    """Raised when dialect identification fails."""


class InvalidTextError(AraNormError, ValueError):
    """Raised when the input is not a valid text value."""


class ProcessorNotFoundError(AraNormError, LookupError):
    """Raised when a requested processor is not registered."""


class IntegrationUnavailableError(AraNormError, RuntimeError):
    """Raised when an explicitly requested optional integration is unavailable."""


class ConfigurationError(AraNormError, ValueError):
    """Raised when a pipeline or processor configuration is invalid."""


class ProcessingTimeoutError(AraNormError, RuntimeError):
    """Raised when a processing operation exceeds its time budget."""


class ProcessingCancelledError(AraNormError, RuntimeError):
    """Raised when cooperative cancellation stops a batch operation."""


class DataLoadError(AraNormError, IOError):
    """Raised when a required data file cannot be loaded."""


class StreamingSessionError(AraNormError, RuntimeError):
    """Raised when a resumable streaming session cannot continue safely."""


class CheckpointError(StreamingSessionError, ValueError):
    """Raised when checkpoint metadata is missing, malformed, or incompatible."""


class StreamingSessionConflictError(StreamingSessionError):
    """Raised when another process already owns the same streaming session."""


class StreamingSourceChangedError(StreamingSessionError):
    """Raised when the source changes while a streaming session is running."""


class BatchProcessingError(AraNormError):
    """Raised when one or more items in a batch fail to process.

    Attributes
    ----------
    failed_indices:
        Zero-based indices of the items that failed.
    errors:
        Mapping of index → exception for failed items.
    results:
        Results that were produced before the batch error was raised
        (populated under the ``collect`` policy). ``None`` when absent,
        preserving the original exception shape for existing handlers.
    """

    def __init__(
        self,
        message: str,
        failed_indices: Optional[list] = None,
        errors: Optional[dict] = None,
        results: Optional[list] = None,
    ) -> None:
        super().__init__(message)
        self.failed_indices = list(failed_indices or [])
        self.errors = dict(errors or {})
        self.results = list(results) if results is not None else None
