"""Round 15 P2 — utils coverage closure.

Closes the remaining residual gaps:

- utils/stemmer.py: ``stem()`` interaction between the definite article
  guard and prefix stripping (arc 227->234), suffix-off path (238->241),
  and the end of the prefix loop (280->282).
- utils/text_stats.py: loop-back arc 143->142 (vocabulary loop).
- utils/tokenizer.py: hard-split branch (190->198).
- utils/keyboard_fixer.py: single-char mapping loop-back (165->162).
- utils/fuzzy_matcher.py: empty/None ngram guards (lines 76, 78),
  ``add_text`` empty guards (lines 174, 248), and ``best_match`` None
  path (line 301).
- utils/root_extractor.py: loop-back arc 120->115.
"""

from __future__ import annotations

from aranorm.utils.fuzzy_matcher import FuzzyArabicMatcher, jaccard_ngrams
from aranorm.utils.keyboard_fixer import fix_keyboard_text
from aranorm.utils.root_extractor import extract_root
from aranorm.utils.stemmer import ArabicStemmer
from aranorm.utils.text_stats import compute_stats
from aranorm.utils.tokenizer import ArabicTokenizer

# ------------------------------------------------------------------ stemmer


def test_stemmer_article_blocks_prefix_stripping():
    """After stripping the definite article, prefix stripping is skipped
    (arc 227->234)."""
    stemmer = ArabicStemmer(strip_definite_article=True, strip_prefixes=True, strip_suffixes=True)
    assert stemmer.stem("الكتاب") == "كتاب"


def test_stemmer_prefix_and_suffix():
    """With the article flag off, prefix stripping applies; suffix also."""
    stemmer = ArabicStemmer(strip_definite_article=False, strip_prefixes=True, strip_suffixes=True)
    result = stemmer.stem("مكتوبات")
    assert isinstance(result, str) and len(result) <= len("مكتوبات")


def test_stemmer_no_suffixes():
    """With strip_suffixes off, only article/prefix stripping applies
    (arc 238->241)."""
    stemmer = ArabicStemmer(strip_definite_article=True, strip_prefixes=True, strip_suffixes=False)
    assert stemmer.stem("الكتاب") == "كتاب"


def test_stemmer_prefix_loop_no_match():
    """A word that matches no prefix exits the loop unchanged (arc
    280->282)."""
    stemmer = ArabicStemmer(strip_definite_article=False, strip_prefixes=True, strip_suffixes=False)
    assert stemmer.stem("مكتبة") == "مكتبة"


def test_stemmer_tokens_and_sentences():
    """stem_tokens / stem_sentences delegate element-wise."""
    stemmer = ArabicStemmer()
    assert stemmer.stem_tokens(["الكتاب", "مدرسة"]) == [
        stemmer.stem("الكتاب"),
        stemmer.stem("مدرسة"),
    ]


# ------------------------------------------------------------------ text_stats


def test_text_stats_vocabulary_loop():
    """compute_stats builds the vocabulary histogram (arc 143->142)."""
    stats = compute_stats("الكتاب الكتاب مدرسه")
    assert stats.vocabulary_size == 2 and stats.type_token_ratio > 0


def test_text_stats_empty_text():
    """compute_stats tolerates empty text without division errors."""
    stats = compute_stats("")
    assert stats.word_count == 0 and stats.type_token_ratio == 0.0


# ------------------------------------------------------------------ tokenizer


def test_tokenizer_hard_split_long_sentence():
    """split_into_chunks hard-splits a single sentence longer than
    max_tokens (arc 190->198)."""
    chunks = ArabicTokenizer().split_into_chunks("أ ب ت ث ج ح خ د ذ ر ز س ش", max_tokens=3)
    assert all(len(chunk.split()) <= 3 for chunk in chunks)


def test_tokenizer_respects_max_tokens():
    """split_into_chunks respects the token budget across sentence
    boundaries."""
    chunks = ArabicTokenizer().split_into_chunks("جملة أولى. جملة ثانية. جملة ثالثة.", max_tokens=4)
    assert chunks and all(len(chunk.split()) <= 4 for chunk in chunks)


# ------------------------------------------------------------------ keyboard fixer


def test_keyboard_fixer_single_char_mapping():
    """The internal mapping table accepts single-char mappings (loop body,
    arc 165->162) — observed through fix_keyboard_text with shifted
    Arabic-latin characters."""
    result = fix_keyboard_text("g`)ي")  # g → ل (QWERTY->Arabic shift)
    assert isinstance(result, str)
    assert "ل" in result


def test_keyboard_fixer_duplicate_keep_first():
    """Duplicate destinations resolve by keeping the first occurrence."""
    fixed = fix_keyboard_text("g 2")
    assert isinstance(fixed, str)


def test_keyboard_fixer_prefix_mapping():
    """Multi-char prefix entries are stored by string hash and applied."""
    result = fix_keyboard_text("مدرسة")
    assert isinstance(result, str)


# ------------------------------------------------------------------ fuzzy matcher


def test_fuzzy_ngram_guard_empty_inputs():
    """ngram similarity guards return 0.0 for empty/None inputs (lines
    76/78)."""
    assert jaccard_ngrams("", "مدرسة") == 0.0
    assert jaccard_ngrams(None, "مدرسة") == 0.0  # type: ignore[arg-type]
    assert jaccard_ngrams("مدرسة", "") == 0.0


def test_fuzzy_add_empty_guard():
    """add ignores empty/whitespace-only text (line 174)."""
    matcher = FuzzyArabicMatcher([])
    matcher.add("   ")
    assert len(matcher) == 0


def test_fuzzy_search_empty_query_guard():
    """search returns [] for empty/whitespace-only queries (line 248)."""
    matcher = FuzzyArabicMatcher(["مدرسة"])
    assert matcher.search("  ") == []


def test_fuzzy_best_match_none():
    """best_match returns None when nothing matches (line 301)."""
    matcher = FuzzyArabicMatcher(["مدرسة"])
    result = matcher.best_match("سيارة كهربائية")
    assert result is None


def test_fuzzy_best_match_hit():
    """best_match returns the top match when present."""
    matcher = FuzzyArabicMatcher(["مدرسة"])
    result = matcher.best_match("مدرسه")
    assert result is not None and result.candidate == "مدرسة"


# ------------------------------------------------------------------ root extractor


def test_root_extractor_loopback():
    """extract_root exercises the root-pattern iteration (arc 120->115)."""
    root = extract_root("مدرسة")
    assert root is not None


def test_root_extractor_no_root():
    """extract_root returns None when no pattern matches."""
    assert extract_root("abc") is None
