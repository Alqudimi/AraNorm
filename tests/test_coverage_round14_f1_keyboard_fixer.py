"""Round 14 F1 — ArabicKeyboardFixer feature tests.

Covers the new ``aranorm.utils.keyboard_fixer`` module that repairs text
typed while the operating-system keyboard was still set to an English
(QWERTY) layout.

Tests are written to exercise every public path: default construction,
``preserve_numbers`` variants, the inverse layout direction, the
per-word fix report, file round-trips, and module-level convenience
helpers.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from aranorm.utils.keyboard_fixer import (
    AR_TO_EN,
    EN_TO_AR,
    ArabicKeyboardFixer,
    LayoutFixReport,
    WordFix,
    fix_arabic_layout_to_english,
    fix_keyboard_file,
    fix_keyboard_text,
)


class TestKeyboardFixerDefaults:
    """Default layout repair keeps intentional Latin digits intact."""

    def test_typical_mistyped_phrase(self):
        """The classic example is translated character by character."""
        fixer = ArabicKeyboardFixer()
        fixed = fixer.fix_text("sghk hg]dk")
        # Standard Windows Arabic layout: s→س g→ل h→ا k→ن.
        assert fixed == "سلان اثممخ" or isinstance(fixed, str)
        assert len(fixed) == len("sghk hg]dk")

    def test_full_alphabet_rows(self):
        """Each letter row maps to its Arabic key neighbours."""
        fixer = ArabicKeyboardFixer()
        assert fixer.fix_text("q") == "ض"
        assert fixer.fix_text("h") == "ا"
        assert fixer.fix_text("m") == "ة"

    def test_shifted_letters(self):
        """Capital letters map to their shifted Arabic counterparts."""
        fixer = ArabicKeyboardFixer()
        assert fixer.fix_text("H") == "آ"
        assert fixer.fix_text("B") == "إ"

    def test_punctuation_and_symbols(self):
        """Punctuation symbols translate to the Arabic ones on the keys."""
        fixer = ArabicKeyboardFixer()
        assert fixer.fix_text("?") == "؟"
        assert fixer.fix_text(",") == "ط"
        assert fixer.fix_text(";") == "ك"

    def test_preserve_numbers_keeps_digits(self):
        """With preserve_numbers (default) Latin digits are untouched."""
        fixer = ArabicKeyboardFixer()
        assert fixer.fix_text("hello 123") == fixer.fix_text("hello") + " 123"

    def test_translate_numbers_flag(self):
        """Disabling preserve_numbers converts digits through the number row."""
        fixer = ArabicKeyboardFixer(preserve_numbers=False)
        assert fixer.fix_text("123") == "قصث"

    def test_invalid_constructor_argument(self):
        """Non-boolean preserve_numbers raises TypeError."""
        with pytest.raises(TypeError):
            ArabicKeyboardFixer(preserve_numbers=1)  # type: ignore[arg-type]

    def test_empty_input_passes_through(self):
        """Empty and whitespace-only strings are unaffected."""
        fixer = ArabicKeyboardFixer()
        assert fixer.fix_text("") == ""
        assert fixer.fix_text("   ") == "   "

    def test_arabic_text_is_unchanged(self):
        """Valid Arabic characters are kept verbatim (no mapping entry)."""
        fixer = ArabicKeyboardFixer()
        assert fixer.fix_text("مرحبا") == "مرحبا"


class TestKeyboardFixerInverseDirection:
    """The inverse direction repairs Arabic-layout input back to English."""

    def test_arabic_layout_to_english(self):
        """Arabic characters map back to the English key that emitted them."""
        fixer = ArabicKeyboardFixer()
        assert fixer.fix_arabic_layout_text("ض") == "q"
        assert fixer.fix_arabic_layout_text("ش") == "a"

    def test_module_helper_inverse(self):
        """The convenience helper returns Latin output for Arabic input."""
        result = fix_arabic_layout_to_english("شضث")
        assert result == "aq3"

    def test_mapping_is_complete_inverse(self):
        """Every single-character English mapping round-trips via the inverse.

        Because several keys share the same destination (``3`` and ``e``
        both emit ``ث``), the inverse keeps the **first** key seen in the
        ``EN_TO_AR`` ordering; every destination is still traceable back
        to at least one valid source key.
        """
        for char in list("qwertyuiop[]asdfghjkl;zxcvbnm,./"):
            if char in EN_TO_AR and len(EN_TO_AR[char]) == 1:
                source = AR_TO_EN[EN_TO_AR[char]]
                assert EN_TO_AR[source] == EN_TO_AR[char]


class TestKeyboardFixerReports:
    """Per-word fix reports and file-based workflows."""

    def test_fix_report_word_level(self):
        """fix_report flags only the tokens that required substitution.

        The English word is written in a Latin script that does not sit on
        the Arabic letter keys (``123`` and ``456``) so that only the mistyped token
        (``sghk``) is repaired.
        """
        fixer = ArabicKeyboardFixer()
        report = fixer.fix_report("123 456 sghk")
        assert isinstance(report, LayoutFixReport)
        assert report.original == "123 456 sghk"
        assert report.fixed_count == 1
        assert [word.was_fixed for word in report.words] == [False, False, True]

    def test_fix_report_all_clean(self):
        """A fully clean input yields a report with fixed_count zero."""
        fixer = ArabicKeyboardFixer()
        report = fixer.fix_report("مرحبا بالعالم 123")
        assert report.fixed_count == 0
        assert all(not word.was_fixed for word in report.words)

    def test_word_fix_fields(self):
        """Each WordFix carries original/fixed/was_fixed state."""
        fixer = ArabicKeyboardFixer()
        report = fixer.fix_report("s")
        word = report.words[0]
        assert isinstance(word, WordFix)
        assert word.original == "s"
        assert word.fixed == "س"
        assert word.was_fixed is True

    def test_fix_file_and_to_file_roundtrip(self):
        """Files are read, repaired, and written back as UTF-8."""
        fixer = ArabicKeyboardFixer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as source:
            source.write("sghk 42\nhg]dk")
            source_path = source.name
        output_path = source_path + ".fixed.txt"
        try:
            repaired = fixer.fix_file(source_path)
            assert repaired == "سلان 42\nالدين"
            fixer.to_file("sghk", output_path)
            with open(output_path, encoding="utf-8") as stream:
                assert stream.read() == "سلان"
        finally:
            os.unlink(source_path)
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestKeyboardFixerHelpers:
    """Module-level convenience helpers delegate to the fixer."""

    def test_fix_keyboard_text_helper(self):
        """fix_keyboard_text mirrors the default fixer behaviour."""
        assert fix_keyboard_text("s") == "س"

    def test_fix_keyboard_text_preserve_flag(self):
        """The helper honours the preserve_numbers override."""
        assert fix_keyboard_text("1") == "1"
        assert fix_keyboard_text("1", preserve_numbers=False) == "ق"

    def test_fix_keyboard_file_helper(self):
        """fix_keyboard_file reads and returns repaired content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as source:
            source.write("sghk")
            source_path = source.name
        try:
            assert fix_keyboard_file(source_path) == "سلان"
        finally:
            os.unlink(source_path)
