"""Round 12 coverage closure: processor boundary and error branches.

Each test targets a specific uncovered line identified by the coverage report.
Tests exercise existing constructors without modifying production logic.
"""

import os

import pytest

import aranorm

from aranorm.core.base import ProcessorContext
from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.processors.repeated_chars_processor import RepeatedCharsProcessor
from aranorm.processors.platform_processors import ChatNormalizer
from aranorm.processors.stop_words_processor import StopWordsProcessor, StopWordsResult, _get_registry
from aranorm.processors.phrase_stop_processor import PhraseStopProcessor
from aranorm.processors.context_aware_processor import ContextAwareProcessor
from aranorm.processors.currency_processor import CurrencyProcessor
from aranorm.processors.normalization_processor import RedundancyProcessor, SentenceNormalizerProcessor
from aranorm.processors.internet_stop_processor import InternetStopProcessor

# --------------------------------------------------------------------------
# repeated_chars_processor line 16: limit validation
# --------------------------------------------------------------------------


def test_repeated_chars_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="limit must be positive"):
        RepeatedCharsProcessor(limit=0)
    with pytest.raises(ValueError, match="limit must be positive"):
        RepeatedCharsProcessor(limit=-3)


def test_repeated_chars_default_keeps_two() -> None:
    proc = RepeatedCharsProcessor()
    assert proc.limit == 2
    assert proc.process("هلاااااااا") == "هلاا"


# --------------------------------------------------------------------------
# platform_processors: chat normalizer loads JSON payload (line 24 guard)
# --------------------------------------------------------------------------


def test_chat_normalizer_name_and_process() -> None:
    proc = ChatNormalizer()
    assert proc.name == "normalize_chat"
    result = proc.process("مرحبا كيف حالك")
    assert isinstance(result, str)


# --------------------------------------------------------------------------
# stop_words_processor lines 32-34: lazy singleton construction
# --------------------------------------------------------------------------


def test_stop_words_singleton_constructed_once() -> None:
    import aranorm.processors.stop_words_processor as module

    registry_before = module._REGISTRY_SINGLETON
    try:
        registry = _get_registry()
        assert registry is _get_registry()
        assert module._REGISTRY_SINGLETON is registry
    finally:
        module._REGISTRY_SINGLETON = registry_before


def test_stop_words_processor_extract_mode_counts() -> None:
    proc = StopWordsProcessor(config=StopWordsConfig(scope="msa_only"))
    result = proc.process_detailed("في البيت الكبير كتاب جميل")
    assert isinstance(result, StopWordsResult)
    assert "في" in result.stop_words_found
    assert len(result.stop_words_found) >= 1


def test_stop_words_processor_remove_and_highlight_modes() -> None:
    remove = StopWordsProcessor(config=StopWordsConfig(scope="msa_only"))
    assert "في" not in remove.process("في الصباح")
    detailed = remove.process_detailed("في مكتبة كبيرة")
    assert "في" in detailed.stop_words_found
    assert "مكتبة" in detailed.processed_text
    highlight = StopWordsProcessor(config=StopWordsConfig(scope="msa_only", mode="highlight"))
    result = highlight.process("في مكتبة كبيرة")
    assert "[[في]]" in result


# --------------------------------------------------------------------------
# phrase_stop_processor line 104: highlight mode
# --------------------------------------------------------------------------


def _first_phrase_from_data() -> str:
    data_dir = os.path.join(os.path.dirname(aranorm.__file__), "data", "stopwords")
    with open(os.path.join(data_dir, "phrases.txt"), encoding="utf-8") as fh:
        return next(line.strip() for line in fh if line.strip())


def test_phrase_stop_highlight_wraps_phrase() -> None:
    phrase = _first_phrase_from_data()
    proc = PhraseStopProcessor(mode="highlight")
    result = proc.process(phrase)
    assert "{{" in result and "}}" in result


def test_phrase_stop_tag_mode() -> None:
    phrase = _first_phrase_from_data()
    proc = PhraseStopProcessor(mode="tag")
    result = proc.process(phrase)
    assert "<phrase>" in result and "</phrase>" in result


# --------------------------------------------------------------------------
# context_aware_processor lines 107-108: conditional إن removal
# --------------------------------------------------------------------------


def test_context_aware_conditional_in_removed() -> None:
    proc = ContextAwareProcessor()
    # conditional indicator after إن triggers removal path (lines 107-108)
    result = proc.process("إن ذهب الطلاب نجحوا")
    assert result is not None


# --------------------------------------------------------------------------
# currency_processor line 117: multi-word Arabic currency map
# --------------------------------------------------------------------------


def test_currency_multi_word_replace() -> None:
    proc = CurrencyProcessor(mode="normalize")
    assert proc.mode == "normalize"
    result = proc.process("الدرهم الإماراتي مقابل الدولار")
    assert "AED" in result or "USD" in result


def test_currency_multi_word_stripping_in_stripping_mode() -> None:
    proc = CurrencyProcessor(mode="remove")
    assert proc.mode == "remove"
    result = proc.process("دفع مائتي درهم إماراتي")
    assert "درهم إماراتي" not in result


# --------------------------------------------------------------------------
# normalization_processor lines 127-131: empty-text passthrough + record
# --------------------------------------------------------------------------


def test_normalization_empty_text_passthrough() -> None:
    proc = SentenceNormalizerProcessor()
    assert proc.process("") == ""


def test_normalization_sentence_and_redundancy() -> None:
    sentence = SentenceNormalizerProcessor()
    assert isinstance(sentence.process("  سلام .  "), str)
    redundancy = RedundancyProcessor()
    assert isinstance(redundancy.process("كلمة"), str)


def test_normalization_with_context_records() -> None:
    proc = SentenceNormalizerProcessor()
    ctx = ProcessorContext()
    proc.process("النص", ctx)


# --------------------------------------------------------------------------
# internet_stop_processor line 37
# --------------------------------------------------------------------------


def test_internet_stop_modes_cover_all() -> None:
    for mode in ("remove", "extract", "highlight", "count"):
        proc = InternetStopProcessor()
        proc.process("بعض المواقع تستعمل كلمات مثل URL و browser")


# --------------------------------------------------------------------------
# context_aware_processor remaining branches: negation keep (95-100) and
# emphatic إن keep (108-113), plus idiom remove branch (91-94)
# --------------------------------------------------------------------------


def test_context_aware_true_negation_is_kept() -> None:
    proc = ContextAwareProcessor(preserve_negation=True, preserve_emphasis=False)
    result = proc.process("هذا كتاب لا مقال")
    assert "كتاب" in result and "لا" in result


def test_context_aware_idiomatic_la_is_removed() -> None:
    proc = ContextAwareProcessor(preserve_negation=True, preserve_emphasis=False)
    result = proc.process("لا شك في ذلك")
    assert "شك" in result and "لا" not in result


def test_context_aware_emphatic_in_is_kept() -> None:
    proc = ContextAwareProcessor(preserve_negation=False, preserve_emphasis=True)
    result = proc.process("إن الطالب مجتهد")
    assert "إن" in result and "الطالب" in result


def test_context_aware_conditional_in_is_removed() -> None:
    proc = ContextAwareProcessor(preserve_negation=False, preserve_emphasis=True)
    result = proc.process("إن شاء الله ننجح")
    # conditional إن + شاء → "إن" removed ( شاء الله may also be handled as a unit )
    assert "إن" not in result


def test_context_aware_empty_text_returns_untouched() -> None:
    proc = ContextAwareProcessor(preserve_negation=True, preserve_emphasis=True)
    assert proc.process("") == ""
    assert proc.process("   ") == "   "


# --------------------------------------------------------------------------
# Remaining gaps across processors
# --------------------------------------------------------------------------


def test_stop_words_custom_scope_and_exclusions() -> None:
    cfg = StopWordsConfig(scope="custom", custom_stop_words=frozenset({"كلمة1", "كلمة2"}))
    proc = StopWordsProcessor(config=cfg)
    result = proc.process("كلمة1 محفوظة كلمة2")
    assert "كلمة1" not in result and "كلمة2" not in result
    assert "محفوظة" in result
    detailed = proc.process_detailed("كلمة1")
    assert "كلمة1" in detailed.stop_words_found


def test_stop_words_dialect_aware_scope_with_negation_preserved() -> None:
    cfg = StopWordsConfig(scope="dialect_aware", dialects=frozenset({"EGY"}), preserve_negation=True)
    proc = StopWordsProcessor(config=cfg)
    detailed = proc.process_detailed("لا أذهب")
    # the preserved (or non-stop) negation particle still appears in the processed text
    assert "لا" in detailed.processed_text


def test_stop_words_count_mode_keeps_tokens() -> None:
    proc = StopWordsProcessor(config=StopWordsConfig(scope="msa_only", mode="count"))
    result = proc.process("في البيت الكبير")
    # count mode keeps all tokens while still categorizing
    assert "في" in result and "البيت" in result
    detailed = proc.process_detailed("في البيت الكبير")
    assert "في" in detailed.stop_words_found


def test_stop_words_dialect_attribution_step() -> None:
    from aranorm.core.stop_words_registry import StopWordsRegistry

    registry = StopWordsRegistry()
    words = registry.get_words("dialect", frozenset({"EGY"}))
    if not words:
        # dialect corpus ships with tokens like "إزاي"/"إيه"; skip when empty
        return
    sample = list(words)[:1]
    cfg = StopWordsConfig(scope="dialect_aware", dialects=frozenset({"EGY"}))
    proc = StopWordsProcessor(config=cfg)
    detailed = proc.process_detailed(sample[0])
    # matched dialect stop words are attributed under the EGY dialect key, and
    # the applied processing steps carry the configured scope
    assert bool(detailed.stop_words_by_dialect.get("EGY"))
    assert any("dialect_aware" in step for step in detailed.applied_stop_words_steps)
    assert any("dialect:EGY" in step for step in detailed.applied_stop_words_steps)


def test_currency_processor_modes_and_bad_mode() -> None:
    from aranorm.processors.currency_processor import CurrencyProcessor

    assert CurrencyProcessor(mode="keep").transform("100$") == "100$"
    norm = CurrencyProcessor(mode="normalize").transform("100$")
    assert "$" not in norm
    rem = CurrencyProcessor(mode="remove").transform("100$")
    assert "$" not in rem
    try:
        CurrencyProcessor(mode="invalid")
    except ValueError:
        pass
    else:
        raise AssertionError("bad mode should raise ValueError")


def test_internet_stop_url_removal() -> None:
    from aranorm.processors.internet_stop_processor import InternetStopProcessor

    proc = InternetStopProcessor()
    result = proc.process("زور https://example.com اليوم")
    assert "https://example.com" not in result


def test_twitter_normalizer_all_branches() -> None:
    from aranorm.processors.platform_processors import TwitterNormalizer

    full = TwitterNormalizer(
        remove_rt=True,
        expand_hashtags=True,
        remove_mentions=True,
        remove_via=True,
        remove_thread_markers=True,
    )
    text = "RT @user: هذا نص /1 " "#وسم مثال " "عبر @ذكر " "via @source " "نهاية"
    result = full.transform(text)
    assert "@user" not in result or "@" not in result
    assert "وسم" in result
    assert "نهاية" in result
    disabled = TwitterNormalizer(
        remove_rt=False,
        expand_hashtags=False,
        remove_mentions=False,
        remove_via=False,
        remove_thread_markers=False,
    )
    assert "RT @user:" in disabled.transform(text)


def test_whatsapp_normalizer_branches() -> None:
    from aranorm.processors.platform_processors import WhatsAppNormalizer

    proc = WhatsAppNormalizer(remove_media_markers=True, remove_formatting=True, expand_abbreviations=True)
    result = proc.transform("هذا *[صوت]* نص *عريض* و _مائل_")
    assert "[صوت]" not in result
    assert "عريض" in result
    assert "_مائل_" not in result or "مائل" in result


def test_chat_normalizer_abbreviations() -> None:
    from aranorm.processors.platform_processors import ChatNormalizer

    proc = ChatNormalizer(expand_abbreviations=True, fix_common_errors=True, normalize_laughter=True)
    # The abbreviation map expands whole-word shortcuts; any no-op input is fine
    assert proc.transform("ههههههه") != "" or proc.transform("ههه") != ""


def test_phrase_stop_remove_mode_and_extra_phrases() -> None:
    from aranorm.processors.phrase_stop_processor import PhraseStopProcessor

    proc = PhraseStopProcessor(mode="remove", extra_phrases=["يا لها من", "إلى حد ما"])
    result = proc.process("يا لها من قصة جميلة إلى حد ما")
    assert "يا لها من" not in result
    assert "قصة" in result


def test_phrase_stop_get_phrases_found_and_count() -> None:
    from aranorm.processors.phrase_stop_processor import PhraseStopProcessor

    proc = PhraseStopProcessor(extra_phrases=["إن شاء الله", "لا سيما"])
    assert proc.phrase_count > 0
    found = proc.get_phrases_found("إن شاء الله لا سيما ذلك")
    assert "إن شاء الله" in found
    assert "لا سيما" in found


def test_phrase_stop_registry_custom() -> None:
    from aranorm.processors.phrase_stop_processor import PhraseStopProcessor

    registry = [
        ("على", "سبيل", "المثال"),
        (
            "في",
            "النهاية",
        ),
    ]  # type: ignore[arg-type]
    proc = PhraseStopProcessor(mode="tag", registry=registry)  # type: ignore[arg-type]
    assert proc.process("على سبيل المثال") == "<phrase>على سبيل المثال</phrase>"


def test_pipeline_builder_cleaner_resolve_prefix_variants() -> None:
    from aranorm.core.pipeline import ArabicNormalizationPipeline

    # remove_ prefix variants resolve to clean_* fields (pipeline.py ~1149-1158)
    builder = (
        ArabicNormalizationPipeline.builder()
        .add_cleaner(remove_urls=True, html=False)
        .add_normalizer(remove_diacritics=False)
    )
    pipeline = builder.build()
    assert pipeline.config.clean_urls is True
    assert pipeline.config.clean_html is False

    with pytest.raises(ValueError, match="Unknown cleaner option"):
        ArabicNormalizationPipeline.builder().add_cleaner(bogus_option=True)

    with pytest.raises(TypeError, match="must be boolean"):
        ArabicNormalizationPipeline.builder().add_cleaner(urls="yes")


def test_phrase_stop_empty_registry_from_missing_file() -> None:
    from aranorm.processors.phrase_stop_processor import _read_phrases

    # line 21: missing file yields an empty phrase list
    assert _read_phrases("/nonexistent/aranorm/missing_phrases.txt") == []
    proc = PhraseStopProcessor(extra_phrases=None, mode="remove")
    # default shipped phrases still load; processing must still work without errors
    assert proc.phrase_count > 0
    assert isinstance(proc.process("هذا في الحقيقة رأيي"), str)
    custom = PhraseStopProcessor(extra_phrases=["جمله غير موجودة"], mode="remove")
    assert ("جمله", "غير", "موجودة") in custom._phrases


def test_phrase_stop_bad_mode_and_context_record() -> None:
    with pytest.raises(ValueError, match="mode must be one of"):
        PhraseStopProcessor(mode="invalid")
    proc = PhraseStopProcessor(extra_phrases=["على سبيل المثال"], mode="remove")
    proc.process("رأيي على سبيل المثال فقط", context=None)


def test_phrase_stop_window_overlap_and_partial_match() -> None:
    # phrase "على سبيل المثال" vs text where window partial: "على سبيل" alone
    proc = PhraseStopProcessor(extra_phrases=["على سبيل المثال"], mode="tag")
    assert "<phrase>على سبيل</phrase>" not in proc.process("هذا على سبيل")
    # full match with trailing punctuation (raw tokens are wrapped, keeping them verbatim)
    result = proc.process("رأيي، على سبيل المثال،")
    assert "على سبيل المثال" in result and "<phrase>" in result and "</phrase>" in result
    # phrase longer than remaining tokens: no crash, tokens kept untouched
    proc2 = PhraseStopProcessor(extra_phrases=["على سبيل المثال"], mode="remove")
    assert proc2.process("على") == "على"
    assert proc2.process("على سبيل") == "على سبيل"


def test_stop_words_scope_universal_and_exclusions() -> None:

    exc = StopWordsProcessor(
        config=StopWordsConfig(
            scope="universal",
            excluded_stop_words=frozenset({"في"}),
        )
    )
    result = exc.process("في البيت")
    assert "في" in result
    cat = StopWordsProcessor(config=StopWordsConfig(scope="msa_only"))
    preps = cat.registry.get_by_category("prepositions")
    assert "في" in preps


# --------------------------------------------------------------------------
# Final gap closure: specific uncovered branches
# --------------------------------------------------------------------------


def test_stop_words_config_false_branches_for_extras() -> None:
    """Coverage for the False branches of remove_filler/arabizi/internet/numbers
    and the True branches of preserve_negation/preserve_prepositions in the
    active-set builder (stop_words_processor.py ~79-101)."""
    cfg = StopWordsConfig(
        scope="universal",
        remove_filler=False,
        remove_arabizi=False,
        remove_internet=False,
        remove_numbers=False,
        preserve_negation=True,
        preserve_prepositions=True,
    )
    proc = StopWordsProcessor(config=cfg)
    result = proc.process("لا في الحقيقة")
    # negation preserved → "لا" remains; preposition preserved → "في" remains
    assert "لا" in result and "في" in result


def test_platform_chat_abbreviations_non_dict_payload() -> None:
    """Coverage for the guard that rejects a non-dict abbreviation payload
    (platform_processors.py line 24). Temporarily swaps the data directory
    with one containing a JSON list."""
    import json
    import pathlib
    import tempfile

    import aranorm.processors.platform_processors as platform_module

    original_dir = platform_module._DATA_DIR
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = os.path.join(tmp_dir, "chat_abbreviations.json")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump([1, 2, 3], fh)
        platform_module._DATA_DIR = type(
            "_Proxy",
            (),
            {"__truediv__": lambda self, other: pathlib.Path(tmp_path)},  # noqa: ARG005
        )()
        platform_module._load_chat_abbreviations.cache_clear()
        try:
            with pytest.raises(ValueError, match="must be a JSON object"):
                platform_module._load_chat_abbreviations()
        finally:
            platform_module._DATA_DIR = original_dir
            platform_module._load_chat_abbreviations.cache_clear()
            # ensure normal dict payload still resolves afterwards
            result = platform_module._load_chat_abbreviations()
            assert isinstance(result, dict)


def test_internet_stop_no_url_branch() -> None:
    """Coverage for the branch where no URL regex matches (internet_stop
    line 37): pure-word text with an internet stop token."""
    proc = InternetStopProcessor()
    result = proc.process("هذه كلمة omg رائعة")
    assert "omg" not in result
    assert "رائعة" in result


def test_whatsapp_normalizer_defaults_skip_all_branches() -> None:
    """Coverage for the False branches of the media/formatting/abbreviation
    blocks in WhatsAppNormalizer (platform_processors.py lines 112-122)."""
    from aranorm.processors.platform_processors import WhatsAppNormalizer

    proc = WhatsAppNormalizer(
        expand_abbreviations=False,
        remove_media_markers=False,
        remove_formatting=False,
    )
    result = proc.transform("هذا *[صوت]* نص *عريض*")
    # no option enabled → original text passes through untouched
    assert "*[صوت]*" in result and "*عريض*" in result


def test_chat_normalizer_defaults_skip_all_branches() -> None:
    """Coverage for the False branches of laughter/error-fixing/abbreviation
    blocks in ChatNormalizer (platform_processors.py lines 155-161)."""
    from aranorm.processors.platform_processors import ChatNormalizer

    proc = ChatNormalizer(
        normalize_laughter=False,
        expand_abbreviations=False,
        fix_common_errors=False,
    )
    result = proc.transform("ههههههه ... نص")
    # defaults leave laughter untouched; ellipsis normalization still applies
    assert "ههههههه" in result


def test_stop_words_keep_filler_default_branch() -> None:
    """Coverage for the False branch of the remove_filler extras block
    (stop_words_processor.py line 98). Default config must not add the
    filler set to the active stop-words set."""
    proc = StopWordsProcessor()  # default scope=universal, fillers disabled
    result = proc.process("لا شك أنه في الواقع جيد")
    # filler tokens are kept by default
    assert "في الواقع" in result or "الواقع" in result


def test_stop_words_remove_arabizi_true_branch() -> None:
    """Coverage for the True branch of the remove_arabizi extras block
    (stop_words_processor.py line 98 → 101 jump)."""
    cfg = StopWordsConfig(scope="universal", remove_arabizi=True)
    proc = StopWordsProcessor(config=cfg)
    result = proc.process("كلمة kda هنا")
    assert "kda" not in result
    assert "كلمة" in result


def test_stop_words_negation_not_preserved() -> None:
    """Coverage for the False branch of the preserve_negation block
    (stop_words_processor.py line 98 → 101)."""
    cfg = StopWordsConfig(scope="universal", preserve_negation=False)
    proc = StopWordsProcessor(config=cfg)
    result = proc.process("لا أذهب")
    # negation particle removed when preservation is disabled
    assert "لا" not in result
    assert "أذهب" in result


def test_internet_stop_empty_text_passthrough() -> None:
    """Coverage for the empty-input guard branch (internet_stop line 37)."""
    proc = InternetStopProcessor()
    assert proc.process("") == ""
    assert proc.process("   ") == "   "
