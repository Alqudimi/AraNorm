"""Public processor exports for AraNorm."""

from aranorm.processors.alef_processor import ALEFProcessor
from aranorm.processors.arabizi_processor import ArabiziProcessor
from aranorm.processors.arabizi_stop_processor import ArabiziStopProcessor
from aranorm.processors._base import TextProcessor, RegexProcessor
from aranorm.processors.context_aware_processor import ContextAwareProcessor
from aranorm.processors.currency_processor import CurrencyProcessor
from aranorm.processors.date_processor import DateTimeProcessor
from aranorm.processors.diacritics_processor import DiacriticsProcessor
from aranorm.processors.dialect_stop_processor import DialectStopProcessor
from aranorm.processors.digits_processor import DigitsProcessor
from aranorm.processors.domain_stop_processor import DomainStopProcessor
from aranorm.processors.emoji_processor import EmojiProcessor
from aranorm.processors.hamza_processor import HamzaProcessor
from aranorm.processors.internet_stop_processor import InternetStopProcessor
from aranorm.processors.ligatures_processor import LigaturesProcessor
from aranorm.processors.morphological_stop_processor import MorphologicalStopProcessor
from aranorm.processors.normalization_processor import (
    RedundancyProcessor,
    SentenceNormalizerProcessor,
)
from aranorm.processors.number_words_processor import NumberWordsProcessor
from aranorm.processors.phone_processor import PhoneProcessor
from aranorm.processors.phrase_stop_processor import PhraseStopProcessor
from aranorm.processors.platform_processors import (
    TwitterNormalizer,
    WhatsAppNormalizer,
    ChatNormalizer,
)
from aranorm.processors.punctuation_processor import PunctuationProcessor
from aranorm.processors.repeated_chars_processor import RepeatedCharsProcessor
from aranorm.processors.spacing_processor import SpacingProcessor, RepeatedPunctuationProcessor
from aranorm.processors.spelling_processor import SpellingProcessor
from aranorm.processors.stop_words_processor import StopWordsProcessor
from aranorm.processors.taa_marbuta_processor import TaaMarbutaProcessor
from aranorm.processors.tatweel_processor import TatweelProcessor
from aranorm.processors.text_cleaning_processors import (
    URLProcessor,
    EmailProcessor,
    MentionProcessor,
    HashtagProcessor,
    HTMLProcessor,
    NonArabicProcessor,
    EnglishProcessor,
)
from aranorm.processors.unicode_processor import UnicodeProcessor
from aranorm.processors.whitespace_processor import WhitespaceProcessor

# Expose alef maqsura separately (imported from alef_processor module)
from aranorm.processors.alef_processor import AlefMaqsuraProcessor

__all__ = [
    # Base classes
    "TextProcessor",
    "RegexProcessor",
    # Content cleaning
    "URLProcessor",
    "EmailProcessor",
    "MentionProcessor",
    "HashtagProcessor",
    "HTMLProcessor",
    "NonArabicProcessor",
    "EnglishProcessor",
    "EmojiProcessor",
    # Orthographic normalization
    "ALEFProcessor",
    "AlefMaqsuraProcessor",
    "ArabiziProcessor",
    "DiacriticsProcessor",
    "DigitsProcessor",
    "HamzaProcessor",
    "LigaturesProcessor",
    "TaaMarbutaProcessor",
    "TatweelProcessor",
    "UnicodeProcessor",
    "WhitespaceProcessor",
    "SpacingProcessor",
    "PunctuationProcessor",
    "RepeatedCharsProcessor",
    "RepeatedPunctuationProcessor",
    # Stop-words processors
    "ArabiziStopProcessor",
    "ContextAwareProcessor",
    "DialectStopProcessor",
    "DomainStopProcessor",
    "InternetStopProcessor",
    "MorphologicalStopProcessor",
    "PhraseStopProcessor",
    "StopWordsProcessor",
    # Enrichment processors
    "CurrencyProcessor",
    "DateTimeProcessor",
    "NumberWordsProcessor",
    "PhoneProcessor",
    "SpellingProcessor",
    # Platform-specific
    "TwitterNormalizer",
    "WhatsAppNormalizer",
    "ChatNormalizer",
    # Sentence/text-level
    "RedundancyProcessor",
    "SentenceNormalizerProcessor",
]
