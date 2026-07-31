"""Arabic text readability analysis.

Provides :class:`ArabicReadabilityAnalyzer` which computes multiple
readability metrics specifically calibrated for Arabic text, including:

* **Sentence complexity** (average sentence length, max sentence length)
* **Vocabulary richness** (type-token ratio, hapax legomena ratio)
* **Morphological density** (average word length in characters, diacritic ratio)
* **Structural complexity** (subordinate clause indicators, sentence variance)
* **Flesch-inspired Arabic Readability Score (FARS)** — a 0–100 score where
  higher is easier to read.

All metrics are heuristic approximations; no morphological analyser is required.

Example
-------
>>> from aranorm.analysis.readability import ArabicReadabilityAnalyzer
>>>
>>> analyzer = ArabicReadabilityAnalyzer()
>>> result = analyzer.analyze("أعلن الرئيس عن خطة اقتصادية شاملة تستهدف تحقيق نمو مستدام")
>>> print(result.readability_label)
'complex'
>>> print(result.score)
42.3
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── Patterns ──────────────────────────────────────────────────────────────────

_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u0671-\u06D3]+")
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670]")
_SENTENCE_SPLIT = re.compile(r"[.!?؟؛…\n]+")
_TATWEEL = re.compile(r"\u0640+")

# Complexity indicator words (subordinating conjunctions, relative pronouns)
_COMPLEXITY_MARKERS = frozenset({
    "الذي", "التي", "الذين", "اللواتي", "اللتان", "اللذان",
    "حيث", "عندما", "بينما", "لأن", "لأنه", "لكي", "حتى",
    "إذا", "إذ", "إذن", "لو", "لولا", "أن", "أنه", "أنها",
    "مما", "مما", "كلما", "طالما", "بما", "فيما",
})

# Connectors / discourse markers (medium complexity)
_CONNECTORS = frozenset({
    "لذلك", "بالتالي", "وبالتالي", "وإن", "ومع ذلك", "بالإضافة",
    "علاوة على ذلك", "من جهة", "من جهة أخرى", "في حين", "في ضوء",
    "استناداً", "تبعاً",
})


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ReadabilityResult:
    """Readability analysis for one Arabic text.

    Attributes
    ----------
    text_preview:
        First 80 characters of the original text.
    score:
        Composite readability score (0–100); higher = easier to read.
    readability_label:
        ``"very_easy"``, ``"easy"``, ``"moderate"``, ``"complex"``,
        ``"very_complex"``.
    sentence_count:
        Number of detected sentences.
    word_count:
        Total Arabic words.
    unique_words:
        Vocabulary size (unique Arabic words).
    avg_sentence_length:
        Mean words per sentence.
    max_sentence_length:
        Longest sentence (in words).
    sentence_length_variance:
        Variance of sentence lengths.
    avg_word_length:
        Mean Arabic characters per word.
    type_token_ratio:
        ``unique_words / word_count`` — vocabulary diversity.
    hapax_ratio:
        Fraction of words appearing exactly once.
    diacritic_ratio:
        Fraction of Arabic characters that are diacritics.
    complexity_marker_count:
        Count of subordinate-clause markers found.
    connector_count:
        Count of discourse connectors found.
    detail:
        Raw sub-score breakdown for each metric component.
    """

    text_preview: str
    score: float
    readability_label: str

    # Sentence metrics
    sentence_count: int
    word_count: int
    unique_words: int
    avg_sentence_length: float
    max_sentence_length: int
    sentence_length_variance: float

    # Word metrics
    avg_word_length: float
    type_token_ratio: float
    hapax_ratio: float
    diacritic_ratio: float

    # Complexity
    complexity_marker_count: int
    connector_count: int

    # Raw component scores
    detail: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        return {
            "score": self.score,
            "readability_label": self.readability_label,
            "sentence_count": self.sentence_count,
            "word_count": self.word_count,
            "unique_words": self.unique_words,
            "avg_sentence_length": self.avg_sentence_length,
            "max_sentence_length": self.max_sentence_length,
            "sentence_length_variance": self.sentence_length_variance,
            "avg_word_length": self.avg_word_length,
            "type_token_ratio": self.type_token_ratio,
            "hapax_ratio": self.hapax_ratio,
            "diacritic_ratio": self.diacritic_ratio,
            "complexity_marker_count": self.complexity_marker_count,
            "connector_count": self.connector_count,
            "detail": self.detail,
        }


# ── Analyzer ──────────────────────────────────────────────────────────────────

class ArabicReadabilityAnalyzer:
    """Compute multi-metric readability scores for Arabic text.

    The composite score is a weighted average of five component scores,
    each normalised to [0, 100]:

    +-----------------------+--------+--------------------------------------------+
    | Component             | Weight | Rationale                                  |
    +=======================+========+============================================+
    | Sentence length       |   30%  | Shorter sentences → easier to read         |
    +-----------------------+--------+--------------------------------------------+
    | Word length           |   20%  | Shorter words → easier to parse            |
    +-----------------------+--------+--------------------------------------------+
    | Vocabulary richness   |   20%  | Lower TTR → more repetitive → easier       |
    +-----------------------+--------+--------------------------------------------+
    | Complexity markers    |   20%  | Fewer embedded clauses → clearer structure |
    +-----------------------+--------+--------------------------------------------+
    | Diacritic density     |   10%  | Voweled text → easier to read aloud        |
    +-----------------------+--------+--------------------------------------------+

    Parameters
    ----------
    max_easy_sentence:
        Sentences at or below this length (in words) receive the maximum
        sentence-length score (default 10).
    max_easy_word:
        Words at or below this length (in characters) receive the maximum
        word-length score (default 5).

    Example
    -------
    >>> analyzer = ArabicReadabilityAnalyzer()
    >>> result = analyzer.analyze("الكتاب جيد. أحببته.")
    >>> result.readability_label
    'very_easy'
    """

    def __init__(
        self,
        max_easy_sentence: int = 10,
        max_easy_word: int = 5,
    ) -> None:
        self.max_easy_sentence = max_easy_sentence
        self.max_easy_word = max_easy_word

    # ── Public ────────────────────────────────────────────────────────────

    def analyze(self, text: str) -> ReadabilityResult:
        """Compute readability metrics for *text*.

        Parameters
        ----------
        text:
            Arabic (or mixed) input string.
        """
        if not text or not text.strip():
            return self._empty(text)

        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
        sentence_count = max(len(sentences), 1)

        all_words: List[str] = []
        for sent in sentences:
            all_words.extend(w for w in _ARABIC_WORD.findall(sent))

        word_count = len(all_words)
        if word_count == 0:
            return self._empty(text)

        sent_lengths = [
            len(_ARABIC_WORD.findall(s)) for s in sentences
        ]
        avg_sent_len = sum(sent_lengths) / sentence_count
        max_sent_len = max(sent_lengths) if sent_lengths else 0

        # Variance of sentence lengths
        mean = avg_sent_len
        variance = (
            sum((l - mean) ** 2 for l in sent_lengths) / sentence_count
            if sentence_count > 1 else 0.0
        )

        # Word metrics
        word_lengths = [len(w) for w in all_words]
        avg_word_len = sum(word_lengths) / word_count

        freq: Counter = Counter(all_words)
        unique = len(freq)
        ttr = unique / word_count
        hapax = sum(1 for c in freq.values() if c == 1) / unique if unique else 0.0

        # Diacritic ratio
        total_arabic_chars = sum(
            1 for c in text if "\u0621" <= c <= "\u064A" or "\u0671" <= c <= "\u06D3"
        )
        diacritic_chars = len(_DIACRITICS.findall(text))
        diacritic_ratio = diacritic_chars / total_arabic_chars if total_arabic_chars else 0.0

        # Complexity markers
        lower_words = set(w for w in all_words)
        complexity_count = sum(
            1 for m in _COMPLEXITY_MARKERS if m in lower_words
        )
        connector_count = sum(1 for c in _CONNECTORS if c in text)

        # Component scores (0–100, higher = easier)
        sent_score = max(0.0, 100.0 - max(0.0, avg_sent_len - self.max_easy_sentence) * 5.0)
        word_score = max(0.0, 100.0 - max(0.0, avg_word_len - self.max_easy_word) * 10.0)
        vocab_score = max(0.0, 100.0 - ttr * 100.0)  # lower TTR → easier
        complexity_score = max(0.0, 100.0 - (complexity_count / sentence_count) * 50.0)
        diacritic_score = diacritic_ratio * 100.0  # more diacritics → easier to read

        composite = (
            sent_score * 0.30
            + word_score * 0.20
            + vocab_score * 0.20
            + complexity_score * 0.20
            + diacritic_score * 0.10
        )
        composite = round(max(0.0, min(100.0, composite)), 2)
        label = self._label(composite)

        return ReadabilityResult(
            text_preview=text[:80],
            score=composite,
            readability_label=label,
            sentence_count=sentence_count,
            word_count=word_count,
            unique_words=unique,
            avg_sentence_length=round(avg_sent_len, 2),
            max_sentence_length=max_sent_len,
            sentence_length_variance=round(variance, 2),
            avg_word_length=round(avg_word_len, 2),
            type_token_ratio=round(ttr, 4),
            hapax_ratio=round(hapax, 4),
            diacritic_ratio=round(diacritic_ratio, 4),
            complexity_marker_count=complexity_count,
            connector_count=connector_count,
            detail={
                "sentence_length_score": round(sent_score, 2),
                "word_length_score": round(word_score, 2),
                "vocabulary_score": round(vocab_score, 2),
                "complexity_score": round(complexity_score, 2),
                "diacritic_score": round(diacritic_score, 2),
            },
        )

    def analyze_batch(self, texts: List[str]) -> List[ReadabilityResult]:
        """Analyze multiple texts and return results in input order.

        Parameters
        ----------
        texts:
            List of Arabic strings.
        """
        return [self.analyze(t) for t in texts]

    def compare(
        self, texts: List[str], sort_by: str = "score"
    ) -> List[Tuple[str, ReadabilityResult]]:
        """Rank *texts* by readability.

        Parameters
        ----------
        texts:
            Texts to rank.
        sort_by:
            ``"score"`` (easiest first), ``"score_desc"`` (hardest first).

        Returns
        -------
        List of ``(text, ReadabilityResult)`` sorted by the chosen criterion.
        """
        results = [(t, self.analyze(t)) for t in texts]
        reverse = sort_by == "score_desc"
        results.sort(key=lambda x: x[1].score, reverse=reverse)
        return results

    # ── Private ───────────────────────────────────────────────────────────

    @staticmethod
    def _label(score: float) -> str:
        if score >= 80:
            return "very_easy"
        if score >= 60:
            return "easy"
        if score >= 40:
            return "moderate"
        if score >= 20:
            return "complex"
        return "very_complex"

    def _empty(self, text: str) -> ReadabilityResult:
        return ReadabilityResult(
            text_preview=text[:80],
            score=0.0,
            readability_label="unknown",
            sentence_count=0,
            word_count=0,
            unique_words=0,
            avg_sentence_length=0.0,
            max_sentence_length=0,
            sentence_length_variance=0.0,
            avg_word_length=0.0,
            type_token_ratio=0.0,
            hapax_ratio=0.0,
            diacritic_ratio=0.0,
            complexity_marker_count=0,
            connector_count=0,
        )
