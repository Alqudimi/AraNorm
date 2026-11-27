"""Round 14 F4 — ``ArabicNormalizationPipeline.process_long_text`` tests.

Covers chunking-based normalization, merging of dialect/stop-words/time
fields across chunks, and empty-input behaviour.
"""

from __future__ import annotations

from aranorm.core.config import PipelineConfig, StopWordsConfig
from aranorm.core.pipeline import ArabicNormalizationPipeline


class TestProcessLongText:
    """Chunking, merging, and edge cases."""

    def test_long_text_is_chunked_and_normalized(self):
        pipeline = ArabicNormalizationPipeline()
        long_text = "مرحبا بالعالم. " * 200
        result = pipeline.process_long_text(long_text)
        assert result.original_text == long_text
        assert len(result.normalized_text) > 1000
        assert result.dialect == "MSA"

    def test_small_chunk_budget_produces_many_chunks(self):
        pipeline = ArabicNormalizationPipeline()
        result = pipeline.process_long_text("مرحبا بالعالم. " * 40, max_chunk_tokens=16)
        assert len(result.normalized_text) > 100

    def test_empty_text_delegates_to_process(self):
        pipeline = ArabicNormalizationPipeline()
        result = pipeline.process_long_text("")
        assert result.normalized_text == ""

    def test_time_accumulates_across_chunks(self):
        pipeline = ArabicNormalizationPipeline()
        result = pipeline.process_long_text("مرحبا بالعالم. " * 100, max_chunk_tokens=64)
        assert result.processing_time_ms is not None
        assert result.processing_time_ms > 0

    def test_steps_union_across_chunks(self):
        pipeline = ArabicNormalizationPipeline()
        result = pipeline.process_long_text("مرحبا بالعالم. " * 40, max_chunk_tokens=32)
        assert "remove_urls" in result.applied_steps
        assert "normalize_whitespace" in result.applied_steps
        # Union must not duplicate steps.
        assert len(result.applied_steps) == len(set(result.applied_steps))

    def test_dialect_highest_confidence_wins(self):
        pipeline = ArabicNormalizationPipeline()
        result = pipeline.process_long_text("مرحبا بالعالم. " * 40, max_chunk_tokens=32)
        assert result.dialect is not None
        assert (result.dialect_confidence or 0) > 0

    def test_stop_words_aggregation(self):
        config = PipelineConfig(stop_words_config=StopWordsConfig(mode="count"))
        pipeline = ArabicNormalizationPipeline(config)
        text = "في البيت الكبير، هناك كتاب على الطاولة. " * 30
        result = pipeline.process_long_text(text, max_chunk_tokens=64)
        assert result.stop_words_stats is not None
        assert result.stop_words_stats["count"] >= 0
        assert result.stop_words_stats["chunk_count"] >= 2
        if result.stop_words_found:
            assert isinstance(result.stop_words_found, set)

    def test_dialect_normalizer_long_text(self):
        config = PipelineConfig(preset="deep", dialect_target="msa")
        pipeline = ArabicNormalizationPipeline(config)
        result = pipeline.process_long_text("شلونك حبيبي؟ " * 60)
        assert result.msa_text is not None
        assert len(result.msa_text) > 0
