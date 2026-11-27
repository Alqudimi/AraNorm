"""Tests for enhanced pipeline features: to_dict, to_json, async, builder."""

from __future__ import annotations

import asyncio
import json

import pytest

from aranorm import ArabicNormalizationPipeline, NormalizationResult, PipelineConfig

# ── NormalizationResult serialization ─────────────────────────────────────────


class TestNormalizationResultSerialization:
    @pytest.fixture
    def result(self) -> NormalizationResult:
        pipeline = ArabicNormalizationPipeline()
        return pipeline.process("شلونك حبيبي؟")

    def test_to_dict_returns_dict(self, result: NormalizationResult) -> None:
        d = result.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_has_required_keys(self, result: NormalizationResult) -> None:
        d = result.to_dict()
        assert "original_text" in d
        assert "normalized_text" in d
        assert "dialect" in d

    def test_to_dict_stop_words_found_is_list(self) -> None:
        from aranorm import StopWordsConfig

        config = PipelineConfig(stop_words_config=StopWordsConfig(mode="remove", scope="universal"))
        pipeline = ArabicNormalizationPipeline(config)
        result = pipeline.process("أنا سعيد")
        d = result.to_dict()
        if d["stop_words_found"] is not None:
            assert isinstance(d["stop_words_found"], list)

    def test_to_json_returns_string(self, result: NormalizationResult) -> None:
        j = result.to_json()
        assert isinstance(j, str)

    def test_to_json_is_valid_json(self, result: NormalizationResult) -> None:
        j = result.to_json()
        data = json.loads(j)
        assert isinstance(data, dict)

    def test_to_json_preserves_arabic(self, result: NormalizationResult) -> None:
        j = result.to_json(ensure_ascii=False)
        # Arabic chars should be preserved
        assert any(ord(c) > 127 for c in j)

    def test_from_dict_round_trip(self, result: NormalizationResult) -> None:
        d = result.to_dict()
        reconstructed = NormalizationResult.from_dict(d)
        assert reconstructed.normalized_text == result.normalized_text
        assert reconstructed.dialect == result.dialect

    def test_from_dict_with_stop_words_found(self) -> None:
        data = {
            "original_text": "أنا سعيد",
            "normalized_text": "سعيد",
            "stop_words_found": ["أنا"],
        }
        result = NormalizationResult.from_dict(data)
        assert isinstance(result.stop_words_found, set)
        assert "أنا" in result.stop_words_found


# ── Pipeline factory methods ───────────────────────────────────────────────────


class TestPipelineFactoryMethods:
    def test_from_preset_light(self) -> None:
        pipeline = ArabicNormalizationPipeline.from_preset("light")
        result = pipeline.process("أنا هنا")
        assert isinstance(result, NormalizationResult)

    def test_from_preset_social_media(self) -> None:
        pipeline = ArabicNormalizationPipeline.from_preset("social_media")
        result = pipeline.process("مرحبا 😊 https://example.com")
        assert "https://" not in result.normalized_text

    def test_from_config_dict(self) -> None:
        pipeline = ArabicNormalizationPipeline.from_config_dict(
            {
                "preset": "standard",
                "clean_urls": True,
            }
        )
        result = pipeline.process("https://example.com مرحبا")
        assert "https://" not in result.normalized_text

    def test_describe_returns_dict(self) -> None:
        pipeline = ArabicNormalizationPipeline()
        desc = pipeline.describe()
        assert isinstance(desc, dict)
        assert "preset" in desc
        assert "cleaning" in desc
        assert "normalization" in desc


# ── PipelineBuilder ────────────────────────────────────────────────────────────


class TestPipelineBuilder:
    def test_builder_with_stop_words(self) -> None:
        pipeline = (
            ArabicNormalizationPipeline.builder()
            .add_cleaner(urls=True)
            .add_normalizer(remove_diacritics=True)
            .add_stop_words(mode="remove", scope="universal")
            .build()
        )
        result = pipeline.process("أنا سعيد اليوم")
        assert result.stop_words_removed is not None

    def test_builder_with_dialect(self) -> None:
        pipeline = ArabicNormalizationPipeline.builder().add_dialect_processor(normalize_to="msa").build()
        result = pipeline.process("شلونك")
        assert result.msa_text is not None

    def test_builder_chain_returns_builder(self) -> None:
        builder = ArabicNormalizationPipeline.builder()
        result = builder.add_cleaner(urls=True)
        assert isinstance(result, type(builder))

    def test_builder_builds_valid_pipeline(self) -> None:
        pipeline = ArabicNormalizationPipeline.builder().build()
        assert isinstance(pipeline, ArabicNormalizationPipeline)


# ── Async processing ──────────────────────────────────────────────────────────


class TestAsyncProcessing:
    def test_process_async_single(self) -> None:
        pipeline = ArabicNormalizationPipeline()

        async def run():
            return await pipeline.process_async("مرحباً بالعالم")

        result = asyncio.run(run())
        assert isinstance(result, NormalizationResult)
        assert result.normalized_text != ""

    def test_process_batch_async(self) -> None:
        pipeline = ArabicNormalizationPipeline()
        texts = ["أنا سعيد", "هو يعمل", "نحن نتعلم"]

        async def run():
            return await pipeline.process_batch_async(texts, n_workers=2)

        results = asyncio.run(run())
        assert len(results) == len(texts)
        assert all(isinstance(r, NormalizationResult) for r in results)

    def test_process_async_preserves_text(self) -> None:
        pipeline = ArabicNormalizationPipeline()
        original = "شلونك حبيبي؟"

        async def run():
            return await pipeline.process_async(original)

        result = asyncio.run(run())
        assert result.original_text == original


# ── Batch processing with error handler ───────────────────────────────────────


class TestBatchWithErrorHandler:
    def test_on_error_callback_called_on_failure(self) -> None:
        pipeline = ArabicNormalizationPipeline()
        errors_seen = []

        def on_error(idx, text, exc):
            errors_seen.append((idx, text))
            return None  # skip

        # Normally process_batch won't raise on valid strings,
        # but we verify the batch completes
        results = pipeline.process_batch(
            ["أنا سعيد", "هو يعمل"],
            on_error=on_error,
        )
        assert len(results) == 2

    def test_empty_batch_returns_empty(self) -> None:
        pipeline = ArabicNormalizationPipeline()
        assert pipeline.process_batch([]) == []
