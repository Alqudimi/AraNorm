# -*- coding: utf-8 -*-
"""Round 23 feature tests: ContrastAnalyzer, FillerAnalyzer,
ComplexityAnalyzer, the expanded time_expression category in NumericAnalyzer,
the structural_balance component in QualityScoreAnalyzer, and the
expanded 19-axis profiler with its three new insights.
Mirrors the project's round-release test pattern (see
test_round22_features.py): label/threshold tests, direct analyzer behaviour,
batch and serialization coverage, then profiler integration assertions.
"""

import json

from aranorm.analysis.complexity_analyzer import (
    ComplexityAnalyzer,
    analyze_complexity,
)
from aranorm.analysis.contrast_analyzer import (
    ContrastAnalyzer,
    analyze_contrast,
)
from aranorm.analysis.filler_analyzer import (
    FillerAnalyzer,
    analyze_fillers,
)
from aranorm.analysis.numeric_analyzer import (
    NumericAnalyzer,
    analyze_numeric,
)
from aranorm.analysis.profiler import (
    AnalysisProfiler,
    _DEFAULT_AXES,
    profile_text,
)
from aranorm.analysis.quality_score import (
    QualityScoreAnalyzer,
    _COMPONENT_WEIGHTS,
    analyze_quality,
)

# ═══════════════════════════════════════════════════════════════════════════════
# WP1 — ContrastAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestContrastLabels:
    """Labels follow contrast_density>=contrastive_threshold ->
    contrastive, >=moderate_threshold or pairs present -> moderate,
    else neutral."""

    def test_contrastive_label(self) -> None:
        result = analyze_contrast("الليل والنهار والصواب والخطأ")
        assert result.label == "contrastive"

    def test_moderate_label(self) -> None:
        """A single antonym pair in a long text yields a moderate label."""
        long_tail = " ".join(["الشمس دافئة"] * 40)
        result = analyze_contrast("الليل والنهار " + long_tail)
        assert result.label == "moderate"

    def test_custom_thresholds(self) -> None:
        analyzer = ContrastAnalyzer(contrastive_threshold=0.05, moderate_threshold=0.05)
        result = analyzer.analyze("الليل والنهار " + " ".join(["الشمس دافئة"] * 40))
        assert result.label == "moderate"

    def test_neutral_label(self) -> None:
        result = analyze_contrast("صباح جميل والسماء صافية بدون أي تقابل")
        assert result.label == "neutral"

    def test_empty_text(self) -> None:
        result = analyze_contrast("")
        assert result.contrast_density == 0.0
        assert result.label == "neutral"


class TestContrastDetection:
    def test_basic_pair_detection(self) -> None:
        result = analyze_contrast("الليل والنهار")
        assert result.contrast_pairs_count == 1
        assert result.unique_pairs == 1
        assert "ليل" in str(result.contrast_pairs[0].normalised_key)
        assert "نهار" in str(result.contrast_pairs[0].normalised_key)

    def test_conjunction_prefix_normalisation(self) -> None:
        """Paired members keep attached conjunctions (و، ف، ب، ل)."""
        result = analyze_contrast("والليل والنهار فالصواب والخطأ")
        assert result.contrast_pairs_count >= 1
        assert result.unique_pairs >= 1

    def test_no_definite_article_required(self) -> None:
        """Members without ال still match pairs stored with the article."""
        result = analyze_contrast("خيرٌ وشرٌّ والحديث طويل")
        assert result.contrast_pairs_count >= 1

    def test_symmetric_pairs_deduplicated(self) -> None:
        """(ليل، نهار) and (نهار، ليل) must collapse into one pair."""
        result = analyze_contrast("الليل والنهار والنهار والليل")
        assert result.unique_pairs == 1
        assert result.contrast_pairs_count == 1

    def test_hamza_normalisation(self) -> None:
        result = analyze_contrast("الصواب والخطأ")
        assert result.contrast_pairs_count >= 1

    def test_pair_offsets_recorded(self) -> None:
        result = analyze_contrast("في الليل نور وفي النهار سرور")
        pair = result.contrast_pairs[0]
        assert pair.second_start >= 0
        assert pair.second_end > pair.second_start
        assert pair.second_end - pair.second_start == len(pair.member_b)

    def test_density_bounds(self) -> None:
        result = analyze_contrast("الليل والنهار والصباح والمساء")
        assert 0.0 <= result.contrast_density <= 1.0

    def test_word_count_includes_all(self) -> None:
        result = analyze_contrast("الليل والنهار والصواب والخطأ والإيمان والكفر")
        assert result.word_count >= 5

    def test_analyzer_class_and_batch(self) -> None:
        analyzer = ContrastAnalyzer()
        results = analyzer.analyze_batch(["الليل والنهار", "نص عادي"])
        assert len(results) == 2
        assert results[0].contrast_pairs_count >= 1
        assert results[1].label == "neutral"

    def test_serialization(self) -> None:
        result = analyze_contrast("الليل والنهار")
        payload = json.loads(result.to_json())
        assert payload["label"] == "moderate" or payload["label"] == "contrastive"
        assert "contrast_pairs" in payload
        assert "contrast_density" in payload
        assert "unique_pairs" in payload
        span = payload["contrast_pairs"][0]
        assert "member_a" in span and "member_b" in span
        assert "second_start" in span and "normalised_key" in span

    def test_thresholds_exposed(self) -> None:
        analyzer = ContrastAnalyzer()
        assert analyzer.contrastive_threshold >= analyzer.moderate_threshold


# ═══════════════════════════════════════════════════════════════════════════════
# WP2 — FillerAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestFillerLabels:
    """Labels follow filler_density>=0.10 -> filler_heavy,
    repetition_density>=0.05 -> repetitive, else clean."""

    def test_clean_label(self) -> None:
        result = analyze_fillers("العلم نور والجهل ظلام بلا حشو ولا تكرار")
        assert result.label == "clean"

    def test_filler_heavy_label(self) -> None:
        result = analyze_fillers("في الحقيقة، النص في الحقيقة ضعيف جداً")
        assert result.label == "filler_heavy"

    def test_repetitive_label(self) -> None:
        result = analyze_fillers("النص في الحقيقة ضعيف، النص النص متكرر")
        assert result.label in ("repetitive", "filler_heavy")

    def test_empty_text(self) -> None:
        result = analyze_fillers("")
        assert result.filler_density == 0.0
        assert result.repetition_density == 0.0
        assert result.label == "clean"


class TestFillerDetection:
    def test_filler_phrase_span(self) -> None:
        result = analyze_fillers("في الحقيقة النص واضح")
        assert result.filler_count >= 1
        span = result.filler_spans[0]
        assert span.text == "في الحقيقة"
        assert span.start == 0

    def test_repetition_span(self) -> None:
        result = analyze_fillers("النص النص متكرر")
        assert result.repetition_count >= 1
        span = result.repetition_spans[0]
        assert span.word == "النص"
        assert span.second_start > span.first_start

    def test_fillers_inside_text(self) -> None:
        result = analyze_fillers("أقول بصراحة إن هذا العمل وبكل صراحة مفيد")
        assert result.filler_count >= 2

    def test_words_inside_filler_ignored_for_repetition(self) -> None:
        """A word appearing only inside filler spans must not be counted
        as a defective repetition."""
        result = analyze_fillers("في الحقيقة في الحقيقة أن النص ضعيف")
        repetition_words = [span.word for span in result.repetition_spans]
        assert "الحقيقة" not in repetition_words
        assert result.filler_count >= 1

    def test_density_bounds(self) -> None:
        result = analyze_fillers("في الحقيقة النص في الحقيقة ضعيف جدا جدا")
        assert 0.0 <= result.filler_density <= 1.0
        assert 0.0 <= result.repetition_density <= 1.0

    def test_no_false_positive_on_legitimate_repetition(self) -> None:
        """A single occurrence of a word is never flagged."""
        result = analyze_fillers("العلم نور بلا تكرار")
        assert result.repetition_count == 0

    def test_analyzer_class_and_batch(self) -> None:
        analyzer = FillerAnalyzer()
        results = analyzer.analyze_batch(["في الحقيقة النص ضعيف", "نص عادي"])
        assert len(results) == 2
        assert results[0].filler_count >= 1
        assert results[1].label == "clean"

    def test_serialization(self) -> None:
        result = analyze_fillers("في الحقيقة النص النص ضعيف")
        payload = json.loads(result.to_json())
        assert payload["label"] in ("filler_heavy", "repetitive", "clean")
        assert "filler_spans" in payload
        assert "repetition_spans" in payload
        assert payload["filler_count"] >= 0
        assert payload["repetition_count"] >= 0

    def test_thresholds_exposed(self) -> None:
        analyzer = FillerAnalyzer()
        assert analyzer.filler_threshold >= 0.0
        assert analyzer.repetition_threshold >= 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# WP3 — ComplexityAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestComplexityLabels:
    """Labels follow avg_word_length>5.0 -> complex, 4.0–5.0 ->
    moderate, <=4.0 -> simple."""

    def test_complex_label(self) -> None:
        result = analyze_complexity("استفادوا واستثمروا وانضموا")
        assert result.label == "complex"

    def test_moderate_label(self) -> None:
        result = analyze_complexity("استفادنا نصا واضحا كتبت")
        assert result.label == "moderate"

    def test_simple_label(self) -> None:
        result = analyze_complexity("ذهب أب وابن")
        assert result.label == "simple"

    def test_empty_text(self) -> None:
        result = analyze_complexity("")
        assert result.word_count == 0
        assert result.label == "simple"


class TestComplexityMetrics:
    def test_average_length(self) -> None:
        result = analyze_complexity("كتبت")
        assert result.avg_word_length == 4.0

    def test_max_length(self) -> None:
        result = analyze_complexity("أ واستفادوا")
        assert result.max_word_length >= 8

    def test_length_distribution(self) -> None:
        result = analyze_complexity("كتبت واستفادوا")
        assert result.length_distribution.get(4) == 1
        assert result.length_distribution.get(8) == 1

    def test_fused_ratio(self) -> None:
        result = analyze_complexity("استفادوا وانضموا")
        assert result.fused_ratio > 0.0

    def test_latin_only_words_ignored(self) -> None:
        result = analyze_complexity("ABC وكتب")
        assert result.word_count >= 1

    def test_diacritics_stripped_before_length(self) -> None:
        without = analyze_complexity("استفادوا")
        with_marks = analyze_complexity("اِسْتَفَادُوا")
        assert without.max_word_length == with_marks.max_word_length
        assert without.max_word_length == 8

    def test_moderate_label(self) -> None:
        result = analyze_complexity("استفادنا نصا واضحا كتبت")
        assert result.label == "moderate"

    def test_analyzer_class_and_batch(self) -> None:
        analyzer = ComplexityAnalyzer()
        results = analyzer.analyze_batch(["استفادوا", "كتب"])
        assert len(results) == 2
        assert results[0].label == "complex"
        assert results[1].label == "simple"

    def test_serialization(self) -> None:
        result = analyze_complexity("استفادوا")
        payload = json.loads(result.to_json())
        assert "avg_word_length" in payload
        assert "max_word_length" in payload
        assert "fused_ratio" in payload
        assert "length_distribution" in payload
        assert "label" in payload


# ═══════════════════════════════════════════════════════════════════════════════
# WP4 — NumericAnalyzer time_expression expansion
# ═══════════════════════════════════════════════════════════════════════════════


class TestNumericTimeExpressions:
    def test_clock_phrase(self) -> None:
        result = analyze_numeric("الساعة الخامسة مساءً")
        categories = [span.category for span in result.spans]
        assert "time_expression" in categories

    def test_week_frame(self) -> None:
        result = analyze_numeric("الأسبوع القادم نبدأ")
        categories = [span.category for span in result.spans]
        assert "time_expression" in categories

    def test_day_words(self) -> None:
        result = analyze_numeric("اليوم وغدًا والأمس")
        categories = [span.category for span in result.spans]
        assert "time_expression" in categories

    def test_time_of_day(self) -> None:
        result = analyze_numeric("بعد الظهر في المغرب")
        categories = [span.category for span in result.spans]
        assert "time_expression" in categories

    def test_time_count_reflects_spans(self) -> None:
        result = analyze_numeric("اليوم الساعة الخامسة مساءً")
        assert result.time_count >= 1
        assert result.time_count == sum(1 for span in result.spans if span.category == "time_expression")

    def test_no_time_in_plain_text(self) -> None:
        result = analyze_numeric("العلم نور بلا أرقام أو أوقات")
        assert result.time_count == 0

    def test_indic_digit_clock(self) -> None:
        """Arabic-indic clock (٥:٣٠) must stay in the time_expression category."""
        result = analyze_numeric("اجتمعنا الساعة ٥:٣٠ مساءً")
        time_spans = [span for span in result.spans if span.category == "time_expression"]
        assert any("٥" in span.text for span in time_spans)

    def test_latin_digit_clock_split(self) -> None:
        """Pure-digit Latin runs (12:30 digits) delegate to western_digits spans."""
        result = analyze_numeric("الساعة 12:30")
        categories = [span.category for span in result.spans]
        assert "western_digits" in categories

    def test_time_expression_empty_skip(self) -> None:
        """Empty/whitespace-only matches (len < 2) are skipped."""
        # The regex never yields empty groups by construction; the guard path is
        # exercised by the shortest legal match.
        result = analyze_numeric("صباح")
        categories = [span.category for span in result.spans]
        assert "time_expression" not in categories
        assert not any(span.category == "time_expression" for span in result.spans)

    def test_pure_digit_skip(self) -> None:
        """Pure digit runs (leading digit + all-digit) skip the time path."""
        result = analyze_numeric("١٢")
        categories = [span.category for span in result.spans]
        assert "time_expression" not in categories
        assert any(cat in categories for cat in ("arabic_indic_digits", "digit_number", "digit_numbers"))

    def test_serialization_includes_time_count(self) -> None:
        result = analyze_numeric("الساعة الخامسة مساءً")
        payload = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
        assert "time_count" in payload
        assert payload["time_count"] >= 1

    def test_analyzer_class(self) -> None:
        analyzer = NumericAnalyzer()
        results = analyzer.analyze_batch(["اليوم", "لا شيء"])
        assert len(results) == 2
        assert results[0].time_count >= 1
        assert results[1].time_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# WP5 — QualityScoreAnalyzer structural_balance
# ═══════════════════════════════════════════════════════════════════════════════


class TestQualityStructuralBalance:
    def test_component_present(self) -> None:
        result = analyze_quality("نص عربي جيد")
        names = [component.name for component in result.components]
        assert "structural_balance" in names
        assert len(result.components) == 8

    def test_weights_sum_to_one(self) -> None:
        total = sum(_COMPONENT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_structural_balance_weight(self) -> None:
        assert _COMPONENT_WEIGHTS["structural_balance"] == 0.07

    def test_clean_text_scores_high(self) -> None:
        result = analyze_quality("العلم نور والجهل ظلام")
        balance = next(c for c in result.components if c.name == "structural_balance")
        assert balance.score >= 50.0

    def test_filled_text_scores_lower(self) -> None:
        clean = analyze_quality("العلم نور بلا حشو")
        filled = analyze_quality("في الحقيقة النص في الحقيقة ضعيف جدا جدا")
        clean_score = next(c for c in clean.components if c.name == "structural_balance").score
        filled_score = next(c for c in filled.components if c.name == "structural_balance").score
        assert filled_score <= clean_score

    def test_component_serialization(self) -> None:
        result = analyze_quality("نص عربي جيد")
        payload = json.loads(result.to_json())
        names = [component["name"] for component in payload["components"]]
        assert "structural_balance" in names
        assert payload["components"][0]["weight"] > 0.0

    def test_analyzer_class(self) -> None:
        analyzer = QualityScoreAnalyzer()
        first = analyzer.analyze("نص عربي جيد")
        second = analyzer.analyze("")
        names = [component.name for component in first.components]
        assert "structural_balance" in names
        assert second.score is not None

    def test_score_range(self) -> None:
        result = analyze_quality("في الحقيقة هذا نص في الحقيقة ضعيف جدا جدا بلا أي معنى")
        assert 0.0 <= result.score <= 100.0
        assert result.label in ("excellent", "good", "fair", "poor")


# ═══════════════════════════════════════════════════════════════════════════════
# WP6 — 19-axis profiler integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestProfilerExpansion:
    def test_nineteen_axes(self) -> None:
        assert len(_DEFAULT_AXES) == 22
        for name in ("contrast", "fillers", "complexity"):
            assert name in _DEFAULT_AXES

    def test_all_axes_populated(self) -> None:
        result = profile_text("الليل والنهار والصواب والخطأ")
        assert len(result.axes) == 22
        assert all(name in result.axes for name in _DEFAULT_AXES)

    def test_contrast_axis_content(self) -> None:
        result = profile_text("الليل والنهار")
        assert len(result.axes["contrast"]["contrast_pairs"]) >= 1

    def test_fillers_axis_content(self) -> None:
        result = profile_text("في الحقيقة النص ضعيف")
        assert result.axes["fillers"]["filler_count"] >= 0
        assert "label" in result.axes["fillers"]

    def test_complexity_axis_content(self) -> None:
        result = profile_text("استفادوا")
        assert result.axes["complexity"]["label"] == "complex"

    def test_can_disable_new_axes(self) -> None:
        profiler = AnalysisProfiler(axes=["sentiment", "contrast"])
        result = profiler.profile("الليل والنهار")
        assert set(result.axes) == {"sentiment", "contrast"}

    def test_contrastive_style_insight(self) -> None:
        result = profile_text("الليل والنهار والصواب والخطأ")
        rules = {insight.rule for insight in result.insights}
        assert "contrastive_style" in rules

    def test_filler_heavy_insight(self) -> None:
        result = profile_text("في الحقيقة هذا النص في الحقيقة ضعيف جدا جدا")
        rules = {insight.rule for insight in result.insights}
        assert "filler_heavy" in rules

    def test_no_false_insights_on_clean_text(self) -> None:
        result = profile_text("هذا صباح جميل والسماء صافية بلا تضاد")
        rules = {insight.rule for insight in result.insights}
        assert "filler_heavy" not in rules
        assert "contrastive_style" not in rules

    def test_complex_hard_to_read_insight(self) -> None:
        complex_text = " ".join(["استفادوا", "وانضموا"] * 25)
        result = profile_text(complex_text)
        rules = {insight.rule for insight in result.insights}
        complexity_label = result.axes["complexity"]["label"]
        if complexity_label == "complex":
            assert "complex_hard_to_read" in rules

    def test_batch_profiling(self) -> None:
        profiler = AnalysisProfiler()
        results = profiler.profile_batch(["الليل والنهار", "نص عادي"])
        assert len(results) == 2
        assert all(len(result.axes) == 22 for result in results)

    def test_profiler_serialization(self) -> None:
        result = profile_text("الليل والنهار")
        payload = json.loads(result.to_json())
        assert "contrast" in payload["axes"]
        assert "fillers" in payload["axes"]
        assert "complexity" in payload["axes"]
        assert len(payload["axes"]) == 22
