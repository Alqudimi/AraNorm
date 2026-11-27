"""Round 13 P2 coverage for analysis edge paths."""

from __future__ import annotations

import aranorm.analysis.summarizer as summarizer_module
from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer
from aranorm.analysis.summarizer import ArabicTextSummarizer
from aranorm.analysis.text_analyzer import TextAnalyzer
from aranorm.analysis.text_comparator import TextComparator, _cosine, _jaccard, _term_frequencies


def test_text_analyzer_covers_complexity_dialect_and_batch_paths() -> None:
    analyzer = TextAnalyzer(top_n=1)

    complex_result = analyzer.analyze("برلمان اقتصادي")
    assert complex_result.estimated_complexity == "complex"
    assert complex_result.content_words_count == 2

    dialect_result = analyzer.analyze("كده اقتصاد")
    assert dialect_result.dialect_hint == "EGY"
    assert analyzer.analyze_batch(["نص", "نص آخر"])

    comparison = analyzer.compare_complexity(["برلمان اقتصادي", "كده اقتصاد"])
    assert len(comparison) == 2
    assert all("complexity" in item for item in comparison)


def test_summarizer_uses_ratio_and_handles_zero_content_sentence(monkeypatch) -> None:
    text = "اقتصاد قوي. سياسة عامة. مشروع وطني."
    monkeypatch.setattr(
        summarizer_module,
        "_sentences",
        lambda _text: ["!!!.", "اقتصاد قوي.", "سياسة عامة.", "مشروع وطني."],
    )
    result = ArabicTextSummarizer(ratio=0.5, max_sentences=None).summarize(text)

    assert result.original_sentence_count == 4
    assert result.summary_sentence_count == 2
    assert "!!!." in result.sentence_scores
    assert result.sentence_scores["!!!."] == 0.0


def test_summarizer_newline_fallback_and_no_sentence_fallback(monkeypatch) -> None:
    newline_result = ArabicTextSummarizer().summarize("سطر أول\nسطر ثان")
    assert newline_result.original_sentence_count == 1

    monkeypatch.setattr(summarizer_module, "_sentences", lambda text: [])
    result = ArabicTextSummarizer().summarize("نص بلا جمل")
    assert result.summary_sentences == ["نص بلا جمل"]
    assert result.compression_ratio == 1.0


def test_comparator_empty_and_helper_boundary_paths() -> None:
    comparator = TextComparator()
    result = comparator.compare("", "")

    assert result.jaccard_similarity == 1.0
    assert result.cosine_similarity == 0.0
    assert result.verdict == "similar"
    assert result.to_dict()["token_count_a"] == 0

    assert _term_frequencies([]) == {}
    assert _cosine({"word": 0.0}, {"word": 0.0}) == 0.0
    assert _cosine({"a": 1.0}, {"b": 1.0}) == 0.0
    assert _jaccard(set(), set()) == 1.0


def test_sentiment_covers_cleaned_empty_tokens_negation_and_stats() -> None:
    analyzer = SentimentAnalyzer()

    empty_score = analyzer._score_sentence("!!!")
    assert empty_score[0] == 0.0
    negated = analyzer._score_sentence("ليس رائع")
    assert negated[4] == ["رائع"]
    assert negated[0] < 0.0
    assert analyzer._confidence([], [], 0.0) == 0.0
    assert analyzer.analyze_batch(["رائع", "سيء"])
    stats = analyzer.get_lexicon_stats()
    assert stats["positive_words"] > 0
    assert stats["negative_words"] > 0


def test_comparator_batch_and_rank_limit() -> None:
    comparator = TextComparator()
    batch = comparator.compare_batch([("اقتصاد", "اقتصاد"), ("سياسة", "رياضة")])
    assert len(batch) == 2

    ranked = comparator.rank_by_similarity("اقتصاد", ["اقتصاد", "سياسة", "اقتصاد عالمي"], top_n=2)
    assert len(ranked) == 2
    assert ranked[0][0] == "اقتصاد"
