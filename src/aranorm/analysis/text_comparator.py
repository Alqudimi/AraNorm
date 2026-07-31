"""Similarity and comparison utilities for Arabic text pairs.

Provides:

* :class:`TextComparator` — compare two texts using multiple similarity
  metrics (Jaccard, cosine TF, overlap, stop-word profile distance).
* :class:`SimilarityResult` — immutable result object returned by
  :meth:`TextComparator.compare`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.processors.stop_words_processor import StopWordsProcessor


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_tokens(text: str) -> List[str]:
    """Return stripped, non-empty tokens from *text*."""
    return [t.strip(".,،؟!؛:()[]{}\"'«»\n\r\t") for t in text.split() if t.strip()]


def _term_frequencies(tokens: List[str]) -> Dict[str, float]:
    """Return a normalised TF vector for *tokens*."""
    if not tokens:
        return {}
    counts: Dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    n = len(tokens)
    return {w: c / n for w, c in counts.items()}


def _cosine(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Cosine similarity between two TF dictionaries."""
    shared = set(vec_a) & set(vec_b)
    if not shared:
        return 0.0
    dot = sum(vec_a[w] * vec_b[w] for w in shared)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return round(dot / (mag_a * mag_b), 4)


def _jaccard(set_a: Set[str], set_b: Set[str]) -> float:
    """Jaccard similarity between two token sets."""
    union = set_a | set_b
    if not union:
        return 1.0
    return round(len(set_a & set_b) / len(union), 4)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SimilarityResult:
    """Immutable similarity analysis between two Arabic texts.

    Attributes
    ----------
    text_a, text_b:
        The original input texts.
    jaccard_similarity:
        Token-set Jaccard similarity (0–1).
    cosine_similarity:
        Cosine similarity of TF vectors over all tokens (0–1).
    content_jaccard:
        Jaccard similarity computed on content words only (stop words excluded).
    content_cosine:
        Cosine TF similarity computed on content words only.
    stop_word_overlap:
        Fraction of shared stop words over the union of both stop-word sets.
    shared_tokens:
        Tokens appearing in both texts.
    shared_content_words:
        Content words appearing in both texts.
    unique_to_a, unique_to_b:
        Tokens exclusive to each text.
    overall_similarity:
        Weighted composite score (content_cosine × 0.5 + content_jaccard × 0.3
        + jaccard_similarity × 0.2).
    verdict:
        Human-readable similarity band: ``"identical"``, ``"very_similar"``,
        ``"similar"``, ``"somewhat_similar"``, ``"different"``.
    """

    text_a: str
    text_b: str

    # Whole-text metrics
    jaccard_similarity: float
    cosine_similarity: float

    # Content-word metrics (stop words removed)
    content_jaccard: float
    content_cosine: float

    # Stop-word profile
    stop_word_overlap: float
    shared_stop_words: FrozenSet[str]

    # Token sets
    shared_tokens: FrozenSet[str]
    shared_content_words: FrozenSet[str]
    unique_to_a: FrozenSet[str]
    unique_to_b: FrozenSet[str]

    # Composite
    overall_similarity: float
    verdict: str

    # Token counts
    token_count_a: int
    token_count_b: int
    content_word_count_a: int
    content_word_count_b: int

    def to_dict(self) -> Dict[str, object]:
        """Return a plain dictionary representation."""
        return {
            "jaccard_similarity": self.jaccard_similarity,
            "cosine_similarity": self.cosine_similarity,
            "content_jaccard": self.content_jaccard,
            "content_cosine": self.content_cosine,
            "stop_word_overlap": self.stop_word_overlap,
            "overall_similarity": self.overall_similarity,
            "verdict": self.verdict,
            "token_count_a": self.token_count_a,
            "token_count_b": self.token_count_b,
            "shared_tokens": list(self.shared_tokens),
            "shared_content_words": list(self.shared_content_words),
            "unique_to_a": list(self.unique_to_a),
            "unique_to_b": list(self.unique_to_b),
        }


# ── TextComparator ────────────────────────────────────────────────────────────

class TextComparator:
    """Compare two Arabic texts across multiple similarity dimensions.

    Parameters
    ----------
    config:
        Stop-words config used to separate content words from function words.
        Defaults to universal removal.
    registry:
        Optional shared registry.

    Example
    -------
    >>> comparator = TextComparator()
    >>> result = comparator.compare("أنا سعيد اليوم", "أنا فرحان اليوم")
    >>> result.content_jaccard
    0.0
    >>> result.overall_similarity
    0.35
    """

    def __init__(
        self,
        config: Optional[StopWordsConfig] = None,
        registry: Optional[StopWordsRegistry] = None,
    ) -> None:
        self.config = config or StopWordsConfig(mode="remove", scope="universal", remove_filler=True)
        self.registry = registry or StopWordsRegistry()
        self._processor = StopWordsProcessor(config=self.config, registry=self.registry)

    # ── Core ─────────────────────────────────────────────────────────────

    def compare(self, text_a: str, text_b: str) -> SimilarityResult:
        """Return a :class:`SimilarityResult` comparing *text_a* and *text_b*.

        Parameters
        ----------
        text_a, text_b:
            Arabic text strings to compare.
        """
        tokens_a = _clean_tokens(text_a)
        tokens_b = _clean_tokens(text_b)

        set_a = set(tokens_a)
        set_b = set(tokens_b)

        # ── Whole-text metrics ────────────────────────────────────────────
        jaccard = _jaccard(set_a, set_b)
        cosine = _cosine(_term_frequencies(tokens_a), _term_frequencies(tokens_b))

        # ── Stop-word analysis ────────────────────────────────────────────
        sw_a = self._processor.process_detailed(text_a)
        sw_b = self._processor.process_detailed(text_b)

        stops_a = sw_a.stop_words_found
        stops_b = sw_b.stop_words_found
        shared_stops = stops_a & stops_b
        stop_overlap = _jaccard(stops_a, stops_b)

        # ── Content-word metrics ──────────────────────────────────────────
        content_a = _clean_tokens(sw_a.stop_words_removed)
        content_b = _clean_tokens(sw_b.stop_words_removed)

        content_set_a = set(content_a)
        content_set_b = set(content_b)

        content_jaccard = _jaccard(content_set_a, content_set_b)
        content_cosine = _cosine(
            _term_frequencies(content_a), _term_frequencies(content_b)
        )

        # ── Composite score ───────────────────────────────────────────────
        overall = round(
            content_cosine * 0.50
            + content_jaccard * 0.30
            + jaccard * 0.20,
            4,
        )

        verdict = self._verdict(overall)

        return SimilarityResult(
            text_a=text_a,
            text_b=text_b,
            jaccard_similarity=jaccard,
            cosine_similarity=cosine,
            content_jaccard=content_jaccard,
            content_cosine=content_cosine,
            stop_word_overlap=stop_overlap,
            shared_stop_words=frozenset(shared_stops),
            shared_tokens=frozenset(set_a & set_b),
            shared_content_words=frozenset(content_set_a & content_set_b),
            unique_to_a=frozenset(set_a - set_b),
            unique_to_b=frozenset(set_b - set_a),
            overall_similarity=overall,
            verdict=verdict,
            token_count_a=len(tokens_a),
            token_count_b=len(tokens_b),
            content_word_count_a=len(content_a),
            content_word_count_b=len(content_b),
        )

    def compare_batch(
        self,
        pairs: List[Tuple[str, str]],
    ) -> List[SimilarityResult]:
        """Compare multiple text pairs.

        Parameters
        ----------
        pairs:
            List of ``(text_a, text_b)`` tuples.
        """
        return [self.compare(a, b) for a, b in pairs]

    def rank_by_similarity(
        self,
        query: str,
        candidates: List[str],
        top_n: Optional[int] = None,
    ) -> List[Tuple[str, SimilarityResult]]:
        """Rank *candidates* by similarity to *query*.

        Returns a list of ``(candidate_text, SimilarityResult)`` tuples
        sorted by ``overall_similarity`` descending.

        Parameters
        ----------
        query:
            Reference text to compare against.
        candidates:
            List of candidate texts.
        top_n:
            If given, return only the top-N results.
        """
        ranked = [
            (text, self.compare(query, text))
            for text in candidates
        ]
        ranked.sort(key=lambda x: x[1].overall_similarity, reverse=True)
        if top_n is not None:
            return ranked[:top_n]
        return ranked

    def find_duplicates(
        self,
        texts: List[str],
        threshold: float = 0.85,
    ) -> List[Tuple[int, int, SimilarityResult]]:
        """Find near-duplicate pairs in *texts*.

        Returns a list of ``(index_a, index_b, SimilarityResult)`` for every
        pair whose ``overall_similarity`` exceeds *threshold*.

        Parameters
        ----------
        texts:
            List of text strings to compare pairwise.
        threshold:
            Minimum similarity score to consider a pair as near-duplicate.
        """
        results: List[Tuple[int, int, SimilarityResult]] = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                sim = self.compare(texts[i], texts[j])
                if sim.overall_similarity >= threshold:
                    results.append((i, j, sim))
        results.sort(key=lambda x: x[2].overall_similarity, reverse=True)
        return results

    # ── Private ───────────────────────────────────────────────────────────

    @staticmethod
    def _verdict(score: float) -> str:
        """Map a similarity score to a human-readable band."""
        if score >= 0.95:
            return "identical"
        if score >= 0.75:
            return "very_similar"
        if score >= 0.50:
            return "similar"
        if score >= 0.25:
            return "somewhat_similar"
        return "different"
