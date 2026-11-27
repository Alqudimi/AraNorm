"""Behavioral tests for dependency-free language detection."""

import pytest

from aranorm.utils.language_detector import (
    DetectionResult,
    LanguageDetector,
    detect_language,
    is_arabic,
)


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("مرحبا بكم في الجامعة", "arabic"),
        ("Hello from London", "latin"),
        ("ana a7ib al 3arabiyya", "arabizi"),
        ("أنا أحب Python", "mixed"),
        ("12345 678", "numeric"),
        ("!!! --- ؟", "unknown"),
        ("", "unknown"),
        ("   \n\t", "unknown"),
    ],
)
def test_detects_supported_labels(text: str, label: str) -> None:
    result = LanguageDetector().detect_detailed(text)

    assert isinstance(result, DetectionResult)
    assert result.label == label
    assert 0.0 <= result.arabic_ratio <= 1.0
    assert 0.0 <= result.latin_ratio <= 1.0
    assert 0.0 <= result.arabizi_score <= 1.0
    assert 0.0 <= result.confidence <= 1.0


def test_detailed_result_counts_non_whitespace_characters() -> None:
    result = LanguageDetector().detect_detailed(" أب C ")

    assert result.char_count == 3
    assert result.arabic_ratio == pytest.approx(2 / 3, abs=0.001)
    assert result.latin_ratio == pytest.approx(1 / 3, abs=0.001)


def test_arabizi_score_distinguishes_digits_and_plain_latin() -> None:
    detector = LanguageDetector()

    arabizi = detector.detect_detailed("7abibi shloak")
    latin = detector.detect_detailed("hello friend")

    assert arabizi.arabizi_score > detector.arabizi_threshold
    assert arabizi.label == "arabizi"
    assert latin.arabizi_score == 0.0
    assert latin.label == "latin"


def test_mixed_classification_respects_arabizi_priority() -> None:
    result = LanguageDetector().detect_detailed("أنا 7abibi")

    assert result.label == "arabizi"
    assert result.arabic_ratio > 0.15
    assert result.latin_ratio > 0.15


def test_predicate_and_ratio_helpers() -> None:
    detector = LanguageDetector()

    assert detector.is_arabic("لغة عربية جميلة")
    assert detector.is_arabizi("7abibi")
    assert detector.is_mixed("مرحبا Python")
    assert detector.arabic_ratio("أب") == 1.0
    assert detector.arabic_ratio("hello") == 0.0


def test_filter_arabic_keeps_only_predominantly_arabic_items() -> None:
    detector = LanguageDetector()
    values = ["هذا عربي", "hello", "123", "نص آخر"]

    assert detector.filter_arabic(values) == ["هذا عربي", "نص آخر"]


def test_custom_thresholds_change_classification() -> None:
    permissive = LanguageDetector(arabic_threshold=0.1, latin_threshold=0.1)
    strict = LanguageDetector(arabic_threshold=1.0, latin_threshold=1.0)

    assert permissive.detect("أ Hello") == "mixed"
    assert strict.detect("أ Hello") == "mixed"
    assert strict.detect("أ") == "arabic"


def test_module_level_helpers_use_default_detector() -> None:
    assert detect_language("مرحبا") == "arabic"
    assert is_arabic("مرحبا") is True
    assert is_arabic("Hello") is False


def test_punctuation_and_arabic_adjacent_blocks_are_supported() -> None:
    detector = LanguageDetector()

    assert detector.detect("السَّلَامُ، عَلَيْكُمْ") == "arabic"
    # Arabic presentation-form characters are part of the supported blocks.
    assert detector.detect("\ufefb") == "arabic"
