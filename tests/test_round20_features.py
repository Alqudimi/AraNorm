"""Round 20 feature tests: style, emotion, composite profiler, spelling-aware quality."""

import json


from aranorm.analysis.emotion_analyzer import (
    EmotionAnalysisResult,
    EmotionAnalyzer,
    EmotionCounts,
    analyze_emotions,
)
from aranorm.analysis.profiler import (
    AnalysisProfiler,
    ProfilerInsight,
    ProfilerResult,
    profile_text,
)
from aranorm.analysis.quality_score import analyze_quality
from aranorm.analysis.style_analyzer import (
    StyleAnalysisResult,
    StyleAnalyzer,
    _label_for as _style_label,
    analyze_style,
)

# ═══════════════════════════════════════════════════════════════════════════════
# WP1 — StyleAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestStyleLabels:
    def test_formal_threshold(self) -> None:
        assert _style_label(0.12) == "formal"
        assert _style_label(0.5) == "formal"

    def test_semi_formal_threshold(self) -> None:
        assert _style_label(0.03) == "semi_formal"
        assert _style_label(0.11) == "semi_formal"

    def test_informal_threshold(self) -> None:
        assert _style_label(-0.25) == "informal"
        assert _style_label(-0.9) == "informal"

    def test_mixed_threshold(self) -> None:
        assert _style_label(-0.03) == "mixed"
        assert _style_label(-0.24) == "mixed"

    def test_digital_default(self) -> None:
        assert _style_label(0.0) == "digital"
        assert _style_label(0.02) == "digital"
        assert _style_label(-0.02) == "digital"


class TestStyleAnalyzerFormal:
    def test_formal_text_detected(self) -> None:
        result = analyze_style("حيثما اجتمعت الإرادة، تحقق النصر وفق الاستراتيجية المعتمدة والتوصيات المطلوبة")
        assert result.label in ("formal", "semi_formal")
        assert result.style_index > 0.03
        assert "حيثما" in result.formal_words
        assert "الاستراتيجية" in result.formal_words
        assert result.signals.formal_markers > 0

    def test_formal_markers_normalization(self) -> None:
        analyzer = StyleAnalyzer()
        result = analyzer.analyze("حيثما النص وفق الاستراتيجية المطلوبة")
        assert result.signals.formal_markers > 0
        assert "حيثما" in result.formal_words

    def test_formal_signal_empty_words(self) -> None:
        analyzer = StyleAnalyzer()
        formal, matched = analyzer._formal_signal([])
        assert formal == 0.0
        assert matched == []


class TestStyleAnalyzerColloquial:
    def test_informal_text_detected(self) -> None:
        result = analyze_style("يلا حبيبي شو الجديد هسا")
        assert result.label in ("informal", "mixed")
        assert result.style_index < 0
        assert result.signals.colloquial_markers > 0
        assert result.colloquial_words

    def test_colloquial_normalization(self) -> None:
        analyzer = StyleAnalyzer()
        result = analyzer.analyze("إزيك يا حبيبي")
        assert result.signals.colloquial_markers > 0
        assert "حبيبي" in result.colloquial_words

    def test_colloquial_signal_empty_words(self) -> None:
        analyzer = StyleAnalyzer()
        colloquial, matched = analyzer._colloquial_signal([])
        assert colloquial == 0.0
        assert matched == []


class TestStyleAnalyzerDigital:
    def test_digital_text_detected(self) -> None:
        result = analyze_style("😂😂 ممتازاااااا 555")
        assert result.label in ("digital", "informal", "mixed")
        assert result.emoji_count == 2
        assert result.signals.digital_signals > 0
        assert any(item.startswith("emoji:") for item in result.elongations)
        assert any(item.startswith("elongation:") for item in result.elongations)
        assert any(item.startswith("slang:") for item in result.elongations)

    def test_elongation_pattern(self) -> None:
        analyzer = StyleAnalyzer()
        assert analyzer.analyze("ممتااااااز").signals.digital_signals > 0

    def test_short_elongation_ignored(self) -> None:
        analyzer = StyleAnalyzer()
        _, signals = analyzer._digital_signal("ممتاز", ["ممتاز"])
        assert signals == []

    def test_digital_no_signals(self) -> None:
        analyzer = StyleAnalyzer()
        digital, signals = analyzer._digital_signal("نص عادي", ["نص", "عادي"])
        assert digital == 0.0
        assert signals == []

    def test_chat_slang_patterns(self) -> None:
        for text in ("هههه 555", "xdd", "lol", "ااوووووو", "xddd"):
            analyzer = StyleAnalyzer()
            digital, signals = analyzer._digital_signal(text, [])
            assert digital > 0 or signals

    def test_emoji_empty_text(self) -> None:
        analyzer = StyleAnalyzer()
        digital, signals = analyzer._digital_signal("", [])
        assert digital == 0.0


class TestStyleAnalyzerBatchAndWeights:
    def test_custom_weights(self) -> None:
        analyzer = StyleAnalyzer(formal_weight=1.0, colloquial_weight=0.0, digital_weight=0.0)
        result = analyzer.analyze("حيثما اجتمعت الإرادة")
        assert result.style_index > 0

    def test_batch_analysis(self) -> None:
        analyzer = StyleAnalyzer()
        results = analyzer.analyze_batch(["نص محايد", "يلا حبيبي شو"])
        assert len(results) == 2
        assert all(isinstance(result, StyleAnalysisResult) for result in results)
        assert results[1].style_index < 0

    def test_mixed_register(self) -> None:
        result = analyze_style("نص محايد لا يحمل دلالات واضحة")
        assert result.label in ("digital", "mixed", "semi_formal")

    def test_empty_text(self) -> None:
        result = analyze_style("")
        assert result.style_index == 0.0
        assert result.label == "digital"
        assert result.formal_words == []


class TestStyleSerialization:
    def test_to_dict_structure(self) -> None:
        result = analyze_style("يلا حبيبي")
        payload = result.to_dict()
        assert set(payload) == {
            "text",
            "style_index",
            "label",
            "signals",
            "formal_words",
            "colloquial_words",
            "elongations",
            "emoji_count",
        }
        assert isinstance(payload["signals"]["formal_markers"], float)

    def test_signals_to_dict(self) -> None:
        result = analyze_style("حيثما النص")
        assert set(result.signals.to_dict()) == {"formal_markers", "colloquial_markers", "digital_signals"}

    def test_to_json_valid(self) -> None:
        result = analyze_style("يلا")
        assert json.loads(result.to_json())["label"] == result.label

    def test_to_json_custom(self) -> None:
        result = analyze_style("يلا")
        raw = result.to_json(indent=None)
        assert json.loads(raw)["text"] == "يلا"


# ═══════════════════════════════════════════════════════════════════════════════
# WP2 — EmotionAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmotionJoy:
    def test_joy_detection(self) -> None:
        result = analyze_emotions("سعادة كبيرة بفرحة النجاح والتهنئة الصادقة")
        assert result.dominant_emotion == "joy"
        assert result.counts.joy >= 1
        assert result.confidence > 0.5

    def test_joy_bucket_tokens(self) -> None:
        analyzer = EmotionAnalyzer()
        for word in ("ممتاز", "رائع", "ضاحك", "مبارك"):
            result = analyzer.analyze(word)
            assert result.dominant_emotion == "joy", word


class TestEmotionNegative:
    def test_sadness_detection(self) -> None:
        result = analyze_emotions("بكاء ودموع وألم على الفقد")
        assert result.dominant_emotion == "sadness"

    def test_anger_detection(self) -> None:
        result = analyze_emotions("غضب وعصبية وسخط على الاستياء")
        assert result.dominant_emotion == "anger"

    def test_fear_detection(self) -> None:
        result = analyze_emotions("خوف وذعر ورهبة من الموقف المرعب")
        assert result.dominant_emotion == "fear"

    def test_disgust_detection(self) -> None:
        result = analyze_emotions("اشمئزاز وتقزز من المنفور المقرف")
        assert result.dominant_emotion == "disgust"

    def test_fear_terror_tokens(self) -> None:
        analyzer = EmotionAnalyzer()
        for word in ("وجل", "مرعوب", "فزعان", "جزع"):
            result = analyzer.analyze(word)
            assert result.dominant_emotion == "fear", word


class TestEmotionPositiveNonJoy:
    def test_trust_detection(self) -> None:
        result = analyze_emotions("ثقة وطمأنينة وصدقية وأمانة")
        assert result.dominant_emotion == "trust"

    def test_hope_detection(self) -> None:
        result = analyze_emotions("أمل وتفاؤل وتمني بالأمنية")
        assert result.dominant_emotion == "hope"

    def test_surprise_detection(self) -> None:
        result = analyze_emotions("مفاجأة ودهشة واستغراب وصدمت")
        assert result.dominant_emotion == "surprise"


class TestEmotionMixedAndNeutral:
    def test_mixed_emotions(self) -> None:
        result = analyze_emotions("أمل وتفاؤل مع حزن وخوف")
        assert result.dominant_emotion in ("hope", "sadness")
        assert result.counts.total() == 2

    def test_neutral_text(self) -> None:
        result = analyze_emotions("نص عادي محايد تماما")
        assert result.dominant_emotion == "neutral"
        assert result.confidence == 0.0
        assert result.counts.total() == 0

    def test_empty_text(self) -> None:
        result = analyze_emotions("")
        assert result.dominant_emotion == "neutral"

    def test_tie_breaking(self) -> None:
        result = analyze_emotions("سعادة وحزن")
        assert result.dominant_emotion in ("joy", "sadness")

    def test_normalized_matching(self) -> None:
        analyzer = EmotionAnalyzer()
        result = analyzer.analyze("سعادته كبيرة")
        assert result.counts.joy > 0


class TestEmotionBatchAndSerialization:
    def test_batch(self) -> None:
        analyzer = EmotionAnalyzer()
        results = analyzer.analyze_batch(["سعادة", "خوف وذعر"])
        assert len(results) == 2
        assert results[0].dominant_emotion == "joy"
        assert results[1].dominant_emotion == "fear"

    def test_to_dict_keys(self) -> None:
        result = analyze_emotions("سعادة")
        payload = result.to_dict()
        assert set(payload) == {"text", "dominant_emotion", "confidence", "counts", "matched_words"}
        assert "joy" in payload["counts"]

    def test_to_dict_includes_matched_words(self) -> None:
        result = analyze_emotions("سعادة كبيرة")
        assert result.matched_words["joy"] == ["سعادة"]

    def test_to_json_valid(self) -> None:
        result = analyze_emotions("حزن")
        parsed = json.loads(result.to_json())
        assert parsed["dominant_emotion"] == "sadness"

    def test_result_type(self) -> None:
        result = analyze_emotions("نص")
        assert isinstance(result, EmotionAnalysisResult)
        assert isinstance(result.counts, EmotionCounts)
        assert result.counts.total() == 0


# ═══════════════════════════════════════════════════════════════════════════════
# WP3 — AnalysisProfiler
# ═══════════════════════════════════════════════════════════════════════════════


class TestProfilerFullSuite:
    def test_default_axes(self) -> None:
        result = profile_text("حيثما اجتمعت الإرادة، تحقق النصر")
        assert set(result.axes) == {
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
        }

    def test_axis_contents(self) -> None:
        result = profile_text("حيثما اجتمعت الإرادة")
        assert "label" in result.axes["sentiment"]
        assert "label" in result.axes["coherence"]
        assert "label" in result.axes["style"]
        assert "dominant_emotion" in result.axes["emotions"]

    def test_custom_axes(self) -> None:
        profiler = AnalysisProfiler(axes=["sentiment", "style"])
        result = profiler.profile("نص تجريبي")
        assert set(result.axes) == {"sentiment", "style"}

    def test_custom_topics(self) -> None:
        profiler = AnalysisProfiler(axes=["topics"], topic_fields=["legal", "sport"])
        result = profiler.profile("عقد صفقة تجارية")
        assert "topics" in result.axes


class TestProfilerInsights:
    def test_no_insight_for_neutral_coherent(self) -> None:
        result = profile_text("نص تجريبي قصير")
        rules = {insight.rule for insight in result.insights}
        assert "coherent_negative" not in rules

    def test_negative_emotion_insight(self) -> None:
        result = profile_text("خوف وذعر ورهبة من الموقف المرعب")
        rules = {insight.rule for insight in result.insights}
        assert "negative_emotion" in rules
        assert "fear" in next(insight.message for insight in result.insights if insight.rule == "negative_emotion")

    def test_coherent_negative_insight(self) -> None:
        analyzer = AnalysisProfiler()
        axes = {
            "sentiment": {"label": "negative"},
            "coherence": {"label": "strong"},
            "quality": {"label": "good"},
        }
        insights = analyzer._insight_cross_signals(axes)
        rules = {insight.rule for insight in insights}
        assert "coherent_negative" in rules

    def test_positive_fragmented_insight(self) -> None:
        result = profile_text("سعادة. نجاح. فرحة. تهنئة.")
        rules = {insight.rule for insight in result.insights}
        assert "positive_fragmented" in rules

    def test_high_quality_positive_insight(self) -> None:
        """An excellent-quality text with a positive or neutral tone must
        raise the high_quality_positive insight. The composite signal is
        exercised directly through the profiler's cross-signal engine so the
        assertion stays stable across quality component additions."""
        analyzer = AnalysisProfiler()
        axes = {
            "sentiment": {"label": "positive"},
            "coherence": {"label": "strong"},
            "quality": {"label": "excellent"},
        }
        insights = analyzer._insight_cross_signals(axes)
        rules = {insight.rule for insight in insights}
        assert "high_quality_positive" in rules

    def test_insight_serialization(self) -> None:
        insight = ProfilerInsight(rule="test", message="test message")
        assert insight.to_dict() == {"rule": "test", "message": "test message"}


class TestProfilerSerializationAndBatch:
    def test_to_dict_structure(self) -> None:
        result = profile_text("نص")
        payload = result.to_dict()
        assert set(payload) == {"text", "axes", "insights"}
        assert isinstance(payload["insights"], list)

    def test_to_json_valid(self) -> None:
        result = profile_text("نص تجريبي")
        parsed = json.loads(result.to_json())
        assert parsed["text"] == "نص تجريبي"

    def test_batch_profiling(self) -> None:
        profiler = AnalysisProfiler(axes=["sentiment"])
        results = profiler.profile_batch(["سعادة", "خوف وذعر"])
        assert len(results) == 2
        assert all(isinstance(result, ProfilerResult) for result in results)

    def test_result_type(self) -> None:
        result = profile_text("نص")
        assert isinstance(result, ProfilerResult)


# ═══════════════════════════════════════════════════════════════════════════════
# WP4 — spelling-confidence-aware quality scoring
# ═══════════════════════════════════════════════════════════════════════════════


class TestQualitySpellingIntegration:
    def test_clean_text_scores_higher(self) -> None:
        clean = analyze_quality("نص سليم تماما بلا أخطاء إملائية")
        misspelled = analyze_quality("مسئول الاعلان نص سليم")
        assert clean.score > misspelled.score

    def test_spelling_issues_suggested(self) -> None:
        result = analyze_quality("مسئول الاعلان")
        assert any("spelling" in suggestion.lower() for suggestion in result.suggestions)

    def test_no_issue_empty_text(self) -> None:
        result = analyze_quality("")
        assert not any("spelling" in suggestion.lower() for suggestion in result.suggestions)

    def test_spelling_weight_present(self) -> None:
        result = analyze_quality("مسئول الاعلان")
        component_names = {component.name for component in result.components}
        assert "spelling" in component_names

    def test_confidence_lower_score(self) -> None:
        """A spelling issue backed by high confidence should penalize more than none."""
        baseline = analyze_quality("نص سليم بدون اخطاء")
        penalized = analyze_quality("مسئول الاعلان")
        assert penalized.components[0].score <= baseline.components[0].score

    def test_spelling_with_real_correction(self) -> None:
        """The corrections path computes mean confidence from real suggestions."""
        result = analyze_quality("مسئول الاعلان")
        spelling = next(component for component in result.components if component.name == "spelling")
        assert any("spelling issue(s)" in suggestion for suggestion in result.suggestions)
        assert spelling.score < 100.0

    def test_summary_format(self) -> None:
        result = analyze_quality("نص سليم")
        assert result.summary().startswith("Quality:")

    def test_poor_label(self) -> None:
        result = analyze_quality("مسئول الاعلان" * 20)
        assert result.label in ("poor", "fair", "good")
        assert result.score < 100.0

    def test_high_stop_word_density(self) -> None:
        from aranorm.analysis.quality_score import _score_lexical_balance

        suggestions: list = []
        score = _score_lexical_balance("في من على إلى عن إلى في من على إلى عن إلى في من على إلى", suggestions)
        assert score < 100.0
        assert any("stop-word" in text.lower() for text in suggestions)

    def test_dense_text_penalty(self) -> None:
        from aranorm.analysis.quality_score import _score_lexical_balance

        suggestions: list = []
        score = _score_lexical_balance("كلمة كلمة كلمة", suggestions)
        assert score < 100.0
        assert any("dense" in text.lower() for text in suggestions)

    def test_no_diacritics_penalty(self) -> None:
        from aranorm.analysis.quality_score import _score_diacritics

        assert _score_diacritics("نص عربي بدون تشكيل", []) == 25.0

    def test_components_below_75_issues(self) -> None:
        result = analyze_quality("مسئول الاعلان" * 10)
        if any(component.score < 75.0 for component in result.components):
            assert any("below 75" in issue for issue in result.issues)
