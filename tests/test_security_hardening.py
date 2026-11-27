"""Security and resource-boundary regression tests."""

import asyncio
import time

import pytest

from aranorm import ArabicNormalizationPipeline, PipelineConfig, ResourceLimits
from aranorm.exceptions import InvalidTextError
from aranorm.utils.patterns import (
    EMAIL_PATTERN,
    HASHTAG_PATTERN,
    HTML_PATTERN,
    MENTION_PATTERN,
    URL_PATTERN,
)


def _limited_pipeline() -> ArabicNormalizationPipeline:
    return ArabicNormalizationPipeline(
        PipelineConfig(
            resource_limits=ResourceLimits(
                max_text_length=32,
                max_batch_size=2,
                max_workers=2,
            )
        )
    )


def test_resource_limits_round_trip_and_unknown_fields_are_strict() -> None:
    limits = ResourceLimits(max_text_length=128, max_batch_size=4, max_workers=3, reject_null_bytes=False)
    restored = ResourceLimits.from_dict(limits.to_dict())

    assert restored == limits
    assert PipelineConfig.from_dict({"resource_limits": limits.to_dict()}).resource_limits == limits
    with pytest.raises(ValueError, match="Unknown ResourceLimits"):
        ResourceLimits.from_dict({"max_workers": 2, "unexpected": True})


@pytest.mark.parametrize(
    "limits",
    [
        {"max_text_length": 0},
        {"max_batch_size": 0},
        {"max_workers": 0},
        {"max_workers": True},
        {"reject_null_bytes": "yes"},
    ],
)
def test_resource_limits_reject_invalid_values(limits: dict) -> None:
    with pytest.raises(ValueError):
        ResourceLimits(**limits)


def test_pipeline_rejects_oversized_and_null_byte_inputs() -> None:
    pipeline = _limited_pipeline()

    with pytest.raises(InvalidTextError, match="exceeds maximum"):
        pipeline.process("أ" * 33)
    with pytest.raises(InvalidTextError, match="null byte"):
        pipeline.process("نص\x00غير صالح")


def test_pipeline_can_explicitly_allow_null_bytes_when_trusted() -> None:
    pipeline = ArabicNormalizationPipeline(
        PipelineConfig(resource_limits=ResourceLimits(max_text_length=64, reject_null_bytes=False))
    )

    result = pipeline.process("نص\x00")

    assert "\x00" in result.original_text


def test_pipeline_rejects_batch_and_worker_limits_before_executor_creation() -> None:
    pipeline = _limited_pipeline()

    with pytest.raises(ValueError, match="batch_size cannot exceed"):
        pipeline.process_batch(["أ"], batch_size=3)
    with pytest.raises(ValueError, match="n_workers cannot exceed"):
        list(pipeline.process_iter(["أ"], batch_size=1, n_workers=3))


def test_async_pipeline_enforces_worker_and_batch_limits() -> None:
    pipeline = _limited_pipeline()

    async def exercise() -> None:
        with pytest.raises(ValueError, match="n_workers cannot exceed"):
            await pipeline.process_batch_async(["أ"], n_workers=3)
        with pytest.raises(ValueError, match="async batch cannot exceed"):
            await pipeline.process_batch_async(["أ", "ب", "ت"], n_workers=1, batch_size=2)

    asyncio.run(exercise())


def test_unicode_edge_cases_are_processed_without_corruption() -> None:
    pipeline = _limited_pipeline()
    text = "السَّلَامُ\u200dعليكم — مرحبًا 👋"

    result = pipeline.process(text)

    assert result.original_text == text
    assert isinstance(result.normalized_text, str)


def test_security_sensitive_regexes_finish_on_adversarial_inputs() -> None:
    adversarial = ("<" * 20_000) + ("@" * 20_000) + ("#" * 20_000) + ("a" * 20_000)
    patterns = [URL_PATTERN, EMAIL_PATTERN, MENTION_PATTERN, HASHTAG_PATTERN, HTML_PATTERN]

    started = time.perf_counter()
    for pattern in patterns:
        pattern.sub("", adversarial)
    elapsed = time.perf_counter() - started

    # These patterns are linear/simple substitutions; keep a generous CI bound.
    assert elapsed < 2.0
