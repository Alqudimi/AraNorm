"""Integration tests for the full ArabicNormalizationPipeline."""

import time

import pytest

from aranorm import ArabicNormalizationPipeline, NormalizationResult, PipelineConfig
from aranorm.exceptions import InvalidTextError
from tests.fixtures.sample_texts import BATCH_1000, EDGE_CASES

# ────────────────────────────────────────────────────────────────────────────
# Basic pipeline behavior
# ────────────────────────────────────────────────────────────────────────────


def test_pipeline_returns_normalization_result():
    pipeline = ArabicNormalizationPipeline()
    result = pipeline.process("أحمد إبراهيم")
    assert isinstance(result, NormalizationResult)


def test_pipeline_preserves_original_text():
    original = "شلونك حبيبي؟ https://example.com 😊"
    pipeline = ArabicNormalizationPipeline(PipelineConfig(clean_urls=True))
    result = pipeline.process(original)
    assert result.original_text == original


def test_pipeline_normalizes_alef_by_default():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))
    result = pipeline.process("أحمد إبراهيم آمن")
    assert "أ" not in result.normalized_text
    assert "إ" not in result.normalized_text


def test_pipeline_removes_diacritics_by_default():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))
    result = pipeline.process("مَرْحَبًا بِكُمْ")
    vowels = set("ًٌٍَُِّْ")
    assert not any(c in vowels for c in result.normalized_text)


def test_pipeline_returns_result_and_metadata():
    pipeline = ArabicNormalizationPipeline(
        PipelineConfig(
            clean_urls=True,
            clean_emojis=True,
            dialect_target="coda",
            normalize_repeated_chars=True,
        )
    )
    result = pipeline.process("شلونك ياااا؟ https://example.com 😊")
    assert result.original_text.startswith("شلونك")
    assert "https://" not in result.normalized_text
    assert result.coda_text is not None
    assert result.dialect == "GLF"
    assert "remove_urls" in result.applied_steps


# ────────────────────────────────────────────────────────────────────────────
# Preset tests
# ────────────────────────────────────────────────────────────────────────────


def test_light_preset_is_dependency_free_and_fast():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    results = pipeline.process_batch(["أحمد", "إبراهيم", "آمن"], batch_size=2)
    assert [item.normalized_text for item in results] == ["احمد", "ابراهيم", "امن"]


def test_standard_preset_strips_tatweel():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))
    result = pipeline.process("مـرحـبـا بـكـم")
    assert "ـ" not in result.normalized_text


def test_deep_preset_normalizes_repeated_chars():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="deep"))
    result = pipeline.process("يااااا سلام عليكم")
    assert "ياا" in result.normalized_text or result.normalized_text.count("ا") <= 3


def test_social_media_preset_removes_urls_and_emojis():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="social_media"))
    result = pipeline.process("مرحبا 😊 https://t.co/abc #موضوع")
    assert "https://" not in result.normalized_text
    assert "😊" not in result.normalized_text


def test_from_preset_classmethod():
    config = PipelineConfig.from_preset("light", normalize_alef=True)
    pipeline = ArabicNormalizationPipeline(config)
    result = pipeline.process("إبراهيم")
    assert result.normalized_text == "ابراهيم"


# ────────────────────────────────────────────────────────────────────────────
# Dialect targets
# ────────────────────────────────────────────────────────────────────────────


def test_pipeline_coda_target_populates_coda_text():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(dialect_target="coda"))
    result = pipeline.process("هاذا الاشياء انشاءالله")
    assert result.coda_text is not None
    assert "هذا" in result.coda_text
    assert result.msa_text is None


def test_pipeline_msa_target_populates_msa_text():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(dialect_target="msa"))
    result = pipeline.process("شلون الحين أبغى شيء")
    assert result.msa_text is not None
    assert "كيف" in result.msa_text
    assert result.coda_text is None


def test_pipeline_no_dialect_target_leaves_both_none():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(dialect_target="none"))
    result = pipeline.process("مرحبا")
    assert result.coda_text is None
    assert result.msa_text is None


# ────────────────────────────────────────────────────────────────────────────
# is_msa / dialect properties
# ────────────────────────────────────────────────────────────────────────────


def test_pipeline_detects_msa_flag():
    pipeline = ArabicNormalizationPipeline()
    result = pipeline.process("أعلن الرئيس عن خطة لتطوير القطاع الاقتصادي وبالتالي")
    assert result.is_msa is True


def test_pipeline_detects_gulf_dialect():
    pipeline = ArabicNormalizationPipeline()
    result = pipeline.process("شلونك وايد زين الحين")
    assert result.dialect == "GLF"
    assert result.is_msa is False


# ────────────────────────────────────────────────────────────────────────────
# Batch processing
# ────────────────────────────────────────────────────────────────────────────


def test_batch_preserves_order_with_workers():
    pipeline = ArabicNormalizationPipeline()
    results = pipeline.process_batch(["أ", "ب", "ج"], n_workers=2)
    assert [item.original_text for item in results] == ["أ", "ب", "ج"]


def test_batch_preserves_order_single_worker():
    pipeline = ArabicNormalizationPipeline()
    texts = ["نص {}".format(i) for i in range(10)]
    results = pipeline.process_batch(texts, n_workers=1)
    assert [r.original_text for r in results] == texts


def test_invalid_batch_options_fail_early():
    pipeline = ArabicNormalizationPipeline()
    with pytest.raises(ValueError):
        pipeline.process_batch(["نص"], batch_size=0)
    with pytest.raises(ValueError):
        pipeline.process_batch(["نص"], n_workers=0)


def test_batch_on_empty_list():
    pipeline = ArabicNormalizationPipeline()
    assert pipeline.process_batch([]) == []


# ────────────────────────────────────────────────────────────────────────────
# Error handling
# ────────────────────────────────────────────────────────────────────────────


def test_invalid_pipeline_input_raises_domain_error():
    pipeline = ArabicNormalizationPipeline()
    with pytest.raises(InvalidTextError):
        pipeline.process(123)


def test_pipeline_handles_empty_string():
    pipeline = ArabicNormalizationPipeline()
    result = pipeline.process("")
    assert result.normalized_text == ""


@pytest.mark.parametrize("text", EDGE_CASES)
def test_pipeline_handles_edge_cases(text):
    pipeline = ArabicNormalizationPipeline()
    result = pipeline.process(text)
    assert isinstance(result.normalized_text, str)


# ────────────────────────────────────────────────────────────────────────────
# Custom builder
# ────────────────────────────────────────────────────────────────────────────


def test_custom_builder_creates_target_pipeline():
    pipeline = (
        ArabicNormalizationPipeline.builder()
        .add_cleaner(remove_urls=True)
        .add_normalizer(normalize_alef=True, normalize_hamza=True)
        .add_dialect_processor(normalize_to="msa")
        .build()
    )
    result = pipeline.process("شو أخبارك؟")
    assert result.msa_text == "ماذا اخبارك?"


def test_custom_builder_with_emojis():
    pipeline = (
        ArabicNormalizationPipeline.builder()
        .add_cleaner(remove_emojis=True, remove_urls=True)
        .add_normalizer(normalize_alef=True, normalize_diacritics=True)
        .build()
    )
    result = pipeline.process("مرحبا 😊 أحمد https://x.com")
    assert "😊" not in result.normalized_text
    assert "https" not in result.normalized_text


def test_builder_supports_dialect_list():
    pipeline = (
        ArabicNormalizationPipeline.builder()
        .add_dialect_processor(
            normalize_to="none",
            supported_dialects=["EGY", "GLF"],
        )
        .build()
    )
    result = pipeline.process("عايز أروح")
    assert result.dialect in ("EGY", "MSA", "UNK")


# ────────────────────────────────────────────────────────────────────────────
# NormalizationResult properties
# ────────────────────────────────────────────────────────────────────────────


def test_result_dialect_label_alias():
    pipeline = ArabicNormalizationPipeline()
    result = pipeline.process("شلونك وايد زين")
    assert result.dialect_label == result.dialect


def test_result_confidence_score_alias():
    pipeline = ArabicNormalizationPipeline()
    result = pipeline.process("شلونك وايد زين")
    assert result.confidence_score == result.dialect_confidence


# ────────────────────────────────────────────────────────────────────────────
# Performance smoke test (light preset)
# ────────────────────────────────────────────────────────────────────────────


def test_light_preset_processes_1000_texts_under_10s():
    """Smoke test: light preset should handle 1 000 texts well under 10 s."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    start = time.perf_counter()
    pipeline.process_batch(BATCH_1000)
    elapsed = time.perf_counter() - start
    assert elapsed < 10.0, f"Too slow: {elapsed:.2f}s for 1000 texts"
