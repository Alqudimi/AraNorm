"""AraNorm exception types."""

from aranorm.exceptions.errors import (
    AraNormError,
    BatchProcessingError,
    ConfigurationError,
    DataLoadError,
    DialectDetectionError,
    IntegrationUnavailableError,
    InvalidTextError,
    NormalizationError,
    ProcessingTimeoutError,
    ProcessorNotFoundError,
)

__all__ = [
    "AraNormError",
    "BatchProcessingError",
    "ConfigurationError",
    "DataLoadError",
    "DialectDetectionError",
    "IntegrationUnavailableError",
    "InvalidTextError",
    "NormalizationError",
    "ProcessingTimeoutError",
    "ProcessorNotFoundError",
]
