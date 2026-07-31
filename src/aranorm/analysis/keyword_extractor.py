"""Keyword extraction for Arabic texts using stop-word filtering + TF scoring."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.processors.stop_words_processor import StopWordsProcessor

_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u0671-\u06D3]{2,}")
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")


def _normalise(word: str) -> str:
    word = _DIACRITICS.sub("", word)
    return word.strip(".,،؟!؛:()[]{}\"'«»")


@dataclass
class KeywordResult:
    """Result of keyword extraction for one text."""

    original_text: str
    keywords: List[Tuple[str, float]]        # [(word, score), …] sorted by score
    top_keywords: List[str]                  # just the words, ordered
    keyword_count: int
    content_word_count: int
    stop_word_count: int
    coverage_ratio: float                    # keywords / total words


class KeywordExtractor:
    """Extract the most salient Arabic content words from a text.

    Uses stop-word removal + term-frequency scoring (with optional
    document-frequency penalty when a reference corpus is provided).

    Parameters
    ----------
    config:
        :class:`~aranorm.core.stop_words_config.StopWordsConfig`.
    registry:
        Optional shared registry.
    top_n:
        Maximum keywords to return per text (default 10).
    min_freq:
        Minimum term frequency to be considered a keyword (default 1).
    min_word_length:
        Minimum character length for a keyword candidate (default 3).
    reference_corpus:
        Optional list of texts used to compute IDF weights.  When supplied
        the scorer becomes TF-IDF instead of plain TF.

    Example
    -------
    >>> extractor = KeywordExtractor(top_n=5)
    >>> result = extractor.extract("الاقتصاد العالمي يشهد تحولات جذرية في ظل الأزمات")
    >>> result.top_keywords
    ['الاقتصاد', 'تحولات', 'جذرية', 'الأزمات', 'العالمي']
    """

    def __init__(
        self,
        config: Optional[StopWordsConfig] = None,
        registry: Optional[StopWordsRegistry] = None,
        top_n: int = 10,
        min_freq: int = 1,
        min_word_length: int = 3,
        reference_corpus: Optional[List[str]] = None,
    ) -> None:
        self.config = config or StopWordsConfig(
            mode="remove", scope="universal", remove_filler=True
        )
        self.registry = registry or StopWordsRegistry()
        self.processor = StopWordsProcessor(config=self.config, registry=self.registry)
        self.top_n = top_n
        self.min_freq = min_freq
        self.min_word_length = min_word_length
        self._idf: Optional[Dict[str, float]] = (
            self._build_idf(reference_corpus) if reference_corpus else None
        )

    # ── Public ────────────────────────────────────────────────────────────

    def extract(self, text: str) -> KeywordResult:
        """Extract keywords from a single *text*."""
        if not text or not text.strip():
            return KeywordResult(
                original_text=text, keywords=[], top_keywords=[],
                keyword_count=0, content_word_count=0,
                stop_word_count=0, coverage_ratio=0.0,
            )

        tokens = text.split()
        total_words = len(tokens)
        sw_result = self.processor.process_detailed(text)
        stop_set = sw_result.stop_words_found

        # Collect candidate content words
        tf: Dict[str, int] = {}
        for token in tokens:
            w = _normalise(token)
            if (
                w
                and w not in stop_set
                and _ARABIC_WORD.match(w)
                and len(w) >= self.min_word_length
            ):
                tf[w] = tf.get(w, 0) + 1

        # Score
        scored: List[Tuple[str, float]] = []
        for word, freq in tf.items():
            if freq < self.min_freq:
                continue
            tf_score = freq / total_words
            if self._idf is not None:
                idf = self._idf.get(word, math.log(2))
                score = tf_score * idf
            else:
                # Plain TF with length bonus (longer Arabic words tend to carry more meaning)
                length_bonus = min(len(word) / 10, 0.5)
                score = tf_score + length_bonus
            scored.append((word, round(score, 6)))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[: self.top_n]

        content_count = len(tf)
        stop_count = len(stop_set)
        coverage = len(top) / total_words if total_words else 0.0

        return KeywordResult(
            original_text=text,
            keywords=top,
            top_keywords=[w for w, _ in top],
            keyword_count=len(top),
            content_word_count=content_count,
            stop_word_count=stop_count,
            coverage_ratio=round(coverage, 4),
        )

    def extract_batch(self, texts: List[str]) -> List[KeywordResult]:
        """Extract keywords from multiple texts."""
        return [self.extract(t) for t in texts]

    def extract_common_keywords(
        self, texts: List[str], min_text_occurrences: int = 2
    ) -> List[Tuple[str, int]]:
        """Return keywords that appear in at least *min_text_occurrences* texts."""
        from collections import Counter

        word_text_count: Counter = Counter()
        for result in self.extract_batch(texts):
            for w in result.top_keywords:
                word_text_count[w] += 1

        return [
            (w, c) for w, c in word_text_count.most_common()
            if c >= min_text_occurrences
        ]

    # ── Private ───────────────────────────────────────────────────────────

    def _build_idf(self, corpus: List[str]) -> Dict[str, float]:
        """Compute IDF weights from a reference corpus."""
        n_docs = len(corpus)
        df: Dict[str, int] = {}
        for text in corpus:
            words = {_normalise(t) for t in text.split() if _normalise(t)}
            for w in words:
                df[w] = df.get(w, 0) + 1
        return {
            w: math.log((n_docs + 1) / (count + 1)) + 1
            for w, count in df.items()
        }
