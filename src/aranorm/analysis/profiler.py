"""Composite one-pass text profiling over multiple AraNorm analyzers.

Writing workflows usually need several analyses at once (sentiment, coherence,
quality, readability, word frequency, style, emotions, topics). Running each
analyzer separately is wasteful; :class:`AnalysisProfiler` orchestrates the
full suite in a single pass and returns a consolidated payload that also
derives *cross-signal insights* — short notes that connect signals from
different analyzers (for example, a coherent text carrying a negative tone).

Enabled axes default to all of: sentiment, coherence, quality, readability,
style, emotions, word_frequency and topics. Each axis can be disabled when
instantiating the profiler.

Example
-------
>>> from aranorm.analysis.profiler import profile_text
>>> result = profile_text("حيثما اجتمعت الإرادة، تحقق النصر")
>>> "sentiment" in result.axes
True
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from aranorm.analysis.anaphora_analyzer import analyze_anaphora
from aranorm.analysis.complexity_analyzer import analyze_complexity
from aranorm.analysis.contrast_analyzer import analyze_contrast
from aranorm.analysis.coherence_score import CoherenceAnalyzer
from aranorm.analysis.filler_analyzer import analyze_fillers
from aranorm.analysis.emotion_analyzer import EmotionAnalyzer
from aranorm.analysis.entity_analyzer import EntityAnalyzer
from aranorm.analysis.figurate_analyzer import analyze_figurative
from aranorm.analysis.loanword_analyzer import analyze_loanwords
from aranorm.analysis.numeric_analyzer import analyze_numeric
from aranorm.analysis.quotation_analyzer import analyze_quotations
from aranorm.analysis.rhetorical_question_analyzer import analyze_rquestions
from aranorm.analysis.rhythm_analyzer import analyze_rhythm
from aranorm.analysis.root_density_analyzer import analyze_root_density
from aranorm.analysis.wordplay_analyzer import analyze_wordplay
from aranorm.utils.dialect_depth import analyze_dialect
from aranorm.analysis.quality_score import QualityScoreAnalyzer
from aranorm.analysis.readability import ArabicReadabilityAnalyzer
from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer
from aranorm.analysis.style_analyzer import StyleAnalyzer
from aranorm.analysis.topic_classifier import TopicClassifier
from aranorm.analysis.word_frequency import WordFrequencyProfiler

_DEFAULT_AXES = (
    "sentiment",
    "coherence",
    "quality",
    "readability",
    "style",
    "emotions",
    "word_frequency",
    "topics",
    "rhythm",
    "figurate",
    "numeric",
    "dialect",
    "entities",
    "quotation",
    "loanwords",
    "root_density",
    "contrast",
    "fillers",
    "complexity",
    "rquestions",
    "anaphora",
    "wordplay",
)


@dataclass
class ProfilerInsight:
    """A cross-signal note derived from two or more analysis axes."""

    rule: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"rule": self.rule, "message": self.message}


@dataclass
class ProfilerResult:
    """Consolidated profiling output for a single Arabic text."""

    text: str
    axes: Dict[str, Dict[str, Any]]
    insights: List[ProfilerInsight]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "axes": self.axes,
            "insights": [insight.to_dict() for insight in self.insights],
        }

    def to_json(self, indent: Optional[int] = 2, ensure_ascii: bool = False) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


class AnalysisProfiler:
    """One-pass composite text profiler.

    Example
    -------
    >>> profiler = AnalysisProfiler()
    >>> result = profiler.profile("هذا نص تجريبي قصير")
    >>> all(name in result.axes for name in ("sentiment", "rhythm", "figurate",
    ...                                      "numeric", "dialect"))
    True
    """

    def __init__(
        self,
        axes: Optional[List[str]] = None,
        topic_fields: Optional[List[str]] = None,
    ) -> None:
        self._axes: tuple = tuple(axes if axes is not None else _DEFAULT_AXES)
        self._sentiment = SentimentAnalyzer()
        self._coherence = CoherenceAnalyzer()
        self._quality = QualityScoreAnalyzer()
        self._readability = ArabicReadabilityAnalyzer()
        self._style = StyleAnalyzer()
        self._emotions = EmotionAnalyzer()
        self._dialect = analyze_dialect
        self._entities = EntityAnalyzer()
        self._word_frequency = WordFrequencyProfiler()
        self._topics = TopicClassifier(topics=topic_fields) if topic_fields else TopicClassifier()

    # ── Internals ────────────────────────────────────────────────────────────

    def _insight_cross_signals(self, axes: Dict[str, Dict[str, Any]]) -> List[ProfilerInsight]:
        insights: List[ProfilerInsight] = []
        sentiment = axes.get("sentiment")
        coherence = axes.get("coherence")
        quality = axes.get("quality")
        emotions = axes.get("emotions")

        if sentiment is not None and coherence is not None:
            tone = sentiment.get("label", "")
            strength = coherence.get("label", "")
            if strength in ("strong", "moderate") and tone == "negative":  # type: ignore[comparison-overlap]
                insights.append(
                    ProfilerInsight(
                        rule="coherent_negative",
                        message="النص متماسك بنيوياً لكنه يحمل نبرة سلبية.",
                    )
                )
            elif strength == "fragmented" and tone == "positive":
                insights.append(
                    ProfilerInsight(
                        rule="positive_fragmented",
                        message="النص إيجابي عاطفياً لكن بنيته متقطعة وغير متماسكة.",
                    )
                )

        if quality is not None and sentiment is not None:
            if quality.get("label", "") == "excellent" and sentiment.get("label", "") in ("positive", "neutral"):
                insights.append(
                    ProfilerInsight(
                        rule="high_quality_positive",
                        message="جودة النص مرتفعة والنبرة محايدة أو إيجابية.",
                    )
                )

        if emotions is not None:
            dominant = emotions.get("dominant_emotion", "neutral")
            if dominant not in ("neutral", "joy", "trust", "hope"):
                insights.append(
                    ProfilerInsight(
                        rule="negative_emotion",
                        message=f"العاطفة الغالبة على النص هي {dominant}.",
                    )
                )

        rhythm = axes.get("rhythm")
        style = axes.get("style")
        if rhythm is not None and style is not None:
            if rhythm.get("label", "flat") == "rhythmic" and style.get("label", "") == "formal":
                insights.append(
                    ProfilerInsight(
                        rule="formal_rhythmic",
                        message="نص فصيح بنسج إيقاعي متوازن — أسلوب أدبي مميز.",
                    )
                )

        figurate = axes.get("figurate")
        if figurate is not None and figurate.get("label", "plain") == "rich":
            figure_names = "، ".join(figurate.get("figures", []))
            insights.append(
                ProfilerInsight(
                    rule="rhetorically_rich",
                    message=f"النص غني بالصور البلاغية ({figure_names}).",
                )
            )

        numeric = axes.get("numeric")
        if numeric is not None and numeric.get("digit_system_mix", False):
            insights.append(
                ProfilerInsight(
                    rule="mixed_digit_systems",
                    message="النص يخلط بين أنظمة الأرقام الغربية والعربية الهندية.",
                )
            )

        dialect = axes.get("dialect")
        if dialect is not None and dialect.get("is_dialectal", False):
            insights.append(
                ProfilerInsight(
                    rule="dialectal_regional",
                    message=f"النص يحمل إشارات لهجة إقليمية غالبة: {dialect.get('dominant_region')}.",
                )
            )

        quotation = axes.get("quotation")
        if quotation is not None:
            if quotation.get("quotation_ratio", 0.0) >= 0.3 or quotation.get("label", "") in (
                "quoted",
                "partially_quoted",
            ):
                insights.append(
                    ProfilerInsight(
                        rule="citation_heavy",
                        message="النص يعتمد على الاقتباسات المباشرة والتوثيق — نمط تحريري/إخباري.",
                    )
                )

        loanwords = axes.get("loanwords")
        if loanwords is not None and loanwords.get("label", "pure_arabic") != "pure_arabic":
            label = loanwords.get("label", "")
            if label == "mixed":
                message = "النص يحتوي مقاطع لاتينية واضحة (تبديل لغوي أو أسماء علامات)."
            else:
                message = "النص يحتوي كلمات معرَّبة دخيلة — لغة رقمية/عامية."
            insights.append(ProfilerInsight(rule="loanwords_flagged", message=message))

        root_density = axes.get("root_density")
        if root_density is not None and root_density.get("label", "") == "root_rich":
            insights.append(
                ProfilerInsight(
                    rule="root_rich",
                    message="النص يوظف تنوعًا جذريًا واسعًا — معجم لغوي ثري.",
                )
            )

        entities = axes.get("entities")
        if entities is not None and entities.get("person_count", 0) >= 1:
            person_count = entities.get("person_count", 0)
            insights.append(
                ProfilerInsight(
                    rule="person_named",
                    message=f"النص يذكر أسماء شخصيات ({person_count}) — نبرة شخصية/إخبارية.",
                )
            )

        contrast = axes.get("contrast")
        if contrast is not None and contrast.get("label", "neutral") in (
            "contrastive",
            "moderate",
        ):
            insights.append(
                ProfilerInsight(
                    rule="contrastive_style",
                    message="النص يوظف التضاد اللغوي (طباق/مقابلة) — أسلوب جدلي إقناعي.",
                )
            )

        fillers = axes.get("fillers")
        if fillers is not None and fillers.get("label", "clean") == "filler_heavy":
            insights.append(
                ProfilerInsight(
                    rule="filler_heavy",
                    message="كثافة عبارات الحشو مرتفعة — يُنصح بالتقشف اللغوي.",
                )
            )

        rquestions = axes.get("rquestions")
        if rquestions is not None and rquestions.get("label", "") == "interrogative-rich":
            density = rquestions.get("question_density", 0.0)
            insights.append(
                ProfilerInsight(
                    rule="interrogative_rich",
                    message=f"النص غني بالأسئلة والاستفهامات ({density:.1f} لكل 100 كلمة) — أسلوب جدلي/حواري.",
                )
            )

        anaphora = axes.get("anaphora")
        if anaphora is not None and anaphora.get("label", "") == "tightly-cohesive":
            insights.append(
                ProfilerInsight(
                    rule="tightly_cohesive",
                    message="النص متماسك مرجعيًا — إشارات إحالية متنوعة عبر الجمل.",
                )
            )
        elif anaphora is not None and anaphora.get("label", "") == "loose":
            insights.append(
                ProfilerInsight(
                    rule="loose_cohesion",
                    message="التماسك المرجعي بين الجمل منخفض — إعادة الربط الإحالي مفيدة.",
                )
            )

        wordplay = axes.get("wordplay")
        if wordplay is not None and wordplay.get("label", "plain") != "plain":
            label = wordplay.get("label", "")
            insights.append(
                ProfilerInsight(
                    rule="wordplay_present",
                    message="النص يوظف تلاعبًا لفظيًا ("
                    + ("جناس" if "paronomasia" in label else "سجع" if "saj" in label else "تورية")
                    + ") — أسلوب فني بلاغي.",
                )
            )

        complexity = axes.get("complexity")
        readability = axes.get("readability")
        if complexity is not None and complexity.get("label", "") == "complex":
            readability_score = (readability or {}).get("score", 50.0) if readability else 50.0
            if readability_score < 60.0:
                insights.append(
                    ProfilerInsight(
                        rule="complex_hard_to_read",
                        message="التعقيد الصرفي مرتفع مع قابلية قراءة منخفضة — تبسيط مفيد.",
                    )
                )

        return insights

    # ── Public API ───────────────────────────────────────────────────────────

    def profile(self, text: str) -> ProfilerResult:
        """Run all enabled analyzers on *text* and return a consolidated result."""
        axes: Dict[str, Dict[str, Any]] = {}
        if "sentiment" in self._axes:
            axes["sentiment"] = self._sentiment.analyze(text).to_dict()
        if "coherence" in self._axes:
            axes["coherence"] = self._coherence.analyze(text).to_dict()
        if "quality" in self._axes:
            axes["quality"] = self._quality.analyze(text).to_dict()
        if "readability" in self._axes:
            axes["readability"] = self._readability.analyze(text).to_dict()
        if "style" in self._axes:
            axes["style"] = self._style.analyze(text).to_dict()
        if "emotions" in self._axes:
            axes["emotions"] = self._emotions.analyze(text).to_dict()
        if "word_frequency" in self._axes:
            axes["word_frequency"] = self._word_frequency.profile(text).to_dict()
        if "topics" in self._axes:
            axes["topics"] = self._topics.classify(text).to_dict()
        if "rhythm" in self._axes:
            axes["rhythm"] = analyze_rhythm(text).to_dict()
        if "figurate" in self._axes:
            axes["figurate"] = analyze_figurative(text).to_dict()
        if "numeric" in self._axes:
            axes["numeric"] = analyze_numeric(text).to_dict()
        if "dialect" in self._axes:
            axes["dialect"] = self._dialect(text).to_dict()
        if "entities" in self._axes:
            axes["entities"] = self._entities.analyze(text).to_dict()
        if "quotation" in self._axes:
            axes["quotation"] = analyze_quotations(text).to_dict()
        if "loanwords" in self._axes:
            axes["loanwords"] = analyze_loanwords(text).to_dict()
        if "root_density" in self._axes:
            axes["root_density"] = analyze_root_density(text).to_dict()
        if "contrast" in self._axes:
            axes["contrast"] = analyze_contrast(text).to_dict()
        if "fillers" in self._axes:
            axes["fillers"] = analyze_fillers(text).to_dict()
        if "complexity" in self._axes:
            axes["complexity"] = analyze_complexity(text).to_dict()
        if "rquestions" in self._axes:
            axes["rquestions"] = analyze_rquestions(text).to_dict()
        if "anaphora" in self._axes:
            axes["anaphora"] = analyze_anaphora(text).to_dict()
        if "wordplay" in self._axes:
            axes["wordplay"] = analyze_wordplay(text).to_dict()
        return ProfilerResult(
            text=text,
            axes=axes,
            insights=self._insight_cross_signals(axes),
        )

    def profile_batch(self, texts: List[str]) -> List[ProfilerResult]:
        """Profile a list of texts independently."""
        return [self.profile(text) for text in texts]


def profile_text(text: str) -> ProfilerResult:
    """Module-level convenience wrapper over :class:`AnalysisProfiler`."""
    return AnalysisProfiler().profile(text)
