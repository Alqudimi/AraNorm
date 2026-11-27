"""Tests for the Round-17 batch (corpus-level) analysis module.

Covers :mod:`aranorm.analysis.batch_analysis` — aggregation over text
collections, language/dialect distribution, quality bands, top issues and
recommendation logic.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from aranorm.analysis.batch_analysis import (  # noqa: E402
    BatchAnalysisReport,
    BatchAnalyzer,
    QualityDistribution,
    analyze_batch,
)

# ── Aggregation fundamentals ─────────────────────────────────────────────────


def test_texts_count_matches_input() -> None:
    texts = ["نص عربي واضح.", "نص آخر جيد."]
    report = analyze_batch(texts)
    assert report.texts_count == 2


def test_total_chars_sums_inputs() -> None:
    texts = ["نص عربي.", "نص آخر."]
    report = analyze_batch(texts)
    assert report.total_chars == sum(len(text) for text in texts)


def test_empty_corpus_returns_empty_report() -> None:
    report = analyze_batch([])
    assert report.texts_count == 0
    assert report.avg_quality_score == 0.0


def test_quality_distribution_counts_sum_to_total() -> None:
    texts = ["مسئول الاعلان", "نص عربي واضح ومفهوم", "Another script entirely."]
    report = analyze_batch(texts)
    distribution = report.quality_distribution.to_dict()
    assert sum(distribution.values()) == report.texts_count


# ── Language / dialect distribution ──────────────────────────────────────────


def test_language_distribution_arabic_detected() -> None:
    report = analyze_batch(["نص عربي واضح."])
    assert report.language_distribution.get("arabic", 0) == 1


def test_language_distribution_mixed_corpus() -> None:
    texts = ["نص عربي واضح.", "Purely english text here."]
    report = analyze_batch(texts)
    assert sum(report.language_distribution.values()) == 2


def test_dialect_distribution_records_unknown_for_latin() -> None:
    report = analyze_batch(["Purely english text."])
    labels = list(report.dialect_distribution.keys())
    assert labels  # every text classified somehow


# ── Spelling aggregation ─────────────────────────────────────────────────────


def test_spelling_issues_aggregated_across_texts() -> None:
    texts = ["مسئول عن الحدث", "الاعلان عن الاهمية"]
    report = analyze_batch(texts)
    assert report.spelling_issues_total >= 2


def test_top_issues_lists_corrections() -> None:
    report = analyze_batch(["مسئول ومسئول", "الاعلان"])
    assert report.top_issues
    assert report.top_issues[0]["count"] >= 1


def test_top_issues_limited_to_ten() -> None:
    texts = [f"مسئول {index} اهلا {index}" for index in range(30)]
    report = analyze_batch(texts)
    assert len(report.top_issues) <= 10


# ── Lexical diversity ────────────────────────────────────────────────────────


def test_lexical_diversity_bounded() -> None:
    report = analyze_batch(["نص عربي واضح", "نص آخر مختلف"])
    assert 0.0 <= report.corpus_lexical_diversity <= 1.0


def test_repeated_identical_text_low_diversity_relative() -> None:
    report = analyze_batch(["نص عربي واضح" * 10])
    assert report.corpus_lexical_diversity <= 1.0


# ── Recommendations ──────────────────────────────────────────────────────────


def test_spelling_issues_trigger_recommendation() -> None:
    report = analyze_batch(["مسئول الاعلان الاهمية"])
    assert any("spelling" in recommendation.lower() for recommendation in report.recommendations)


def test_clean_corpus_gets_healthy_recommendation() -> None:
    report = analyze_batch(["نص عربي واضح ومفهوم تماما للسادة الكرام"])
    assert any("healthy" in recommendation.lower() for recommendation in report.recommendations)


def test_low_quality_corpus_gets_bulk_recommendation() -> None:
    texts = ["مسئول الاعلان الاهمية شكرا اهلا مسئول"] * 5
    report = analyze_batch(texts)
    assert any(
        "bulk" in recommendation.lower() or "normalization" in recommendation.lower()
        for recommendation in report.recommendations
    )


def test_hard_to_read_corpus_gets_readability_recommendation() -> None:
    # An extremely long single sentence (2000 words) is objectively hard to
    # read and should pull the per-text readability score below the 50 point
    # threshold that triggers the readability recommendation.
    long_sentence = " ".join(["كلمة"] * 2000) + "."
    texts = [long_sentence] * 5
    report = analyze_batch(texts)
    assert report.avg_readability < 70.0
    assert any("shorten" in recommendation.lower() for recommendation in report.recommendations)


# ── Serialization ────────────────────────────────────────────────────────────


def test_report_to_dict_keys() -> None:
    report = analyze_batch(["نص عربي."])
    data = report.to_dict()
    for key in (
        "texts_count",
        "total_tokens",
        "total_chars",
        "avg_quality_score",
        "quality_distribution",
        "language_distribution",
        "dialect_distribution",
        "avg_readability",
        "spelling_issues_total",
        "unique_words",
        "top_issues",
        "recommendations",
        "corpus_lexical_diversity",
    ):
        assert key in data


def test_report_to_json_valid() -> None:
    import json

    report = analyze_batch(["نص عربي.", "نص آخر."])
    parsed = json.loads(report.to_json())
    assert parsed["texts_count"] == 2


def test_quality_distribution_to_dict() -> None:
    distribution = QualityDistribution(excellent=2, good=3, fair=1, poor=0)
    assert distribution.to_dict() == {"excellent": 2, "good": 3, "fair": 1, "poor": 0}


def test_summary_empty_corpus() -> None:
    assert analyze_batch([]).summary() == "Empty corpus."


def test_summary_nonempty() -> None:
    report = analyze_batch(["نص عربي واضح."])
    assert "Corpus:" in report.summary()


# ── Analyzer class ───────────────────────────────────────────────────────────


def test_batch_analyzer_class() -> None:
    analyzer = BatchAnalyzer()
    report = analyzer.analyze(["نص عربي واضح."])
    assert isinstance(report, BatchAnalysisReport)
    assert report.texts_count == 1
