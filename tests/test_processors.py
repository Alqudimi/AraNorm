"""Unit tests for individual AraNorm processors."""

import pytest

from aranorm.exceptions import InvalidTextError
from aranorm.processors import (
    ALEFProcessor,
    AlefMaqsuraProcessor,
    ArabiziProcessor,
    ChatNormalizer,
    DiacriticsProcessor,
    DigitsProcessor,
    HamzaProcessor,
    LigaturesProcessor,
    RepeatedCharsProcessor,
    TaaMarbutaProcessor,
    TatweelProcessor,
    TwitterNormalizer,
    WhatsAppNormalizer,
)
from aranorm.processors.spacing_processor import RepeatedPunctuationProcessor, SpacingProcessor
from aranorm.processors.text_cleaning_processors import (
    EmailProcessor,
    EnglishProcessor,
    HashtagProcessor,
    HTMLProcessor,
    MentionProcessor,
    NonArabicProcessor,
    URLProcessor,
)
from tests.fixtures.sample_texts import (
    ALEF_VARIANTS,
    DIACRITICS_CASES,
    DIGIT_CASES,
    EMAIL_CASES,
    EMOJI_CASES,
    HTML_CASES,
    LIGATURE_CASES,
    MENTION_CASES,
    REPEATED_CHARS_CASES,
    TAA_MARBUTA_CASES,
    TATWEEL_CASES,
)


# ────────────────────────────────────────────────────────────────────────────
# Alef processor
# ────────────────────────────────────────────────────────────────────────────

def test_alef_processor_normalizes_all_variants():
    assert ALEFProcessor().process("أحمد إبراهيم آمن ٱلله") == "احمد ابراهيم امن الله"


@pytest.mark.parametrize("source,expected", ALEF_VARIANTS)
def test_alef_processor_parametrized(source, expected):
    assert ALEFProcessor().process(source) == expected


# ────────────────────────────────────────────────────────────────────────────
# Hamza processor
# ────────────────────────────────────────────────────────────────────────────

def test_hamza_processor_preserves_standalone_hamza():
    assert HamzaProcessor().process("سؤال شيئ") == "سءال شيء"


def test_hamza_processor_waw_hamza():
    assert HamzaProcessor().process("مؤمن") == "مءمن"


def test_hamza_processor_ya_hamza():
    assert HamzaProcessor().process("شيئ") == "شيء"


# ────────────────────────────────────────────────────────────────────────────
# Parametrized basic processors
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("processor", "source", "expected"),
    [
        (TaaMarbutaProcessor(), "مدرسة", "مدرسه"),
        (TaaMarbutaProcessor(), "جامعة كبيرة", "جامعه كبيره"),
        (AlefMaqsuraProcessor(), "على", "علي"),
        (AlefMaqsuraProcessor(), "مصطفى", "مصطفي"),
        (DiacriticsProcessor(), "مَرْحَبًا", "مرحبا"),
        (DiacriticsProcessor(), "السَّلَامُ عَلَيْكُمْ", "السلام عليكم"),
        (TatweelProcessor(), "مـرحـبـا", "مرحبا"),
        (TatweelProcessor(), "جمـيـل", "جميل"),
        (DigitsProcessor(), "١۲3", "123"),
        (DigitsProcessor(), "٠٩٨", "098"),
        (LigaturesProcessor(), "ﻻ ﻷ ﻹ ﻵ", "لا لأ لإ لآ"),
        (RepeatedCharsProcessor(), "يااااا!", "ياا!"),
        (RepeatedCharsProcessor(), "هههههه", "هه"),
    ],
)
def test_basic_processors(processor, source, expected):
    assert processor.process(source) == expected


# ────────────────────────────────────────────────────────────────────────────
# Fixtures-backed parametrized tests
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("source,expected", DIACRITICS_CASES)
def test_diacritics_processor(source, expected):
    assert DiacriticsProcessor().process(source) == expected


@pytest.mark.parametrize("source,expected", DIGIT_CASES)
def test_digits_processor(source, expected):
    assert DigitsProcessor().process(source) == expected


@pytest.mark.parametrize("source,expected", TATWEEL_CASES)
def test_tatweel_processor(source, expected):
    assert TatweelProcessor().process(source) == expected


@pytest.mark.parametrize("source,expected", LIGATURE_CASES)
def test_ligatures_processor(source, expected):
    assert LigaturesProcessor().process(source) == expected


@pytest.mark.parametrize("source,expected", TAA_MARBUTA_CASES)
def test_taa_marbuta_processor(source, expected):
    assert TaaMarbutaProcessor().process(source) == expected


# ────────────────────────────────────────────────────────────────────────────
# Content cleaning
# ────────────────────────────────────────────────────────────────────────────

def test_content_cleaning_chain():
    text = "<b>زوروا</b> https://example.com a@b.com @user #موضوع"
    text = HTMLProcessor().process(text)
    text = URLProcessor().process(text)
    text = EmailProcessor().process(text)
    text = MentionProcessor().process(text)
    text = HashtagProcessor().process(text)
    assert "موضوع" in text
    assert "example" not in text
    assert "@user" not in text
    assert "<b>" not in text
    assert "a@b.com" not in text


@pytest.mark.parametrize("source,after_url", URL_CASES := [
    ("زوروا https://example.com للمزيد", True),
    ("http://foo.org/path?q=1 مقال", True),
    ("www.google.com أداة", True),
])
def test_url_processor_removes_links(source, after_url):
    result = URLProcessor().process(source)
    assert "http" not in result and "www." not in result


@pytest.mark.parametrize("source,_expected", EMAIL_CASES)
def test_email_processor(source, _expected):
    result = EmailProcessor().process(source)
    assert "@" not in result or result.count("@") == 0


@pytest.mark.parametrize("source,_expected", MENTION_CASES)
def test_mention_processor(source, _expected):
    result = MentionProcessor().process(source)
    assert "@" not in result


@pytest.mark.parametrize("source,_expected", HTML_CASES)
def test_html_processor_removes_tags(source, _expected):
    result = HTMLProcessor().process(source)
    assert "<" not in result and ">" not in result


# ────────────────────────────────────────────────────────────────────────────
# Spacing and punctuation
# ────────────────────────────────────────────────────────────────────────────

def test_repeated_punctuation_processor():
    assert RepeatedPunctuationProcessor().process("مرحبا؟؟؟!!!") == "مرحبا؟!"


def test_spacing_processor():
    assert SpacingProcessor().process("مرحبا ،كيفك؟تمام") == "مرحبا، كيفك؟ تمام"


# ────────────────────────────────────────────────────────────────────────────
# Non-Arabic and English
# ────────────────────────────────────────────────────────────────────────────

def test_non_arabic_processor_can_keep_digits():
    result = NonArabicProcessor().process("مرحبا hello 123")
    assert "مرحبا" in result
    assert "hello" not in result
    assert "123" in result


def test_english_processor_removes_latin():
    result = EnglishProcessor().process("مرحبا hello world")
    assert "hello" not in result
    assert "world" not in result
    assert "مرحبا" in result


# ────────────────────────────────────────────────────────────────────────────
# Arabizi
# ────────────────────────────────────────────────────────────────────────────

def test_arabizi_processor_converts_common_tokens():
    assert ArabiziProcessor().process("7abibi 3amel eh") == "حابيبي عاميل ه"


def test_arabizi_digit_substitutions():
    result = ArabiziProcessor().process("2anta 3arabi")
    assert "ء" in result or "ع" in result


# ────────────────────────────────────────────────────────────────────────────
# Platform processors
# ────────────────────────────────────────────────────────────────────────────

def test_twitter_normalizer_removes_rt_prefix():
    text = "RT @someuser: نص مهم جداً"
    result = TwitterNormalizer().process(text)
    assert "RT" not in result
    assert "@someuser" not in result
    assert "نص مهم جداً" in result


def test_twitter_normalizer_expands_hashtags():
    text = "نص #موضوع_مهم للجميع"
    result = TwitterNormalizer(remove_mentions=False).process(text)
    assert "#" not in result
    assert "موضوع_مهم" in result


def test_twitter_normalizer_removes_mentions():
    text = "مرحبا @أحمد كيف حالك"
    result = TwitterNormalizer().process(text)
    assert "@" not in result
    assert "مرحبا" in result


def test_whatsapp_normalizer_expands_abbreviations():
    text = "انشالله تكون بخير"
    result = WhatsAppNormalizer().process(text)
    assert "إن شاء الله" in result


def test_whatsapp_normalizer_removes_bold_format():
    text = "هذا *نص عريض* في واتساب"
    result = WhatsAppNormalizer(expand_abbreviations=False).process(text)
    assert "*" not in result
    assert "نص عريض" in result


def test_chat_normalizer_reduces_laughter():
    text = "هههههههههه مضحك جداً"
    result = ChatNormalizer().process(text)
    assert len(result) < len(text)
    assert "هه" in result


def test_chat_normalizer_expands_abbreviations():
    text = "ان شاء الله نلتقي قريباً"
    result = ChatNormalizer().process(text)
    assert "إن شاء الله" in result


# ────────────────────────────────────────────────────────────────────────────
# Error handling
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("processor", [
    ALEFProcessor(),
    HamzaProcessor(),
    DiacriticsProcessor(),
    TatweelProcessor(),
    URLProcessor(),
])
def test_processors_reject_non_string_input(processor):
    with pytest.raises(InvalidTextError):
        processor.process(None)


def test_processor_accepts_empty_string():
    assert ALEFProcessor().process("") == ""


def test_processor_handles_whitespace_only():
    assert TatweelProcessor().process("   ") == "   "
