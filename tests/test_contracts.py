"""Contract tests for public extension points."""

from __future__ import annotations

import pytest

from aranorm import ArabicNormalizationPipeline, NormalizationResult, PipelineHooks
from aranorm.core import ProgressCallbackProtocol
from aranorm.exceptions import InvalidTextError


class RecordingCallback:
    """Duck-typed callback used to verify structural compatibility."""

    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def on_start(self, total: int) -> None:
        self.events.append(("start", total))

    def on_item(self, index: int, text: str, success: bool) -> None:
        self.events.append(("item", (index, text, success)))

    def on_finish(self) -> None:
        self.events.append(("finish", None))


def test_callback_protocol_is_structural() -> None:
    callback = RecordingCallback()
    assert isinstance(callback, ProgressCallbackProtocol)


def test_batch_accepts_structural_callback_and_reports_lifecycle() -> None:
    pipeline = ArabicNormalizationPipeline()
    callback = RecordingCallback()
    texts = ["أحمد", "إبراهيم", "مرحبا"]

    results = pipeline.process_batch(texts, progress_callback=callback)

    assert [result.original_text for result in results] == texts
    assert callback.events[0] == ("start", len(texts))
    assert callback.events[-1] == ("finish", None)
    item_events = [event for event in callback.events if event[0] == "item"]
    assert len(item_events) == len(texts)
    assert [event[1][0] for event in item_events] == list(range(len(texts)))
    assert all(event[1][2] is True for event in item_events)


def test_streaming_accepts_unknown_total_without_materializing_input() -> None:
    pipeline = ArabicNormalizationPipeline()
    callback = RecordingCallback()

    def inputs():
        for value in ("أ", "ب", "ت"):
            yield value

    results = list(pipeline.process_iter(inputs(), progress_callback=callback))

    assert [result.original_text for result in results] == ["أ", "ب", "ت"]
    assert callback.events[0] == ("start", 0)
    assert callback.events[-1] == ("finish", None)
    assert len([event for event in callback.events if event[0] == "item"]) == 3


def test_pipeline_hooks_cover_success_and_error_lifecycle() -> None:
    seen: list[tuple[str, object]] = []

    def before(text: str) -> str:
        seen.append(("before", text))
        return text + " إضافي"

    def after(result: NormalizationResult) -> None:
        seen.append(("after", result.normalized_text))

    pipeline = ArabicNormalizationPipeline(hooks=PipelineHooks(before_process=before, after_process=after))
    result = pipeline.process("نص")

    assert result.original_text == "نص إضافي"
    assert seen[0] == ("before", "نص")
    assert seen[1][0] == "after"


def test_pipeline_error_hook_observes_original_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    errors: list[tuple[str, Exception]] = []

    def on_error(text: str, error: Exception) -> None:
        errors.append((text, error))

    pipeline = ArabicNormalizationPipeline(hooks=PipelineHooks(on_error=on_error))

    def fail(text: str) -> NormalizationResult:
        raise InvalidTextError("synthetic failure")

    monkeypatch.setattr(pipeline, "_process_unmeasured", fail)
    with pytest.raises(InvalidTextError, match="synthetic failure"):
        pipeline.process("valid")

    assert errors and errors[0][0] == "valid"
    assert isinstance(errors[0][1], InvalidTextError)


def test_pipeline_error_hook_cannot_hide_original_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def on_error(text: str, error: Exception) -> None:
        raise RuntimeError("hook failure")

    pipeline = ArabicNormalizationPipeline(hooks=PipelineHooks(on_error=on_error))

    def fail(text: str) -> NormalizationResult:
        raise InvalidTextError("synthetic failure")

    monkeypatch.setattr(pipeline, "_process_unmeasured", fail)
    with pytest.raises(InvalidTextError, match="synthetic failure"):
        pipeline.process("valid")
