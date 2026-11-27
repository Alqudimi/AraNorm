"""Composite Arabic text quality scoring.

Produces a :class:`TextQualityScore` in the range ``0–100`` by combining
several orthogonal signals:

+---------------------+----------+--------------------------------------------------+
| Component           | Weight   | Source                                           |
+---------------------+----------+--------------------------------------------------+
| Spelling hygiene    | 27%      | Rule-based correction ratio from                 |
|                     |          | :class:`~aranorm.analysis.spelling_report`       |
+---------------------+----------+--------------------------------------------------+
| Consistency         | 23%      | Diacritic / punctuation / script consistency     |
+---------------------+----------+--------------------------------------------------+
| Lexical balance     | 20%      | Stop-word vs content-word ratio from             |
|                     |          | :class:`~aranorm.analysis.text_analyzer`         |
+---------------------+----------+--------------------------------------------------+
| Readability         | 10%      | :class:`~aranorm.analysis.readability`           |
+---------------------+----------+--------------------------------------------------+
| Diacritic guidance  | 5%       | Heuristic presence of harakat                    |
+---------------------+----------+--------------------------------------------------+
| Rhetorical richness | 8%       | Detected rhetorical figures from                 |
|                     |          | :class:`~aranorm.analysis.figurate_analyzer`     |
+---------------------+----------+--------------------------------------------------+
| Structural balance  | 7%       | Parallel-structure balance from                  |
|                     |          | :class:`~aranorm.analysis.rhythm_analyzer` plus  |
|                     |          | filler density from                              |
|                     |          | :class:`~aranorm.analysis.filler_analyzer`       |
+---------------------+----------+--------------------------------------------------+

The composite is a weighted average of per-component scores, each normalized
to ``0–100``. Each component also emits a list of human-readable *issues*
and *suggestions* that justify the final grade.

Example
-------
>>> from aranorm.analysis.quality_score import analyze_quality
>>> result = analyze_quality("هذا نص عربي واضح ومفهوم.")
>>> 0 <= result.score <= 100
True
>>> result.label in ("excellent", "good", "fair", "poor")
True
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from aranorm.analysis.spelling_report import analyze_spelling

# ── Constants ────────────────────────────────────────────────────────────────

_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_ARABIC_LETTER = re.compile(r"[\u0621-\u064A\u0671-\u06D3]")
_LATIN_RUN = re.compile(r"[A-Za-z]+")
_PUNCTUATION = re.compile(r"[.,،؟!؛:()«»\u061F\u060C]")
_SPACE_PUNCTUATION = re.compile(r"\s+[.,،؟!؛:]|\s{3,}")

_COMPONENT_WEIGHTS = {
    "spelling": 0.26,
    "consistency": 0.22,
    "lexical_balance": 0.19,
    "readability": 0.10,
    "diacritics": 0.05,
    "rhetorical_richness": 0.08,
    "structural_balance": 0.07,
    "rhetorical_depth": 0.03,
}

_QUALITY_LABELS: List[Tuple[float, str]] = [
    (90.0, "excellent"),
    (75.0, "good"),
    (55.0, "fair"),
    (0.0, "poor"),
]


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class ComponentScore:
    """One weighted input of the composite quality score.

    Attributes
    ----------
    name:
        Component identifier (e.g. ``"spelling"``).
    score:
        Normalized score in ``0–100``.
    weight:
        Weight of this component in the composite (``0.0–1.0``).
    issues:
        Human-readable problems detected by this component.
    """

    name: str
    score: float
    weight: float
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "name": self.name,
            "score": self.score,
            "weight": self.weight,
            "issues": list(self.issues),
        }


@dataclass
class TextQualityScore:
    """Composite quality assessment for one Arabic text.

    Attributes
    ----------
    score:
        Final quality score in ``0–100``.
    label:
        Qualitative band: ``"excellent"`` (>= 90), ``"good"`` (>= 75),
        ``"fair"`` (>= 55), ``"poor"`` (below 55).
    components:
        Ordered list of the per-component scores that were combined.
    issues:
        All issues aggregated across components.
    suggestions:
        Actionable improvement suggestions aggregated across components.
    analyzed_text_length:
        Character count of the analyzed text.
    """

    score: float
    label: str
    components: List[ComponentScore]
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    analyzed_text_length: int = 0

    # ── Serialization / presentation ─────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "score": self.score,
            "label": self.label,
            "components": [component.to_dict() for component in self.components],
            "issues": list(self.issues),
            "suggestions": list(self.suggestions),
            "analyzed_text_length": self.analyzed_text_length,
        }

    def to_json(self, indent: Optional[int] = 2, ensure_ascii: bool = False) -> str:
        """Return a JSON string of the assessment."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    def summary(self) -> str:
        """Return a human-readable one-line summary."""
        return f"Quality: {self.score:.1f}/100 ({self.label}) — {len(self.issues)} issue(s)."


# ── Component scorers ────────────────────────────────────────────────────────


def _label_for(score: float) -> str:
    """Map a 0-100 score to its qualitative band."""
    for threshold, label in _QUALITY_LABELS:
        if score >= threshold:
            return label
    return "poor"


def _score_spelling(text: str, suggestions: List[str]) -> float:
    """Score based on the spelling correction ratio (27%).

    Beyond the raw correct-word ratio, the correction confidence values are
    weighted: confident rule-based suggestions (confidence near 0.9) are
    treated as confirmed issues, while low-confidence synthetic suggestions
    soften the penalty. The final score is

        base * (1 - 0.15 * mean_confidence)  when issues exist
    """
    report = analyze_spelling(text)
    if report.total_words == 0:
        return 100.0
    ratio = report.correct_ratio
    base = ratio * 100.0
    if report.spelling_issues_found:
        mean_confidence = 0.0
        if report.corrections:
            mean_confidence = sum(
                suggestion.get("confidence", 0.0)
                for correction in report.corrections
                for suggestion in correction.suggestions
            ) / len(report.corrections)
        weighted = base * (1.0 - 0.15 * min(mean_confidence, 1.0))
        suggestions.append(
            f"Fix {report.spelling_issues_found} spelling issue(s): "
            + ", ".join(f"{correction.word} → {correction.replacement}" for correction in report.corrections[:5])
        )
        return round(max(0.0, weighted), 2)
    return round(base, 2)


def _score_consistency(text: str, suggestions: List[str]) -> float:
    """Score script and punctuation consistency (23%)."""
    issues: List[str] = []
    latin_chars = sum(len(match.group()) for match in _LATIN_RUN.finditer(text))
    arabic_chars = sum(1 for match in _ARABIC_LETTER.finditer(text))

    score = 100.0

    if arabic_chars > 0 and latin_chars > arabic_chars:
        score -= 25.0
        issues.append("Latin characters dominate the Arabic text.")
        suggestions.append("Consider separating Latin fragments from Arabic prose.")

    mixed_runs = len(_LATIN_RUN.findall(text))
    if arabic_chars > 5 and 0 < mixed_runs <= 3:
        pass  # minor mixing is acceptable
    elif mixed_runs > 3:
        score -= 10.0
        issues.append("Frequent Latin/Arabic mixing detected.")
        suggestions.append("Reduce code-switching for formal Arabic documents.")

    if _SPACE_PUNCTUATION.search(text):
        score -= 10.0
        issues.append("Irregular whitespace before punctuation.")
        suggestions.append("Attach punctuation directly to the preceding word.")

    arabic_letters = set(_ARABIC_LETTER.findall(text))
    if arabic_letters:
        alef_variants = sum(1 for ch in ("ا", "أ", "آ", "إ") if ch in arabic_letters)
        if len(arabic_letters) > 4 and alef_variants <= 1:
            score -= 5.0
            issues.append("Limited hamza/alef variation (possible un-hamza'd text).")
            suggestions.append("Apply hamza normalization for formal writing.")

    score = max(0.0, score)
    if issues:
        suggestions[0:0] = []  # no-op, keep suggestions ordered by caller
    return round(score, 2)


def _score_lexical_balance(text: str, suggestions: List[str]) -> float:
    """Score stop-word vs content-word balance (20%)."""
    try:
        from aranorm.analysis.text_analyzer import TextAnalyzer
    except ImportError:  # pragma: no cover (dependency always present)
        return 50.0

    analysis = TextAnalyzer().analyze(text)
    if analysis.total_words == 0:
        return 100.0

    ratio = analysis.stop_words_ratio
    # Healthy Arabic prose keeps stop words between 20% and 60%.
    if ratio < 0.20:
        score = 100.0 - (0.20 - ratio) * 100.0
        suggestions.append("Text is unusually dense — consider simplifying.")
    elif ratio > 0.60:
        score = 100.0 - (ratio - 0.60) * 100.0
        suggestions.append("High stop-word density — add more content words.")
    else:
        score = 100.0
    return round(max(0.0, min(100.0, score)), 2)


def _score_readability(text: str) -> float:
    """Score multi-metric readability (15%)."""
    try:
        from aranorm.analysis.readability import ArabicReadabilityAnalyzer
    except ImportError:  # pragma: no cover (dependency always present)
        return 50.0

    analyzer = ArabicReadabilityAnalyzer()
    return round(analyzer.analyze(text).score, 2)


def _score_rhetorical_richness(text: str, suggestions: List[str]) -> float:
    """Score rhetorical-figure richness (8%).

    Rewards texts that use recognised Arabic rhetorical devices (تشبيه,
    طباق، ترادف، تكرار). A plain text scores 50 (neutral baseline); each
    detected figure class lifts the score toward 100, while a figure
    density below the ``moderate`` band keeps the score near the baseline.
    """
    try:
        from aranorm.analysis.figurate_analyzer import analyze_figurative
    except ImportError:  # pragma: no cover (dependency always present)
        return 50.0

    result = analyze_figurative(text)
    if result.word_count == 0:
        return 50.0
    figure_density = len(result.occurrences) / max(1, result.word_count)
    score = 50.0 + min(1.0, figure_density * 10.0) * 50.0
    if result.label == "plain" and not result.figures:
        score = 50.0
        suggestions.append("Text lacks rhetorical figures; enrichment improves engagement.")
    return round(max(0.0, min(100.0, score)), 2)


def _score_diacritics(text: str, suggestions: List[str]) -> float:
    """Score diacritic guidance density (5%)."""
    arabic_chars = sum(1 for match in _ARABIC_LETTER.finditer(text))
    if arabic_chars == 0:
        return 100.0
    density = sum(1 for match in _DIACRITICS.finditer(text)) / arabic_chars
    if density >= 0.15:
        return 100.0
    if density >= 0.05:
        return 75.0
    if density > 0.0:
        return 50.0
    suggestions.append("Text carries no diacritics; consider voweled text for readers.")
    return 25.0


def _score_structural_balance(text: str, suggestions: List[str]) -> float:
    """Score structural balance: parallel rhythm plus padding hygiene (7%).

    Combines the parallel-structure balance reported by
    :class:`~aranorm.analysis.rhythm_analyzer` (weighted 50%) with filler
    cleanliness reported by :class:`~aranorm.analysis.filler_analyzer`
    (weighted 50%). A text that flows with parallel structure and carries
    no hedging filler scores near 100.
    """
    balance_score = 50.0
    cleanliness_score = 50.0
    try:
        from aranorm.analysis.rhythm_analyzer import analyze_rhythm
    except ImportError:  # pragma: no cover (dependency always present)
        balance_score = 50.0
    else:
        rhythm_result = analyze_rhythm(text)
        balance = rhythm_result.parallel_balance
        if balance >= 0.7:
            balance_score = 100.0
        elif balance >= 0.4:
            balance_score = 75.0
        elif balance > 0.0:
            balance_score = 50.0
        else:
            balance_score = 25.0
            suggestions.append("Sentence structure lacks parallel balance; revise for rhythm.")
    try:
        from aranorm.analysis.filler_analyzer import analyze_fillers
    except ImportError:  # pragma: no cover (dependency always present)
        cleanliness_score = 50.0
    else:
        filler_result = analyze_fillers(text)
        if filler_result.filler_density == 0.0:
            cleanliness_score = 100.0
        elif filler_result.filler_density < 0.05:
            cleanliness_score = 75.0
        else:
            cleanliness_score = 50.0
            suggestions.append("Hedging filler phrases dilute the argument; prune padding.")
    composite = 0.5 * balance_score + 0.5 * cleanliness_score
    return round(max(0.0, min(100.0, composite)), 2)


def _score_rhetorical_depth(text: str, suggestions: List[str]) -> float:
    """Score layered rhetorical depth (3%).

    A composite of rhetorical-questioning intensity
    (:func:`~aranorm.analysis.rhetorical_question_analyzer.analyze_rquestions`)
    and cross-sentence cohesion
    (:func:`~aranorm.analysis.anaphora_analyzer.analyze_anaphora`). A text that
    asks probing questions *and* anchors its references earns near 100 — a
    hallmark of engaged argumentative prose. Plain, loosely-connected texts
    land near the 50 baseline.
    """
    question_score = 50.0
    try:
        from aranorm.analysis.rhetorical_question_analyzer import analyze_rquestions
    except ImportError:  # pragma: no cover (dependency always present)
        question_score = 50.0
    else:
        rresult = analyze_rquestions(text)
        label = rresult.label
        if label == "interrogative-rich":
            question_score = 100.0
        elif label == "moderate":
            question_score = 75.0
        else:
            question_score = 30.0

    cohesion_score = 50.0
    try:
        from aranorm.analysis.anaphora_analyzer import analyze_anaphora
    except ImportError:  # pragma: no cover (dependency always present)
        cohesion_score = 50.0
    else:
        aresult = analyze_anaphora(text)
        label = aresult.label
        if label == "tightly-cohesive":
            cohesion_score = 100.0
        elif label == "moderate":
            cohesion_score = 75.0
        else:
            cohesion_score = 30.0

    if question_score == 30.0 and cohesion_score == 30.0:
        suggestions.append("Text carries little questioning or reference anchoring; deepen the argument.")

    composite = 0.5 * question_score + 0.5 * cohesion_score
    return round(max(0.0, min(100.0, composite)), 2)


# ── Analyzer ─────────────────────────────────────────────────────────────────


class QualityScoreAnalyzer:
    """Compute composite Arabic text quality assessments.

    Example
    -------
    >>> analyzer = QualityScoreAnalyzer()
    >>> result = analyzer.analyze("هذا نص عربي واضح.")
    >>> result.label
    'good'
    """

    def analyze(self, text: str) -> TextQualityScore:
        """Analyze *text* and return a :class:`TextQualityScore`.

        Parameters
        ----------
        text:
            Arabic text to assess. Non-Arabic fragments do not cause
            failures; they affect the consistency component instead.
        """
        suggestions: List[str] = []
        issues: List[str] = []

        scoring = [
            _score_spelling(text, suggestions),
            _score_consistency(text, suggestions),
            _score_lexical_balance(text, suggestions),
            _score_readability(text),
            _score_diacritics(text, suggestions),
            _score_rhetorical_richness(text, suggestions),
            _score_structural_balance(text, suggestions),
            _score_rhetorical_depth(text, suggestions),
        ]
        names = [
            "spelling",
            "consistency",
            "lexical_balance",
            "readability",
            "diacritics",
            "rhetorical_richness",
            "structural_balance",
            "rhetorical_depth",
        ]
        components = [
            ComponentScore(name=name, score=scoring[index], weight=_COMPONENT_WEIGHTS[name])
            for index, name in enumerate(names)
        ]
        if any(component.score < 75.0 for component in components):
            issues.append("Some quality components scored below 75.")

        composite = sum(component.score * component.weight for component in components)
        composite = round(max(0.0, min(100.0, composite)), 2)

        return TextQualityScore(
            score=composite,
            label=_label_for(composite),
            components=components,
            issues=issues,
            suggestions=suggestions,
            analyzed_text_length=len(text),
        )


# ── Module-level convenience ─────────────────────────────────────────────────


def analyze_quality(text: str) -> TextQualityScore:
    """Compute the composite quality score for *text*.

    Thin convenience wrapper around :class:`QualityScoreAnalyzer`.

    Example
    -------
    >>> result = analyze_quality("نص عربي جيد.")
    >>> 0 <= result.score <= 100
    True
    """
    return QualityScoreAnalyzer().analyze(text)
