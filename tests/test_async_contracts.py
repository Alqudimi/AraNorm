"""Contract tests for asynchronous batch parity."""

from __future__ import annotations

import asyncio
from typing import List, Optional

import pytest

from aranorm import (
    ArabicNormalizationPipeline,
    BatchProcessingPolicy,
    CancellationToken,
    NormalizationResult,
    PipelineConfig,
    ResourceLimits,
)
from aranorm.exceptions import (
    BatchProcessingError,
    InvalidTextError,
    ProcessingCancelledError,
)


class RecordingCallback:
    def __init__(self) -> None:
        self.events: List[tuple[str, object]] = []

    def on_start(self, total: int) -> None:
        self.events.append(("start", total))

    def on_item(self, index: int, text: str, success: bool) -> None:
        self.events.append(("item", (index, text, success)))

    def on_finish(self) -> None:
        self.events.append(("finish", None))


class CancellingCallback(RecordingCallback):
    def __init__(self, token: CancellationToken) -> None:
        super().__init__()
        self.token = token

    def on_item(self, index: int, text: str, success: bool) -> None:
        super().on_item(index, text, success)
        if index == 0:
            self.token.cancel()


def fake_process(text: str) -> NormalizationResult:
    if text == "BAD":
        raise InvalidTextError("invalid async test item")
    return NormalizationResult(original_text=text, normalized_text=f"ok:{text}")


def patch_process(monkeypatch: pytest.MonkeyPatch, pipeline: ArabicNormalizationPipeline) -> None:
    monkeypatch.setattr(pipeline, "process", fake_process)


def test_async_batch_is_bounded_ordered_and_reports_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ArabicNormalizationPipeline()
    patch_process(monkeypatch, pipeline)
    callback = RecordingCallback()

    async def run() -> List[NormalizationResult]:
        return await pipeline.process_batch_async(
            ["a", "b", "c", "d", "e"],
            n_workers=2,
            batch_size=2,
            progress_callback=callback,
        )

    results = asyncio.run(run())

    assert [result.normalized_text for result in results] == ["ok:a", "ok:b", "ok:c", "ok:d", "ok:e"]
    assert callback.events == [
        ("start", 5),
        ("item", (0, "a", True)),
        ("item", (1, "b", True)),
        ("item", (2, "c", True)),
        ("item", (3, "d", True)),
        ("item", (4, "e", True)),
        ("finish", None),
    ]


def test_async_keeps_legacy_positional_policy_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ArabicNormalizationPipeline()
    patch_process(monkeypatch, pipeline)

    async def run() -> List[NormalizationResult]:
        return await pipeline.process_batch_async(
            ["a", "b"],
            2,
            BatchProcessingPolicy("skip"),
        )

    results = asyncio.run(run())
    assert [result.normalized_text for result in results] == ["ok:a", "ok:b"]


def test_async_on_error_can_recover_failed_item(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ArabicNormalizationPipeline()
    patch_process(monkeypatch, pipeline)
    callback = RecordingCallback()
    seen: List[tuple[int, str]] = []

    def fallback(index: int, text: str, error: Exception) -> Optional[str]:
        seen.append((index, text))
        return "recovered"

    async def run() -> List[NormalizationResult]:
        return await pipeline.process_batch_async(
            ["a", "BAD", "b"],
            n_workers=2,
            on_error=fallback,
            progress_callback=callback,
            policy=BatchProcessingPolicy("collect"),
        )

    results = asyncio.run(run())

    assert seen == [(1, "BAD")]
    assert [result.normalized_text for result in results] == ["ok:a", "ok:recovered", "ok:b"]
    assert ("item", (1, "BAD", True)) in callback.events


def test_async_collect_reports_failed_indices_and_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ArabicNormalizationPipeline()
    patch_process(monkeypatch, pipeline)
    callback = RecordingCallback()

    async def run() -> None:
        with pytest.raises(BatchProcessingError) as raised:
            await pipeline.process_batch_async(
                ["BAD", "a", "BAD"],
                n_workers=2,
                batch_size=1,
                progress_callback=callback,
                policy=BatchProcessingPolicy("collect"),
            )
        assert raised.value.failed_indices == [0, 2]

    asyncio.run(run())
    assert ("item", (0, "BAD", False)) in callback.events
    assert ("item", (1, "a", True)) in callback.events
    assert ("item", (2, "BAD", False)) in callback.events
    assert callback.events[-1] == ("finish", None)


def test_async_empty_batch_has_balanced_progress_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ArabicNormalizationPipeline()
    patch_process(monkeypatch, pipeline)
    callback = RecordingCallback()

    async def run() -> List[NormalizationResult]:
        return await pipeline.process_batch_async([], progress_callback=callback)

    assert asyncio.run(run()) == []
    assert callback.events == [("start", 0), ("finish", None)]


def test_async_cancellation_before_start_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ArabicNormalizationPipeline()
    patch_process(monkeypatch, pipeline)
    token = CancellationToken()
    token.cancel()

    async def run() -> None:
        with pytest.raises(ProcessingCancelledError, match="cancelled"):
            await pipeline.process_batch_async(["a"], cancellation_token=token)

    asyncio.run(run())


def test_async_cancellation_between_chunks_balances_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ArabicNormalizationPipeline()
    patch_process(monkeypatch, pipeline)
    token = CancellationToken()
    callback = CancellingCallback(token)

    async def run() -> None:
        with pytest.raises(ProcessingCancelledError, match="cancelled"):
            await pipeline.process_batch_async(
                ["a", "b", "c"],
                batch_size=1,
                progress_callback=callback,
                cancellation_token=token,
            )

    asyncio.run(run())
    assert callback.events == [
        ("start", 3),
        ("item", (0, "a", True)),
        ("finish", None),
    ]


@pytest.mark.parametrize("kwargs", [{"batch_size": 0}, {"batch_size": 17}])
def test_async_rejects_invalid_batch_size(kwargs: dict[str, int]) -> None:
    pipeline = ArabicNormalizationPipeline(config=PipelineConfig(resource_limits=ResourceLimits(max_batch_size=16)))

    async def run() -> None:
        with pytest.raises(ValueError, match="batch_size"):
            await pipeline.process_batch_async(["نص"], **kwargs)

    asyncio.run(run())
