"""Thread-safe memoization cache for :class:`~aranorm.core.pipeline.ArabicNormalizationPipeline`.

Wraps an :class:`~aranorm.core.pipeline.ArabicNormalizationPipeline` and caches
:class:`~aranorm.core.pipeline.NormalizationResult` objects by their input text,
so identical strings are only processed once.

Design
------
* **LRU eviction** — configurable ``maxsize`` (default 4 096).
* **Thread-safe** — a :class:`threading.RLock` serialises cache mutations; reads
  use dict look-ups which are GIL-protected under CPython.
* **Cache-key** — the raw input string (after type validation); diacritics and
  spaces are preserved so normalisation variants remain distinct.
* **Statistics** — :meth:`stats` returns hits, misses, size, and hit-rate.

Example
-------
>>> from aranorm import ArabicNormalizationPipeline, PipelineConfig
>>> from aranorm.utils.cache import NormalizationCache
>>>
>>> pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))
>>> cache = NormalizationCache(pipeline, maxsize=8192)
>>>
>>> result1 = cache.process("شلونك حبيبي؟")   # cache miss → pipeline
>>> result2 = cache.process("شلونك حبيبي؟")   # cache hit → instant
>>> cache.stats()["hit_rate"]
0.5
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import TYPE_CHECKING, Dict, List, Sequence

if TYPE_CHECKING:
    from aranorm.core.pipeline import ArabicNormalizationPipeline, NormalizationResult


class NormalizationCache:
    """LRU-evicting, thread-safe cache wrapping an :class:`ArabicNormalizationPipeline`.

    Parameters
    ----------
    pipeline:
        The underlying :class:`~aranorm.core.pipeline.ArabicNormalizationPipeline`
        that is called on cache misses.
    maxsize:
        Maximum number of entries to keep (default 4 096).  When the cache is
        full the least-recently-used entry is evicted.

    Example
    -------
    >>> cache = NormalizationCache(pipeline, maxsize=1000)
    >>> r = cache.process("مرحباً بكم")
    >>> print(cache.stats())
    {'hits': 0, 'misses': 1, 'size': 1, 'maxsize': 1000, 'hit_rate': 0.0}
    """

    def __init__(
        self,
        pipeline: "ArabicNormalizationPipeline",
        maxsize: int = 4096,
    ) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self.pipeline = pipeline
        self.maxsize = maxsize
        self._lock: threading.RLock = threading.RLock()
        self._cache: OrderedDict[str, "NormalizationResult"] = OrderedDict()
        self._hits: int = 0
        self._misses: int = 0

    # ── Public API ────────────────────────────────────────────────────────

    def process(self, text: str) -> "NormalizationResult":
        """Return the cached result for *text*, computing it on a miss.

        Parameters
        ----------
        text:
            Input Arabic string.

        Returns
        -------
        NormalizationResult
            From the cache on a hit, freshly computed on a miss.
        """
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                self._hits += 1
                return self._cache[text]

        # Compute outside the lock to avoid blocking concurrent callers
        result = self.pipeline.process(text)

        with self._lock:
            # Another thread may have inserted while we were computing
            if text not in self._cache:
                if len(self._cache) >= self.maxsize:
                    self._cache.popitem(last=False)  # evict LRU
                self._cache[text] = result
            else:
                self._cache.move_to_end(text)
            self._misses += 1
            return self._cache[text]

    def process_batch(
        self,
        texts: Sequence[str],
        n_workers: int = 1,
    ) -> List["NormalizationResult"]:
        """Process a batch, serving cached results and computing only misses.

        Parameters
        ----------
        texts:
            Sequence of Arabic strings.
        n_workers:
            Worker count passed to the underlying pipeline for uncached texts.

        Returns
        -------
        List[NormalizationResult]
            Results in the same order as *texts*.
        """
        texts_list = list(texts)
        results: Dict[int, "NormalizationResult"] = {}
        miss_indices: List[int] = []
        miss_texts: List[str] = []

        # Identify cache hits
        with self._lock:
            for i, text in enumerate(texts_list):
                if text in self._cache:
                    self._cache.move_to_end(text)
                    results[i] = self._cache[text]
                    self._hits += 1
                else:
                    miss_indices.append(i)
                    miss_texts.append(text)

        # Compute misses via the underlying pipeline
        if miss_texts:
            computed = self.pipeline.process_batch(miss_texts, n_workers=n_workers)
            with self._lock:
                for idx, (i, text) in enumerate(zip(miss_indices, miss_texts)):
                    result = computed[idx]
                    if text not in self._cache:
                        if len(self._cache) >= self.maxsize:
                            self._cache.popitem(last=False)
                        self._cache[text] = result
                    results[i] = self._cache[text]
                    self._misses += 1

        return [results[i] for i in range(len(texts_list))]

    def invalidate(self, text: str) -> bool:
        """Remove one entry from the cache.

        Returns
        -------
        bool
            *True* if the entry existed and was removed.
        """
        with self._lock:
            if text in self._cache:
                del self._cache[text]
                return True
            return False

    def clear(self) -> None:
        """Evict all entries and reset hit/miss counters."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, object]:
        """Return cache performance statistics.

        Returns
        -------
        dict
            ``hits``, ``misses``, ``size``, ``maxsize``, ``hit_rate``.
        """
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "maxsize": self.maxsize,
                "hit_rate": round(self._hits / total, 4) if total else 0.0,
            }

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, text: object) -> bool:
        return text in self._cache

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"NormalizationCache("
            f"size={s['size']}/{s['maxsize']}, "
            f"hit_rate={s['hit_rate']:.1%})"
        )
