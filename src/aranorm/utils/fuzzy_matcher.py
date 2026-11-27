"""Fuzzy Arabic word matching built on top of AraNorm normalisation.

Provides :class:`FuzzyArabicMatcher`, an index-based fuzzy search that
matches queries against a list of candidate texts using a **canonical
form** (diacritics removed, alef/tatweel normalised) plus optional
**stemmed form** and **root form**. Matches are scored between ``0.0``
(no similarity) and ``1.0`` (exact match) and returned sorted from
best to worst.

Example
-------
>>> from aranorm.utils.fuzzy_matcher import FuzzyArabicMatcher
>>> matcher = FuzzyArabicMatcher(["كتابٌ", "مكتبة", "كُتّب", "سيارة"])
>>> for candidate, score in matcher.search("كتب", threshold=0.5):
...     print(candidate, round(score, 2))
كتابٌ 0.8
كُتّب 0.8
مكتبة 0.6
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from aranorm.utils.normalizer_utils import (
    char_ngrams,
    levenshtein,
    remove_diacritics,
)
from aranorm.utils.root_extractor import extract_root
from aranorm.utils.stemmer import stem

# ── Types ──────────────────────────────────────────────────────────────

#: Similarity metric selectable by name.
MetricName = str

# ── Helpers ────────────────────────────────────────────────────────────


def canonical_form(word: str) -> str:
    """Return the diacritics-free, normalised form of *word*.

    Alef variants and alef-maqsura are unified so that spelling variants
    (``ة``/``ه``, ``ا``/``أ``) resolve to the same canonical key.

    Example
    -------
    >>> canonical_form("كتابٌ")
    'كتاب'
    """
    cleaned = remove_diacritics(word or "")
    cleaned = cleaned.replace("\u0640", "")
    # Unify alef variants and alef-maqsura toward plain alef.
    for variant in ("\u0622", "\u0623", "\u0624", "\u0625", "\u0626", "\u0649"):
        cleaned = cleaned.replace(variant, "\u0627")
    cleaned = cleaned.replace("\u0629", "\u0647")
    return cleaned


def jaccard_ngrams(a: str, b: str, n: int = 2) -> float:
    """Bigram-based Jaccard similarity between two strings.

    Example
    -------
    >>> jaccard_ngrams("كتب", "كتب")
    1.0
    """
    if not a or not b:
        return 0.0
    na = set(char_ngrams(a, n))
    nb = set(char_ngrams(b, n))
    if not na and not nb:
        return 0.0
    if not na or not nb:
        return 0.0
    intersection = len(na & nb)
    union = len(na | nb)
    return intersection / union if union else 0.0


def blended_similarity(canonical_query: str, canonical_candidate: str) -> float:
    """Combine Levenshtein normalised similarity with bigram Jaccard.

    The final score is ``0.6 * (1 - norm_lev) + 0.4 * jaccard`` so that a
    single insert/delete does not dominate short-word comparisons.

    Example
    -------
    >>> blended_similarity("كتب", "كتاب")
    0.7
    """
    if canonical_query == canonical_candidate:
        return 1.0
    if not canonical_query or not canonical_candidate:
        return 0.0
    max_len = max(len(canonical_query), len(canonical_candidate))
    lev_sim = 1.0 - (levenshtein(canonical_query, canonical_candidate) / max_len)
    jac = jaccard_ngrams(canonical_query, canonical_candidate, n=2)
    return 0.6 * lev_sim + 0.4 * jac


# ── Public API ─────────────────────────────────────────────────────────


@dataclass
class FuzzyMatchResult:
    """A single fuzzy match entry."""

    candidate: str
    score: float
    stemmed: Optional[str] = None
    root: Optional[str] = None


@dataclass
class FuzzyArabicMatcher:
    """Index-based fuzzy search over Arabic candidate texts.

    Each candidate is pre-computed into a **canonical form** (used for
    scoring) and optionally into a **stemmed form** and a **root form**
    (used to boost matches whose morphology collapses onto the same
    base).

    Parameters
    ----------
    candidates:
        Texts to index. Duplicate canonical forms are de-duplicated
        keeping the longest original form.
    use_stem:
        When *True* (default), candidates whose **stem** matches the
        query stem receive a score boost.
    use_root:
        When *True* (default), candidates whose **root** matches the
        query root receive a score boost.

    Example
    -------
    >>> matcher = FuzzyArabicMatcher(["كتابٌ", "مكتبة", "سيارة"])
    >>> matcher.search("كتب", threshold=0.5)  # doctest: +ELLIPSIS
    [FuzzyMatchResult(candidate='كتابٌ', score=...)]
    """

    candidates: List[str] = field(default_factory=list)
    use_stem: bool = True
    use_root: bool = True

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._canonical_index: Dict[str, str] = {}
        self._stem_index: Dict[str, List[str]] = {}
        self._root_index: Dict[str, List[str]] = {}
        for text in self.candidates:
            self.add(text)

    # ── Index management ───────────────────────────────────────────────

    def add(self, text: str) -> None:
        """Insert *text* into the index (thread-safe).

        Example
        -------
        >>> matcher = FuzzyArabicMatcher()
        >>> matcher.add("مدرسة")
        >>> len(matcher)
        1
        """
        if not text or not text.strip():
            return
        canon = canonical_form(text.strip())
        if not canon:
            return
        with self._lock:
            existing = self._canonical_index.get(canon)
            if existing is None or len(text) > len(existing):
                self._canonical_index[canon] = text
            if self.use_stem:
                s = stem(canon)
                if s:
                    self._stem_index.setdefault(s, []).append(canon)
            if self.use_root:
                r = extract_root(canon)
                if r:
                    self._root_index.setdefault(r, []).append(canon)

    def add_many(self, texts: Iterable[str]) -> None:
        """Insert an iterable of texts into the index.

        Example
        -------
        >>> matcher = FuzzyArabicMatcher()
        >>> matcher.add_many(["مدرسة", "جامعة"])
        >>> len(matcher)
        2
        """
        for text in texts:
            self.add(text)

    def __len__(self) -> int:
        """Return the number of distinct canonical forms in the index."""
        return len(self._canonical_index)

    def __contains__(self, text: object) -> bool:
        """Return *True* when *text* is present in the index."""
        if not isinstance(text, str):
            return False
        return canonical_form(text) in self._canonical_index

    # ── Search ─────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        threshold: float = 0.0,
        limit: Optional[int] = None,
    ) -> List[FuzzyMatchResult]:
        """Return fuzzy matches for *query* sorted from best to worst.

        Parameters
        ----------
        query:
            The search word (diacritics are stripped automatically).
        threshold:
            Minimum similarity score to include (``0.0`` returns all).
        limit:
            Maximum number of results to return (``None`` returns all).

        Returns
        -------
        list[FuzzyMatchResult]
            Matches sorted by descending score, ties broken by the
            original candidate insertion order.

        Example
        -------
        >>> matcher = FuzzyArabicMatcher(["كتابٌ", "مكتبة"])
        >>> res = matcher.search("كتاب", threshold=0.9)
        >>> len(res)
        1
        """
        if not query or not query.strip():
            return []
        query_stripped = query.strip()
        query_canon = canonical_form(query_stripped)
        if not query_canon:
            return []

        scored: List[Tuple[float, int, FuzzyMatchResult]] = []
        original_index = {canon: position for position, canon in enumerate(self._canonical_index)}

        morph_boost_canons = set()
        with self._lock:
            if self.use_stem:
                query_stem = stem(query_canon)
                if query_stem and query_stem in self._stem_index:
                    morph_boost_canons.update(self._stem_index[query_stem])
            if self.use_root:
                query_root = extract_root(query_canon)
                if query_root and query_root in self._root_index:
                    morph_boost_canons.update(self._root_index[query_root])

        with self._lock:
            index_snapshot = list(self._canonical_index.items())
        for canon, original in index_snapshot:
            score = blended_similarity(query_canon, canon)
            if canon in morph_boost_canons and score < 1.0:
                score = min(1.0, score + 0.2)
            if score < threshold:
                continue
            stemmed = stem(canon) if self.use_stem else None
            root = extract_root(canon) if self.use_root else None
            result = FuzzyMatchResult(
                candidate=original,
                score=score,
                stemmed=stemmed if stemmed != canon else None,
                root=root,
            )
            scored.append((score, original_index[canon], result))

        scored.sort(key=lambda item: (-item[0], item[1]))
        results = [item[2] for item in scored]
        return results[:limit] if limit is not None else results

    def search_many(
        self,
        queries: Iterable[str],
        threshold: float = 0.0,
        limit: Optional[int] = None,
    ) -> Dict[str, List[FuzzyMatchResult]]:
        """Fuzzy-search several queries and return results grouped by query.

        Example
        -------
        >>> matcher = FuzzyArabicMatcher(["مدرسة", "جامعة"])
        >>> grouped = matcher.search_many(["مدرسه", "سيارة"])
        >>> list(grouped.keys())
        ['مدرسه', 'سيارة']
        """
        return {query: self.search(query, threshold=threshold, limit=limit) for query in queries}

    def best_match(self, query: str) -> Optional[FuzzyMatchResult]:
        """Return the single best match for *query*, or *None*.

        Example
        -------
        >>> matcher = FuzzyArabicMatcher(["مدرسة"])
        >>> matcher.best_match("مدرسه")
        FuzzyMatchResult(candidate='مدرسة', score=...)
        """
        results = self.search(query, threshold=0.5, limit=1)
        return results[0] if results else None


def fuzzy_search(
    query: str,
    candidates: List[str],
    threshold: float = 0.0,
    limit: Optional[int] = None,
    metric: Optional[Callable[[str, str], float]] = None,
) -> List[FuzzyMatchResult]:
    """One-shot convenience function mirroring :meth:`FuzzyArabicMatcher.search`.

    Example
    -------
    >>> fuzzy_search("كتب", ["كتابٌ", "سيارة"])  # doctest: +ELLIPSIS
    [FuzzyMatchResult(candidate='كتابٌ', score=...)]
    """
    matcher = FuzzyArabicMatcher(candidates)
    return matcher.search(query, threshold=threshold, limit=limit)
