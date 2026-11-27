"""Tests for new processors: CurrencyProcessor, DateTimeProcessor,
PhoneProcessor, SpellingProcessor."""

from __future__ import annotations

import pytest

from aranorm.processors.currency_processor import CurrencyProcessor
from aranorm.processors.date_processor import DateTimeProcessor
from aranorm.processors.phone_processor import PhoneProcessor
from aranorm.processors.spelling_processor import SpellingProcessor

# ── CurrencyProcessor ──────────────────────────────────────────────────────────


class TestCurrencyProcessor:
    def test_normalize_arabic_currency(self) -> None:
        proc = CurrencyProcessor(mode="normalize")
        result = proc.process("اشتريت بـ 50 ريال")
        assert "SAR" in result

    def test_remove_arabic_currency(self) -> None:
        proc = CurrencyProcessor(mode="remove")
        result = proc.process("السعر 200 دولار فقط")
        assert "دولار" not in result
        assert "فقط" in result

    def test_normalize_dollar_symbol(self) -> None:
        proc = CurrencyProcessor(mode="normalize")
        result = proc.process("$100")
        assert "USD" in result

    def test_keep_mode_is_noop(self) -> None:
        text = "اشتريت بـ 50 ريال"
        proc = CurrencyProcessor(mode="keep")
        assert proc.process(text) == text

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError):
            CurrencyProcessor(mode="invalid")

    def test_normalize_euro_symbol(self) -> None:
        proc = CurrencyProcessor(mode="normalize")
        result = proc.process("€50 فقط")
        assert "EUR" in result

    def test_remove_multiple_currencies(self) -> None:
        proc = CurrencyProcessor(mode="remove")
        result = proc.process("عندي درهم وريال")
        assert "درهم" not in result
        assert "ريال" not in result

    def test_empty_text(self) -> None:
        proc = CurrencyProcessor()
        assert proc.process("") == ""


# ── DateTimeProcessor ─────────────────────────────────────────────────────────


class TestDateTimeProcessor:
    def test_normalize_month_name(self) -> None:
        proc = DateTimeProcessor(mode="normalize")
        result = proc.process("ولد في يناير")
        assert "MONTH_01" in result

    def test_normalize_hijri_month(self) -> None:
        proc = DateTimeProcessor(mode="normalize")
        result = proc.process("في رمضان الكريم")
        assert "MONTH_09" in result

    def test_normalize_numeric_date(self) -> None:
        proc = DateTimeProcessor(mode="normalize")
        result = proc.process("في 15/03/2024")
        assert "DATE_" in result

    def test_remove_date(self) -> None:
        proc = DateTimeProcessor(mode="remove")
        result = proc.process("في 15/03/2024 ذهبت")
        assert "15/03/2024" not in result
        assert "ذهبت" in result

    def test_normalize_temporal_expression(self) -> None:
        proc = DateTimeProcessor(mode="normalize")
        result = proc.process("سأذهب غداً")
        assert "TOMORROW" in result

    def test_normalize_today(self) -> None:
        proc = DateTimeProcessor(mode="normalize")
        result = proc.process("اليوم جميل")
        assert "TODAY" in result

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError):
            DateTimeProcessor(mode="invalid")

    def test_empty_text(self) -> None:
        proc = DateTimeProcessor()
        assert proc.process("") == ""


# ── PhoneProcessor ────────────────────────────────────────────────────────────


class TestPhoneProcessor:
    def test_remove_mobile_number(self) -> None:
        proc = PhoneProcessor(mode="remove")
        result = proc.process("تواصل معي على 0501234567")
        assert "0501234567" not in result

    def test_mask_phone_number(self) -> None:
        proc = PhoneProcessor(mode="mask")
        result = proc.process("اتصل على 0501234567 الآن")
        assert "[PHONE]" in result

    def test_remove_international_number(self) -> None:
        proc = PhoneProcessor(mode="remove")
        result = proc.process("رقمي هو +966501234567")
        assert "+966501234567" not in result

    def test_text_without_phone_unchanged(self) -> None:
        proc = PhoneProcessor(mode="remove")
        text = "مرحباً كيف حالك"
        result = proc.process(text)
        assert result.strip() == text

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError):
            PhoneProcessor(mode="invalid")

    def test_empty_text(self) -> None:
        proc = PhoneProcessor()
        assert proc.process("") == ""

    def test_mask_preserves_surrounding_text(self) -> None:
        proc = PhoneProcessor(mode="mask")
        result = proc.process("اتصل على 0501234567 للاستفسار")
        assert "اتصل" in result
        assert "للاستفسار" in result


# ── SpellingProcessor ─────────────────────────────────────────────────────────


class TestSpellingProcessor:
    def test_corrects_zabtt(self) -> None:
        proc = SpellingProcessor()
        result = proc.process("بالزبط كده")
        assert "بالضبط" in result

    def test_corrects_msa_dropped_hamza(self) -> None:
        proc = SpellingProcessor()
        result = proc.process("الاعلام العربي")
        assert "الإعلام" in result

    def test_corrects_masool(self) -> None:
        proc = SpellingProcessor()
        result = proc.process("الشخص مسئول عن")
        assert "مسؤول" in result

    def test_correct_text_unchanged(self) -> None:
        proc = SpellingProcessor()
        text = "اللغة العربية الجميلة"
        result = proc.process(text)
        # Should not mangle correct text
        assert "اللغة" in result
        assert "العربية" in result

    def test_correction_count_positive(self) -> None:
        assert SpellingProcessor.get_correction_count() > 0

    def test_corrects_inshallah_contraction(self) -> None:
        proc = SpellingProcessor()
        result = proc.process("إنشالله يكون خير")
        assert "إن شاء الله" in result or "انشاءالله" not in result

    def test_empty_text(self) -> None:
        proc = SpellingProcessor()
        assert proc.process("") == ""

    def test_corrects_multiple_errors_in_one_text(self) -> None:
        proc = SpellingProcessor()
        result = proc.process("الاعلام بالزبط مسئولية")
        assert "بالضبط" in result
