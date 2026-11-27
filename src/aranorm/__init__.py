"""AraNorm: a composable Arabic text normalization stack.

Quick start::

    from aranorm import ArabicNormalizationPipeline, PipelineConfig

    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))
    result = pipeline.process("شلونك حبيبي؟")
    print(result.normalized_text, result.dialect)

Stop-words quick start::

    from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

    config = PipelineConfig(
        preset="standard",
        stop_words_config=StopWordsConfig(mode="remove", scope="universal"),
    )
    pipeline = ArabicNormalizationPipeline(config)
    result = pipeline.process("أنا سعيد جداً اليوم")
    print(result.stop_words_removed)   # → "سعيد جداً"
    print(result.stop_words_found)     # → {"أنا", "اليوم"}

Text analysis quick start::

    from aranorm.analysis import TextAnalyzer, KeywordExtractor, SentimentAnalyzer
    from aranorm.analysis.spelling_report import analyze_spelling
    from aranorm.analysis.quality_score import analyze_quality
    from aranorm.analysis.batch_analysis import analyze_batch
    from aranorm.utils import compute_stats, word_tokenize, stem, extract_root

    analyzer = TextAnalyzer()
    result = analyzer.analyze("النص العربي الذي تريد تحليله")
    print(result.content_words)

    sa = SentimentAnalyzer()
    sentiment = sa.analyze("هذا المنتج رائع جداً")
    print(sentiment.label, sentiment.score)

Caching & export::

    from aranorm.utils import NormalizationCache, BatchExporter

    cache = NormalizationCache(pipeline, maxsize=10000)
    result = cache.process("شلونك؟")  # first call computes, subsequent calls are instant

    results = pipeline.process_batch(texts)
    exporter = BatchExporter(results)
    exporter.to_csv("output.csv")
    exporter.to_jsonl("output.jsonl")

Config serialization::

    cfg = PipelineConfig(preset="deep")
    json_str = cfg.to_json()
    cfg2 = PipelineConfig.from_json(json_str)
    assert cfg2.preset == cfg.preset
"""

from aranorm.core import (
    ArabicNormalizationPipeline,
    BatchProcessingPolicy,
    CancellationToken,
    DialectTarget,
    NormalizationResult,
    PipelineBuilder,
    PipelineConfig,
    PipelineHooks,
    ResourceLimits,
    Preset,
    Processor,
    ProcessorContext,
    PluginDiscoveryFailure,
    PluginDiscoveryReport,
    ProcessorFactory,
    ProcessorRegistry,
    ProcessingMetrics,
    ProcessingMetricsSnapshot,
    StopWordsConfig,
    StopWordsRegistry,
    BatchRetryPolicy,
    BatchRetryReport,
    PipelineRuntime,
    ReloadResult,
    RuntimeHealth,
    PipelineSpec,
    PIPELINE_SPEC_SCHEMA_VERSION,
    DEFAULT_MAX_SPEC_BYTES,
    CHECKPOINT_SCHEMA_VERSION,
    DEFAULT_CHECKPOINT_MAX_BYTES,
    DEFAULT_FINGERPRINT_CHUNK_BYTES,
    DEFAULT_SESSION_LOCK_SUFFIX,
    StreamCheckpoint,
    StreamingSession,
    StreamingSessionReport,
    fingerprint_file,
)
from aranorm.analysis.spelling_report import (
    SpellingAnalyzer,
    analyze_spelling,
    SpellingReport,
)
from aranorm.analysis.quality_score import (
    QualityScoreAnalyzer,
    analyze_quality,
    TextQualityScore,
)
from aranorm.analysis.batch_analysis import (
    BatchAnalyzer,
    analyze_batch,
    BatchAnalysisReport,
    QualityDistribution,
)
from aranorm.exceptions import (
    AraNormError,
    BatchProcessingError,
    ConfigurationError,
    DataLoadError,
    DialectDetectionError,
    IntegrationUnavailableError,
    InvalidTextError,
    NormalizationError,
    ProcessingCancelledError,
    ProcessingTimeoutError,
    ProcessorNotFoundError,
    CheckpointError,
    StreamingSessionConflictError,
    StreamingSessionError,
    StreamingSourceChangedError,
)

__version__ = "1.15.0"
__author__ = "AraNorm Contributors"
__license__ = "MIT"

__all__ = [
    # Pipeline
    "ArabicNormalizationPipeline",
    "BatchProcessingPolicy",
    "CancellationToken",
    "NormalizationResult",
    "PipelineBuilder",
    "PipelineConfig",
    "PipelineHooks",
    "ResourceLimits",
    "Preset",
    "DialectTarget",
    # Stop-words
    "StopWordsConfig",
    "StopWordsRegistry",
    # Base abstractions
    "Processor",
    "ProcessorContext",
    "PluginDiscoveryFailure",
    "PluginDiscoveryReport",
    "ProcessorFactory",
    "ProcessorRegistry",
    "ProcessingMetrics",
    "ProcessingMetricsSnapshot",
    "BatchRetryPolicy",
    "BatchRetryReport",
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
    # Exceptions
    "AraNormError",
    "BatchProcessingError",
    "ConfigurationError",
    "DataLoadError",
    "DialectDetectionError",
    "IntegrationUnavailableError",
    "InvalidTextError",
    "NormalizationError",
    "ProcessingCancelledError",
    "ProcessingTimeoutError",
    "ProcessorNotFoundError",
    "CheckpointError",
    "StreamingSessionConflictError",
    "StreamingSessionError",
    "StreamingSourceChangedError",
    # Advanced analysis
    "SpellingAnalyzer",
    "analyze_spelling",
    "SpellingReport",
    "QualityScoreAnalyzer",
    "analyze_quality",
    "TextQualityScore",
    "BatchAnalyzer",
    "analyze_batch",
    "BatchAnalysisReport",
    "QualityDistribution",
    # Version
    "__version__",
]
