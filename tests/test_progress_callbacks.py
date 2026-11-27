"""Tests for progress callback implementations."""

from io import StringIO

import pytest

from aranorm.utils.progress import (
    ConsoleProgressCallback,
    NoOpProgressCallback,
    TqdmProgressCallback,
)


def test_noop_callback_exposes_complete_lifecycle() -> None:
    callback = NoOpProgressCallback()

    callback.on_start(2)
    callback.on_item(0, "نص", True)
    callback.on_item(1, "نص", False)
    callback.on_finish()


def test_console_callback_renders_progress_and_errors() -> None:
    output = StringIO()
    callback = ConsoleProgressCallback(total=2, width=4, prefix="اختبار", file=output)

    callback.on_start(2)
    callback.on_item(0, "أ", True)
    callback.on_item(1, "ب", False)
    callback.on_finish()

    rendered = output.getvalue()
    assert "اختبار" in rendered
    assert "2/2" in rendered
    assert "errors: 1" in rendered
    assert "████" in rendered


def test_console_callback_handles_unknown_total() -> None:
    output = StringIO()
    callback = ConsoleProgressCallback(width=3, file=output)

    callback.on_start(0)
    callback.on_finish()

    rendered = output.getvalue()
    assert "0/0" in rendered
    assert "0%" in rendered


def test_tqdm_callback_updates_and_closes() -> None:
    pytest.importorskip("tqdm")
    callback = TqdmProgressCallback(disable=True)

    callback.on_start(2)
    assert callback._bar is not None
    callback.on_item(0, "أ", True)
    callback.on_item(1, "ب", False)
    callback.on_finish()

    assert callback._bar is None


def test_tqdm_callback_finish_is_safe_before_start() -> None:
    pytest.importorskip("tqdm")
    callback = TqdmProgressCallback(disable=True)

    callback.on_item(0, "أ", True)
    callback.on_finish()
    assert callback._bar is None
