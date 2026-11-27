"""AraNorm exception types."""

from aranorm.exceptions.errors import (
    AraNormError,
    BatchProcessingError,
    CheckpointError,
    ConfigurationError,
    DataLoadError,
    DialectDetectionError,
    IntegrationUnavailableError,
    InvalidTextError,
    NormalizationError,
    ProcessingCancelledError,
    ProcessingTimeoutError,
    ProcessorNotFoundError,
    StreamingSessionConflictError,
    StreamingSessionError,
    StreamingSourceChangedError,
)

__all__ = [
    "AraNormError",
    "BatchProcessingError",
    "CheckpointError",
    "ConfigurationError",
    "DataLoadError",
    "DialectDetectionError",
    "IntegrationUnavailableError",
    "InvalidTextError",
    "NormalizationError",
    "ProcessingCancelledError",
    "ProcessingTimeoutError",
    "ProcessorNotFoundError",
    "StreamingSessionConflictError",
    "StreamingSessionError",
    "StreamingSourceChangedError",
]
