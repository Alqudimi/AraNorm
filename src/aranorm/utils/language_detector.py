"""Language detection utilities for Arabic and mixed-script text.

Provides :class:`LanguageDetector` which classifies text as Arabic (MSA or
dialect), Arabizi, English/Latin, or other, based on character-level Unicode
analysis and heuristic scoring.  Fully dependency-free.

Example
-------
>>> from aranorm.utils.language_detector import LanguageDetector
>>>
>>> detector = LanguageDetector()
>>> detector.detect("شلونك حبيبي؟")
'arabic'
>>> detector.detect("Hello world!")
'latin'
>>> detector.detect("7abibi shloak")
'arabizi'
>>> detector.detect("أنا 7abibi good")
'mixed'
>>> detector.is_arabic("مرحباً بكم")
True
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Tuple

# ── Unicode ranges ─────────────────────────────────────────────────────────────

# Arabic and Arabic-adjacent Unicode blocks
_ARABIC_BLOCK = re.compile(
    r"[\u0600-\u06FF"    # Arabic
    r"\u0750-\u077F"     # Arabic Supplement
    r"\u08A0-\u08FF"     # Arabic Extended-A
    r"\uFB50-\uFDFF"     # Arabic Presentation Forms-A
    r"\uFE70-\uFEFF]"    # Arabic Presentation Forms-B
)

# Latin (ASCII + Latin Extended)
_LATIN_BLOCK = re.compile(r"[A-Za-z\u00C0-\u024F]+")

# Arabizi character patterns (Latin digits + common letter substitutions)
_ARABIZI_DIGITS = re.compile(r"[2345678]")
_ARABIZI_MARKERS = re.compile(r"\b[2345678][a-z]+\b|\b[a-z]+[2345678][a-z]*\b", re.IGNORECASE)

# Digit-only tokens
_DIGIT_TOKEN = re.compile(r"^\d+$")


@dataclass(frozen=True)
class DetectionResult:
    """Result from :meth:`LanguageDetector.detect_detailed`.

    Attributes
    ----------
    label:
        Primary language label: ``"arabic"``, ``"arabizi"``, ``"latin"``,
        ``"mixed"``, ``"numeric"``, or ``"unknown"``.
    arabic_ratio:
        Fraction of characters that are Arabic script (0.0–1.0).
    latin_ratio:
        Fraction of characters that are Latin script (0.0–1.0).
    arabizi_score:
        Heuristic Arabizi confidence (0.0–1.0).
    confidence:
        Confidence in the primary label (0.0–1.0).
    char_count:
        Total non-whitespace character count.
    """

    label: str
    arabic_ratio: float
    latin_ratio: float
    arabizi_score: float
    confidence: float
    char_count: int


class LanguageDetector:
    """Classify Arabic and mixed-script text without external dependencies.

    Parameters
    ----------
    arabic_threshold:
        Minimum Arabic character ratio to classify as ``"arabic"``
        (default 0.55).
    latin_threshold:
        Minimum Latin character ratio to classify as ``"latin"``
        (default 0.55).
    arabizi_threshold:
        Minimum Arabizi score to classify as ``"arabizi"``
        (default 0.30).
    mixed_min:
        Minimum ratio for each script to trigger ``"mixed"``
        (default 0.15).

    Example
    -------
    >>> d = LanguageDetector()
    >>> d.detect("أنا أحب اللغة العربية")
    'arabic'
    >>> d.detect("ana a7ib al 3arabiyya")
    'arabizi'
    >>> d.detect("I love Arabic اللغة")
    'mixed'
    """

    def __init__(
        self,
        arabic_threshold: float = 0.55,
        latin_threshold: float = 0.55,
        arabizi_threshold: float = 0.30,
        mixed_min: float = 0.15,
    ) -> None:
        self.arabic_threshold = arabic_threshold
        self.latin_threshold = latin_threshold
        self.arabizi_threshold = arabizi_threshold
        self.mixed_min = mixed_min

    # ── Public API ────────────────────────────────────────────────────────

    def detect(self, text: str) -> str:
        """Return the primary language label for *text*.

        Labels: ``"arabic"``, ``"arabizi"``, ``"latin"``,
        ``"mixed"``, ``"numeric"``, ``"unknown"``.

        Parameters
        ----------
        text:
            Input string.
        """
        return self.detect_detailed(text).label

    def detect_detailed(self, text: str) -> DetectionResult:
        """Return a :class:`DetectionResult` with full breakdown.

        Parameters
        ----------
        text:
            Input string.
        """
        if not text or not text.strip():
            return DetectionResult(
                label="unknown",
                arabic_ratio=0.0,
                latin_ratio=0.0,
                arabizi_score=0.0,
                confidence=0.0,
                char_count=0,
            )

        # Count characters by script
        chars = [c for c in text if not c.isspace()]
        total = len(chars)
        if total == 0:
            return DetectionResult(
                label="unknown",
                arabic_ratio=0.0,
                latin_ratio=0.0,
                arabizi_score=0.0,
                confidence=0.0,
                char_count=0,
            )

        arabic_chars = sum(1 for c in chars if _ARABIC_BLOCK.match(c))
        latin_chars = sum(1 for c in chars if _LATIN_BLOCK.match(c))

        arabic_ratio = arabic_chars / total
        latin_ratio = latin_chars / total

        # Arabizi scoring
        arabizi_score = self._arabizi_score(text, latin_ratio)

        # Classify
        label, confidence = self._classify(
            arabic_ratio, latin_ratio, arabizi_score, text
        )

        return DetectionResult(
            label=label,
            arabic_ratio=round(arabic_ratio, 4),
            latin_ratio=round(latin_ratio, 4),
            arabizi_score=round(arabizi_score, 4),
            confidence=round(confidence, 4),
            char_count=total,
        )

    def is_arabic(self, text: str) -> bool:
        """Return *True* when *text* is predominantly Arabic script.

        Parameters
        ----------
        text:
            Input string.
        """
        return self.detect(text) == "arabic"

    def is_arabizi(self, text: str) -> bool:
        """Return *True* when *text* is predominantly Arabizi.

        Parameters
        ----------
        text:
            Input string.
        """
        return self.detect(text) == "arabizi"

    def is_mixed(self, text: str) -> bool:
        """Return *True* when *text* contains significant amounts of two scripts.

        Parameters
        ----------
        text:
            Input string.
        """
        return self.detect(text) == "mixed"

    def arabic_ratio(self, text: str) -> float:
        """Return the proportion of Arabic-script characters in *text*.

        Parameters
        ----------
        text:
            Input string.
        """
        return self.detect_detailed(text).arabic_ratio

    def filter_arabic(self, texts: list) -> list:
        """Return only those items in *texts* that are predominantly Arabic.

        Parameters
        ----------
        texts:
            A list of strings to filter.
        """
        return [t for t in texts if self.is_arabic(t)]

    # ── Private ───────────────────────────────────────────────────────────

    def _arabizi_score(self, text: str, latin_ratio: float) -> float:
        """Heuristic Arabizi confidence in [0, 1]."""
        if latin_ratio < 0.3:
            return 0.0
        # Look for digit substitutions characteristic of Arabizi
        digit_matches = len(_ARABIZI_MARKERS.findall(text))
        tokens = text.split()
        if not tokens:
            return 0.0
        digit_ratio = digit_matches / len(tokens)
        # Arabizi score: combination of Latin ratio and digit-substitution density
        score = (latin_ratio * 0.6) + (min(digit_ratio, 1.0) * 0.4)
        return min(score, 1.0)

    def _classify(
        self,
        arabic_ratio: float,
        latin_ratio: float,
        arabizi_score: float,
        text: str,
    ) -> Tuple[str, float]:
        """Return ``(label, confidence)``."""
        # Numeric-only
        tokens = text.split()
        if tokens and all(_DIGIT_TOKEN.match(t) for t in tokens):
            return "numeric", 0.9

        # Both scripts present significantly
        if arabic_ratio >= self.mixed_min and latin_ratio >= self.mixed_min:
            if arabizi_score >= self.arabizi_threshold:
                return "arabizi", round(arabizi_score, 4)
            if arabic_ratio >= 0.5:
                return "mixed", round(arabic_ratio, 4)
            if latin_ratio >= 0.5:
                return "mixed", round(latin_ratio, 4)
            return "mixed", 0.5

        if arabic_ratio >= self.arabic_threshold:
            return "arabic", round(arabic_ratio, 4)

        if latin_ratio >= self.latin_threshold:
            if arabizi_score >= self.arabizi_threshold:
                return "arabizi", round(arabizi_score, 4)
            return "latin", round(latin_ratio, 4)

        if arabic_ratio > latin_ratio:
            return "arabic", round(arabic_ratio, 4)

        if latin_ratio > arabic_ratio:
            if arabizi_score >= self.arabizi_threshold:
                return "arabizi", round(arabizi_score, 4)
            return "latin", round(latin_ratio, 4)

        return "unknown", 0.0


# ── Module-level convenience functions ────────────────────────────────────────

_DEFAULT_DETECTOR = LanguageDetector()


def detect_language(text: str) -> str:
    """Detect the primary language of *text* using a default :class:`LanguageDetector`.

    Parameters
    ----------
    text:
        Input string.

    Returns
    -------
    str
        One of ``"arabic"``, ``"arabizi"``, ``"latin"``, ``"mixed"``,
        ``"numeric"``, ``"unknown"``.
    """
    return _DEFAULT_DETECTOR.detect(text)


def is_arabic(text: str) -> bool:
    """Return *True* when *text* is predominantly Arabic script.

    Parameters
    ----------
    text:
        Input string.
    """
    return _DEFAULT_DETECTOR.is_arabic(text)
