"""Arabic morphological complexity and word-length statistics engine.
Profiles how morphologically dense an Arabic text is — a proxy for how
demanding it is to read and parse:
+-------------------------+----------------------------------------------------+
| Signal                  | Detection approach                                 |
+-------------------------+----------------------------------------------------+
| avg_word_length         | Mean character length of content words            |
|                         | (diacritic-insensitive).                          |
+-------------------------+----------------------------------------------------+
| max_word_length         | Longest content word observed.                    |
+-------------------------+----------------------------------------------------+
| fused_ratio             | Share of long (≥ 6 letters) fused forms —        |
|                         | verbs/nouns carrying several proclitics,         |
|                         | infixes and suffixes at once.                     |
+-------------------------+----------------------------------------------------+
| length_distribution     | Per-length frequency map (1 … 8+) for all        |
|                         | content words.                                     |
+-------------------------+----------------------------------------------------+
| label                   | ``"simple"`` / ``"moderate"`` / ``"complex"``    |
|                         | derived from the average length.                  |
+-------------------------+----------------------------------------------------+
Deterministic, dependency-free, and consistent with the
``aranorm.analysis`` family (dataclass results with ``to_dict``/JSON APIs).
Example
-------
>>> from aranorm.analysis.complexity_analyzer import analyze_complexity
>>> result = analyze_complexity('استفادوا')
>>> result.max_word_length == 7
True
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List

_WORD_RE = re.compile(r"[\u0621-\u0652\u0660-\u06690-9A-Za-z]+")
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640\u064E\u064F\u0650\u0651]")
_LATIN_RUN = re.compile(r"[A-Za-z]+")


def _strip_diacritics(word: str) -> str:
    """Return *word* with all Arabic diacritics and tatweel removed."""
    return _DIACRITICS.sub("", word)


@dataclass
class ComplexityResult:
    """Morphological complexity profile for a single Arabic text.
    Attributes
    ----------
    avg_word_length:
        Mean letter count across content words (0.0 when empty).
    max_word_length:
        Longest content word letter count (0 when empty).
    fused_ratio:
        Share of words whose stripped length is at least 6 letters.
    length_distribution:
        Mapping of letter count ``n`` (capped at 8) to its frequency.
    word_count:
        Total content words examined.
    label:
        ``"simple"`` (avg < 4), ``"moderate"`` (avg 4–5),
        or ``"complex"`` (avg > 5).
    """

    avg_word_length: float
    max_word_length: int
    fused_ratio: float
    length_distribution: Dict[int, int]
    word_count: int
    label: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "avg_word_length": round(self.avg_word_length, 4),
            "max_word_length": self.max_word_length,
            "fused_ratio": round(self.fused_ratio, 4),
            "length_distribution": {str(key): value for key, value in self.length_distribution.items()},
            "word_count": self.word_count,
            "label": self.label,
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


@dataclass
class ComplexityAnalyzer:
    """Arabic morphological complexity profiling over prose.
    Parameters
    ----------
    complex_threshold:
        Average word length above which the text is labelled ``"complex"``.
    simple_threshold:
        Average word length at or below which the text is labelled
        ``"simple"``; in between the label is ``"moderate"``.
    fused_length:
        Letter count at or above which a word is counted as a fused
        (morphologically dense) form.
    """

    complex_threshold: float = 5.0
    simple_threshold: float = 4.0
    fused_length: int = 6

    def analyze(self, text: str) -> ComplexityResult:
        """Profile the morphological complexity of *text*."""
        raw_words = [match.group() for match in _WORD_RE.finditer(text)]
        # Drop pure-Latin fragments so that mixed-script samples do not
        # deflate the Arabic length statistics.
        words = [word for word in raw_words if not _LATIN_RUN.fullmatch(word)]
        lengths = [len(_strip_diacritics(word)) for word in words]
        word_count = len(lengths)
        if word_count == 0:
            return ComplexityResult(
                avg_word_length=0.0,
                max_word_length=0,
                fused_ratio=0.0,
                length_distribution={},
                word_count=0,
                label="simple",
            )
        distribution: Dict[int, int] = {}
        for length in lengths:
            distribution[min(length, 8)] = distribution.get(min(length, 8), 0) + 1
        average = sum(lengths) / word_count
        fused = sum(1 for length in lengths if length >= self.fused_length)
        fused_ratio = fused / word_count
        if average > self.complex_threshold:
            label = "complex"
        elif average <= self.simple_threshold:
            label = "simple"
        else:
            label = "moderate"
        return ComplexityResult(
            avg_word_length=average,
            max_word_length=max(lengths),
            fused_ratio=fused_ratio,
            length_distribution=distribution,
            word_count=word_count,
            label=label,
        )

    def analyze_batch(self, texts: List[str]) -> List[ComplexityResult]:
        """Profile a list of texts independently."""
        return [self.analyze(text) for text in texts]


def analyze_complexity(text: str) -> ComplexityResult:
    """Convenience function profiling the complexity of *text*.
    Example
    -------
    >>> result = analyze_complexity("استفادوا")
    >>> result.label == "complex"
    True
    """
    return ComplexityAnalyzer().analyze(text)
