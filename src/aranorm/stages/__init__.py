"""High-level AraNorm pipeline stages."""

from aranorm.stages.cleaner import ContentCleaner
from aranorm.stages.dialect_id import ALL_DIALECT_LABELS, DialectIdentification, DialectIdentifier
from aranorm.stages.dialect_norm import (
    DialectNormalizer,
    DialectStrategy,
    ModelDialectStrategy,
    RuleBasedCODAStrategy,
    RuleBasedMSAStrategy,
)
from aranorm.stages.morphological import MorphologicalProcessor
from aranorm.stages.normalizer import OrthographicNormalizer
from aranorm.stages.stop_words_stage import StopWordsStage

# Alias for backwards-compat and for the prompt API
DialectProcessor = DialectNormalizer

__all__ = [
    "ALL_DIALECT_LABELS",
    "ContentCleaner",
    "DialectIdentification",
    "DialectIdentifier",
    "DialectNormalizer",
    "DialectProcessor",
    "DialectStrategy",
    "ModelDialectStrategy",
    "MorphologicalProcessor",
    "OrthographicNormalizer",
    "RuleBasedCODAStrategy",
    "RuleBasedMSAStrategy",
    "StopWordsStage",
]
