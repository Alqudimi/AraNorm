"""Defensive serialization tests for NormalizationResult."""

from aranorm import ArabicNormalizationPipeline, NormalizationResult, StopWordsConfig


def test_result_to_dict_returns_defensive_nested_values() -> None:
    result = ArabicNormalizationPipeline().process("شلونك وايد زين")
    payload = result.to_dict()

    payload["processing_metadata"]["injected"] = True
    payload["applied_steps"].append("injected")

    assert "injected" not in result.processing_metadata
    assert "injected" not in result.applied_steps


def test_result_from_dict_does_not_alias_input_payload() -> None:
    payload = {
        "original_text": "أحمد",
        "normalized_text": "احمد",
        "processing_metadata": {"source": "test"},
        "applied_steps": ["normalizer"],
    }

    result = NormalizationResult.from_dict(payload)
    payload["processing_metadata"]["source"] = "changed"
    payload["applied_steps"].append("changed")

    assert result.processing_metadata == {"source": "test"}
    assert result.applied_steps == ["normalizer"]


def test_result_round_trip_preserves_stop_word_collections() -> None:
    result = ArabicNormalizationPipeline.from_preset(
        "social_media",
        stop_words_config=StopWordsConfig.count_only(),
    ).process("هذا هو اختبار")

    restored = NormalizationResult.from_dict(result.to_dict())

    assert restored.original_text == result.original_text
    assert restored.normalized_text == result.normalized_text
    assert restored.stop_words_found == result.stop_words_found
