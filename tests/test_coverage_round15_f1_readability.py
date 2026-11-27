"""Round 15 F1 — ArabicReadabilityAnalyzer + readability metrics tests.

Covers src/aranorm/analysis/readability.py (composite score, labels,
empty paths, batch analysis, corpus_summary, compare) and the
readability attributes of TextStats (analysis/text_stats.py).
"""

from __future__ import annotations

import statistics

import pytest

from aranorm.analysis.readability import (
    ArabicReadabilityAnalyzer,
    ReadabilityResult,
)
from aranorm.utils.text_stats import compute_stats


@pytest.fixture
def analyzer() -> ArabicReadabilityAnalyzer:
    return ArabicReadabilityAnalyzer()


# ------------------------------------------------------------------ labels


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (90.0, "very_easy"),
        (80.0, "very_easy"),
        (79.9, "easy"),
        (60.0, "easy"),
        (59.9, "moderate"),
        (40.0, "moderate"),
        (39.9, "complex"),
        (20.0, "complex"),
        (19.9, "very_complex"),
        (0.0, "very_complex"),
    ],
)
def test_readability_label_boundaries(analyzer, score, expected):
    assert analyzer._label(score) == expected


# ------------------------------------------------------------------ analyze


def test_analyze_short_simple_text(analyzer):
    """Short, simple text scores high on the readability scale."""
    result = analyzer.analyze("الكتاب جيد. أحببته كثيرا.")
    assert result.readability_label == "easy"
    assert result.score >= 60
    assert 0.0 <= result.score <= 100.0
    assert result.sentence_count >= 2
    assert result.word_count > 0
    assert result.unique_words <= result.word_count
    assert 0.0 <= result.type_token_ratio <= 1.0
    assert 0.0 <= result.hapax_ratio <= 1.0
    assert 0.0 <= result.diacritic_ratio <= 1.0


def test_analyze_complex_text(analyzer):
    """Long sentences with subordinate markers lower the score."""
    text = (
        "أعلن الرئيس في مؤتمر صحفي مطول عن خطة اقتصادية شاملة تستهدف "
        "تحقيق نمو مستدام على المدى الطويل، والذي يعتمد على عوامل متعددة، "
        "حيث يجب مراعاة الظروف الاقتصادية الراهنة، بينما تتصاعد التحديات."
    )
    result = analyzer.analyze(text)
    assert result.readability_label in ("complex", "very_complex", "moderate")
    assert result.complexity_marker_count >= 2
    assert result.avg_sentence_length >= 8


def test_analyze_diacritic_ratio(analyzer):
    text = "مَدْرَسَةٌ"
    result = analyzer.analyze(text)
    assert result.diacritic_ratio > 0.0


def test_analyze_variance_single_sentence(analyzer):
    """Variance is 0.0 when there is a single sentence."""
    result = analyzer.analyze("نص واحد بدون فواصل")
    assert result.sentence_count == 1
    assert result.sentence_length_variance == 0.0


def test_analyze_variance_multiple_sentences(analyzer):
    """Variance is positive when sentence lengths differ."""
    text = "أ. " + " ".join(["كلمة"] * 20) + "."
    result = analyzer.analyze(text)
    assert result.sentence_count == 2
    assert result.sentence_length_variance > 0.0


def test_analyze_custom_thresholds():
    analyzer = ArabicReadabilityAnalyzer(max_easy_sentence=3, max_easy_word=3)
    result = analyzer.analyze("الكتاب المثير للإعجاب جداً ممتاز")
    assert result.score < analyzer.analyze("كتاب جيد").score


# ------------------------------------------------------------------ empty


def test_analyze_empty_text(analyzer):
    result = analyzer.analyze("")
    assert result.score == 0.0
    assert result.readability_label == "unknown"
    assert result.word_count == 0
    assert result.to_dict()["sentence_count"] == 0


def test_analyze_whitespace_only(analyzer):
    result = analyzer.analyze("     \n  ")
    assert result.readability_label == "unknown"


def test_analyze_no_arabic_words(analyzer):
    """Punctuation-only input yields the empty result."""
    result = analyzer.analyze("... ؟؟؟ !")
    assert result.readability_label == "unknown"


# ------------------------------------------------------------------ batch


def test_analyze_batch_preserves_order(analyzer):
    texts = ["الكتاب جيد.", "مدرسة كبيرة"]
    results = analyzer.analyze_batch(texts)
    assert len(results) == 2
    assert isinstance(results[0], ReadabilityResult)


# ------------------------------------------------------------------ compare


def test_compare_sorted_ascending(analyzer):
    texts = ["ن", "الكتاب جيد جداً وممتاز"]
    ranked = analyzer.compare(texts, sort_by="score")
    scores = [r.score for _, r in ranked]
    assert scores == sorted(scores)


def test_compare_sorted_descending(analyzer):
    texts = ["ن", "الكتاب جيد جداً وممتاز"]
    ranked = analyzer.compare(texts, sort_by="score_desc")
    scores = [r.score for _, r in ranked]
    assert scores == sorted(scores, reverse=True)


# ------------------------------------------------------------------ corpus_summary


def test_corpus_summary_empty(analyzer):
    summary = analyzer.corpus_summary([])
    assert summary["text_count"] == 0
    assert summary["mean_score"] == 0.0
    assert summary["easiest_index"] is None
    assert summary["hardest_index"] is None


def test_corpus_summary_single_text(analyzer):
    summary = analyzer.corpus_summary(["الكتاب جيد."])
    assert summary["text_count"] == 1
    assert summary["score_std"] == 0.0
    assert summary["easiest_index"] == 0
    assert summary["hardest_index"] == 0


def test_corpus_summary_multiple_texts(analyzer):
    texts = ["الكتاب جيد جداً وممتاز وسهل القراءة", "ن", "مدرسة"]
    summary = analyzer.corpus_summary(texts)
    assert summary["text_count"] == 3
    assert 0.0 <= summary["mean_score"] <= 100.0
    assert summary["score_std"] >= 0.0
    assert sum(summary["label_distribution"].values()) == 3
    assert 0 <= summary["easiest_index"] <= 2
    assert 0 <= summary["hardest_index"] <= 2
    # Manual verification of mean/std
    scores = [analyzer.analyze(t).score for t in texts]
    assert abs(summary["mean_score"] - statistics.mean(scores)) < 0.01
    assert abs(summary["score_std"] - statistics.pstdev(scores)) < 0.01


def test_corpus_summary_mean_metrics(analyzer):
    texts = ["الكتاب جيد.", "مدرسة كبيرة"]
    summary = analyzer.corpus_summary(texts)
    assert summary["mean_sentence_length"] > 0
    assert summary["mean_type_token_ratio"] >= 0.0


# ------------------------------------------------------------------ text_stats readability


def test_text_stats_readability_attributes():
    stats = compute_stats("الكتاب جيد جداً. أحببته كثيراً.")
    assert hasattr(stats, "readability_score")
    assert hasattr(stats, "readability_label")
    assert 0.0 <= stats.readability_score <= 100.0
    assert stats.readability_label in {
        "very_easy",
        "easy",
        "moderate",
        "difficult",
        "very_difficult",
    }


def test_text_stats_readability_empty():
    stats = compute_stats("")
    assert stats.readability_score == 0.0
    assert stats.readability_label == "very_difficult"
