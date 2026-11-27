from __future__ import annotations

from typing import List

import pytest

from aranorm import ArabicNormalizationPipeline, BatchProcessingPolicy, NormalizationResult
from aranorm.exceptions import BatchProcessingError, InvalidTextError


def _fake_process(text: str) -> NormalizationResult:
    if text == "BAD":
        raise InvalidTextError("invalid test item")
    return NormalizationResult(original_text=text, normalized_text=f"ok:{text}")


class RecordingCallback:
    def __init__(self) -> None:
        self.started: List[int] = []
        self.items: List[tuple[int, str, bool]] = []
        self.finished = 0

    def on_start(self, total: int) -> None:
        self.started.append(total)

    def on_item(self, index: int, text: str, success: bool) -> None:
        self.items.append((index, text, success))

    def on_finish(self) -> None:
        self.finished += 1


def _patch_process(monkeypatch: pytest.MonkeyPatch, pipeline: ArabicNormalizationPipeline) -> None:
    monkeypatch.setattr(pipeline, "process", _fake_process)


def test_fail_fast_preserves_legacy_exception_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ArabicNormalizationPipeline()
    _patch_process(monkeypatch, pipeline)

    with pytest.raises(InvalidTextError, match="invalid test item"):
        list(pipeline.process_iter(["a", "BAD", "b"], policy=BatchProcessingPolicy("fail_fast")))


def test_collect_processes_all_items_and_reports_ordered_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = ArabicNormalizationPipeline()
    _patch_process(monkeypatch, pipeline)
    callback = RecordingCallback()

    iterator = pipeline.process_iter(
        ["a", "BAD", "b", "BAD"],
        batch_size=2,
        n_workers=2,
        policy=BatchProcessingPolicy("collect"),
        progress_callback=callback,
        total=4,
    )
    with pytest.raises(BatchProcessingError) as raised:
        list(iterator)

    assert raised.value.failed_indices == [1, 3]
    assert list(raised.value.errors) == [1, 3]
    assert callback.started == [4]
    assert callback.items == [(0, "a", True), (1, "BAD", False), (2, "b", True), (3, "BAD", False)]
    assert callback.finished == 1


def test_skip_policy_yields_successful_items_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ArabicNormalizationPipeline()
    _patch_process(monkeypatch, pipeline)

    results = list(pipeline.process_iter(["a", "BAD", "b"], policy=BatchProcessingPolicy("skip")))

    assert [result.normalized_text for result in results] == ["ok:a", "ok:b"]


def test_on_error_fallback_remains_compatible_with_collect_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = ArabicNormalizationPipeline()
    _patch_process(monkeypatch, pipeline)

    def fallback(index: int, text: str, error: Exception) -> str | None:
        assert index == 1
        assert text == "BAD"
        assert isinstance(error, InvalidTextError)
        return "recovered"

    results = list(
        pipeline.process_iter(
            ["a", "BAD", "b"],
            policy=BatchProcessingPolicy("collect"),
            on_error=fallback,
        )
    )

    assert [result.normalized_text for result in results] == ["ok:a", "ok:recovered", "ok:b"]


def test_invalid_policy_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="fail_fast"):
        BatchProcessingPolicy("unknown")  # type: ignore[arg-type]


def test_batch_processing_error_owns_mutable_inputs() -> None:
    failed_indices = [2]
    errors: dict[int, Exception] = {2: InvalidTextError("bad")}
    error = BatchProcessingError("failed", failed_indices=failed_indices, errors=errors)

    failed_indices.append(9)
    errors.clear()

    assert error.failed_indices == [2]
    assert list(error.errors) == [2]


def test_process_batch_forwards_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = ArabicNormalizationPipeline()
    _patch_process(monkeypatch, pipeline)

    with pytest.raises(BatchProcessingError) as raised:
        pipeline.process_batch(["a", "BAD"], policy=BatchProcessingPolicy("collect"))

    assert raised.value.failed_indices == [1]


def test_collect_records_failure_when_fallback_is_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = ArabicNormalizationPipeline()
    _patch_process(monkeypatch, pipeline)

    def skip_fallback(index: int, text: str, error: Exception) -> None:
        return None

    with pytest.raises(BatchProcessingError) as raised:
        list(
            pipeline.process_iter(
                ["a", "BAD"],
                on_error=skip_fallback,
                policy=BatchProcessingPolicy("collect"),
            )
        )

    assert raised.value.failed_indices == [1]


def test_skip_policy_keeps_legacy_on_error_skip_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = ArabicNormalizationPipeline()
    _patch_process(monkeypatch, pipeline)

    results = list(
        pipeline.process_iter(
            ["BAD"],
            on_error=lambda index, text, error: None,
            policy=BatchProcessingPolicy("skip"),
        )
    )

    assert results == []


def test_async_collect_reports_all_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    pipeline = ArabicNormalizationPipeline()
    _patch_process(monkeypatch, pipeline)

    async def run() -> None:
        with pytest.raises(BatchProcessingError) as raised:
            await pipeline.process_batch_async(
                ["a", "BAD", "b", "BAD"],
                n_workers=2,
                policy=BatchProcessingPolicy("collect"),
            )
        assert raised.value.failed_indices == [1, 3]

    asyncio.run(run())


def test_async_skip_returns_successes_in_input_order(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    pipeline = ArabicNormalizationPipeline()
    _patch_process(monkeypatch, pipeline)

    async def run() -> list[NormalizationResult]:
        return await pipeline.process_batch_async(
            ["b", "BAD", "a"],
            n_workers=2,
            policy=BatchProcessingPolicy("skip"),
        )

    results = asyncio.run(run())
    assert [result.normalized_text for result in results] == ["ok:b", "ok:a"]


def test_async_fail_fast_keeps_original_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    pipeline = ArabicNormalizationPipeline()
    _patch_process(monkeypatch, pipeline)

    async def run() -> None:
        with pytest.raises(InvalidTextError, match="invalid test item"):
            await pipeline.process_batch_async(["a", "BAD"], policy=BatchProcessingPolicy("fail_fast"))

    asyncio.run(run())
