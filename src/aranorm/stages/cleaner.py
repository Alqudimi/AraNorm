"""Content cleaning stage."""

from typing import Optional

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.config import PipelineConfig
from aranorm.processors import (
    EmailProcessor,
    EmojiProcessor,
    HashtagProcessor,
    HTMLProcessor,
    MentionProcessor,
    NonArabicProcessor,
    URLProcessor,
    WhitespaceProcessor,
)


class ContentCleaner:
    """Compose content-cleaning processors from a pipeline configuration."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.processors = self._build_processors()

    def _build_processors(self) -> list[Processor]:
        """Build enabled cleaning processors in deterministic order."""
        processors: list[Processor] = []
        if self.config.clean_html:
            processors.append(HTMLProcessor())
        if self.config.clean_urls:
            processors.append(URLProcessor())
        if self.config.clean_emails:
            processors.append(EmailProcessor())
        if self.config.clean_mentions:
            processors.append(MentionProcessor())
        if self.config.clean_hashtags:
            processors.append(HashtagProcessor())
        if self.config.clean_emojis:
            processors.append(EmojiProcessor())
        if self.config.remove_non_arabic:
            processors.append(NonArabicProcessor())
        if self.config.remove_english:
            from aranorm.processors.text_cleaning_processors import EnglishProcessor

            processors.append(EnglishProcessor())
        if self.config.normalize_whitespace:
            processors.append(WhitespaceProcessor())
        return processors

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Clean text with all configured processors."""
        for processor in self.processors:
            text = processor.process(text, context)
        return text
