"""Orthographic normalization stage."""

from typing import Optional

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.config import PipelineConfig
from aranorm.processors import (
    ALEFProcessor,
    AlefMaqsuraProcessor,
    ArabiziProcessor,
    DiacriticsProcessor,
    DigitsProcessor,
    LigaturesProcessor,
    PunctuationProcessor,
    RepeatedCharsProcessor,
    RepeatedPunctuationProcessor,
    SpacingProcessor,
    TaaMarbutaProcessor,
    TatweelProcessor,
    UnicodeProcessor,
    WhitespaceProcessor,
)
from aranorm.processors.hamza_processor import HamzaProcessor


class OrthographicNormalizer:
    """Compose orthographic processors from configuration."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.processors = self._build_processors()

    def _build_processors(self) -> list[Processor]:
        """Build enabled orthographic processors."""
        processors: list[Processor] = []
        if self.config.handle_arabizi:
            processors.append(ArabiziProcessor())
        if self.config.normalize_unicode:
            processors.append(UnicodeProcessor())
        if self.config.normalize_ligatures:
            processors.append(LigaturesProcessor())
        if self.config.normalize_alef:
            processors.append(ALEFProcessor())
        if self.config.normalize_alef_maqsura:
            processors.append(AlefMaqsuraProcessor())
        if self.config.normalize_taa_marbuta:
            processors.append(TaaMarbutaProcessor())
        if self.config.normalize_hamza:
            processors.append(HamzaProcessor())
        if self.config.remove_diacritics:
            processors.append(DiacriticsProcessor())
        if self.config.normalize_tatweel:
            processors.append(TatweelProcessor())
        if self.config.normalize_digits:
            processors.append(DigitsProcessor())
        if self.config.normalize_punctuation:
            processors.append(PunctuationProcessor())
        if self.config.normalize_repeated_chars:
            processors.append(RepeatedCharsProcessor())
        if self.config.remove_extra_punctuation:
            processors.append(RepeatedPunctuationProcessor())
        if self.config.fix_spacing:
            processors.append(SpacingProcessor())
        if self.config.normalize_whitespace:
            processors.append(WhitespaceProcessor())
        return processors

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Normalize text with all configured processors."""
        for processor in self.processors:
            text = processor.process(text, context)
        return text
