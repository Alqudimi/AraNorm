"""Tests for StopWordsRegistry."""

import time

import pytest

from aranorm.core.stop_words_registry import StopWordsRegistry


@pytest.fixture(scope="module")
def registry() -> StopWordsRegistry:
    return StopWordsRegistry()


# ── Basic MSA lookups ─────────────────────────────────────────────────────────

def test_is_stop_msa_preposition(registry: StopWordsRegistry) -> None:
    assert registry.is_stop("من") is True


def test_is_stop_msa_pronoun(registry: StopWordsRegistry) -> None:
    assert registry.is_stop("أنا") is True


def test_is_stop_msa_conjunction(registry: StopWordsRegistry) -> None:
    assert registry.is_stop("لكن") is True


def test_is_stop_real_word_not_stop(registry: StopWordsRegistry) -> None:
    assert registry.is_stop("سعيد") is False


def test_is_stop_empty(registry: StopWordsRegistry) -> None:
    assert registry.is_stop("") is False


# ── Dialect-specific lookups ──────────────────────────────────────────────────

def test_is_stop_dialect_egy(registry: StopWordsRegistry) -> None:
    """Egyptian 'كده' should match EGY dialect."""
    assert registry.is_stop("كده", dialect="EGY") is True


def test_is_stop_dialect_glf(registry: StopWordsRegistry) -> None:
    """Egyptian 'كده' should NOT match GLF dialect."""
    assert registry.is_stop("كده", dialect="GLF") is False


def test_is_stop_glf_word(registry: StopWordsRegistry) -> None:
    """Gulf 'الحين' (now) is in the GLF list."""
    assert registry.is_stop("الحين", dialect="GLF") is True


# ── Arabizi ───────────────────────────────────────────────────────────────────

def test_is_stop_arabizi(registry: StopWordsRegistry) -> None:
    assert registry.is_stop("2na", is_arabizi=True) is True


def test_is_stop_arabizi_not_a_stop(registry: StopWordsRegistry) -> None:
    assert registry.is_stop("7aga", is_arabizi=True) is False


def test_is_stop_internet(registry: StopWordsRegistry) -> None:
    assert registry.is_stop("lol", is_internet=True) is True


# ── get_words ─────────────────────────────────────────────────────────────────

def test_get_words_universal_non_empty(registry: StopWordsRegistry) -> None:
    words = registry.get_words("universal")
    assert len(words) > 100


def test_get_words_msa_non_empty(registry: StopWordsRegistry) -> None:
    words = registry.get_words("msa")
    assert len(words) > 50


def test_get_words_dialect_includes_msa(registry: StopWordsRegistry) -> None:
    """Dialect scope should include MSA words too."""
    dialect_words = registry.get_words("dialect", frozenset(["EGY"]))
    msa_words = registry.get_words("msa")
    assert msa_words.issubset(dialect_words)


# ── get_by_category ───────────────────────────────────────────────────────────

def test_get_by_category_prepositions(registry: StopWordsRegistry) -> None:
    preps = registry.get_by_category("prepositions")
    assert "في" in preps
    assert "من" in preps
    assert "على" in preps


def test_get_by_category_pronouns(registry: StopWordsRegistry) -> None:
    pronouns = registry.get_by_category("pronouns")
    assert "أنا" in pronouns


def test_get_by_category_filler(registry: StopWordsRegistry) -> None:
    filler = registry.get_by_category("filler")
    assert "يعني" in filler


def test_get_by_category_unknown_returns_empty(registry: StopWordsRegistry) -> None:
    assert registry.get_by_category("nonexistent_category") == set()


# ── get_stats ─────────────────────────────────────────────────────────────────

def test_get_stats_keys(registry: StopWordsRegistry) -> None:
    stats = registry.get_stats()
    assert "total_universal" in stats
    assert "msa" in stats
    assert stats["total_universal"] >= stats["msa"]


# ── Performance ───────────────────────────────────────────────────────────────

def test_is_stop_performance(registry: StopWordsRegistry) -> None:
    """is_stop should complete 10 000 lookups in under 100 ms."""
    # Prime the cache
    registry.is_stop("من")
    start = time.perf_counter()
    for _ in range(10_000):
        registry.is_stop("من")
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"10 000 lookups took {elapsed:.3f}s (expected < 0.1s)"


def test_trie_membership_non_stop(registry: StopWordsRegistry) -> None:
    """Repeated non-stop lookups should also be fast."""
    start = time.perf_counter()
    for _ in range(10_000):
        registry.is_stop("برلمان")
    elapsed = time.perf_counter() - start
    assert elapsed < 0.2
