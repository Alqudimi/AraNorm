import asyncio
from unittest.mock import patch

import pytest

from aranorm import ArabicNormalizationPipeline, BatchRetryPolicy, BatchProcessingPolicy
from aranorm.exceptions import ConfigurationError


def _pipeline() -> ArabicNormalizationPipeline:
    return ArabicNormalizationPipeline()


def test_retry_policy_round_trip_and_defensive_validation() -> None:
    policy = BatchRetryPolicy(max_retries=2, batch_size=4, n_workers=1)
    payload = policy.to_dict()
    assert payload == {"max_retries": 2, "batch_size": 4, "n_workers": 1}
    payload["max_retries"] = 9
    assert policy.max_retries == 2
    assert BatchRetryPolicy.from_dict({"max_retries": 2, "batch_size": 4, "n_workers": 1}) == policy

    with pytest.raises(ValueError, match="Unknown BatchRetryPolicy"):
        BatchRetryPolicy.from_dict({"unknown": 1})
    with pytest.raises(TypeError, match="max_retries must be an integer"):
        BatchRetryPolicy(max_retries=True)
    with pytest.raises(ValueError, match="between 0 and 10"):
        BatchRetryPolicy(max_retries=11)
    with pytest.raises(ValueError, match="batch_size must be positive"):
        BatchRetryPolicy(batch_size=0)
    with pytest.raises(TypeError, match="retry_policy must be a dictionary"):
        BatchRetryPolicy.from_dict([])  # type: ignore[arg-type]


def test_sync_retry_policy_recovers_transient_failure_and_preserves_order() -> None:
    pipeline = _pipeline()
    calls = {"flaky": 0}
    original = pipeline.process

    def flaky(text: str):
        if text == "flaky":
            calls["flaky"] += 1
            if calls["flaky"] == 1:
                raise RuntimeError("transient")
        return original(text)

    with patch.object(pipeline, "process", side_effect=flaky):
        report = pipeline.process_batch_retry(
            ["ألف", "flaky", "باء"],
            retry_policy=BatchRetryPolicy(max_retries=2, batch_size=3, n_workers=1),
        )

    assert report.failed_indices == []
    assert [item.original_text for item in report.results] == ["ألف", "flaky", "باء"]
    assert report.retry_report["recovered_count"] == 1
    assert report.retry_report["retry_attempts"] == 0


def test_sync_retry_zero_records_final_failure_without_leaking_text() -> None:
    pipeline = _pipeline()

    def always_fail(text: str):
        if text == "سر":
            raise RuntimeError("secret failure")
        return pipeline._process_unmeasured(text)

    with patch.object(pipeline, "process", side_effect=always_fail):
        report = pipeline.process_batch_retry(["سليم", "سر"], max_retries=0)

    assert report.failed_indices == [1]
    assert report.results[0].original_text == "سليم"
    assert "secret failure" not in str(report.to_dict())
    assert report.retry_report["retry_attempts"] == 0


def test_retry_rejects_fail_fast_policy() -> None:
    with pytest.raises(ConfigurationError, match="requires BatchProcessingPolicy"):
        _pipeline().process_batch_retry(["نص"], policy=BatchProcessingPolicy(mode="fail_fast"))


def test_async_retry_matches_sync_contract() -> None:
    pipeline = _pipeline()
    calls = {"flaky": 0}
    original = pipeline.process

    def flaky(text: str):
        if text == "flaky":
            calls["flaky"] += 1
            if calls["flaky"] == 1:
                raise RuntimeError("transient")
        return original(text)

    async def run():
        with patch.object(pipeline, "process", side_effect=flaky):
            return await pipeline.process_batch_retry_async(
                ["ألف", "flaky", "باء"],
                retry_policy=BatchRetryPolicy(max_retries=2, batch_size=3, n_workers=1),
            )

    report = asyncio.run(run())
    assert report.failed_indices == []
    assert [item.original_text for item in report.results] == ["ألف", "flaky", "باء"]
    assert report.retry_report["recovered_count"] == 1


def test_async_retry_empty_input_and_validation() -> None:
    async def run():
        return await _pipeline().process_batch_retry_async([], max_retries=0)

    report = asyncio.run(run())
    assert report.results == []
    assert report.retry_report["total_inputs"] == 0

    with pytest.raises(ValueError, match="between 0 and 10"):
        asyncio.run(_pipeline().process_batch_retry_async(["نص"], max_retries=11))
    with pytest.raises(TypeError, match="retry_policy must be a BatchRetryPolicy"):
        asyncio.run(_pipeline().process_batch_retry_async(["نص"], retry_policy={}))  # type: ignore[arg-type]
