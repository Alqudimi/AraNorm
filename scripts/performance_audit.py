"""Repeatable performance and bounded-memory audit for AraNorm."""

from __future__ import annotations

import json
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Callable, Dict, List, Union, cast

from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.core.pipeline import NormalizationResult
from aranorm.utils.cache import NormalizationCache


class _SleepPipeline:
    """Controlled pipeline used to expose single-flight call amplification."""

    def __init__(self, delay: float = 0.01) -> None:
        self.delay = delay
        self.calls = 0
        self._lock = Lock()

    def process(self, text: str) -> NormalizationResult:
        with self._lock:
            self.calls += 1
        time.sleep(self.delay)
        return NormalizationResult(original_text=text, normalized_text=text)


def _timed(function: Callable[[], object]) -> float:
    started = time.perf_counter()
    function()
    return time.perf_counter() - started


def measure_cache() -> Dict[str, Union[float, int]]:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    repeated = ["شلونك حبيبي؟"] * 1_000
    cache = NormalizationCache(pipeline, maxsize=8)

    uncached_s = _timed(lambda: [pipeline.process(text) for text in repeated])
    cached_s = _timed(lambda: [cache.process(text) for text in repeated])
    stats = cache.stats()
    return {
        "repeated_items": len(repeated),
        "uncached_s": round(uncached_s, 6),
        "cached_s": round(cached_s, 6),
        "speedup": round(uncached_s / cached_s, 2) if cached_s else 0.0,
        "cache_hits": cast(int, stats["hits"]),
        "cache_misses": cast(int, stats["misses"]),
    }


def measure_single_flight() -> Dict[str, Union[float, int]]:
    callers = 16
    pipeline = _SleepPipeline()
    cache = NormalizationCache(pipeline, maxsize=4)  # type: ignore[arg-type]
    cached_s = _timed(lambda: _run_concurrent([cache.process] * callers, "same"))

    baseline = _SleepPipeline()
    uncached_s = _timed(lambda: _run_concurrent([baseline.process] * callers, "same"))
    return {
        "concurrent_callers": callers,
        "single_flight_pipeline_calls": pipeline.calls,
        "uncached_pipeline_calls": baseline.calls,
        "single_flight_s": round(cached_s, 6),
        "uncached_concurrent_s": round(uncached_s, 6),
        "latency_ratio": round(cached_s / uncached_s, 2) if uncached_s else 0.0,
    }


def _run_concurrent(functions: List[Callable[[str], object]], text: str) -> None:
    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = [executor.submit(function, text) for function in functions]
        for future in futures:
            future.result()


def measure_streaming() -> Dict[str, Union[float, int]]:
    count = 10_000
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    corpus = ("شلونك حبيبي؟" for _ in range(count))
    tracemalloc.start()
    started = time.perf_counter()
    processed = sum(1 for _ in pipeline.process_iter(corpus, batch_size=64, n_workers=1))
    elapsed = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "streaming_items": processed,
        "streaming_s": round(elapsed, 6),
        "streaming_texts_per_second": round(processed / elapsed, 2) if elapsed else 0.0,
        "tracemalloc_current_bytes": current,
        "tracemalloc_peak_bytes": peak,
    }


def main() -> None:
    report = {
        "cache": measure_cache(),
        "single_flight": measure_single_flight(),
        "streaming": measure_streaming(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
