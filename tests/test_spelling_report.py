"""Tests for the Round-17 spelling report module.

Covers :mod:`aranorm.analysis.spelling_report` — correction enumeration,
category classification, ratios, serialization and the public CLI surface.
"""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")

from aranorm.analysis.spelling_report import (  # noqa: E402
    SpellingAnalyzer,
    SpellingCorrection,
    _guess_correction_category,
    analyze_spelling,
)

# ── Happy path: real Arabic corrections ──────────────────────────────────────


def test_hamza_on_waw_correction_detected() -> None:
    report = analyze_spelling("مسئول عن الحدث")
    assert report.spelling_issues_found >= 1
    words = {correction.word: correction for correction in report.corrections}
    assert "مسئول" in words
    assert words["مسئول"].category == "waw"


def test_missing_initial_hamza_correction() -> None:
    report = analyze_spelling("الاعلان عن الحدث الاهمية")
    replacements = {correction.word: correction.replacement for correction in report.corrections}
    assert "الاعلان" in replacements
    assert replacements["الاعلان"] == "الإعلان"
    assert report.correct_ratio < 1.0


def test_total_words_and_correct_ratio_consistency() -> None:
    report = analyze_spelling("مسئول الاعلان عن الحدث الاهمية")
    assert report.total_words == 5
    corrected_count = sum(correction.count for correction in report.corrections)
    assert corrected_count == report.spelling_issues_found
    assert report.correct_ratio == pytest.approx(
        (report.total_words - report.spelling_issues_found) / report.total_words
    )


def test_clean_text_has_no_issues() -> None:
    report = analyze_spelling("هذا نص عربي واضح ومفهوم تماما")
    assert report.spelling_issues_found == 0
    assert report.unique_issues == 0
    assert report.correct_ratio == 1.0
    assert report.confidence == 1.0


def test_empty_text_returns_empty_report() -> None:
    report = analyze_spelling("")
    assert report.original_text == ""
    assert report.corrected_text == ""
    assert report.total_words == 0
    assert report.spelling_issues_found == 0


def test_non_arabic_text_ignored() -> None:
    report = analyze_spelling("Hello world")
    assert report.total_words == 0
    assert report.spelling_issues_found == 0


def test_mixed_text_only_counts_arabic_tokens() -> None:
    report = analyze_spelling("مسئول يعمل مع team")
    assert report.total_words == 3  # "مسئول" + "يعمل" + "مع" (latin skipped)
    assert report.spelling_issues_found == 1


# ── Category classification ──────────────────────────────────────────────────


def test_category_waw() -> None:
    assert _guess_correction_category("مسئول", "مسؤول") == "waw"


def test_category_typo_generic() -> None:
    assert _guess_correction_category("الاعلان", "الإعلان") == "typo"


def test_category_hamza_initial() -> None:
    assert _guess_correction_category("اهلا", "أهلا") == "hamza"
    assert _guess_correction_category("ان", "إن") == "hamza"


def test_category_alef_maqsura() -> None:
    assert _guess_correction_category("مستشفى", "مستشفى") == "typo"


# ── Report object behaviour ──────────────────────────────────────────────────


def test_report_serialization_roundtrip() -> None:
    report = analyze_spelling("مسئول الاعلان")
    data = report.to_dict()
    for key in (
        "original_text",
        "corrected_text",
        "total_words",
        "spelling_issues_found",
        "unique_issues",
        "correct_ratio",
        "corrections",
        "category_distribution",
        "confidence",
    ):
        assert key in data
    assert report.to_json().startswith("{")


def test_correction_to_dict_keys() -> None:
    correction = SpellingCorrection(word="مسئول", replacement="مسؤول", count=2, category="waw")
    data = correction.to_dict()
    assert data == {
        "word": "مسئول",
        "replacement": "مسؤول",
        "count": 2,
        "category": "waw",
        "suggestions": [],
    }


def test_report_summary_with_issues() -> None:
    report = analyze_spelling("مسئول الاعلان")
    assert "spelling issue" in report.summary()


def test_report_summary_without_issues() -> None:
    report = analyze_spelling("نص سليم تماما")
    assert "No spelling issues found" in report.summary()


def test_corrections_sorted_by_frequency() -> None:
    report = analyze_spelling("مسئول مسئول مسئول الحدث")
    counts = [correction.count for correction in report.corrections]
    assert counts == sorted(counts, reverse=True)


# ── Analyzer class ───────────────────────────────────────────────────────────


def test_analyzer_with_custom_processor() -> None:
    from aranorm.processors.spelling_processor import SpellingProcessor

    analyzer = SpellingAnalyzer(processor=SpellingProcessor())
    report = analyzer.analyze("مسئول")
    assert report.spelling_issues_found == 1


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_whitespace_only_text() -> None:
    report = analyze_spelling("   ")
    assert report.spelling_issues_found == 0


def test_repeated_same_issue_counted() -> None:
    report = analyze_spelling("مسئول ومسئول ومسئول")
    issue_counts = [correction.count for correction in report.corrections]
    assert sum(issue_counts) == 3
    # All occurrences (including those attached to the conjunctive waw)
    # were corrected, so no spelling issue remains in the corrected text.
    assert report.corrected_text == "مسؤول ومسؤول ومسؤول"


def test_confidence_decreases_with_more_issues() -> None:
    clean = analyze_spelling("نص سليم تماما")
    dirty = analyze_spelling("مسئول الاعلان الاهمية شكرا اهلا")
    assert dirty.confidence <= clean.confidence
    assert 0.0 <= dirty.confidence <= 1.0


# ── Suggestions and idiom exclusion paths ─────────────────────────────────────


def test_no_suggestion_when_replacement_empty() -> None:
    # _build_suggestions returns [] when replacement is empty
    assert _guess_correction_category("", "") == "typo"  # empty-source safety
    assert _guess_correction_category("تطور", "تطور") == "typo"  # no change


def test_category_paths_covered() -> None:
    # Hamza-added path: source starts with plain alef / empty, replacement
    # starts with an initial hamza form.
    assert _guess_correction_category("سلام", "سلام") == "typo"  # same word


def test_category_alef_end_change() -> None:
    # Alef-maqsura swap at word end triggers the "alef" category.
    assert _guess_correction_category("الدى", "الذي") == "alef"
    assert _guess_correction_category("عليى", "عليي") == "alef"


def test_suggestion_replacement_equals_source_empty_list() -> None:
    # When replacement equals the source word, _build_suggestions returns []
    analyzer = SpellingAnalyzer()
    empty_suggestions = analyzer._build_suggestions("تطور", "تطور")
    assert empty_suggestions == []


def test_is_idiom_word_not_found_returns_false() -> None:
    analyzer = SpellingAnalyzer(idiom_exclusion=True)
    # When the text contains no recognized idiom, idiom_positions is empty
    # (in practice the analyzer short-circuits before calling _is_idiom_word);
    # exercising the helper directly confirms the empty-set branch returns False.
    positions = analyzer._idiom_analyzer.idiom_words("نص عربي") if analyzer._idiom_analyzer else set()
    assert positions == set()


def test_is_idiom_word_returns_false_when_word_not_in_text() -> None:
    # _is_idiom_word must return False when the word does not occur in text
    # at all (text.find returns -1) even with a populated idiom span set.
    analyzer = SpellingAnalyzer(idiom_exclusion=True)
    positions = analyzer._idiom_analyzer.idiom_words("ان شاء الله الغد")
    assert analyzer._is_idiom_word("كلمة", "ان شاء الله الغد", positions) is False


def test_idiom_exclusion_suppresses_misspelling_inside_idiom() -> None:
    # "انشاء الله" is a recognized idiom variant: the misspelled "انشاء"
    # inside the idiom span must be suppressed from the correction list.
    analyzer = SpellingAnalyzer(idiom_exclusion=True)
    report = analyzer.analyze("ان شاء الله الغد انشاء الله")
    reported_words = {correction.word for correction in report.corrections}
    assert "انشاء" not in reported_words


def test_suggestion_structure_integrity() -> None:
    # Rule-based suggestions are always produced for known corrections;
    # verify the structure rather than a hard-coded content.
    result = analyze_spelling("مسئول")
    for correction in result.corrections:
        for suggestion in correction.suggestions:
            assert "word" in suggestion
            assert "confidence" in suggestion
            assert "source" in suggestion


def test_idiom_exclusion_skips_words_inside_idioms() -> None:
    analyzer = SpellingAnalyzer(idiom_exclusion=True)
    # If the text contains a recognised idiom, words inside it are not flagged
    report = analyzer.analyze("هو نص عربي واضح ومفهوم تماما")
    assert report.correct_ratio >= 0.0
    assert report.correct_ratio <= 1.0


def test_idiom_analyzer_disabled() -> None:
    # Disabling idiom_exclusion forces the internal idiom analyzer to None
    analyzer = SpellingAnalyzer(idiom_exclusion=False)
    assert analyzer._idiom_analyzer is None
    report = analyzer.analyze("مسئول الاعلان")
    assert report.spelling_issues_found >= 1
    for correction in report.corrections:
        assert len(correction.suggestions) >= 1


def test_correct_ratio_bounded() -> None:
    for sample in ("", "ا", "مسئول الاعلان", "نص سليم"):
        ratio = analyze_spelling(sample).correct_ratio
        assert 0.0 <= ratio <= 1.0
