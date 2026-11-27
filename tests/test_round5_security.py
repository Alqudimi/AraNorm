"""Security and resource-boundary contracts for Round 5."""

from __future__ import annotations

import json
import re

import pytest

from aranorm import ArabicNormalizationPipeline, PipelineConfig, ResourceLimits
from aranorm.exceptions import InvalidTextError


def test_hostile_source_text_is_not_present_in_operational_telemetry() -> None:
    """Metrics and operational descriptions contain counters/config, not text."""
    hostile_text = "سرّي </script> '\" & __aranorm_secret_7f2c__"
    pipeline = ArabicNormalizationPipeline.from_preset("standard")

    result = pipeline.process(hostile_text)
    telemetry = json.dumps(
        {
            "metrics": pipeline.metrics_snapshot().to_dict(include_schema=True),
            "description": pipeline.describe_operational(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    assert result.original_text == hostile_text
    assert hostile_text not in telemetry
    assert "__aranorm_secret_7f2c__" not in telemetry
    assert re.fullmatch(r"[0-9a-f]{64}", pipeline.configuration_fingerprint())


def test_fingerprint_is_independent_of_processed_source_text() -> None:
    """Configuration fingerprints do not become content identifiers."""
    first = ArabicNormalizationPipeline.from_preset("standard")
    second = ArabicNormalizationPipeline.from_preset("standard")

    first.process("نص أول مع token-A")
    second.process("نص ثانٍ مع token-B")

    assert first.configuration_fingerprint() == second.configuration_fingerprint()
    assert first.describe_operational() == second.describe_operational()


def test_resource_limits_reject_oversized_and_null_byte_text() -> None:
    config = PipelineConfig(
        resource_limits=ResourceLimits(
            max_text_length=3,
            max_batch_size=2,
            max_workers=1,
            reject_null_bytes=True,
        )
    )
    pipeline = ArabicNormalizationPipeline(config)

    with pytest.raises(InvalidTextError, match="exceeds maximum allowed length 3"):
        pipeline.process("أربعة")
    with pytest.raises(InvalidTextError, match="contains a null byte"):
        pipeline.process("أ\x00ب")


def test_batch_and_worker_limits_are_enforced_before_work() -> None:
    config = PipelineConfig(resource_limits=ResourceLimits(max_batch_size=2, max_workers=1))
    pipeline = ArabicNormalizationPipeline(config)

    with pytest.raises(ValueError, match="batch_size cannot exceed configured maximum 2"):
        pipeline.process_batch(["أ"], batch_size=3)
    with pytest.raises(ValueError, match="n_workers cannot exceed configured maximum 1"):
        pipeline.process_batch(["أ"], batch_size=1, n_workers=2)
    assert len(pipeline.process_batch(["أ", "ب"], batch_size=2, n_workers=1)) == 2


def test_async_batch_limit_rejects_materialized_overflow() -> None:
    """Async parity retains the same maximum batch boundary."""
    import asyncio

    config = PipelineConfig(resource_limits=ResourceLimits(max_batch_size=1, max_workers=1))
    pipeline = ArabicNormalizationPipeline(config)

    async def run() -> None:
        with pytest.raises(ValueError, match="async batch cannot exceed configured maximum 1 items"):
            await pipeline.process_batch_async(["أ", "ب"], batch_size=1, n_workers=1)

    asyncio.run(run())


def test_metrics_repr_and_snapshot_do_not_capture_source_text() -> None:
    secret = "__metrics_secret_not_allowed__"
    pipeline = ArabicNormalizationPipeline.from_preset("light")
    pipeline.process(secret)

    snapshot = pipeline.metrics_snapshot()
    rendered = repr(pipeline.metrics) + json.dumps(snapshot.to_dict(include_schema=True), sort_keys=True)

    assert secret not in rendered
    assert snapshot.total_items == 1
    assert snapshot.succeeded == 1
