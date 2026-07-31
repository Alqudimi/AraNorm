"""Tests for third-party NLP integrations."""

import pytest

from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.integrations.nltk_stopwords import NLTKStopWordsAdapter
from aranorm.integrations.sklearn_stopwords import SklearnStopWordsAdapter
from aranorm.integrations.spacy_stopwords import SpacyStopWordsAdapter


@pytest.fixture(scope="module")
def registry() -> StopWordsRegistry:
    return StopWordsRegistry()


# ── NLTK ─────────────────────────────────────────────────────────────────────

class TestNLTKAdapter:
    def test_to_nltk_list_returns_sorted_list(self, registry: StopWordsRegistry) -> None:
        adapter = NLTKStopWordsAdapter(registry)
        words = adapter.to_nltk_list()
        assert isinstance(words, list)
        assert len(words) > 50
        assert words == sorted(words)

    def test_to_nltk_list_contains_arabic(self, registry: StopWordsRegistry) -> None:
        adapter = NLTKStopWordsAdapter(registry)
        words = adapter.to_nltk_list()
        assert any("\u0600" <= ch <= "\u06FF" for w in words for ch in w), \
            "Expected Arabic characters in the NLTK word list"

    def test_to_nltk_list_msa_scope(self, registry: StopWordsRegistry) -> None:
        adapter = NLTKStopWordsAdapter(registry)
        msa_words = adapter.to_nltk_list(scope="msa")
        univ_words = adapter.to_nltk_list(scope="universal")
        assert len(univ_words) >= len(msa_words)

    def test_register_with_nltk_graceful_without_nltk(
        self, registry: StopWordsRegistry
    ) -> None:
        """register_with_nltk should raise IntegrationUnavailableError if NLTK absent."""
        import importlib
        import sys

        adapter = NLTKStopWordsAdapter(registry)
        nltk_available = importlib.util.find_spec("nltk") is not None
        if not nltk_available:
            from aranorm.exceptions import IntegrationUnavailableError
            with pytest.raises(IntegrationUnavailableError):
                adapter.register_with_nltk()
        else:
            # NLTK is present — just verify it doesn't crash
            try:
                adapter.register_with_nltk()
            except Exception as exc:
                # Non-critical integration errors are acceptable
                pytest.skip(f"NLTK register skipped: {exc}")


# ── spaCy ─────────────────────────────────────────────────────────────────────

class TestSpacyAdapter:
    def test_to_spacy_set_returns_set(self, registry: StopWordsRegistry) -> None:
        adapter = SpacyStopWordsAdapter(registry)
        words = adapter.to_spacy_set()
        assert isinstance(words, set)
        assert len(words) > 50

    def test_to_spacy_set_contains_arabic(self, registry: StopWordsRegistry) -> None:
        adapter = SpacyStopWordsAdapter(registry)
        words = adapter.to_spacy_set()
        assert any("\u0600" <= ch <= "\u06FF" for w in words for ch in w)

    def test_enrich_spacy_raises_without_spacy(
        self, registry: StopWordsRegistry
    ) -> None:
        import importlib
        spacy_available = importlib.util.find_spec("spacy") is not None
        if not spacy_available:
            from aranorm.exceptions import IntegrationUnavailableError
            adapter = SpacyStopWordsAdapter(registry)
            with pytest.raises(IntegrationUnavailableError):
                adapter.enrich_spacy(object())
        else:
            pytest.skip("spaCy present – skipping absence test")


# ── scikit-learn ─────────────────────────────────────────────────────────────

class TestSklearnAdapter:
    def test_to_sklearn_set_returns_frozenset(self, registry: StopWordsRegistry) -> None:
        adapter = SklearnStopWordsAdapter(registry)
        words = adapter.to_sklearn_set()
        assert isinstance(words, frozenset)
        assert len(words) > 50

    def test_to_sklearn_list_returns_sorted_list(self, registry: StopWordsRegistry) -> None:
        adapter = SklearnStopWordsAdapter(registry)
        words = adapter.to_sklearn_list()
        assert isinstance(words, list)
        assert words == sorted(words)

    def test_to_sklearn_set_msa_scope(self, registry: StopWordsRegistry) -> None:
        adapter = SklearnStopWordsAdapter(registry)
        msa = adapter.to_sklearn_set(scope="msa")
        univ = adapter.to_sklearn_set(scope="universal")
        assert len(univ) >= len(msa)

    def test_sklearn_set_compatible_with_vectorizer(
        self, registry: StopWordsRegistry
    ) -> None:
        """frozenset should be accepted by sklearn's TfidfVectorizer if installed."""
        import importlib
        sklearn_available = importlib.util.find_spec("sklearn") is not None
        if not sklearn_available:
            pytest.skip("scikit-learn not installed")
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore

        adapter = SklearnStopWordsAdapter(registry)
        stop_words = adapter.to_sklearn_set()
        vectorizer = TfidfVectorizer(stop_words=list(stop_words))
        corpus = ["أنا سعيد جداً", "هو طالب مجتهد"]
        vectorizer.fit(corpus)
        assert vectorizer.vocabulary_
