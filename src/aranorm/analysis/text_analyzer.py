"""Full text analysis: stop-word density, readability, content word stats."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set

from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.processors.stop_words_processor import StopWordsProcessor

# Basic Arabic word pattern
_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u0671-\u06D3]+")
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")


def _clean_word(word: str) -> str:
    """Strip punctuation and diacritics from a word."""
    word = _DIACRITICS.sub("", word)
    return word.strip(".,،؟!؛:()[]{}\"'«»")


@dataclass
class TextAnalysisResult:
    """Complete analytical breakdown of a single text."""

    # Raw counts
    original_text: str
    total_tokens: int
    total_words: int           # Arabic words only
    total_chars: int
    unique_words: int

    # Stop-word metrics
    stop_words_count: int
    stop_words_ratio: float    # 0.0–1.0
    content_words_count: int
    content_words_ratio: float

    # Content
    content_words: List[str]   # Non-stop-word tokens (preserves order)
    stop_words_found: Set[str]
    stop_words_by_category: Dict[str, List[str]]

    # Frequency
    word_frequency: Dict[str, int]
    content_word_frequency: Dict[str, int]
    top_content_words: List[tuple]   # [(word, count), …] sorted by freq

    # Readability indicators (heuristic)
    avg_word_length: float
    lexical_diversity: float      # unique / total words
    stop_word_density: float      # stop words per sentence (approx)
    estimated_complexity: str     # "simple" | "moderate" | "complex"

    # Sentence stats
    sentence_count: int
    avg_sentence_length: float    # tokens per sentence

    # Extra metadata
    dialect_hint: Optional[str]   # detected from dialect stop words
    extra: Dict[str, Any] = field(default_factory=dict)


class TextAnalyzer:
    """Analyze an Arabic text's linguistic complexity and stop-word profile.

    Parameters
    ----------
    config:
        :class:`~aranorm.core.stop_words_config.StopWordsConfig` controlling
        which stop words are recognised.  Defaults to universal removal.
    registry:
        Optional shared registry.
    top_n:
        How many top content words to include in the result (default 10).

    Example
    -------
    >>> analyzer = TextAnalyzer()
    >>> result = analyzer.analyze("أنا والله سعيد جداً بهذا النتيجة")
    >>> result.content_words
    ['سعيد', 'النتيجة']
    >>> result.stop_words_ratio
    0.71
    """

    def __init__(
        self,
        config: Optional[StopWordsConfig] = None,
        registry: Optional[StopWordsRegistry] = None,
        top_n: int = 10,
    ) -> None:
        self.config = config or StopWordsConfig(
            mode="remove", scope="universal", remove_filler=True
        )
        self.registry = registry or StopWordsRegistry()
        self.processor = StopWordsProcessor(config=self.config, registry=self.registry)
        self.top_n = top_n

    # ── Core ─────────────────────────────────────────────────────────────

    def analyze(self, text: str) -> TextAnalysisResult:
        """Return a :class:`TextAnalysisResult` for *text*."""
        if not text or not text.strip():
            return self._empty_result(text)

        raw_tokens = text.split()
        total_tokens = len(raw_tokens)
        arabic_words = [_clean_word(t) for t in raw_tokens if _ARABIC_WORD.search(t)]
        total_words = len(arabic_words)
        total_chars = sum(len(w) for w in arabic_words)

        # Stop-words analysis
        sw_result = self.processor.process_detailed(text)
        stop_set = sw_result.stop_words_found
        content_tokens = [
            _clean_word(t) for t in raw_tokens
            if _clean_word(t) and _clean_word(t) not in stop_set
            and _ARABIC_WORD.search(t)
        ]

        # Frequency
        word_freq: Dict[str, int] = {}
        for w in arabic_words:
            if w:
                word_freq[w] = word_freq.get(w, 0) + 1

        content_freq: Dict[str, int] = {}
        for w in content_tokens:
            if w:
                content_freq[w] = content_freq.get(w, 0) + 1

        top_content = sorted(content_freq.items(), key=lambda x: x[1], reverse=True)[
            : self.top_n
        ]

        # Sentence approximation (split on . ! ? ؟ ؛)
        sentences = re.split(r"[.!?؟؛\n]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentence_count = max(len(sentences), 1)
        avg_sentence_len = total_tokens / sentence_count

        stop_count = len(stop_set)
        content_count = len(content_tokens)
        total_analysed = stop_count + content_count
        stop_ratio = stop_count / total_analysed if total_analysed else 0.0
        content_ratio = 1.0 - stop_ratio
        avg_word_len = (total_chars / total_words) if total_words else 0.0
        unique = len(set(w for w in arabic_words if w))
        lex_diversity = unique / total_words if total_words else 0.0

        # Complexity heuristic
        if stop_ratio > 0.55 or avg_word_len < 4:
            complexity = "simple"
        elif stop_ratio > 0.35 or avg_word_len < 6:
            complexity = "moderate"
        else:
            complexity = "complex"

        # Dialect hint from dialect-specific stop words
        dialect_hint = self._detect_dialect_hint(stop_set)

        return TextAnalysisResult(
            original_text=text,
            total_tokens=total_tokens,
            total_words=total_words,
            total_chars=total_chars,
            unique_words=unique,
            stop_words_count=stop_count,
            stop_words_ratio=round(stop_ratio, 4),
            content_words_count=content_count,
            content_words_ratio=round(content_ratio, 4),
            content_words=content_tokens,
            stop_words_found=stop_set,
            stop_words_by_category=sw_result.stop_words_by_category,
            word_frequency=word_freq,
            content_word_frequency=content_freq,
            top_content_words=top_content,
            avg_word_length=round(avg_word_len, 2),
            lexical_diversity=round(lex_diversity, 4),
            stop_word_density=round(stop_count / sentence_count, 2),
            estimated_complexity=complexity,
            sentence_count=sentence_count,
            avg_sentence_length=round(avg_sentence_len, 2),
            dialect_hint=dialect_hint,
        )

    def analyze_batch(self, texts: List[str]) -> List[TextAnalysisResult]:
        """Analyze multiple texts and return a result list."""
        return [self.analyze(t) for t in texts]

    def compare_complexity(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Return a sorted summary of texts by complexity (most complex first)."""
        results = self.analyze_batch(texts)
        summaries = [
            {
                "text_preview": t[:60] + ("…" if len(t) > 60 else ""),
                "stop_ratio": r.stop_words_ratio,
                "content_words": r.content_words_count,
                "complexity": r.estimated_complexity,
                "lexical_diversity": r.lexical_diversity,
            }
            for t, r in zip(texts, results)
        ]
        return sorted(summaries, key=lambda x: x["lexical_diversity"], reverse=True)

    # ── Private helpers ───────────────────────────────────────────────────

    def _detect_dialect_hint(self, stop_set: Set[str]) -> Optional[str]:
        """Heuristically identify a dialect from the stop words found."""
        dialect_indicators: Dict[str, Set[str]] = {
            "EGY": {"كده", "ده", "دي", "دول", "إيه", "بقى"},
            "GLF": {"الحين", "شلون", "وايد", "ترى", "عاد"},
            "LEV": {"هيك", "شو", "هلق", "رح", "هاد"},
            "IRQ": {"هسة", "گاعد", "مو", "شنو", "يمعود"},
            "NOR": {"درك", "واخا", "بزاف", "مزيان", "دابا"},
        }
        scores: Dict[str, int] = {}
        for dialect, indicators in dialect_indicators.items():
            scores[dialect] = len(stop_set & indicators)
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else None

    def _empty_result(self, text: str) -> TextAnalysisResult:
        return TextAnalysisResult(
            original_text=text, total_tokens=0, total_words=0, total_chars=0,
            unique_words=0, stop_words_count=0, stop_words_ratio=0.0,
            content_words_count=0, content_words_ratio=0.0, content_words=[],
            stop_words_found=set(), stop_words_by_category={}, word_frequency={},
            content_word_frequency={}, top_content_words=[], avg_word_length=0.0,
            lexical_diversity=0.0, stop_word_density=0.0,
            estimated_complexity="simple", sentence_count=0, avg_sentence_length=0.0,
            dialect_hint=None,
        )
