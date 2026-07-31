"""AraNorm utility modules."""

from aranorm.utils.cache import NormalizationCache
from aranorm.utils.chunker import TextChunker, TextChunk, chunk_text
from aranorm.utils.exporters import BatchExporter
from aranorm.utils.helpers import contains_arabic, is_arabic_char, join_nonempty
from aranorm.utils.language_detector import (
    DetectionResult,
    LanguageDetector,
    detect_language,
    is_arabic,
)
from aranorm.utils.normalizer_utils import (
    normalize_alef,
    remove_diacritics,
    normalize_unicode,
    collapse_whitespace,
    is_arabic_text,
    strip_punctuation,
    truncate_repeated_chars,
    count_arabic_words,
    extract_arabic_words,
    char_ngrams,
    word_ngrams,
    levenshtein,
    fuzzy_match,
)
from aranorm.utils.progress import (
    ConsoleProgressCallback,
    NoOpProgressCallback,
    ProgressCallback,
    TqdmProgressCallback,
)
from aranorm.utils.root_extractor import RootExtractor, extract_root
from aranorm.utils.stemmer import ArabicStemmer, stem, stem_sentence
from aranorm.utils.text_stats import TextStats, compute_stats, compare_stats
from aranorm.utils.tokenizer import (
    ArabicTokenizer,
    Sentence,
    Token,
    sent_tokenize,
    word_tokenize,
)

__all__ = [
    # Tokenization
    "ArabicTokenizer",
    "Sentence",
    "Token",
    "sent_tokenize",
    "word_tokenize",
    # Text statistics
    "TextStats",
    "compute_stats",
    "compare_stats",
    # Chunking
    "TextChunker",
    "TextChunk",
    "chunk_text",
    # Caching
    "NormalizationCache",
    # Export
    "BatchExporter",
    # Language detection
    "DetectionResult",
    "LanguageDetector",
    "detect_language",
    "is_arabic",
    # Progress
    "ProgressCallback",
    "NoOpProgressCallback",
    "ConsoleProgressCallback",
    "TqdmProgressCallback",
    # Helpers
    "contains_arabic",
    "is_arabic_char",
    "join_nonempty",
    # Normalization utils (standalone)
    "normalize_alef",
    "remove_diacritics",
    "normalize_unicode",
    "collapse_whitespace",
    "is_arabic_text",
    "strip_punctuation",
    "truncate_repeated_chars",
    "count_arabic_words",
    "extract_arabic_words",
    "char_ngrams",
    "word_ngrams",
    "levenshtein",
    "fuzzy_match",
    # Stemming
    "ArabicStemmer",
    "stem",
    "stem_sentence",
    # Root extraction
    "RootExtractor",
    "extract_root",
]
