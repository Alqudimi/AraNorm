"""Core pipeline API."""

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.config import DialectTarget, PipelineConfig, Preset
from aranorm.core.pipeline import ArabicNormalizationPipeline, NormalizationResult, PipelineBuilder
from aranorm.core.registry import ProcessorFactory, ProcessorRegistry
from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.core.stop_words_registry import StopWordsRegistry

__all__ = [
    "ArabicNormalizationPipeline",
    "DialectTarget",
    "NormalizationResult",
    "PipelineBuilder",
    "PipelineConfig",
    "Preset",
    "Processor",
    "ProcessorContext",
    "ProcessorFactory",
    "ProcessorRegistry",
    "StopWordsConfig",
    "StopWordsRegistry",
]
