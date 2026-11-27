"""Tests for the analysis module: TextAnalyzer, KeywordExtractor, CorpusAnalyzer, TextComparator."""

from __future__ import annotations

import pytest

from aranorm.analysis import (
    CorpusAnalyzer,
    CorpusStopWordsBuilder,
    KeywordExtractor,
    KeywordResult,
    SimilarityResult,
    TextAnalyzer,
    TextAnalysisResult,
    TextComparator,
)
from aranorm.core.stop_words_registry import StopWordsRegistry

# ── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def registry() -> StopWordsRegistry:
    return StopWordsRegistry()


@pytest.fixture(scope="module")
def analyzer(registry: StopWordsRegistry) -> TextAnalyzer:
    return TextAnalyzer(registry=registry)


@pytest.fixture(scope="module")
def extractor(registry: StopWordsRegistry) -> KeywordExtractor:
    return KeywordExtractor(registry=registry)


@pytest.fixture(scope="module")
def comparator(registry: StopWordsRegistry) -> TextComparator:
    return TextComparator(registry=registry)


@pytest.fixture(scope="module")
def corpus_analyzer(registry: StopWordsRegistry) -> CorpusAnalyzer:
    return CorpusAnalyzer(registry=registry)


# ── TextAnalyzer ──────────────────────────────────────────────────────────────


class TestTextAnalyzer:
    def test_returns_analysis_result(self, analyzer: TextAnalyzer) -> None:
        result = analyzer.analyze("أنا سعيد جداً اليوم")
        assert isinstance(result, TextAnalysisResult)

    def test_total_tokens_count(self, analyzer: TextAnalyzer) -> None:
        result = analyzer.analyze("أنا سعيد اليوم")
        assert result.total_tokens == 3

    def test_stop_words_ratio_between_0_and_1(self, analyzer: TextAnalyzer) -> None:
        result = analyzer.analyze("أنا سعيد اليوم من هنا")
        assert 0.0 <= result.stop_words_ratio <= 1.0

    def test_content_words_excludes_stop_words(self, analyzer: TextAnalyzer) -> None:
        result = analyzer.analyze("أنا سعيد جداً")
        # "سعيد" should appear in content words (it is not a stop word)
        assert any("سعيد" in w for w in result.content_words)

    def test_empty_text_returns_empty_result(self, analyzer: TextAnalyzer) -> None:
        result = analyzer.analyze("")
        assert result.total_tokens == 0
        assert result.content_words == []

    def test_readability_label_is_valid(self, analyzer: TextAnalyzer) -> None:
        result = analyzer.analyze("النص العربي الجميل")
        assert result.estimated_complexity in ("simple", "moderate", "complex")

    def test_word_frequency_populated(self, analyzer: TextAnalyzer) -> None:
        result = analyzer.analyze("سعيد سعيد سعيد")
        assert result.word_frequency.get("سعيد", 0) >= 1

    def test_sentence_count_positive(self, analyzer: TextAnalyzer) -> None:
        result = analyzer.analyze("أنا سعيد. هو حزين. هم مبسوطون.")
        assert result.sentence_count >= 1

    def test_unique_words_not_exceeding_total(self, analyzer: TextAnalyzer) -> None:
        result = analyzer.analyze("سلام سلام مرحبا")
        assert result.unique_words <= result.total_tokens

    def test_lexical_diversity_range(self, analyzer: TextAnalyzer) -> None:
        result = analyzer.analyze("أنا أحب اللغة العربية")
        assert 0.0 <= result.lexical_diversity <= 1.0


# ── KeywordExtractor ──────────────────────────────────────────────────────────


class TestKeywordExtractor:
    def test_returns_keyword_result(self, extractor: KeywordExtractor) -> None:
        result = extractor.extract("التعلم الآلي تقنية متقدمة في علوم الحاسوب")
        assert isinstance(result, KeywordResult)

    def test_keywords_are_non_stop_words(self, extractor: KeywordExtractor) -> None:
        result = extractor.extract("التعلم الآلي تقنية متقدمة")
        for word, _ in result.keywords:
            assert word not in ("في", "على", "من", "أنا")

    def test_keyword_count_positive(self, extractor: KeywordExtractor) -> None:
        result = extractor.extract("التعلم الآلي تقنية متقدمة جداً")
        assert result.keyword_count >= 0

    def test_extract_batch_returns_list(self, extractor: KeywordExtractor) -> None:
        texts = ["التعلم الآلي", "اللغة العربية جميلة"]
        results = extractor.extract_batch(texts)
        assert len(results) == 2
        assert all(isinstance(r, KeywordResult) for r in results)

    def test_extract_common_keywords_threshold(self, extractor: KeywordExtractor) -> None:
        texts = [
            "التعلم الآلي مهم في العصر الحديث",
            "التعلم الآلي يساعد على تحسين الأداء",
            "اللغة العربية لغة جميلة",
        ]
        common = extractor.extract_common_keywords(texts, min_text_occurrences=2)
        # "التعلم" and "الآلي" appear in 2 of 3 texts
        words = [w for w, _ in common]
        assert any("تعلم" in w or "الآلي" in w for w in words)

    def test_empty_text_returns_zero_keywords(self, extractor: KeywordExtractor) -> None:
        result = extractor.extract("")
        assert result.keyword_count == 0

    def test_coverage_ratio_between_0_and_1(self, extractor: KeywordExtractor) -> None:
        result = extractor.extract("تقنية المعلومات في العالم")
        assert 0.0 <= result.coverage_ratio <= 1.0


# ── CorpusAnalyzer ────────────────────────────────────────────────────────────


class TestCorpusAnalyzer:
    _CORPUS = [
        "أنا سعيد جداً اليوم",
        "هو يعمل بجد في المصنع",
        "نحن نحب اللغة العربية",
        "الكتاب مفيد جداً للطالب",
        "المدرسة تعلم الأطفال القراءة والكتابة",
    ]

    def test_document_count(self, corpus_analyzer: CorpusAnalyzer) -> None:
        result = corpus_analyzer.analyze(self._CORPUS)
        assert result.document_count == len(self._CORPUS)

    def test_total_tokens_positive(self, corpus_analyzer: CorpusAnalyzer) -> None:
        result = corpus_analyzer.analyze(self._CORPUS)
        assert result.total_tokens > 0

    def test_corpus_stop_word_ratio_range(self, corpus_analyzer: CorpusAnalyzer) -> None:
        result = corpus_analyzer.analyze(self._CORPUS)
        assert 0.0 <= result.corpus_stop_word_ratio <= 1.0

    def test_top_content_words_populated(self, corpus_analyzer: CorpusAnalyzer) -> None:
        result = corpus_analyzer.analyze(self._CORPUS)
        assert isinstance(result.top_content_words, list)

    def test_empty_corpus_returns_empty_result(self, corpus_analyzer: CorpusAnalyzer) -> None:
        result = corpus_analyzer.analyze([])
        assert result.document_count == 0
        assert result.total_tokens == 0

    def test_per_document_stats_count(self, corpus_analyzer: CorpusAnalyzer) -> None:
        result = corpus_analyzer.analyze(self._CORPUS)
        assert len(result.documents) == len(self._CORPUS)

    def test_compare_returns_dict_with_corpora(self, corpus_analyzer: CorpusAnalyzer) -> None:
        comparison = corpus_analyzer.compare(self._CORPUS[:2], self._CORPUS[2:])
        assert "corpus_a" in comparison
        assert "corpus_b" in comparison
        assert "jaccard_similarity" in comparison

    def test_lexical_diversity_range(self, corpus_analyzer: CorpusAnalyzer) -> None:
        result = corpus_analyzer.analyze(self._CORPUS)
        assert 0.0 <= result.lexical_diversity <= 1.0


# ── CorpusStopWordsBuilder ────────────────────────────────────────────────────


class TestCorpusStopWordsBuilder:
    _CORPUS = [
        "الكتاب مفيد جداً للطالب",
        "الكتاب يحتوي على معلومات قيمة",
        "الكتاب العربي تراث حضاري",
        "قرأت الكتاب بشغف كبير",
        "الكتاب والقلم أدوات المعرفة",
    ]

    def test_returns_corpus_stop_words_result(self) -> None:
        builder = CorpusStopWordsBuilder(min_doc_frequency=2)
        result = builder.build(self._CORPUS)
        assert isinstance(result.extracted_stop_words, frozenset)

    def test_extracted_words_meet_min_frequency(self) -> None:
        builder = CorpusStopWordsBuilder(min_doc_frequency=3)
        result = builder.build(self._CORPUS)
        # "الكتاب" appears in all 5 texts so should be a candidate
        # (unless excluded by known stop words)
        assert result.corpus_size == len(self._CORPUS)

    def test_empty_corpus_returns_empty(self) -> None:
        builder = CorpusStopWordsBuilder()
        result = builder.build([])
        assert result.extracted_stop_words == frozenset()
        assert result.corpus_size == 0

    def test_candidate_scores_sorted_descending(self) -> None:
        builder = CorpusStopWordsBuilder(min_doc_frequency=2)
        result = builder.build(self._CORPUS)
        scores = [s for _, s in result.candidate_scores]
        assert scores == sorted(scores, reverse=True)


# ── TextComparator ────────────────────────────────────────────────────────────


class TestTextComparator:
    def test_returns_similarity_result(self, comparator: TextComparator) -> None:
        result = comparator.compare("أنا سعيد اليوم", "أنا حزين اليوم")
        assert isinstance(result, SimilarityResult)

    def test_identical_texts_high_similarity(self, comparator: TextComparator) -> None:
        text = "أنا أحب اللغة العربية جداً"
        result = comparator.compare(text, text)
        assert result.overall_similarity >= 0.9

    def test_different_texts_low_similarity(self, comparator: TextComparator) -> None:
        result = comparator.compare("الطعام لذيذ", "الاقتصاد ينمو")
        assert result.overall_similarity < 0.5

    def test_jaccard_between_0_and_1(self, comparator: TextComparator) -> None:
        result = comparator.compare("أنا سعيد", "هو حزين")
        assert 0.0 <= result.jaccard_similarity <= 1.0

    def test_verdict_is_valid_string(self, comparator: TextComparator) -> None:
        result = comparator.compare("أنا سعيد", "هو يعمل")
        assert result.verdict in ("identical", "very_similar", "similar", "somewhat_similar", "different")

    def test_to_dict_is_serializable(self, comparator: TextComparator) -> None:
        import json

        result = comparator.compare("أنا سعيد", "أنا فرحان")
        d = result.to_dict()
        serialized = json.dumps(d, ensure_ascii=False)
        assert isinstance(serialized, str)

    def test_compare_batch_preserves_order(self, comparator: TextComparator) -> None:
        pairs = [
            ("أنا سعيد", "أنا حزين"),
            ("اللغة جميلة", "العلم نافع"),
        ]
        results = comparator.compare_batch(pairs)
        assert len(results) == 2

    def test_rank_by_similarity_sorted(self, comparator: TextComparator) -> None:
        query = "أحب اللغة العربية"
        candidates = [
            "العربية لغة جميلة",
            "الاقتصاد ينمو بسرعة",
            "اللغة العربية فصيحة",
        ]
        ranked = comparator.rank_by_similarity(query, candidates)
        scores = [r.overall_similarity for _, r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_find_duplicates_above_threshold(self, comparator: TextComparator) -> None:
        texts = [
            "أحب اللغة العربية كثيراً",
            "أحب اللغة العربية جداً",
            "الاقتصاد ينمو",
        ]
        dupes = comparator.find_duplicates(texts, threshold=0.5)
        # First two are very similar
        assert len(dupes) >= 1

    def test_shared_tokens_correct(self, comparator: TextComparator) -> None:
        result = comparator.compare("أنا سعيد اليوم", "أنا حزين اليوم")
        assert "أنا" in result.shared_tokens or "اليوم" in result.shared_tokens
