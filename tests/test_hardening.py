"""Regression tests for production-hardening changes."""

import asyncio

import pytest

from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.analysis.readability import ArabicReadabilityAnalyzer
from aranorm.stages.dialect_id import DialectIdentifier


def test_config_from_dict_does_not_mutate_input() -> None:
    payload = {
        "preset": "deep",
        "clean_emojis": True,
        "stop_words_config": {"mode": "count", "scope": "universal"},
    }
    original = {
        "preset": payload["preset"],
        "clean_emojis": payload["clean_emojis"],
        "stop_words_config": dict(payload["stop_words_config"]),
    }

    config = PipelineConfig.from_dict(payload)

    assert payload == original
    assert config.preset.value == "deep"
    assert config.stop_words_config is not None
    assert config.stop_words_config.mode == "count"


def test_config_from_dict_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="Unknown PipelineConfig field"):
        PipelineConfig.from_dict({"normalise_alef": True})


def test_result_round_trip_preserves_processing_metadata() -> None:
    result = ArabicNormalizationPipeline().process("مرحبا بالعالم")
    restored = type(result).from_dict(result.to_dict())

    assert restored.processing_metadata == result.processing_metadata
    assert restored.normalized_text == result.normalized_text
    assert restored.applied_steps == result.applied_steps


def test_readability_reports_long_word_ratio() -> None:
    result = ArabicReadabilityAnalyzer().analyze("هذا نص عربي طويل للغاية للاختبار")

    assert 0.0 <= result.long_word_ratio <= 1.0
    assert result.to_dict()["long_word_ratio"] == result.long_word_ratio


def test_dialect_markers_do_not_match_inside_longer_words() -> None:
    identifier = DialectIdentifier()

    result = identifier.identify("شلونك")

    assert result.dialect == "GLF"
    assert result.confidence_score >= 0.55


def test_async_batch_rejects_invalid_worker_count() -> None:
    async def run() -> None:
        with pytest.raises(ValueError, match="n_workers must be positive"):
            await ArabicNormalizationPipeline().process_batch_async(["نص"], n_workers=0)

    asyncio.run(run())


def test_async_batch_preserves_input_order() -> None:
    async def run() -> None:
        results = await ArabicNormalizationPipeline().process_batch_async(["أول", "ثان", "ثالث"], n_workers=2)
        assert [item.original_text for item in results] == ["أول", "ثان", "ثالث"]

    asyncio.run(run())
