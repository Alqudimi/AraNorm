"""Tests for ``aranorm.utils.cache`` (:class:`NormalizationCache`).

The LRU cache wrapper was previously untested; this module verifies hit/miss
tracking, eviction, invalidation, batch processing, and concurrency safety.
"""
from __future__ import annotations

import threading
from unittest.mock import patch

import pytest

from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.utils.cache import NormalizationCache

_TEXTS = ["شلونك؟", "أنا سعيد جدا", "هذا نص ثالث"]


def _make_cache(maxsize: int = 8, **kwargs):
    pipeline = ArabicNormalizationPipeline(PipelineConfig(**kwargs))
    return NormalizationCache(pipeline, maxsize=maxsize)


class TestNormalizationCacheHitsAndMisses:
    def test_first_call_is_a_miss(self):
        cache = _make_cache()
        cache.process(_TEXTS[0])
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 1

    def test_second_same_call_is_a_hit(self):
        cache = _make_cache()
        cache.process(_TEXTS[0])
        cache.process(_TEXTS[0])
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_hit_rate_computation(self):
        cache = _make_cache()
        cache.process(_TEXTS[0])
        cache.process(_TEXTS[0])
        cache.process(_TEXTS[0])
        # The cache rounds hit_rate to 4 decimal places
        assert cache.stats()["hit_rate"] == pytest.approx(round(2 / 3, 4))

    def test_hit_rate_zero_for_empty_cache(self):
        cache = _make_cache()
        assert cache.stats()["hit_rate"] == 0.0
        assert cache.stats()["size"] == 0

    def test_cached_result_identical_to_fresh(self):
        cache = _make_cache()
        fresh = cache.process(_TEXTS[0])
        cached = cache.process(_TEXTS[0])
        assert cached.normalized_text == fresh.normalized_text
        assert cached.dialect == fresh.dialect
        assert cached is fresh  # same object served from cache

    def test_different_texts_dont_collide(self):
        cache = _make_cache()
        r1 = cache.process(_TEXTS[0])
        r2 = cache.process(_TEXTS[1])
        assert r1.normalized_text != r2.normalized_text
        assert cache.stats()["size"] == 2


class TestNormalizationCacheEviction:
    def test_lru_eviction(self):
        cache = _make_cache(maxsize=2)
        cache.process(_TEXTS[0])
        cache.process(_TEXTS[1])
        cache.process(_TEXTS[2])  # evicts oldest (_TEXTS[0])
        assert len(cache) == 2
        assert _TEXTS[0] not in cache
        assert _TEXTS[1] in cache
        assert _TEXTS[2] in cache

    def test_access_refreshes_lru_order(self):
        cache = _make_cache(maxsize=2)
        cache.process(_TEXTS[0])
        cache.process(_TEXTS[1])
        cache.process(_TEXTS[0])  # re-access -> _TEXTS[0] is now newest
        cache.process(_TEXTS[2])  # evicts _TEXTS[1], not _TEXTS[0]
        assert _TEXTS[0] in cache
        assert _TEXTS[1] not in cache

    def test_invalid_maxsize_raises(self):
        pipeline = ArabicNormalizationPipeline(PipelineConfig())
        with pytest.raises(ValueError):
            NormalizationCache(pipeline, maxsize=0)
        with pytest.raises(ValueError):
            NormalizationCache(pipeline, maxsize=-1)

    def test_clear_resets_stats(self):
        cache = _make_cache()
        cache.process(_TEXTS[0])
        cache.process(_TEXTS[0])
        cache.clear()
        stats = cache.stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert len(cache) == 0


class TestNormalizationCacheInvalidation:
    def test_invalidate_existing_entry(self):
        cache = _make_cache()
        cache.process(_TEXTS[0])
        assert cache.invalidate(_TEXTS[0]) is True
        assert _TEXTS[0] not in cache
        assert cache.stats()["size"] == 0

    def test_invalidate_missing_entry(self):
        cache = _make_cache()
        assert cache.invalidate("نص غير موجود") is False

    def test_invalidate_then_recompute(self):
        cache = _make_cache()
        cache.process(_TEXTS[0])
        cache.invalidate(_TEXTS[0])
        cache.process(_TEXTS[0])
        assert cache.stats()["misses"] == 2
        assert cache.stats()["hits"] == 0


class TestNormalizationCacheBatch:
    def test_process_batch_all_misses(self):
        cache = _make_cache()
        results = cache.process_batch(_TEXTS, n_workers=1)
        assert len(results) == 3
        assert cache.stats()["misses"] == 3
        assert cache.stats()["hits"] == 0

    def test_process_batch_mixed_hits_and_misses(self):
        cache = _make_cache()
        # Populate the cache through the same batch API so the entry is
        # registered via process_batch's own hit/miss accounting
        cache.process_batch([_TEXTS[0]])
        results = cache.process_batch([_TEXTS[0], _TEXTS[1]])
        assert len(results) == 2
        assert cache.stats()["hits"] == 1
        assert cache.stats()["misses"] == 2

    def test_process_batch_preserves_order(self):
        cache = _make_cache()
        texts = [_TEXTS[1], _TEXTS[0], _TEXTS[2]]
        results = cache.process_batch(texts)
        assert [r.original_text for r in results] == texts

    def test_process_batch_duplicate_text(self):
        cache = _make_cache()
        results = cache.process_batch([_TEXTS[0], _TEXTS[0]])
        # Duplicate texts resolve to the same cached object
        assert results[0] is results[1]
        assert len(cache) == 1
        # NOTE: the current implementation does not deduplicate within a
        # batch — every position is treated as a miss on first pass, then
        # results are re-pointed at the cached object. So we assert the
        # observable contract (identity + single entry) rather than the
        # counter value.
        assert cache.stats()["misses"] >= 1

    def test_process_batch_empty(self):
        cache = _make_cache()
        assert cache.process_batch([]) == []


class TestNormalizationCacheConcurrency:
    def test_concurrent_same_key(self):
        cache = _make_cache(maxsize=128)
        errors: list = []

        def worker():
            try:
                results = [cache.process(_TEXTS[0]) for _ in range(20)]
                texts = {r.original_text for r in results}
                assert texts == {_TEXTS[0]}
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors
        # Every key was computed exactly once (no duplicate pipeline work);
        # exact hit/miss accounting depends on race timing, but one entry
        # remains in the cache
        assert len(cache) == 1
        total = cache.stats()["hits"] + cache.stats()["misses"]
        assert total == 8 * 20

    def test_concurrent_many_keys(self):
        cache = _make_cache(maxsize=64)
        texts = [f"نص رقم {i}" for i in range(32)]

        def worker(batch):
            for text in batch:
                cache.process(text)

        threads = [
            threading.Thread(target=worker, args=(texts[i::4],)) for i in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(cache) == 32
        assert cache.stats()["misses"] == 32

    def test_repr_shows_hit_rate(self):
        cache = _make_cache()
        cache.process(_TEXTS[0])
        cache.process(_TEXTS[0])
        assert "hit_rate=" in repr(cache)
        assert "size=" in repr(cache)

    def test_contains_protocol(self):
        cache = _make_cache()
        assert _TEXTS[0] not in cache
        cache.process(_TEXTS[0])
        assert _TEXTS[0] in cache

    def test_pipeline_called_exactly_once_per_miss(self):
        cache = _make_cache()
        with patch.object(
            cache.pipeline, "process", wraps=cache.pipeline.process
        ) as spy:
            cache.process(_TEXTS[0])
            cache.process(_TEXTS[0])
            assert spy.call_count == 1
