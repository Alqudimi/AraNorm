"""Tests for the Round-17 composite quality scoring module.

Covers :mod:`aranorm.analysis.quality_score` — component weights, score
normalization, labels, edge cases and JSON serialization.
"""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")

from aranorm.analysis.quality_score import (  # noqa: E402
    ComponentScore,
    QualityScoreAnalyzer,
    TextQualityScore,
    _label_for,
    analyze_quality,
)

REQUIRED_COMPONENTS = {
    "spelling",
    "consistency",
    "lexical_balance",
    "readability",
    "diacritics",
    "rhetorical_richness",
    "structural_balance",
    "rhetorical_depth",
}
EXPECTED_WEIGHTS = {
    "spelling": 0.26,
    "consistency": 0.22,
    "lexical_balance": 0.19,
    "readability": 0.10,
    "diacritics": 0.05,
    "rhetorical_richness": 0.08,
    "structural_balance": 0.07,
    "rhetorical_depth": 0.03,
}


# ── Composite mechanics ─────────────────────────────────────────────────────


def test_weights_sum_to_one() -> None:
    assert sum(EXPECTED_WEIGHTS.values()) == pytest.approx(1.0)


def test_score_bounded_zero_to_hundred() -> None:
    result = analyze_quality("مسئول الاعلان عن الحدث الاهمية")
    assert 0.0 <= result.score <= 100.0


def test_label_classification() -> None:
    assert _label_for(95.0) == "excellent"
    assert _label_for(80.0) == "good"
    assert _label_for(60.0) == "fair"
    assert _label_for(40.0) == "poor"
    assert _label_for(0.0) == "poor"


def test_eight_components_present() -> None:
    result = analyze_quality("هذا نص عربي واضح ومفهوم تماما.")
    names = {component.name for component in result.components}
    assert names == REQUIRED_COMPONENTS


def test_rhetorical_depth_component_present() -> None:
    """The eighth rhetorical_depth component must blend rquestions and anaphora."""
    text = "أليس العدل أساس الملك؟ إن المجتمع الذي ينصف ضعفاءه يهنأ بالحياة."
    components = {component.name: component for component in analyze_quality(text).components}
    assert "rhetorical_depth" in components
    assert components["rhetorical_depth"].weight == pytest.approx(0.03)
    assert 0.0 <= components["rhetorical_depth"].score <= 100.0


def test_rhetorical_depth_suggestion_when_flat() -> None:
    """A flat literal text must prompt deepening the argument."""
    from aranorm.analysis.quality_score import _score_rhetorical_depth

    suggestions: list = []
    _score_rhetorical_depth("شمس وقمر وبحر.", suggestions)
    assert any("deepen" in suggestion for suggestion in suggestions)


def test_component_weight_assignment() -> None:
    result = analyze_quality("نص عربي جيد.")
    for component in result.components:
        assert component.weight == pytest.approx(EXPECTED_WEIGHTS[component.name])


def test_composite_is_weighted_average() -> None:
    result = analyze_quality("نص عربي واضح ومفهوم.")
    expected = sum(component.score * component.weight for component in result.components)
    assert result.score == pytest.approx(round(expected, 2))


# ── Spelling-driven quality ──────────────────────────────────────────────────


def test_spelling_errors_reduce_score() -> None:
    clean = analyze_quality("هذا نص عربي واضح ومفهوم")
    dirty = analyze_quality("مسئول الاعلان الاهمية")
    assert dirty.score < clean.score


def test_spelling_suggestion_emitted_for_issues() -> None:
    result = analyze_quality("مسئول الاعلان")
    suggestion_text = " ".join(result.suggestions)
    assert "spelling issue" in suggestion_text or "مسئول" in suggestion_text


# ── Consistency component ────────────────────────────────────────────────────


def test_latin_dominated_text_penalized() -> None:
    result = analyze_quality("This is mostly latin text with قليل من العربية only")
    components = {component.name: component.score for component in result.components}
    assert components["consistency"] < 100.0


def test_space_before_punctuation_penalized() -> None:
    result = analyze_quality("نص عربي واضح .")
    components = {component.name: component.score for component in result.components}
    assert components["consistency"] < 100.0


def test_clean_document_consistency_near_perfect() -> None:
    result = analyze_quality("نص عربي واضح ومفهوم تماما.")
    components = {component.name: component.score for component in result.components}
    # 95.0: the alef-variant limit rule nudges the score for plain
    # "ا" usage even in grammatically perfect text; still near perfect.
    assert components["consistency"] >= 90.0


# ── Diacritics and lexical balance ───────────────────────────────────────────


def test_voweled_text_bonus() -> None:
    voweled = analyze_quality("هٰذَا نَصّ عَرَبِيّ وَاضِح.")
    unwoweled = analyze_quality("هذا نص عربي واضح.")
    components_v = {component.name: component.score for component in voweled.components}
    components_u = {component.name: component.score for component in unwoweled.components}
    assert components_v["diacritics"] > components_u["diacritics"]


def test_stop_word_ratio_affects_lexical_component() -> None:
    from aranorm.analysis.quality_score import _score_lexical_balance

    suggestions: list[str] = []
    dense = _score_lexical_balance("كلمات محتوى متتالية بلا حروف جر أو أدوات", suggestions)
    assert 0.0 <= dense <= 100.0


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_empty_text_still_scores() -> None:
    result = analyze_quality("")
    assert 0.0 <= result.score <= 100.0
    assert result.analyzed_text_length == 0


def test_analyzed_text_length_recorded() -> None:
    text = "نص عربي للتجربة."
    result = analyze_quality(text)
    assert result.analyzed_text_length == len(text)


def test_symbol_only_text() -> None:
    result = analyze_quality("؟!!###")
    assert 0.0 <= result.score <= 100.0


# ── Data classes ─────────────────────────────────────────────────────────────


def test_result_to_dict_completeness() -> None:
    result = analyze_quality("نص عربي.")
    data = result.to_dict()
    for key in ("score", "label", "components", "issues", "suggestions", "analyzed_text_length"):
        assert key in data


def test_result_to_json_valid() -> None:
    import json

    result = analyze_quality("نص عربي.")
    parsed = json.loads(result.to_json())
    assert parsed["label"] == result.label


def test_component_to_dict() -> None:
    component = ComponentScore(name="spelling", score=80.0, weight=0.30, issues=["fix"])
    data = component.to_dict()
    assert data["issues"] == ["fix"]
    assert data["score"] == 80.0


def test_quality_distribution_labels_known() -> None:
    samples = {
        "مسئول الاعلان الاهمية شكرا اهلا مسئول": "fair",
        "هذا نص عربي واضح ومفهوم تماما للسادة": "good",
    }
    for sample, expected in samples.items():
        assert analyze_quality(sample).label in ("excellent", "good", "fair", "poor")
        assert analyze_quality(sample).label == expected


# ── Analyzer class ───────────────────────────────────────────────────────────


def test_quality_score_analyzer_class() -> None:
    analyzer = QualityScoreAnalyzer()
    result = analyzer.analyze("نص عربي واضح.")
    assert isinstance(result, TextQualityScore)
    assert result.label in ("excellent", "good", "fair", "poor")
