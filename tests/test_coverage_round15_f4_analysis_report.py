"""Round 15 F4 — ``AnalysisReport`` diagnostic report tests."""

from __future__ import annotations

from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.core.pipeline import AnalysisReport, NormalizationResult


def make_result(
    original: str = "شلونك حبيبي؟",
    normalized: str = "شلونك حبيبي؟",
    dialect: str = "GLF",
    confidence: float = 0.9,
    steps=None,
) -> NormalizationResult:
    return NormalizationResult(
        original_text=original,
        normalized_text=normalized,
        dialect=dialect,
        dialect_confidence=confidence,
        applied_steps=steps if steps is not None else ["cleaner", "normalizer", "dialect"],
    )


def test_analysis_report_from_result():
    result = make_result()
    report = AnalysisReport.from_result(result)
    assert report.input_length == len(result.original_text)
    assert report.output_length == len(result.normalized_text)
    assert report.change_ratio == 0.0
    assert report.confidence_band == "high"
    assert len(report.step_summary) == 3
    assert report.diff_changed_positions == 0


def test_analysis_report_with_changes():
    result = make_result(original="شلونك!!!", normalized="شلونك!")
    report = AnalysisReport.from_result(result)
    assert report.diff_changed_positions == 2
    assert report.change_ratio > 0.0
    assert 0.0 < report.change_ratio <= 1.0


def test_analysis_report_truncation_changes():
    """Normalized text longer than original still counts extra chars."""
    result = make_result(original="أهلا", normalized="أهلا وسهلا")
    report = AnalysisReport.from_result(result)
    assert report.diff_changed_positions == len(" وسهلا")


def test_analysis_report_empty_original():
    result = make_result(original="", normalized="")
    report = AnalysisReport.from_result(result)
    assert report.change_ratio == 0.0
    assert report.confidence_band == "high"


def test_analysis_report_no_steps():
    result = NormalizationResult(original_text="نص", normalized_text="نص")
    report = AnalysisReport.from_result(result)
    assert report.step_summary == {}
    assert report.confidence_band == "low"


def test_analysis_report_confidence_bands():
    assert AnalysisReport.from_result(make_result(confidence=0.8)).confidence_band == "high"
    assert AnalysisReport.from_result(make_result(confidence=0.5)).confidence_band == "medium"
    assert AnalysisReport.from_result(make_result(confidence=0.49)).confidence_band == "low"
    assert AnalysisReport.from_result(make_result(confidence=None)).confidence_band == "low"


def test_analysis_report_step_summary_counts():
    result = make_result(steps=["cleaner", "cleaner", "normalizer"])
    report = AnalysisReport.from_result(result)
    assert report.step_summary["cleaner"] == 2
    assert report.step_summary["normalizer"] == 1


def test_analysis_report_to_dict():
    report = AnalysisReport.from_result(make_result())
    data = report.to_dict()
    assert set(data) == {
        "input_length",
        "output_length",
        "change_ratio",
        "confidence_band",
        "confidence",
        "dialect",
        "step_summary",
        "diff_changed_positions",
        "processing_time_ms",
    }
    assert data["dialect"] == "GLF"
    assert data["processing_time_ms"] is None


def test_analysis_report_through_pipeline():
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    result = pipeline.process("شلونك؟")
    report = AnalysisReport.from_result(result)
    assert report.result is result
    assert report.input_length == len("شلونك؟")
    assert 0.0 <= report.change_ratio <= 1.0
