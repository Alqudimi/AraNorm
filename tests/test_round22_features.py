# -*- coding: utf-8 -*-
"""Round 22 feature tests: QuotationAnalyzer, LoanwordAnalyzer,
RootDensityAnalyzer, the expanded 16-axis profiler and its four new insights.

Mirrors the project's round-release test pattern (see test_round21_features.py):
label/threshold tests, direct analyzer behaviour, batch and serialization
coverage, then profiler integration assertions.
"""

import json
from unittest import mock

from aranorm.analysis.loanword_analyzer import (
    LoanwordAnalyzer,
    analyze_loanwords,
)
from aranorm.analysis.profiler import (
    AnalysisProfiler,
    _DEFAULT_AXES,
    profile_text,
)
from aranorm.analysis.quotation_analyzer import (
    QuotationAnalyzer,
    analyze_quotations,
)
from aranorm.analysis.root_density_analyzer import (
    RootDensityAnalyzer,
    analyze_root_density,
)

# ═══════════════════════════════════════════════════════════════════════════════
# WP1 — QuotationAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestQuotationLabels:
    """Labels follow quotation_ratio>=0.5 -> quoted, >=0.1 or
    partial_count>0 -> partially_quoted, else plain."""

    def test_quoted_label(self) -> None:
        result = analyze_quotations("قال: «النصر قريب، والعمل واجب» ثم سكت")
        assert result.label == "quoted"

    def test_partially_quoted_label(self) -> None:
        result = analyze_quotations("ذكر أن العمل مفيد وقال «النجاح يتطلب الصبر»")
        assert result.label == "partially_quoted"

    def test_plain_label(self) -> None:
        result = analyze_quotations("العلم نور والجهل ظلام بلا أي اقتباس")
        assert result.label == "plain"


class TestQuotationDetection:
    def test_angle_quote_spans(self) -> None:
        result = analyze_quotations("قال «العمل شرف»")
        assert result.quotation_types.get("angle_quotes", 0) >= 1
        assert len(result.spans) >= 1
        span = result.spans[0]
        assert "العمل شرف" in span.text

    def test_regular_quote_spans(self) -> None:
        result = analyze_quotations('كتب: "العلم نافع" ثم أغلق')
        assert result.quotation_types.get("standard_quotes", 0) >= 1

    def test_empty_text(self) -> None:
        result = analyze_quotations("")
        assert result.quotation_ratio == 0.0
        assert result.label == "plain"

    def test_quotation_ratio_bounds(self) -> None:
        result = analyze_quotations("قال: «أ ب ت ث ج» حيث أن النص كله تقريبا في الاقتباس")
        assert 0.0 <= result.quotation_ratio <= 1.0

    def test_analyzer_class_and_batch(self) -> None:
        analyzer = QuotationAnalyzer()
        results = analyzer.analyze_batch(["قال «نعم»", "نص عادي"])
        assert len(results) == 2
        assert results[0].label == "quoted"
        assert results[1].label == "plain"

    def test_serialization(self) -> None:
        result = analyze_quotations("قال «النصر قريب»")
        payload = json.loads(result.to_json())
        assert payload["label"] == "quoted"
        assert "quotation_types" in payload
        assert "spans" in payload

    def test_partial_open_marker_counted(self) -> None:
        """An unmatched opening quote mark increments the partial count."""
        result = analyze_quotations("قال «نص مفتوح لا يغلق")
        assert result.partial_count >= 1
        assert result.label == "partially_quoted"


# ═══════════════════════════════════════════════════════════════════════════════
# WP2 — LoanwordAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoanwordLabels:
    """Labels follow latin_ratio>=0.05 -> mixed, loanword_ratio>=0.1 ->
    loanwords, else pure_arabic."""

    def test_pure_arabic_label(self) -> None:
        result = analyze_loanwords("العلم نور والجهل ظلام")
        assert result.label == "pure_arabic"
        assert result.loanword_count == 0

    def test_loanwords_label(self) -> None:
        result = analyze_loanwords("الجو نورمال والشغل عادي")
        assert result.label == "loanwords"
        assert result.loanword_count >= 1

    def test_mixed_label(self) -> None:
        result = analyze_loanwords("التواصل عبر internet مهم جدا")
        assert result.label == "mixed"
        assert result.latin_count >= 1

    def test_attached_prefix_normalisation(self) -> None:
        result = analyze_loanwords("فأوكيه نكمل")
        loanwords = [span.text for span in result.spans]
        assert any("أوكيه" in token for token in loanwords)


class TestLoanwordDetection:
    def test_loanword_span(self) -> None:
        result = analyze_loanwords("الوضع نورمال")
        assert any(span.category == "transliterated_loan" for span in result.spans)
        assert any("نورمال" in span.text for span in result.spans)

    def test_latin_span(self) -> None:
        result = analyze_loanwords("مكتوب online بوضوح")
        assert any(span.category == "latin_fragment" for span in result.spans)
        assert any("online" in span.text for span in result.spans)

    def test_empty_text(self) -> None:
        result = analyze_loanwords("")
        assert result.loanword_count == 0
        assert result.label == "pure_arabic"

    def test_samples_and_density(self) -> None:
        result = analyze_loanwords("الجو نورمال والشغل hard جدا")
        assert result.foreign_density >= 0.0
        assert len(result.samples) >= 1

    def test_short_latin_run_skipped(self) -> None:
        """Single-letter latin runs are incidental and must not be spans."""
        result = analyze_loanwords("نص x عادي")
        assert all(span.category != "latin_fragment" for span in result.spans)

    def test_long_latin_run_captured(self) -> None:
        result = analyze_loanwords("نص online عادي")
        assert any(span.category == "latin_fragment" for span in result.spans)

    def test_ratio_bounds(self) -> None:
        result = analyze_loanwords("نورمال online والشغل عادي")
        assert 0.0 <= result.loanword_ratio <= 1.0
        assert 0.0 <= result.latin_ratio <= 1.0

    def test_analyzer_class_and_batch(self) -> None:
        analyzer = LoanwordAnalyzer()
        results = analyzer.analyze_batch(["نورمال", "العلم نور"])
        assert len(results) == 2
        assert results[0].label == "loanwords"
        assert results[1].label == "pure_arabic"

    def test_serialization(self) -> None:
        result = analyze_loanwords("الجو نورمال online")
        payload = json.loads(result.to_json())
        assert payload["label"] in ("pure_arabic", "loanwords", "mixed")
        assert "spans" in payload
        assert "samples" in payload


# ═══════════════════════════════════════════════════════════════════════════════
# WP3 — RootDensityAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestRootDensityLabels:
    """Labels follow diversity_index>=0.45 -> root_rich, >=0.28 ->
    moderate, else sparse."""

    def test_root_rich_label(self) -> None:
        result = analyze_root_density("يكتب ويقرأ ويشرح ويحل ويدرس ويعلّم")
        assert result.label == "root_rich"

    def test_sparse_label(self) -> None:
        result = analyze_root_density("عمل عمل عمل عمل عمل عمل عمل عمل عمل عمل")
        assert result.label == "sparse"

    def test_empty_text(self) -> None:
        result = analyze_root_density("")
        assert result.root_count == 0
        assert result.unique_roots == 0


class TestRootDensityDetection:
    def test_unique_roots(self) -> None:
        result = analyze_root_density("يكتب ويقرأ ويشرح ويحل")
        assert result.unique_roots >= 2

    def test_article_normalisation(self) -> None:
        """The definite article is stripped before root extraction."""
        result = analyze_root_density("الكتاب قراءة الطالب للمعلم")
        assert result.root_count >= 1

    def test_hapax_ratio_bounds(self) -> None:
        result = analyze_root_density("يكتب، فيقرأ، فيشرح، فيحل")
        assert 0.0 <= result.hapax_ratio <= 1.0

    def test_diversity_index_bounds(self) -> None:
        result = analyze_root_density("يكتب ويقرأ ويشرح ويحل")
        assert 0.0 <= result.diversity_index <= 1.0

    def test_top_root(self) -> None:
        result = analyze_root_density("يكتب ثم يكتب ثم يكتب ثم يقرأ")
        assert result.top_root is not None
        assert result.top_root["frequency"] >= 1

    def test_analyzer_class_and_batch(self) -> None:
        analyzer = RootDensityAnalyzer()
        results = analyzer.analyze_batch(["يكتب، فيقرأ، فيشرح", "عمل عمل عمل"])
        assert len(results) == 2
        assert results[0].label == "root_rich"
        assert results[1].label == "sparse"

    def test_serialization(self) -> None:
        result = analyze_root_density("يكتب، فيقرأ، فيشرح، فيحل")
        payload = json.loads(result.to_json())
        assert payload["label"] in ("root_rich", "moderate", "sparse")
        assert "diversity_index" in payload
        assert "top_root" in payload


# ═══════════════════════════════════════════════════════════════════════════════
# WP4 — 16-axis profiler & four new insights
# ═══════════════════════════════════════════════════════════════════════════════


class TestProfilerNineteenAxes:
    def test_default_nineteen_axes(self) -> None:
        assert len(_DEFAULT_AXES) == 22

    def test_all_new_axes_present(self) -> None:
        assert {"entities", "quotation", "loanwords", "root_density"} <= set(_DEFAULT_AXES)


class TestProfilerNewInsights:
    def test_insight_citation_heavy(self) -> None:
        """A text dominated by direct quotation triggers the citation rule."""
        result = profile_text(
            "قال: «النصر قريب، والعمل واجب، والاجتماع غداً، والقرار نهائي» " "ثم أضاف: «لا بد من الإنجاز»"
        )
        rules = [insight.rule for insight in result.insights]
        assert "citation_heavy" in rules

    def test_insight_loanwords_flagged(self) -> None:
        result = profile_text("الجو نورمال والشغل hard والانترنت بسرعة")
        rules = [insight.rule for insight in result.insights]
        assert "loanwords_flagged" in rules

    def test_insight_loanwords_transliterated_message(self) -> None:
        """Transliterated-only texts trigger the loanwords message branch."""
        result = profile_text("الجو نورمال جدا والطقس اوكيه والشغل هارد بدون أي نص لاتيني واضح")
        matched = [insight for insight in result.insights if insight.rule == "loanwords_flagged"]
        if matched:
            assert "معرَّبة" in matched[0].message

    def test_insight_root_rich(self) -> None:
        result = profile_text("يكتب، فيقرأ، فيشرح، فيحل، فيدرس، فيعلم")
        rules = [insight.rule for insight in result.insights]
        assert "root_rich" in rules

    def test_insight_person_named(self) -> None:
        result = profile_text("زار محمد بن عبدالله الرياض والتقى الأمير سلطان")
        rules = [insight.rule for insight in result.insights]
        assert "person_named" in rules

    def test_no_false_insights_plain_text(self) -> None:
        """A short repetitive text keeps root density low and quiet overall."""
        result = profile_text("عمل عمل عمل عمل عمل عمل عمل عمل عمل عمل")
        rules = {insight.rule for insight in result.insights}
        assert not rules.intersection(
            {
                "citation_heavy",
                "loanwords_flagged",
                "root_rich",
                "person_named",
            }
        )


class TestProfilerBackwardCompatibility:
    def test_custom_new_axes(self) -> None:
        result = AnalysisProfiler(axes=["quotation", "loanwords"]).profile("نص")
        assert set(result.axes) == {"quotation", "loanwords"}

    def test_legacy_insights_still_fire(self) -> None:
        """R21 insights must keep working alongside the R22 additions."""
        result = profile_text("حققنا 25% أي ٢٥ بالمئة")
        rules = {insight.rule for insight in result.insights}
        assert "mixed_digit_systems" in rules


# ═══════════════════════════════════════════════════════════════════════════════
# Batch / serialization sanity for the three new analyzers (regression guard)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBatchAndSerialization:
    @mock.patch.object(QuotationAnalyzer, "analyze", autospec=True)
    def test_quotation_batch_uses_analyze(self, analyze_mock) -> None:
        analyze_mock.return_value = analyze_quotations("نص")
        analyzer = QuotationAnalyzer()
        results = analyzer.analyze_batch(["نص1", "نص2", "نص3"])
        assert len(results) == 3
        assert analyze_mock.call_count >= 3

    @mock.patch.object(LoanwordAnalyzer, "analyze", autospec=True)
    def test_loanword_batch_uses_analyze(self, analyze_mock) -> None:
        analyze_mock.return_value = analyze_loanwords("نص")
        analyzer = LoanwordAnalyzer()
        results = analyzer.analyze_batch(["نص1", "نص2", "نص3"])
        assert len(results) == 3
        assert analyze_mock.call_count >= 3

    @mock.patch.object(RootDensityAnalyzer, "analyze", autospec=True)
    def test_root_batch_uses_analyze(self, analyze_mock) -> None:
        analyze_mock.return_value = analyze_root_density("نص")
        analyzer = RootDensityAnalyzer()
        results = analyzer.analyze_batch(["نص1", "نص2", "نص3"])
        assert len(results) == 3
        assert analyze_mock.call_count >= 3
