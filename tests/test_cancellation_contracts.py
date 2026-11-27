"""Contract tests for cooperative cancellation."""

from __future__ import annotations

from typing import List, Tuple

import pytest

from aranorm import ArabicNormalizationPipeline, CancellationToken, NormalizationResult
from aranorm.exceptions import ProcessingCancelledError


class CancelOnFirstItem:
    def __init__(self, token: CancellationToken) -> None:
        self.token = token
        self.events: List[Tuple[str, object]] = []

    def on_start(self, total: int) -> None:
        self.events.append(("start", total))

    def on_item(self, index: int, text: str, success: bool) -> None:
        self.events.append(("item", (index, text, success)))
        if index == 0:
            self.token.cancel()

    def on_finish(self) -> None:
        self.events.append(("finish", None))


def fake_process(text: str) -> NormalizationResult:
    return NormalizationResult(original_text=text, normalized_text=f"ok:{text}")


def test_cancellation_token_is_idempotent_and_explicit() -> None:
    token = CancellationToken()
    assert token.is_cancelled is False

    token.cancel()
    token.cancel()

    assert token.is_cancelled is True
    with pytest.raises(ProcessingCancelledError, match="cancelled"):
        token.raise_if_cancelled()


def test_process_iter_rejects_pre_cancel_without_start_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = ArabicNormalizationPipeline()
    monkeypatch.setattr(pipeline, "process", fake_process)
    token = CancellationToken()
    token.cancel()
    callback = CancelOnFirstItem(token)

    with pytest.raises(ProcessingCancelledError, match="cancelled"):
        list(
            pipeline.process_iter(
                ["a"],
                progress_callback=callback,
                cancellation_token=token,
            )
        )

    assert callback.events == []


def test_process_iter_cancels_between_items_and_finishes_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = ArabicNormalizationPipeline()
    monkeypatch.setattr(pipeline, "process", fake_process)
    token = CancellationToken()
    callback = CancelOnFirstItem(token)

    with pytest.raises(ProcessingCancelledError, match="cancelled"):
        list(
            pipeline.process_iter(
                ["a", "b"],
                batch_size=1,
                progress_callback=callback,
                cancellation_token=token,
            )
        )

    assert callback.events == [
        ("start", 0),
        ("item", (0, "a", True)),
        ("finish", None),
    ]
