"""Corpus-level (batch) analysis reporting.

Bundles the library's analytical engines — corpus statistics, language
distribution, dialect profiling, spelling hygiene and composite quality —
into a single :class:`BatchAnalysisReport` over an arbitrary collection of
texts.

Example
-------
>>> from aranorm.analysis.batch_analysis import analyze_batch
>>> texts = ["نص عربي واضح.", "Another script entirely."]
>>> report = analyze_batch(texts)
>>> report.texts_count == 2
True
>>> "language_distribution" in report.to_dict()
True
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class QualityDistribution:
    """Quality-score band counts across the corpus.

    Attributes
    ----------
    excellent:
        Texts scoring >= 90.
    good:
        Texts scoring 75–89.
    fair:
        Texts scoring 55–74.
    poor:
        Texts scoring below 55.
    """

    excellent: int = 0
    good: int = 0
    fair: int = 0
    poor: int = 0

    def to_dict(self) -> Dict[str, int]:
        """Return a JSON-serializable representation."""
        return {
            "excellent": self.excellent,
            "good": self.good,
            "fair": self.fair,
            "poor": self.poor,
        }


@dataclass
class BatchAnalysisReport:
    """Aggregated analysis result for a collection of texts.

    Attributes
    ----------
    texts_count:
        Number of texts analyzed.
    total_tokens:
        Combined Arabic word token count.
    total_chars:
        Combined character count.
    avg_quality_score:
        Mean composite quality score across the corpus (0.0–100.0).
    quality_distribution:
        Counts of texts falling in each quality band.
    language_distribution:
        Mapping of detected script/language labels to text counts
        (e.g. ``{"arabic": 8, "mixed": 2, "latin": 1}``).
    dialect_distribution:
        Mapping of detected dialect labels to text counts
        (e.g. ``{"MSA": 5, "GLF": 3}``).
    avg_readability:
        Mean readability score across the corpus.
    spelling_issues_total:
        Total spelling issues found across all texts.
    unique_words:
        Size of the union of Arabic vocabulary across the corpus.
    top_issues:
        Most frequent spelling corrections across the corpus.
    recommendations:
        High-level corpus improvement suggestions.
    corpus_lexical_diversity:
        Corpus-level lexical diversity (unique words / total words).
    """

    texts_count: int = 0
    total_tokens: int = 0
    total_chars: int = 0
    avg_quality_score: float = 0.0
    quality_distribution: QualityDistribution = field(default_factory=QualityDistribution)
    language_distribution: Dict[str, int] = field(default_factory=dict)
    dialect_distribution: Dict[str, int] = field(default_factory=dict)
    avg_readability: float = 0.0
    spelling_issues_total: int = 0
    unique_words: int = 0
    top_issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    corpus_lexical_diversity: float = 0.0

    # ── Serialization / presentation ─────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "texts_count": self.texts_count,
            "total_tokens": self.total_tokens,
            "total_chars": self.total_chars,
            "avg_quality_score": self.avg_quality_score,
            "quality_distribution": self.quality_distribution.to_dict(),
            "language_distribution": dict(self.language_distribution),
            "dialect_distribution": dict(self.dialect_distribution),
            "avg_readability": self.avg_readability,
            "spelling_issues_total": self.spelling_issues_total,
            "unique_words": self.unique_words,
            "top_issues": list(self.top_issues),
            "recommendations": list(self.recommendations),
            "corpus_lexical_diversity": self.corpus_lexical_diversity,
        }

    def to_json(self, indent: Optional[int] = 2, ensure_ascii: bool = False) -> str:
        """Return a JSON string of the report."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    def summary(self) -> str:
        """Return a human-readable one-line summary."""
        if self.texts_count == 0:
            return "Empty corpus."
        return (
            f"Corpus: {self.texts_count} text(s), {self.total_tokens} words, "
            f"avg quality {self.avg_quality_score:.1f}/100 "
            f"({self.spelling_issues_total} spelling issue(s))."
        )


# ── Analyzer ─────────────────────────────────────────────────────────────────


class BatchAnalyzer:
    """Run corpus-wide analytics over an iterable of texts.

    Example
    -------
    >>> texts = ["نص عربي واضح.", "نص آخر."]
    >>> report = BatchAnalyzer().analyze(texts)
    >>> report.texts_count == 2
    True
    """

    def __init__(self) -> None:
        from aranorm.analysis.corpus_analyzer import CorpusAnalyzer
        from aranorm.analysis.quality_score import QualityScoreAnalyzer
        from aranorm.analysis.spelling_report import SpellingAnalyzer
        from aranorm.utils.language_detector import LanguageDetector

        self._corpus = CorpusAnalyzer()
        self._quality = QualityScoreAnalyzer()
        self._spelling = SpellingAnalyzer()
        self._detector = LanguageDetector()

    def _classify_language(self, text: str) -> str:
        """Map :class:`DetectionResult` to a stable language label."""
        result = self._detector.detect_detailed(text)
        if result.arabic_ratio > 0.5:
            return "arabic"
        if result.latin_ratio > 0.5:
            return "latin"
        if result.arabic_ratio > 0.0 or result.latin_ratio > 0.0:
            return "mixed"
        return result.label

    def analyze(self, texts: Sequence[str]) -> BatchAnalysisReport:
        """Analyze *texts* and return a :class:`BatchAnalysisReport`.

        Parameters
        ----------
        texts:
            Sequence of Arabic (or mixed) texts.
        """
        if not texts:
            return BatchAnalysisReport()

        language_distribution: Dict[str, int] = {}
        dialect_distribution: Dict[str, int] = {}
        quality_scores: List[float] = []
        readability_scores: List[float] = []
        spelling_issues_total = 0
        correction_counts: Dict[str, int] = {}
        vocabulary: set = set()

        # Corpus-level statistics (token/stop-word baselines).
        corpus_result = self._corpus.analyze(texts)

        for text in texts:
            # Language + dialect profiling
            language_distribution[self._classify_language(text)] = (
                language_distribution.get(self._classify_language(text), 0) + 1
            )
            dialect_result = self._detector.detect_detailed(text)
            label = dialect_result.label if dialect_result.label != "unknown" else "unknown"
            dialect_distribution[label] = dialect_distribution.get(label, 0) + 1

            # Quality
            quality = self._quality.analyze(text)
            quality_scores.append(quality.score)
            readability = next(
                (component.score for component in quality.components if component.name == "readability"),
                0.0,
            )
            readability_scores.append(readability)

            # Spelling
            spelling = self._spelling.analyze(text)
            spelling_issues_total += spelling.spelling_issues_found
            for correction in spelling.corrections:
                key = f"{correction.word}->{correction.replacement}"
                correction_counts[key] = correction_counts.get(key, 0) + correction.count

            # Vocabulary union
            vocabulary.update(spelling.original_text.split())

        quality_distribution = QualityDistribution()
        for score in quality_scores:
            if score >= 90.0:
                quality_distribution.excellent += 1
            elif score >= 75.0:
                quality_distribution.good += 1
            elif score >= 55.0:
                quality_distribution.fair += 1
            else:
                quality_distribution.poor += 1

        # Top corpus-wide spelling issues (descending frequency)
        top_issues = [
            {"correction": pair, "count": count}
            for pair, count in sorted(correction_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
        ]

        recommendations = self._build_recommendations(quality_distribution, spelling_issues_total, readability_scores)

        total_tokens = corpus_result.total_tokens if corpus_result.total_tokens else 0
        total_words_or_default = total_tokens if total_tokens else sum(len(text.split()) for text in texts)

        return BatchAnalysisReport(
            texts_count=len(texts),
            total_tokens=total_words_or_default,
            total_chars=sum(len(text) for text in texts),
            avg_quality_score=(round(statistics.fmean(quality_scores), 2) if quality_scores else 0.0),
            quality_distribution=quality_distribution,
            language_distribution=language_distribution,
            dialect_distribution=dialect_distribution,
            avg_readability=(round(statistics.fmean(readability_scores), 2) if readability_scores else 0.0),
            spelling_issues_total=spelling_issues_total,
            unique_words=len(vocabulary),
            top_issues=top_issues,
            recommendations=recommendations,
            corpus_lexical_diversity=corpus_result.lexical_diversity,
        )

    # ── Recommendation engine ────────────────────────────────────────────────

    def _build_recommendations(
        self,
        quality_distribution: QualityDistribution,
        spelling_issues_total: int,
        readability_scores: List[float],
    ) -> List[str]:
        """Derive actionable corpus-level recommendations."""
        recommendations: List[str] = []
        total = (
            quality_distribution.excellent
            + quality_distribution.good
            + quality_distribution.fair
            + quality_distribution.poor
        )
        if total == 0:
            return recommendations

        poor_share = (quality_distribution.poor + quality_distribution.fair) / total
        if poor_share >= 0.5:
            recommendations.append(
                "Over half of the corpus scored fair or poor — "
                "consider running bulk normalization and spelling correction first."
            )

        if spelling_issues_total:
            recommendations.append(
                f"Address {spelling_issues_total} spelling issue(s) before "
                "publishing or feeding the corpus to downstream models."
            )

        low_readability = sum(1 for score in readability_scores if score < 70.0)
        if low_readability >= max(1, total // 3):
            recommendations.append(
                "A significant share of texts is hard to read — " "shorten sentences and simplify vocabulary."
            )

        if not recommendations:
            recommendations.append("Corpus quality looks healthy overall.")
        return recommendations


# ── Module-level convenience ─────────────────────────────────────────────────


def analyze_batch(texts: Sequence[str]) -> BatchAnalysisReport:
    """Run corpus-wide analysis on *texts* and return a :class:`BatchAnalysisReport`.

    Thin convenience wrapper around :class:`BatchAnalyzer`.

    Example
    -------
    >>> report = analyze_batch(["نص عربي.", "نص آخر."])
    >>> report.texts_count == 2
    True
    """
    return BatchAnalyzer().analyze(texts)
