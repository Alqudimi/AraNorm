"""Round 14 F2 — ``FuzzyArabicMatcher`` indexing and fuzzy search tests.

Covers canonical-form normalisation, stemming/root morphological boosts,
search thresholding/limiting, batch search, and the one-shot helper.
"""

from __future__ import annotations

import threading

from aranorm.utils.fuzzy_matcher import (
    FuzzyArabicMatcher,
    FuzzyMatchResult,
    blended_similarity,
    canonical_form,
    fuzzy_search,
    jaccard_ngrams,
)


class TestCanonicalForms:
    """Low-level form helpers."""

    def test_canonical_strips_diacritics(self):
        assert canonical_form("كتابٌ") == "كتاب"

    def test_canonical_removes_tatweel(self):
        assert canonical_form("كتــــاب") == "كتاب"

    def test_canonical_empty_input(self):
        assert canonical_form("") == ""
        assert canonical_form(None) == ""  # type: ignore[arg-type]

    def test_jaccard_identical(self):
        assert jaccard_ngrams("كتب", "كتب") == 1.0

    def test_jaccard_empty_inputs(self):
        assert jaccard_ngrams("", "كتب") == 0.0
        assert jaccard_ngrams("كتب", "") == 0.0

    def test_blended_exact_match(self):
        assert blended_similarity("كتب", "كتب") == 1.0

    def test_blended_empty_inputs(self):
        assert blended_similarity("", "كتب") == 0.0


class TestFuzzyArabicMatcherIndex:
    """Index construction and management."""

    def test_index_deduplicates_canonical_forms(self):
        matcher = FuzzyArabicMatcher(["كتابٌ", "كتاب"])
        assert len(matcher) == 1

    def test_index_keeps_longest_original_form(self):
        matcher = FuzzyArabicMatcher(["كتاب", "كتابٌ"])
        assert matcher.best_match("كتاب").candidate == "كتابٌ"  # type: ignore[union-attr]

    def test_add_many_and_contains(self):
        matcher = FuzzyArabicMatcher()
        matcher.add_many(["مدرسة", "جامعة"])
        assert len(matcher) == 2
        assert "مدرسه" in matcher
        assert 123 not in matcher  # type: ignore[operator]

    def test_add_rejects_empty_and_whitespace(self):
        matcher = FuzzyArabicMatcher()
        matcher.add("")
        matcher.add("   ")
        assert len(matcher) == 0

    def test_stem_and_root_indexes_populated(self):
        matcher = FuzzyArabicMatcher(["مدرسة"], use_stem=True, use_root=True)
        assert matcher.search("مدرسه")  # stem morphological hit
        matcher2 = FuzzyArabicMatcher(["مدرسة"], use_stem=False, use_root=False)
        res = matcher2.search("مدرسه")
        assert res and res[0].stemmed is None


class TestFuzzyArabicMatcherSearch:
    """Search behaviour and scoring."""

    def test_search_ranking(self):
        matcher = FuzzyArabicMatcher(["مدرسة", "جامعة", "سيارة"])
        results = matcher.search("مدرسه")
        assert results[0].candidate == "مدرسة"
        assert results[0].score > 0.9

    def test_threshold_filtering(self):
        matcher = FuzzyArabicMatcher(["مدرسة", "سيارة"])
        results = matcher.search("مدرسه", threshold=0.95)
        assert all(result.score >= 0.95 for result in results)
        assert results[0].candidate == "مدرسة"

    def test_limit_truncation(self):
        matcher = FuzzyArabicMatcher(["مدرسة", "جامعة", "سيارة"])
        assert len(matcher.search("مدرسه", limit=1)) == 1

    def test_empty_query(self):
        matcher = FuzzyArabicMatcher(["مدرسة"])
        assert matcher.search("") == []
        assert matcher.search("   ") == []

    def test_morphological_stem_boost(self):
        """مكتبة and مكتب share the stem مكتب — boost applies."""
        matcher = FuzzyArabicMatcher(["مكتبة"])
        result = matcher.search("مكتب")
        assert result
        assert result[0].score > 0.6

    def test_result_fields(self):
        matcher = FuzzyArabicMatcher(["مدرسة"])
        result = matcher.search("مدرسه")[0]
        assert isinstance(result, FuzzyMatchResult)
        assert result.stemmed == "مدرس"

    def test_best_match_none(self):
        matcher = FuzzyArabicMatcher(["سيارة"])
        assert matcher.best_match("xyz") is None


class TestFuzzyArabicMatcherConcurrency:
    """Thread safety of the shared index."""

    def test_concurrent_add_and_search(self):
        matcher = FuzzyArabicMatcher()
        barrier = threading.Barrier(4)

        def producer(start: int) -> None:
            barrier.wait()
            for index in range(start, start + 100):
                matcher.add(f"كلمة{index}")

        def consumer() -> None:
            barrier.wait()
            for _ in range(50):
                matcher.search("كلمة")

        threads = [threading.Thread(target=producer, args=(offset,)) for offset in (0, 100)] + [
            threading.Thread(target=consumer) for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(matcher) == 200


class TestFuzzySearchHelper:
    """The one-shot ``fuzzy_search`` convenience wrapper."""

    def test_fuzzy_search_basic(self):
        results = fuzzy_search("كتب", ["كتابٌ", "سيارة"])
        assert results[0].candidate == "كتابٌ"

    def test_fuzzy_search_with_limit(self):
        results = fuzzy_search("مدرسه", ["مدرسة", "جامعة"], limit=1)
        assert len(results) == 1
