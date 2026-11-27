"""Deterministic Arabic text coherence assessment.

Scores how *coherent* an Arabic text reads along four independent axes and
combines them into an overall coherence index:

+---------------------+-------------------------------------------------------+
| Axis                | Rationale                                             |
+---------------------+-------------------------------------------------------+
| lexical_repeat      | Content words that reappear across sentences signal   |
|                     | a sustained topic chain; measured as the fraction of  |
|                     | adjacent sentence pairs sharing content vocabulary.   |
+---------------------+-------------------------------------------------------+
| connectors          | Explicit discourse connectives (ثم، لذلك، بالإضافة)   |
|                     | explicitly stitch sentences together; measured as     |
|                     | occurrences per content word.                         |
+---------------------+-------------------------------------------------------+
| sentence_balance    | Wildly unequal sentence lengths suggest fragmented    |
|                     | writing; measured as 1 - normalized length stdev.     |
+---------------------+-------------------------------------------------------+
| topic_consistency   | A text that keeps returning to the same vocabulary    |
|                     | cluster reads as unified; measured as the fraction of |
|                     | content words that appear in more than one sentence.  |
+---------------------+-------------------------------------------------------+

The overall score is a weighted average of the four axes (weights tuned for
prose: lexical chaining matters most, balance matters least).

Example
-------
>>> from aranorm.analysis.coherence_score import analyze_coherence
>>> result = analyze_coherence("افتتح الاجتماع رئيس اللجنة. ثم ناقش الحضور التقرير. "
...                            "لذلك قرر المجلس اعتماد التوصيات.")
>>> 0.0 <= result.score <= 1.0
True
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u0671-\u06D3]{2,}")
_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_SENTENCE_SPLIT = re.compile(r"[.!?۔؟]+|\n{2,}")

# High-precision Arabic discourse connectives (normalized forms).
_CONNECTIVES = frozenset(
    [
        "ثم",
        "لذلك",
        "لهذا",
        "بالإضافة",
        "أيضا",
        "كذلك",
        "بالنسبة",
        "علاوة",
        "بالتالي",
        "نتيجة",
        "بمعنى",
        "فيما",
        "بينما",
        "حيث",
        "لأن",
        "بما",
        "حتى",
        "رغم",
        "على",
        "من",
        "إلى",
    ]
)

# Weights summing to 1.0 across the four axes.
_WEIGHTS = {
    "lexical_repeat": 0.35,
    "connectors": 0.25,
    "sentence_balance": 0.15,
    "topic_consistency": 0.25,
}

# Verbal description boundaries for the overall score.
_SCORE_LABELS = (
    (0.7, "strong"),
    (0.5, "moderate"),
    (0.3, "weak"),
    (0.0, "fragmented"),
)


def _normalize(word: str) -> str:
    return _DIA_RE.sub("", word).strip()


def _sentences(text: str) -> List[str]:
    """Split *text* into sentence fragments on terminal punctuation.

    Consecutive separators (or blank lines) are treated as one boundary so
    that spacing noise does not create empty fragments.
    """
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(text)]
    return [part for part in parts if part]


@dataclass
class CoherenceBreakdown:
    """Per-axis evidence behind the overall coherence score."""

    axis: str
    value: float  # raw normalized score on this axis (0.0-1.0)
    weight: float
    contribution: float  # value * weight

    def to_dict(self) -> Dict[str, object]:
        return {
            "axis": self.axis,
            "value": round(self.value, 4),
            "weight": self.weight,
            "contribution": round(self.contribution, 4),
        }


@dataclass
class CoherenceScore:
    """Overall coherence assessment for one Arabic text.

    Attributes
    ----------
    text:
        The analyzed input.
    score:
        Overall coherence index (0.0-1.0), weighted across the four axes.
    label:
        Human-readable band (``"strong"`` | ``"moderate"`` | ``"weak"`` |
        ``"fragmented"``).
    sentence_count:
        Number of sentence fragments detected.
    content_word_count:
        Content words (min length 3, diacritics stripped) after stop-words
        are ignored in axis computations.
    breakdown:
        Per-axis scores with weights and contributions.
    connective_count:
        Discourse connectives actually present in the text.
    axes:
        Legacy dict view (axis -> normalized value) for callers preferring
        flat access.
    """

    text: str
    score: float = 0.0
    label: str = "fragmented"
    sentence_count: int = 0
    content_word_count: int = 0
    breakdown: List[CoherenceBreakdown] = field(default_factory=list)
    connective_count: int = 0
    axes: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "score": round(self.score, 4),
            "label": self.label,
            "sentence_count": self.sentence_count,
            "content_word_count": self.content_word_count,
            "connective_count": self.connective_count,
            "breakdown": [b.to_dict() for b in self.breakdown],
            "axes": {k: round(v, 4) for k, v in self.axes.items()},
        }

    def to_json(self, indent: Optional[int] = 2, ensure_ascii: bool = False) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    def summary(self) -> str:
        items = ", ".join(f"{b.axis}={b.value:.2f}" for b in self.breakdown)
        return (
            f"Coherence {self.label} ({self.score:.2f}) over {self.sentence_count} "
            f"sentence(s) and {self.content_word_count} content words: {items}."
        )


# ── Analyzer ────────────────────────────────────────────────────────────────


class CoherenceAnalyzer:
    """Deterministic coherence scoring for Arabic prose.

    Example
    -------
    >>> analyzer = CoherenceAnalyzer()
    >>> result = analyzer.analyze("افتتح الاجتماع رئيس اللجنة. ثم ناقش الحضور التقرير.")
    >>> result.sentence_count >= 2
    True
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self._weights = dict(_WEIGHTS)
        if weights:
            for key, value in weights.items():
                if key not in self._weights:
                    raise ValueError(f"unknown axis {key!r}")
                self._weights[key] = value

    # ── Axis computations ────────────────────────────────────────────────────

    def _sentence_vocabularies(self, text: str) -> List[List[str]]:
        """Content-word lists per sentence (normalized, length >= 3)."""
        out: List[List[str]] = []
        for fragment in _sentences(text):
            words = [_normalize(w) for w in _ARABIC_WORD.findall(fragment)]
            out.append([w for w in words if len(w) >= 3])
        return out

    def _lexical_repeat(self, vocabularies: List[List[str]]) -> float:
        """Share of adjacent sentence pairs whose content vocabularies touch.

        Texts with a single sentence (no adjacent pair) score 0.0 on this
        axis rather than inventing evidence.
        """
        if len(vocabularies) < 2:
            return 0.0
        matches = 0
        for first, second in zip(vocabularies[:-1], vocabularies[1:]):
            if set(first) & set(second):
                matches += 1
        return matches / (len(vocabularies) - 1)

    def _connectors(self, text: str, content_word_count: int) -> float:
        """Connective density normalized against content vocabulary size.

        Score saturates at 0.25 connectives per content word (beyond that,
        connective spam no longer adds coherence). Normalization guards the
        per-word rate against division by zero and caps the raw rate.
        """
        if not content_word_count:
            return 0.0
        words = [_normalize(w) for w in _ARABIC_WORD.findall(text)]
        found = [w for w in words if len(w) >= 3 and w in _CONNECTIVES]
        self._last_connective_count = len(found)
        rate = len(found) / content_word_count
        return min(1.0, rate / 0.25)

    def _sentence_balance(self, vocabularies: List[List[str]]) -> float:
        """1 - normalized coefficient of variation over sentence lengths.

        Short texts with fewer than two sentences trivially score full marks
        (nothing to balance); the coefficient of variation is capped at 1.5
        so that extreme imbalance still leaves a residual score of 0.33.
        """
        if len(vocabularies) < 2:
            return 1.0
        lengths = [len(v) for v in vocabularies]
        mean = sum(lengths) / len(lengths)
        if not mean:
            return 0.0
        variance = sum((length - mean) ** 2 for length in lengths) / len(lengths)
        stdev = math.sqrt(variance)
        return max(0.0, min(1.0, 1.0 - min(stdev / mean, 1.5) / 1.5))

    def _topic_consistency(self, vocabularies: List[List[str]]) -> float:
        """Share of content words that occur in more than one sentence.

        A single-sentence text cannot demonstrate cross-sentence consistency,
        so it scores 0.0 on this axis rather than asserting perfect unity.
        """
        if len(vocabularies) < 2:
            return 0.0
        all_words: List[str] = []
        per_sentence: List[set] = []
        for vocab in vocabularies:
            unique = set(vocab)
            per_sentence.append(unique)
            all_words.extend(unique)
        if not all_words:
            return 0.0
        frequency: Dict[str, int] = {}
        for unique in per_sentence:
            for word in unique:
                frequency[word] = frequency.get(word, 0) + 1
        recurring = sum(1 for word in set(all_words) if frequency[word] > 1)
        return recurring / len(set(all_words))

    # ── Public API ───────────────────────────────────────────────────────────

    def analyze(self, text: str) -> CoherenceScore:
        """Score the coherence of *text*.

        Parameters
        ----------
        text:
            Arabic text to assess. Empty or non-Arabic text yields a zero
            score with a ``"fragmented"`` label rather than raising.
        """
        if not (text or "").strip():
            return CoherenceScore(
                text=text,
                score=0.0,
                label="fragmented",
                sentence_count=0,
                content_word_count=0,
                breakdown=[],
                connective_count=0,
                axes={},
            )

        vocabularies = self._sentence_vocabularies(text)
        content_words = [word for vocab in vocabularies for word in vocab]
        content_word_count = len(content_words)

        self._last_connective_count = 0
        values: Dict[str, float] = {
            "lexical_repeat": self._lexical_repeat(vocabularies),
            "connectors": self._connectors(text, content_word_count),
            "sentence_balance": self._sentence_balance(vocabularies),
            "topic_consistency": self._topic_consistency(vocabularies),
        }

        breakdown: List[CoherenceBreakdown] = []
        weighted = 0.0
        for axis, value in values.items():
            weight = self._weights[axis]
            breakdown.append(
                CoherenceBreakdown(
                    axis=axis,
                    value=value,
                    weight=weight,
                    contribution=value * weight,
                )
            )
            weighted += value * weight

        label_choice = "fragmented"
        for limit, label in _SCORE_LABELS:
            if weighted >= limit:
                label_choice = label
                break
        return CoherenceScore(
            text=text,
            score=weighted,
            label=label_choice,
            sentence_count=len(vocabularies),
            content_word_count=content_word_count,
            breakdown=breakdown,
            connective_count=self._last_connective_count,
            axes=values,
        )


def analyze_coherence(text: str) -> CoherenceScore:
    """Analyze Arabic text coherence and return a :class:`CoherenceScore`.

    Thin convenience wrapper around :class:`CoherenceAnalyzer`.
    """
    return CoherenceAnalyzer().analyze(text)
