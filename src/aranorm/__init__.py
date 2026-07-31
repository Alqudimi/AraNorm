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
    DialectTarget,
    NormalizationResult,
    PipelineBuilder,
    PipelineConfig,
    Preset,
    Processor,
    ProcessorContext,
    ProcessorFactory,
    ProcessorRegistry,
    StopWordsConfig,
    StopWordsRegistry,
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
    ProcessingTimeoutError,
    ProcessorNotFoundError,
)

__version__ = "1.2.0"
__author__ = "AraNorm Contributors"
__license__ = "MIT"

__all__ = [
    # Pipeline
    "ArabicNormalizationPipeline",
    "NormalizationResult",
    "PipelineBuilder",
    "PipelineConfig",
    "Preset",
    "DialectTarget",
    # Stop-words
    "StopWordsConfig",
    "StopWordsRegistry",
    # Base abstractions
    "Processor",
    "ProcessorContext",
    "ProcessorFactory",
    "ProcessorRegistry",
    # Exceptions
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
    # Version
    "__version__",
]
