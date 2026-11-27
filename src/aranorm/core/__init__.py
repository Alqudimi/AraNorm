"""Core pipeline API."""

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.config import DialectTarget, PipelineConfig, Preset, ResourceLimits
from aranorm.core.contracts import (
    BatchProcessingPolicy,
    BatchRetryPolicy,
    BatchRetryReport,
    CancellationToken,
    ErrorHandler,
    PipelineHooks,
    ProgressCallbackProtocol,
)
from aranorm.core.metrics import ProcessingMetrics, ProcessingMetricsSnapshot
from aranorm.core.pipeline import ArabicNormalizationPipeline, NormalizationResult, PipelineBuilder
from aranorm.core.runtime import PipelineRuntime, ReloadResult, RuntimeHealth
from aranorm.core.spec import DEFAULT_MAX_SPEC_BYTES, PIPELINE_SPEC_SCHEMA_VERSION, PipelineSpec
from aranorm.core.streaming import (
    CHECKPOINT_SCHEMA_VERSION,
    DEFAULT_CHECKPOINT_MAX_BYTES,
    DEFAULT_FINGERPRINT_CHUNK_BYTES,
    DEFAULT_SESSION_LOCK_SUFFIX,
    StreamCheckpoint,
    StreamingSession,
    StreamingSessionReport,
    fingerprint_file,
)
from aranorm.core.registry import (
    PluginDiscoveryFailure,
    PluginDiscoveryReport,
    ProcessorFactory,
    ProcessorRegistry,
)
from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.core.stop_words_registry import StopWordsRegistry

__all__ = [
    "ArabicNormalizationPipeline",
    "BatchProcessingPolicy",
    "BatchRetryPolicy",
    "BatchRetryReport",
    "CancellationToken",
    "DialectTarget",
    "ErrorHandler",
    "NormalizationResult",
    "ProgressCallbackProtocol",
    "PipelineBuilder",
    "PipelineHooks",
    "ProcessingMetrics",
    "ProcessingMetricsSnapshot",
    "PipelineConfig",
    "Preset",
    "ResourceLimits",
    "Processor",
    "ProcessorContext",
    "PluginDiscoveryFailure",
    "PluginDiscoveryReport",
    "ProcessorFactory",
    "ProcessorRegistry",
    "StopWordsConfig",
    "StopWordsRegistry",
    "PipelineRuntime",
    "ReloadResult",
    "RuntimeHealth",
    "PipelineSpec",
    "PIPELINE_SPEC_SCHEMA_VERSION",
    "DEFAULT_MAX_SPEC_BYTES",
    "CHECKPOINT_SCHEMA_VERSION",
    "DEFAULT_CHECKPOINT_MAX_BYTES",
    "DEFAULT_FINGERPRINT_CHUNK_BYTES",
    "DEFAULT_SESSION_LOCK_SUFFIX",
    "StreamCheckpoint",
    "StreamingSession",
    "StreamingSessionReport",
    "fingerprint_file",
]
