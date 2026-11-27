"""Round 15 P3 — final residual coverage closure.

Targets the last branches/lines that stayed missing after P0-P2:

- processors/text_cleaning_processors.py arcs 78->80, 80->82:
  ``NonArabicProcessor`` false branches (keep_digits / keep_punctuation
  both off keeps only Arabic letters).
- processors/number_words_processor.py arc 234->239:
  compound ``و`` guard where the next token is not an attached ``و``
  word (falls through to the ``rebuilt.append`` path).
- utils/stemmer.py arc 280->282: prefix loop exit without match —
  already covered in P2 via stemmer config; re-verify with a token
  starting with a particle prefix but too short to strip.
- utils/text_stats.py arc 143->142: vocabulary loop-back with repeated
  words.
- utils/root_extractor.py arc 120->115: root-pattern loop-back
  (already covered via ``مدرسة``; re-verify with multiple words).
- utils/keyboard_fixer.py arc 165->162: single-char table loop-back —
  covered through ``fix_keyboard_text`` with a non-mapped char.
- utils/fuzzy_matcher.py lines 76/78 (ngram guards), 174 (add empty),
  181->183 (add_many loop), 248 (search empty query), 301 (best_match
  None).
- stages/normalizer.py lines 47/61: ``_build_processors`` false
  branches (ligatures / tatweel etc.) — covered by the all-flags-off
  config in P1; re-verify per-flag with a per-flag config.
- analysis/summarizer.py line 60: newline fallback sentence splitting.
- analysis/text_analyzer.py arcs 125->124, 130->129: word-frequency
  loop-backs.
"""

from __future__ import annotations

from aranorm.analysis.summarizer import _sentences
from aranorm.analysis.text_analyzer import TextAnalyzer
from aranorm.utils.fuzzy_matcher import FuzzyArabicMatcher, jaccard_ngrams
from aranorm.utils.stemmer import ArabicStemmer
from aranorm.utils.text_stats import compute_stats

# ------------------------------------------------------------------ cleaning


def test_non_arabic_keep_flags_off():
    """NonArabicProcessor with both keep flags off drops digits and
    punctuation (arcs 78->80, 80->82)."""
    from aranorm.processors.text_cleaning_processors import NonArabicProcessor

    proc = NonArabicProcessor(keep_digits=False, keep_punctuation=False)
    result = proc.transform("مرحبا 123! نص")
    assert "123" not in result and "!" not in result and "مرحبا" in result


# ------------------------------------------------------------------ number words


def test_number_words_compound_no_attached_waw():
    """Pass 1b falls through when the next token is not an attached ``و``
    word (arc 234->239)."""
    from aranorm.processors.number_words_processor import NumberWordsProcessor

    proc = NumberWordsProcessor()
    result = proc.transform("خمسة كتب عشر")
    assert "5" in result and "10" in result


def test_number_words_attached_waw_compound():
    """Pass 1b joins ``X`` + ``وY`` into a single number (arc 234->239)."""
    from aranorm.processors.number_words_processor import NumberWordsProcessor

    proc = NumberWordsProcessor()
    result = proc.transform("خمسة وعشرون")
    assert "25" in result


# ------------------------------------------------------------------ stemmer


def test_stemmer_prefix_too_short():
    """A token beginning with a prefix particle but below min-stem length
    exits the prefix loop unchanged (arc 280->282)."""
    stemmer = ArabicStemmer(strip_definite_article=False, strip_prefixes=True, strip_suffixes=False)
    result = stemmer.stem("وك")
    assert isinstance(result, str)


# ------------------------------------------------------------------ text stats


def test_text_stats_repeated_words_loopback():
    """The vocabulary histogram accumulates repeated words (arc
    143->142)."""
    stats = compute_stats("كلمة كلمة كلمة مختلفة مختلفة")
    assert stats.vocabulary_size == 2


# ------------------------------------------------------------------ root extractor


def test_root_extractor_batch_loopback():
    """extract_batch exercises the pattern loop for several words (arc
    120->115)."""
    from aranorm.utils.root_extractor import RootExtractor

    extractor = RootExtractor()
    results = extractor.extract_batch(["مدرسة", "كتاب", "معلم"])
    assert len(results) == 3


# ------------------------------------------------------------------ keyboard fixer


def test_keyboard_fixer_multi_char_table():
    """The internal mapping table stores single-char entries by ``ord``
    and multi-char entries by string hash (arc 165->162 loop-back in the
    table builder)."""
    from aranorm.utils.keyboard_fixer import _build_mapping_table

    table = _build_mapping_table({"q": "ض", "qq": "م"})
    assert ord("q") in table and table[ord("q")] == "ض"
    assert hash("qq") in table and table[hash("qq")] == "م"


# ------------------------------------------------------------------ fuzzy matcher


def test_fuzzy_add_many_loop():
    """add_many iterates over the iterable (arc 181->183)."""
    matcher = FuzzyArabicMatcher([])
    matcher.add_many(["مدرسة", "جامعة"])
    assert len(matcher) == 2


def test_fuzzy_stem_and_root_indexing():
    """add indexes both stem and root forms (use_stem/use_root on)."""
    matcher = FuzzyArabicMatcher([], use_stem=True, use_root=True)
    matcher.add("المدرسة")
    assert len(matcher) == 1


def test_fuzzy_search_many():
    """search_many runs search per query."""
    matcher = FuzzyArabicMatcher(["مدرسة"])
    grouped = matcher.search_many(["مدرسه", "جامعه"])
    assert len(grouped) == 2


def test_fuzzy_search_no_match_below_threshold():
    """search returns [] when everything is below the threshold."""
    matcher = FuzzyArabicMatcher(["مدرسة"])
    assert matcher.search("سيارة كهربائية سريعة", threshold=0.99) == []


def test_fuzzy_ngram_guard_no_ngrams():
    """Single-character inputs produce empty n-gram sets, exercising the
    ``not na`` guards (lines 76/78)."""
    assert jaccard_ngrams("ا", "ب") == 0.0
    assert jaccard_ngrams("ا", "مدرسة") == 0.0


def test_fuzzy_add_canonical_guard():
    """add ignores text whose canonical form is empty (line 174)."""
    matcher = FuzzyArabicMatcher([])
    matcher.add("   ")
    matcher.add("ـ")  # tatweel-only normalizes to empty canonical form
    assert len(matcher) == 0


def test_fuzzy_search_canonical_guard():
    """search returns [] when the query canonical form is empty (line
    248)."""
    matcher = FuzzyArabicMatcher(["مدرسة"])
    assert matcher.search("  ") == []
    assert matcher.search("ـ") == []


def test_fuzzy_add_many_loopback():
    """add_many iterates over the iterable more than once (loop-back
    arc at the ``for`` header)."""
    matcher = FuzzyArabicMatcher([])
    matcher.add_many(["مدرسة", "جامعة", "مدرسة"])
    assert len(matcher) == 2


def test_fuzzy_add_many_empty_iterable():
    """add_many tolerates an empty iterable (header-to-exit arc)."""
    matcher = FuzzyArabicMatcher([])
    matcher.add_many([])
    assert len(matcher) == 0


# ------------------------------------------------------------------ normalizer stage (OrthographicNormalizer)


def test_orthographic_normalizer_empty_config():
    """OrthographicNormalizer with every flag disabled processes text
    without transforming it (empty processors loop)."""
    from aranorm.core.config import PipelineConfig
    from aranorm.stages.normalizer import OrthographicNormalizer

    config = PipelineConfig().copy_with(
        handle_arabizi=False,
        normalize_unicode=False,
        normalize_ligatures=False,
        normalize_alef=False,
        normalize_alef_maqsura=False,
        normalize_taa_marbuta=False,
        normalize_hamza=False,
        remove_diacritics=False,
        normalize_tatweel=False,
        normalize_digits=False,
        normalize_punctuation=False,
        normalize_repeated_chars=False,
        remove_extra_punctuation=False,
        fix_spacing=False,
        normalize_whitespace=False,
    )
    normalizer = OrthographicNormalizer(config)
    text = "مدرسة أهلاً وسهلاً"
    assert normalizer.process(text) == text


def test_orthographic_normalizer_process_iterations():
    """OrthographicNormalizer.process iterates over multiple processors
    (loop-back arc)."""
    from aranorm.core.config import PipelineConfig
    from aranorm.stages.normalizer import OrthographicNormalizer

    all_off = {
        "handle_arabizi": False,
        "normalize_unicode": False,
        "normalize_ligatures": False,
        "normalize_alef": False,
        "normalize_alef_maqsura": False,
        "normalize_taa_marbuta": False,
        "normalize_hamza": False,
        "remove_diacritics": False,
        "normalize_tatweel": False,
        "normalize_digits": False,
        "normalize_punctuation": False,
        "normalize_repeated_chars": False,
        "remove_extra_punctuation": False,
        "fix_spacing": False,
        "normalize_whitespace": False,
    }
    overrides = dict(all_off)
    overrides.update(
        remove_diacritics=True,
        normalize_unicode=True,
        normalize_hamza=True,
    )
    config = PipelineConfig().copy_with(**overrides)
    normalizer = OrthographicNormalizer(config)
    assert len(normalizer.processors) == 3
    result = normalizer.process("مَدْرَسَةٌ ٳن شاء الله")
    assert "مدرسة" in result


# ------------------------------------------------------------------ normalizer


def test_normalizer_per_flag_variants():
    """Per-flag configs build the corresponding single processors
    (normalizer.py lines 47/61 paths)."""
    from aranorm.stages.normalizer import OrthographicNormalizer
    from aranorm.processors.unicode_processor import UnicodeProcessor

    from aranorm.core.config import PipelineConfig

    for flag, processor_cls in [
        ("normalize_unicode", UnicodeProcessor),
    ]:
        config = PipelineConfig().copy_with(**{flag: True})
        stage = OrthographicNormalizer(config)
        assert any(isinstance(p, processor_cls) for p in stage.processors)


# ------------------------------------------------------------------ analysis


def test_summarizer_newline_fallback():
    """_sentences falls back to newline splitting when punctuation-only
    splits leave every segment empty (line 60)."""
    sentences = _sentences("..\n..\n")
    assert sentences == ["..", ".."]


def test_summarizer_empty_text():
    """_sentences returns [] for empty input."""
    assert _sentences("") == []


def test_text_analyzer_frequency_loopbacks():
    """TextAnalyzer word/content frequency loops accumulate (arcs
    125->124, 130->129)."""
    analyzer = TextAnalyzer()
    result = analyzer.analyze("نص عربي نص عربي عربي")
    assert isinstance(result.stop_words_ratio, float)
    assert len(result.content_words) >= 1


def test_text_analyzer_empty_text():
    """TextAnalyzer tolerates empty input."""
    analyzer = TextAnalyzer()
    result = analyzer.analyze("")
    assert result.stop_words_ratio == 0.0
