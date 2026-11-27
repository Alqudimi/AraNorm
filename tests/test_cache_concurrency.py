from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import pytest

from aranorm.core.pipeline import NormalizationResult
from aranorm.utils.cache import NormalizationCache


class BlockingPipeline:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.calls = 0
        self._lock = Lock()

    def process(self, text: str) -> NormalizationResult:
        with self._lock:
            self.calls += 1
            self.started.set()
        assert self.release.wait(timeout=2)
        return NormalizationResult(original_text=text, normalized_text=f"ok:{text}")


class FailingPipeline:
    def __init__(self) -> None:
        self.calls = 0
        self.started = Event()
        self.release = Event()
        self._lock = Lock()

    def process(self, text: str) -> NormalizationResult:
        with self._lock:
            self.calls += 1
            self.started.set()
        assert self.release.wait(timeout=2)
        raise ValueError("synthetic cache failure")


def test_same_key_is_computed_once_for_concurrent_callers() -> None:
    pipeline = BlockingPipeline()
    cache = NormalizationCache(pipeline, maxsize=4)  # type: ignore[arg-type]

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cache.process, "same")
        assert pipeline.started.wait(timeout=2)
        second = executor.submit(cache.process, "same")
        pipeline.release.set()
        results = [first.result(timeout=2), second.result(timeout=2)]

    assert pipeline.calls == 1
    assert results[0].normalized_text == results[1].normalized_text == "ok:same"
    assert cache.stats()["misses"] == 1
    assert cache.stats()["hits"] == 1


def test_concurrent_waiters_receive_the_same_failure() -> None:
    pipeline = FailingPipeline()
    cache = NormalizationCache(pipeline, maxsize=4)  # type: ignore[arg-type]

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cache.process, "bad")
        assert pipeline.started.wait(timeout=2)
        second = executor.submit(cache.process, "bad")
        pipeline.release.set()
        for future in (first, second):
            with pytest.raises(ValueError, match="synthetic cache failure"):
                future.result(timeout=2)

    assert pipeline.calls == 1
    assert "bad" not in cache
    assert cache.stats()["size"] == 0
