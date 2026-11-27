"""Extractive text summarization for Arabic documents.

Provides :class:`ArabicTextSummarizer` which selects the most salient
sentences from an Arabic text using a combination of:

* **TF-IDF sentence scoring** — sentences containing high-frequency,
  high-information-value words score higher.
* **Position bias** — introductory sentences (first ~20% of the document)
  receive a small weight bonus, mirroring journalistic Arabic prose conventions.
* **Stop-word filtering** — function words are excluded from the
  importance calculation so scores reflect content words only.

The summarizer is fully dependency-free and works for any Arabic variant
(MSA or dialect).

Example
-------
>>> from aranorm.analysis.summarizer import ArabicTextSummarizer
>>>
>>> summarizer = ArabicTextSummarizer(ratio=0.3)
>>> text = "..."  # long Arabic article
>>> summary = summarizer.summarize(text)
>>> print(summary.summary_text)
>>> print(f"Compressed {summary.compression_ratio:.0%}")
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from aranorm.core.stop_words_registry import StopWordsRegistry

# ── Patterns ──────────────────────────────────────────────────────────────────

_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u0671-\u06D3]+")
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟؛…])\s+|(?<=\n)\n+")


def _clean(word: str) -> str:
    return _DIACRITICS.sub("", word).strip(".,،؟!؛:()[]{}\"'«»")


def _sentences(text: str) -> List[str]:
    """Split text into non-empty sentences preserving punctuation."""
    parts = re.split(r"([.!?؟؛…])", text)
    sentences: List[str] = []
    i = 0
    while i < len(parts):
        seg = parts[i].strip()
        punct = parts[i + 1] if i + 1 < len(parts) else ""
        if seg:
            sentences.append((seg + punct).strip())
        i += 2
    if not sentences:
        # Fallback: split on newlines
        sentences = [s.strip() for s in text.split("\n") if s.strip()]
    return [s for s in sentences if s]


# ── Result dataclass ──────────────────────────────────────────────────────────


@dataclass
class SummaryResult:
    """Result of extractive summarization.

    Attributes
    ----------
    original_text:
        First 200 characters of the source text.
    summary_text:
        The extracted summary.
    summary_sentences:
        Ordered list of extracted sentences.
    sentence_scores:
        ``{sentence: score}`` for all sentences that were considered.
    original_sentence_count:
        Total sentences in the source.
    summary_sentence_count:
        Sentences in the summary.
    compression_ratio:
        ``summary_word_count / original_word_count``.
    top_keywords:
        Highest-scoring content words driving the summary.
    """

    original_text: str
    summary_text: str
    summary_sentences: List[str]
    sentence_scores: Dict[str, float]
    original_sentence_count: int
    summary_sentence_count: int
    compression_ratio: float
    top_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a complete, JSON-serialisable dictionary."""
        return {
            "original_text": self.original_text,
            "summary_text": self.summary_text,
            "summary_sentences": list(self.summary_sentences),
            "sentence_scores": dict(self.sentence_scores),
            "original_sentence_count": self.original_sentence_count,
            "summary_sentence_count": self.summary_sentence_count,
            "compression_ratio": self.compression_ratio,
            "top_keywords": list(self.top_keywords),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SummaryResult":
        """Reconstruct a result from :meth:`to_dict` output."""
        return cls(
            original_text=str(data.get("original_text", "")),
            summary_text=str(data.get("summary_text", "")),
            summary_sentences=list(data.get("summary_sentences", [])),
            sentence_scores={str(k): float(v) for k, v in data.get("sentence_scores", {}).items()},
            original_sentence_count=int(data.get("original_sentence_count", 0)),
            summary_sentence_count=int(data.get("summary_sentence_count", 0)),
            compression_ratio=float(data.get("compression_ratio", 0.0)),
            top_keywords=list(data.get("top_keywords", [])),
        )


# ── Summarizer ────────────────────────────────────────────────────────────────


class ArabicTextSummarizer:
    """Extractive Arabic text summarizer using TF-IDF sentence scoring.

    Parameters
    ----------
    ratio:
        Target fraction of the original text to keep (0.0–1.0, default 0.3).
        Ignored when *max_sentences* is given.
    max_sentences:
        Hard cap on the number of sentences in the summary.  Takes priority
        over *ratio* when set.
    min_sentences:
        Minimum sentences in the summary even if the document is very short
        (default 1).
    position_weight:
        Bonus multiplier for sentences in the first 20% of the document
        (default 1.2 — a 20% boost).
    registry:
        Optional shared :class:`~aranorm.core.stop_words_registry.StopWordsRegistry`.

    Example
    -------
    >>> s = ArabicTextSummarizer(max_sentences=3)
    >>> result = s.summarize(long_arabic_text)
    >>> print(result.summary_text)
    """

    def __init__(
        self,
        ratio: float = 0.3,
        max_sentences: Optional[int] = None,
        min_sentences: int = 1,
        position_weight: float = 1.2,
        registry: Optional[StopWordsRegistry] = None,
    ) -> None:
        if not 0.0 < ratio <= 1.0:
            raise ValueError("ratio must be in (0, 1]")
        if max_sentences is not None and max_sentences < 1:
            raise ValueError("max_sentences must be >= 1")
        self.ratio = ratio
        self.max_sentences = max_sentences
        self.min_sentences = max(1, min_sentences)
        self.position_weight = position_weight
        self._registry = registry or StopWordsRegistry()
        self._stop_words: Optional[Set[str]] = None

    # ── Public ────────────────────────────────────────────────────────────

    def summarize(self, text: str) -> SummaryResult:
        """Summarize *text* and return a :class:`SummaryResult`.

        Parameters
        ----------
        text:
            Arabic (or mixed) source document.
        """
        if not text or not text.strip():
            return SummaryResult(
                original_text=text[:200],
                summary_text="",
                summary_sentences=[],
                sentence_scores={},
                original_sentence_count=0,
                summary_sentence_count=0,
                compression_ratio=0.0,
            )

        sents = _sentences(text)
        n = len(sents)

        if n == 0:
            return SummaryResult(
                original_text=text[:200],
                summary_text=text,
                summary_sentences=[text],
                sentence_scores={text: 1.0},
                original_sentence_count=1,
                summary_sentence_count=1,
                compression_ratio=1.0,
            )

        # Determine target summary length
        if self.max_sentences is not None:
            k = min(self.max_sentences, n)
        else:
            k = max(self.min_sentences, round(n * self.ratio))
        k = min(k, n)

        # Build vocabulary and compute term frequencies
        stop_words = self._get_stop_words()
        doc_tokens: List[List[str]] = []
        for sent in sents:
            tokens = [_clean(w) for w in _ARABIC_WORD.findall(sent)]
            tokens = [t for t in tokens if t and t not in stop_words and len(t) >= 2]
            doc_tokens.append(tokens)

        # TF per sentence
        all_words = [w for tokens in doc_tokens for w in tokens]
        total_words = len(all_words)
        if total_words == 0:
            # No content words — return first k sentences
            selected = sents[:k]
            return self._build_result(text, sents, selected, {}, [])

        # Global word frequency for IDF
        global_freq: Dict[str, int] = {}
        for w in all_words:
            global_freq[w] = global_freq.get(w, 0) + 1

        # IDF: log(N / df) where df = number of sentences containing the word
        df: Dict[str, int] = {}
        for tokens in doc_tokens:
            for w in set(tokens):
                df[w] = df.get(w, 0) + 1

        idf: Dict[str, float] = {w: math.log(n / (df[w] + 1)) + 1 for w in df}

        # Score each sentence
        scores: Dict[str, float] = {}
        for i, (sent, tokens) in enumerate(zip(sents, doc_tokens)):
            if not tokens:
                scores[sent] = 0.0
                continue
            tf_idf = sum((tokens.count(w) / len(tokens)) * idf.get(w, 1.0) for w in set(tokens))
            # Position bonus for leading sentences
            pos_factor = self.position_weight if i < max(1, n // 5) else 1.0
            scores[sent] = tf_idf * pos_factor

        # Normalise scores
        max_score = max(scores.values()) or 1.0
        scores = {s: round(v / max_score, 6) for s, v in scores.items()}

        # Select top-k sentences preserving original order
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_k_set = {s for s, _ in ranked[:k]}
        selected = [s for s in sents if s in top_k_set]

        # Top keywords
        top_kw = [w for w, _ in sorted(global_freq.items(), key=lambda x: x[1], reverse=True) if len(w) >= 3][:10]

        return self._build_result(text, sents, selected, scores, top_kw)

    def summarize_batch(self, texts: List[str]) -> List[SummaryResult]:
        """Summarize multiple texts.

        Parameters
        ----------
        texts:
            List of Arabic strings.
        """
        return [self.summarize(t) for t in texts]

    # ── Private ───────────────────────────────────────────────────────────

    def _get_stop_words(self) -> Set[str]:
        if self._stop_words is None:
            self._stop_words = self._registry.get_words("universal")
        return self._stop_words

    @staticmethod
    def _build_result(
        text: str,
        all_sents: List[str],
        selected: List[str],
        scores: Dict[str, float],
        keywords: List[str],
    ) -> SummaryResult:
        summary = " ".join(selected)
        original_words = len(_ARABIC_WORD.findall(text))
        summary_words = len(_ARABIC_WORD.findall(summary))
        compression = round(summary_words / original_words, 4) if original_words else 0.0
        return SummaryResult(
            original_text=text[:200],
            summary_text=summary,
            summary_sentences=selected,
            sentence_scores=scores,
            original_sentence_count=len(all_sents),
            summary_sentence_count=len(selected),
            compression_ratio=compression,
            top_keywords=keywords,
        )
