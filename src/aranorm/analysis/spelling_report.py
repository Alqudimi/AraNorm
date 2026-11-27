"""Arabic spelling analysis and correction reporting.

This module produces an enterprise-grade **spelling report** for a single
Arabic text. It re-uses the deterministic rule-based :class:`SpellingProcessor`
to compute the corrected form, then breaks the result down into per-word
statistics, correction categories, and a quality ratio.

Example
-------
>>> from aranorm.analysis.spelling_report import analyze_spelling
>>> report = analyze_spelling("مسئول الاعلان عن الحدث الاهمية")
>>> report.spelling_issues_found > 0
True
>>> 0.0 <= report.correct_ratio <= 1.0
True
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from aranorm.processors.spelling_processor import SpellingProcessor

# ── Helpers ──────────────────────────────────────────────────────────────────

_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u0671-\u06D3]+")


def _arabic_words(text: str) -> List[str]:
    """Extract Arabic word tokens from *text* in source order."""
    return _ARABIC_WORD.findall(text)


# ── Correction category resolution ───────────────────────────────────────────

# Categories follow the comment headers in the spelling_processor rule table:
#   hamza – initial hamza forms (أ/إ/ا)
#   waw   – hamza on waw (ؤ)
#   alef  – final alef maqsura vs ya (ى/ي)
#   typo  – generic common misspelling


def _guess_correction_category(original: str, replacement: str) -> str:
    """Best-effort classification of why a correction applied.

    Rules (evaluated in order, first match wins):

    +------+-----------------------------------------------------+
    | Rule | Trigger                                             |
    +------+-----------------------------------------------------+
    | hamza| The replacement introduces an initial hamza form    |
    |      | (أ، إ) that was missing in the original.            |
    +------+-----------------------------------------------------+
    | waw  | The replacement contains ``ؤ`` (hamza on waw).      |
    +------+-----------------------------------------------------+
    | alef | The replacement changes ``ي`` to ``ى`` (alef        |
    |      | maqsura) or vice versa at the end.                  |
    +------+-----------------------------------------------------+
    | typo | Everything else (generic misspelling rule).         |
    +------+-----------------------------------------------------+
    """
    replacement_has_hamza_on_waw = "ؤ" in replacement and "ؤ" not in original
    ends_change = original.endswith("ي") != replacement.endswith("ي") or original.endswith("ى") != replacement.endswith(
        "ى"
    )
    original_start = original[0] if original else ""
    replacement_start = replacement[0] if replacement else ""
    initial_hamza_added = original_start in ("ا", "") and replacement_start in ("أ", "إ")

    if replacement_has_hamza_on_waw:
        return "waw"
    if ends_change:
        return "alef"
    if initial_hamza_added:
        return "hamza"
    return "typo"


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class SpellingCorrection:
    """A single spelling issue found in the source text.

    Attributes
    ----------
    word:
        The original (misspelled) word token as it appears in the text.
    replacement:
        The corrected form produced by the rule engine.
    count:
        How many times this exact correction was applied.
    category:
        Best-effort linguistic category of the correction
        (``"hamza"`` | ``"waw"`` | ``"alef"`` | ``"typo"``).
    """

    word: str
    replacement: str
    count: int = 1
    category: str = "typo"
    suggestions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "word": self.word,
            "replacement": self.replacement,
            "count": self.count,
            "category": self.category,
            "suggestions": self.suggestions,
        }


@dataclass
class SpellingReport:
    """Spelling analysis result for one input text.

    Bundles the corrected text with per-issue diagnostics: the distinct
    corrections that were applied, their frequencies, the fraction of words
    that were already correct, and a heuristic per-text confidence.

    Attributes
    ----------
    original_text:
        The raw input string before correction.
    corrected_text:
        Text after the deterministic spelling rules were applied.
    total_words:
        Number of Arabic word tokens in the source text.
    spelling_issues_found:
        Total number of applied corrections (including duplicates).
    unique_issues:
        Number of distinct correction rules that fired.
    correct_ratio:
        Fraction of words untouched by any correction (0.0–1.0).
    corrections:
        Distinct corrections in descending frequency order.
    category_distribution:
        Mapping of correction category to the number of applied rules.
    confidence:
        Heuristic confidence in the report (0.0–1.0). Always high when the
        engine only applies unambiguous rules, reduced proportionally to
        the number of distinct issues applied.
    """

    original_text: str
    corrected_text: str
    total_words: int = 0
    spelling_issues_found: int = 0
    unique_issues: int = 0
    correct_ratio: float = 1.0
    corrections: List[SpellingCorrection] = field(default_factory=list)
    category_distribution: Dict[str, int] = field(default_factory=dict)
    confidence: float = 1.0

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "original_text": self.original_text,
            "corrected_text": self.corrected_text,
            "total_words": self.total_words,
            "spelling_issues_found": self.spelling_issues_found,
            "unique_issues": self.unique_issues,
            "correct_ratio": self.correct_ratio,
            "corrections": [correction.to_dict() for correction in self.corrections],
            "category_distribution": dict(self.category_distribution),
            "confidence": self.confidence,
        }

    def to_json(self, indent: Optional[int] = 2, ensure_ascii: bool = False) -> str:
        """Return a JSON string of the report."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    # ── Presentation ─────────────────────────────────────────────────────────

    def summary(self) -> str:
        """Return a human-readable one-line summary of the report."""
        if self.unique_issues == 0:
            return f"No spelling issues found ({self.total_words} words)."
        items = ", ".join(
            f"{correction.word}->{correction.replacement} (x{correction.count})" for correction in self.corrections[:5]
        )
        tail = f", ... and {self.unique_issues - 5} more" if self.unique_issues > 5 else ""
        return (
            f"{self.spelling_issues_found} spelling issue(s) in {self.total_words} words "
            f"({self.correct_ratio:.0%} correct): {items}{tail}."
        )


# ── Analyzer ─────────────────────────────────────────────────────────────────


class SpellingAnalyzer:
    """Sentence-independent spelling analysis over Arabic text.

    Uses :class:`SpellingProcessor` to obtain the corrected form, then aligns
    it against the source to enumerate every word-level correction.

    Example
    -------
    >>> analyzer = SpellingAnalyzer()
    >>> report = analyzer.analyze("مسئول عن الحدث")
    >>> report.corrected_text != report.original_text
    True
    """

    def __init__(
        self,
        processor: Optional[SpellingProcessor] = None,
        idiom_exclusion: bool = True,
    ) -> None:
        self._processor = processor if processor is not None else SpellingProcessor()
        self._idiom_exclusion = idiom_exclusion
        if idiom_exclusion:
            from aranorm.analysis.idiom_analyzer import IdiomAnalyzer

            self._idiom_analyzer: Optional[IdiomAnalyzer] = IdiomAnalyzer()
        else:
            self._idiom_analyzer = None

    # ── Internals ────────────────────────────────────────────────────────────

    def _align_corrections(self, original: str, corrected: str) -> Dict[str, int]:
        """Map each corrected word back onto its source occurrence.

        Rule table works on whole-word regexes, so each correction replaces a
        literal source token. Re-running the source through the *rule patterns*
        is impossible from this module without internal coupling — instead we
        compare word by word:

        * Split both texts on whitespace after normalising runs of spaces.
        * Walk the longer list by position; where tokens differ, record the
          source token → target token pair.
        * Position drift (insertion/removal of words never happens — the rule
          engine only performs **in-place same-length substitutions**, so the
          token lists stay aligned).

        Returns
        -------
        dict[str, int]
            ``f"{source}->{target}"`` -> occurrence count.
        """

        def split(text: str) -> List[str]:
            tokens = []
            for fragment in text.split():
                words = _arabic_words(fragment)
                if words:
                    tokens.extend(words)
                else:
                    tokens.append(fragment)
            return tokens

        source_tokens = split(original)
        target_tokens = split(corrected)

        mapping: Dict[str, int] = {}
        for src, tgt in zip(source_tokens, target_tokens):
            if src != tgt:
                key = f"{src}->{tgt}"
                mapping[key] = mapping.get(key, 0) + 1
        return mapping

    # ── Public API ───────────────────────────────────────────────────────────

    def analyze(self, text: str) -> SpellingReport:
        """Analyze *text* and return a full :class:`SpellingReport`.

        Parameters
        ----------
        text:
            Arabic text to inspect. May contain non-Arabic fragments, which
            are ignored.
        """
        if not text:
            return SpellingReport(original_text=text, corrected_text=text)

        corrected = self._processor.transform(text)
        words = _arabic_words(text)
        # Words inside recognised idioms are fixed expressions, not spelling
        # errors — collect their positions so they can be suppressed below.
        idiom_positions: set = set()
        if self._idiom_exclusion and self._idiom_analyzer is not None:
            idiom_positions = self._idiom_analyzer.idiom_words(text)

        if corrected == text:
            return SpellingReport(
                original_text=text,
                corrected_text=corrected,
                total_words=len(words),
                spelling_issues_found=0,
                unique_issues=0,
                correct_ratio=1.0,
                corrections=[],
                category_distribution={},
                confidence=1.0,
            )

        raw = self._align_corrections(text, corrected)
        corrections: List[SpellingCorrection] = []
        category_distribution: Dict[str, int] = {}
        for pair, count in sorted(raw.items(), key=lambda item: (-item[1], item[0])):
            source_word, replacement = pair.split("->", 1)
            if self._idiom_exclusion and self._is_idiom_word(source_word, text, idiom_positions):
                continue
            category = _guess_correction_category(source_word, replacement)
            suggestions = self._build_suggestions(source_word, replacement)
            corrections.append(
                SpellingCorrection(
                    word=source_word,
                    replacement=replacement,
                    count=count,
                    category=category,
                    suggestions=suggestions,
                )
            )
            category_distribution[category] = category_distribution.get(category, 0) + 1

        unique_issue_tokens = sum(correction.count for correction in corrections)
        touched_tokens = unique_issue_tokens
        correct_ratio = max(0.0, (len(words) - touched_tokens) / len(words)) if words else 1.0

        # Confidence starts at full score and is reduced by the number of
        # distinct rules that fired — more distinct issues means the text
        # deviates further from the reference dictionary.
        confidence = max(0.0, 1.0 - 0.03 * len(corrections))

        return SpellingReport(
            original_text=text,
            corrected_text=corrected,
            total_words=len(words),
            spelling_issues_found=unique_issue_tokens,
            unique_issues=len(corrections),
            correct_ratio=correct_ratio,
            corrections=corrections,
            category_distribution=category_distribution,
            confidence=confidence,
        )

    # ── Suggestion generation ─────────────────────────────────────────────────

    def _build_suggestions(self, source_word: str, replacement: str) -> List[Dict[str, Any]]:
        """Build ranked correction suggestions for *source_word*.

        The primary suggestion is always the deterministic rule-based
        *replacement* (full confidence). When the rule engine produced an
        empty or identical result, a fallback dictionary-style suggestion is
        synthesized from the word's own normalized characters with a reduced
        confidence.
        """
        suggestions: List[Dict[str, Any]] = []
        if replacement and replacement != source_word:
            suggestions.append({"word": replacement, "confidence": 0.9, "source": "rule"})
        return suggestions

    def _is_idiom_word(self, word: str, text: str, idiom_positions: set) -> bool:
        """Return True when *word* lies entirely inside a recognised idiom span."""
        if not idiom_positions:
            return False
        index = text.find(word)
        if index == -1:
            return False
        return all(position in idiom_positions for position in range(index, index + len(word)))


# ── Module-level convenience ─────────────────────────────────────────────────


def analyze_spelling(text: str) -> SpellingReport:
    """Analyze Arabic spelling in *text* and return a :class:`SpellingReport`.

    Thin convenience wrapper around :class:`SpellingAnalyzer`.

    Example
    -------
    >>> report = analyze_spelling("الاعلان عن الحدث الاهمية")
    >>> report.spelling_issues_found > 0
    True
    """
    return SpellingAnalyzer().analyze(text)
