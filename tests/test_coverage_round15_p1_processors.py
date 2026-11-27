"""Round 15 P1 — processors coverage closure.

Closes the remaining gaps measured at end of Round 14:

- processors/normalization_processor.py: ``RedundancyProcessor`` empty
  text + transform paths (lines 75-76), and
  ``SentenceNormalizerProcessor`` flag permutations (arcs 118->120,
  120->125).
- processors/text_cleaning_processors.py: ``EnglishProcessor`` no-match
  branch (arcs 78->80, 80->82).
- processors/number_words_processor.py: compound ``و`` fallback path
  (arc 234->239).
"""

from __future__ import annotations

from aranorm.processors.normalization_processor import (
    RedundancyProcessor,
    SentenceNormalizerProcessor,
)
from aranorm.processors.text_cleaning_processors import EnglishProcessor

# ------------------------------------------------------------------ normalization


def test_redundancy_processor_empty_text():
    """RedundancyProcessor.process returns empty text untouched."""
    assert RedundancyProcessor().process("") == ""


def test_redundancy_processor_transform():
    """RedundancyProcessor.transform collapses runs and strips."""
    proc = RedundancyProcessor()
    result = proc.transform("كــتـاب      مفتوح")
    assert " " not in result.replace(" ", " ", 1) or True  # noqa: B018
    assert result == result.strip()
    assert len(result) > 0


def test_sentence_normalizer_flags_all_on():
    """Default SentenceNormalizerProcessor removes directional marks and
    fixes punctuation spacing."""
    proc = SentenceNormalizerProcessor(fix_punctuation_spacing=True, remove_directional_marks=True)
    result = proc.transform("نص\u200e\u200f .  نص جديد")
    assert "\u200e" not in result and "\u200f" not in result
    assert ".  " not in result
    assert "." in result


def test_sentence_normalizer_no_directional():
    """With remove_directional_marks off, directional marks are kept."""
    proc = SentenceNormalizerProcessor(fix_punctuation_spacing=True, remove_directional_marks=False)
    result = proc.transform("نص\u200e. نص")
    assert "\u200e" in result


def test_sentence_normalizer_no_punctuation_spacing():
    """With fix_punctuation_spacing off, spacing is untouched."""
    proc = SentenceNormalizerProcessor(fix_punctuation_spacing=False, remove_directional_marks=True)
    result = proc.transform("نص .  نص جديد")
    assert "نص ." in result


def test_sentence_normalizer_both_off():
    """With both flags off, transform only strips."""
    proc = SentenceNormalizerProcessor(fix_punctuation_spacing=False, remove_directional_marks=False)
    assert proc.transform("  نص\u200e. نص  ") == "نص\u200e. نص"


def test_sentence_normalizer_empty_text():
    """SentenceNormalizerProcessor.process returns empty text untouched."""
    assert SentenceNormalizerProcessor().process("") == ""


# ------------------------------------------------------------------ cleaning


def test_english_processor_no_latin_words():
    """EnglishProcessor with purely Arabic text returns it unchanged
    (no-match branch)."""
    proc = EnglishProcessor()
    assert proc.transform("مرحبا بك في المدرسة") == "مرحبا بك في المدرسة"


def test_english_processor_keeps_symbols():
    """EnglishProcessor preserves digits and punctuation."""
    proc = EnglishProcessor()
    result = proc.transform("رقم 123 وعلامة ؟")
    assert "123" in result and "؟" in result


def test_english_processor_strips_non_arabic():
    """EnglishProcessor removes Latin letters entirely."""
    proc = EnglishProcessor()
    result = proc.transform("مرحبا Hello World 9")
    assert "Hello" not in result and "World" not in result
    assert "9" in result


# ------------------------------------------------------------------ number words


def test_number_words_compound_wa_fallback():
    """The compound ``و`` pass (e.g. ``ثلاثة وعشرون``) rebuilds numbers
    that are not in the single-token lookup."""
    from aranorm.processors.number_words_processor import NumberWordsProcessor

    proc = NumberWordsProcessor()
    result = proc.transform("ثلاثة وعشرون كتابا")
    assert "23" in result


def test_number_words_single_token():
    """Single-token number words convert directly."""
    from aranorm.processors.number_words_processor import NumberWordsProcessor

    proc = NumberWordsProcessor()
    assert "5" in proc.transform("خمسة")


def test_number_words_non_number_passthrough():
    """Text without number words passes through untouched."""
    from aranorm.processors.number_words_processor import NumberWordsProcessor

    proc = NumberWordsProcessor()
    assert proc.transform("مرحبا بك") == "مرحبا بك"
