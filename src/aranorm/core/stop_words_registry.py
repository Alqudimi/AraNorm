"""Registry of Arabic stop words, organised by scope and category.

Design goals
------------
* **O(m) lookup** via a Trie structure (where m = word length).
* **Lazy loading** – dialect/category lists are only read from disk on first access.
* **lru_cache** on hot paths to amortise repeated look-ups.
* Zero mandatory external dependencies (pure-Python Trie).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict, FrozenSet, List, Optional, Set

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "stopwords")
_CAT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "stopwords_categorized.json")

_DIALECT_FILE_MAP: Dict[str, str] = {
    "EGY": "egy.txt",
    "GLF": "glf.txt",
    "LEV": "lev.txt",
    "IRQ": "irq.txt",
    "NOR": "nor.txt",
    "TUN": "tun.txt",
    "YEM": "yem.txt",
}


# ── Pure-Python Trie ──────────────────────────────────────────────────────────


class _TrieNode:
    __slots__ = ("children", "is_end")

    def __init__(self) -> None:
        self.children: Dict[str, "_TrieNode"] = {}
        self.is_end: bool = False


class _Trie:
    """Compressed character trie for O(m) membership queries."""

    def __init__(self) -> None:
        self._root = _TrieNode()

    def insert(self, word: str) -> None:
        node = self._root
        for ch in word:
            node = node.children.setdefault(ch, _TrieNode())
        node.is_end = True

    def __contains__(self, word: str) -> bool:
        node = self._root
        for ch in word:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.is_end

    def words(self) -> Set[str]:
        """Return every word stored in the trie."""
        result: Set[str] = set()
        self._dfs(self._root, [], result)
        return result

    def _dfs(self, node: _TrieNode, path: List[str], result: Set[str]) -> None:
        if node.is_end:
            result.add("".join(path))
        for ch, child in node.children.items():
            path.append(ch)
            self._dfs(child, path, result)
            path.pop()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _read_txt(path: str) -> Set[str]:
    """Read a line-per-word text file; ignore blank lines and comments."""
    if not os.path.isfile(path):
        return set()
    with open(path, encoding="utf-8") as fh:
        return {line.strip() for line in fh if line.strip() and not line.startswith("#")}


# ── Registry ─────────────────────────────────────────────────────────────────


class StopWordsRegistry:
    """Central stop-words registry with Trie-backed lookup.

    All data is loaded lazily on first access.

    Example
    -------
    >>> registry = StopWordsRegistry()
    >>> registry.is_stop("من")
    True
    >>> registry.is_stop("كده", dialect="EGY")
    True
    >>> registry.is_stop("كده", dialect="GLF")
    False
    """

    def __init__(self) -> None:
        self._msa_trie: Optional[_Trie] = None
        self._universal_trie: Optional[_Trie] = None
        self._dialect_tries: Dict[str, _Trie] = {}
        self._arabizi_trie: Optional[_Trie] = None
        self._internet_trie: Optional[_Trie] = None
        self._filler_trie: Optional[_Trie] = None
        self._social_trie: Optional[_Trie] = None
        self._numbers_trie: Optional[_Trie] = None
        self._categories: Optional[Dict[str, List[str]]] = None

    # ── Lazy loaders ─────────────────────────────────────────────────────

    def _load_msa(self) -> _Trie:
        if self._msa_trie is None:
            self._msa_trie = _Trie()
            for w in _read_txt(os.path.join(_DATA_DIR, "msa.txt")):
                self._msa_trie.insert(w)
        return self._msa_trie

    def _load_universal(self) -> _Trie:
        if self._universal_trie is None:
            self._universal_trie = _Trie()
            for w in _read_txt(os.path.join(_DATA_DIR, "universal.txt")):
                self._universal_trie.insert(w)
        return self._universal_trie

    def _load_dialect(self, code: str) -> _Trie:
        code = code.upper()
        if code not in self._dialect_tries:
            trie = _Trie()
            filename = _DIALECT_FILE_MAP.get(code)
            if filename:
                for w in _read_txt(os.path.join(_DATA_DIR, filename)):
                    trie.insert(w)
            self._dialect_tries[code] = trie
        return self._dialect_tries[code]

    def _load_arabizi(self) -> _Trie:
        if self._arabizi_trie is None:
            self._arabizi_trie = _Trie()
            for w in _read_txt(os.path.join(_DATA_DIR, "arabizi.txt")):
                self._arabizi_trie.insert(w)
        return self._arabizi_trie

    def _load_internet(self) -> _Trie:
        if self._internet_trie is None:
            self._internet_trie = _Trie()
            for w in _read_txt(os.path.join(_DATA_DIR, "internet.txt")):
                self._internet_trie.insert(w)
        return self._internet_trie

    def _load_filler(self) -> _Trie:
        if self._filler_trie is None:
            self._filler_trie = _Trie()
            for w in _read_txt(os.path.join(_DATA_DIR, "filler.txt")):
                self._filler_trie.insert(w)
        return self._filler_trie

    def _load_social(self) -> _Trie:
        if self._social_trie is None:
            self._social_trie = _Trie()
            for w in _read_txt(os.path.join(_DATA_DIR, "social_media.txt")):
                self._social_trie.insert(w)
        return self._social_trie

    def _load_numbers(self) -> _Trie:
        if self._numbers_trie is None:
            self._numbers_trie = _Trie()
            for w in _read_txt(os.path.join(_DATA_DIR, "numbers.txt")):
                self._numbers_trie.insert(w)
        return self._numbers_trie

    def _load_categories(self) -> Dict[str, List[str]]:
        if self._categories is None:
            cat_path = os.path.normpath(_CAT_FILE)
            if os.path.isfile(cat_path):
                with open(cat_path, encoding="utf-8") as fh:
                    self._categories = json.load(fh)
            else:
                self._categories = {}
        return self._categories

    # ── Public API ────────────────────────────────────────────────────────

    @lru_cache(maxsize=65536)
    def is_stop(
        self,
        word: str,
        dialect: Optional[str] = None,
        is_arabizi: bool = False,
        is_internet: bool = False,
    ) -> bool:
        """Return *True* when *word* is a stop word in the requested scope.

        Parameters
        ----------
        word:       The word to check (case-sensitive, already normalised).
        dialect:    If given, checks MSA + *that* dialect only.  When omitted,
                    the full universal set (all dialects combined) is used.
                    This means ``is_stop("كده", dialect="EGY")`` returns
                    *True* while ``is_stop("كده", dialect="GLF")`` returns
                    *False* because "كده" is an Egyptian-only word.
        is_arabizi: If *True*, only check the Arabizi trie.
        is_internet:If *True*, only check the internet-tokens trie.
        """
        if is_arabizi:
            return word in self._load_arabizi()
        if is_internet:
            return word in self._load_internet()

        if dialect:
            # Dialect-scoped check: MSA base + that specific dialect only
            if word in self._load_msa():
                return True
            if word in self._load_dialect(dialect):
                return True
            return False

        # No dialect specified → use the full universal set
        return word in self._load_universal()

    def get_words(
        self,
        scope: str = "universal",
        dialects: Optional[FrozenSet[str]] = None,
    ) -> Set[str]:
        """Return the stop-words set for the requested *scope*.

        Parameters
        ----------
        scope:    ``"universal"`` | ``"msa"`` | ``"dialect"`` | ``"filler"``
                  | ``"social"`` | ``"arabizi"`` | ``"internet"`` | ``"numbers"``
        dialects: Dialect codes used when *scope* is ``"dialect"``.
        """
        scope = scope.lower()
        if scope in ("universal", "all"):
            return self._load_universal().words()
        if scope == "msa":
            return self._load_msa().words()
        if scope in ("dialect", "dialect_aware"):
            result: Set[str] = self._load_msa().words()
            for code in dialects or frozenset():
                result |= self._load_dialect(code).words()
            return result
        if scope == "filler":
            return self._load_filler().words()
        if scope == "social":
            return self._load_social().words()
        if scope == "arabizi":
            return self._load_arabizi().words()
        if scope == "internet":
            return self._load_internet().words()
        if scope == "numbers":
            return self._load_numbers().words()
        return set()

    def get_by_category(self, category: str) -> Set[str]:
        """Return all stop words belonging to *category*.

        Categories: ``prepositions``, ``pronouns``, ``conjunctions``,
        ``interrogatives``, ``demonstratives``, ``relative_pronouns``,
        ``negation``, ``emphasis``, ``particles``, ``adverbs``,
        ``filler``, ``social_media``, ``internet``, ``arabizi``, ``numbers``.
        """
        cats = self._load_categories()
        return set(cats.get(category, []))

    def get_stats(self) -> Dict[str, int]:
        """Return word counts per loaded list."""
        stats = {
            "total_universal": len(self._load_universal().words()),
            "msa": len(self._load_msa().words()),
            "filler": len(self._load_filler().words()),
            "social_media": len(self._load_social().words()),
            "arabizi": len(self._load_arabizi().words()),
            "internet": len(self._load_internet().words()),
            "numbers": len(self._load_numbers().words()),
        }
        for code in _DIALECT_FILE_MAP:
            stats[code.lower()] = len(self._load_dialect(code).words())
        return stats

    def add_custom(self, words: Set[str]) -> None:
        """Insert additional words into the universal trie at runtime."""
        trie = self._load_universal()
        for w in words:
            trie.insert(w)
        # Invalidate lru_cache since the trie changed
        self.is_stop.cache_clear()

    def get_all_dialects(self) -> Dict[str, Set[str]]:
        """Return per-dialect stop-word sets."""
        return {code: self._load_dialect(code).words() for code in _DIALECT_FILE_MAP}
