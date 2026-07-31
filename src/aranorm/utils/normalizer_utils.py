"""Standalone normalization utility functions.

Provides a set of pure functions for common Arabic text normalization tasks
that can be used independently of the pipeline, as well as helper decorators
and caching utilities for processor authors.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import List

# Arabic ranges
_ARABIC_RANGE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_ALEF_VARIANTS = re.compile(r"[أإآٱ]")
_WHITESPACE_RE = re.compile(r"\s+")


@lru_cache(maxsize=65536)
def normalize_alef(word: str) -> str:
    """Normalize all alef variants (أإآٱ) to bare alef (ا).

    Example
    -------
    >>> normalize_alef("أحمد")
    'احمد'
    """
    return _ALEF_VARIANTS.sub("ا", word)


@lru_cache(maxsize=65536)
def remove_diacritics(text: str) -> str:
    """Strip all Arabic diacritical marks (harakat, shadda, sukun, tatweel).

    Example
    -------
    >>> remove_diacritics("مَرْحَبًا")
    'مرحبا'
    """
    return _DIACRITICS.sub("", text)


@lru_cache(maxsize=65536)
def normalize_unicode(text: str) -> str:
    """Apply Unicode NFKC normalization (composition + compatibility).

    Example
    -------
    >>> normalize_unicode("ﻛﺘﺐ")  # presentation forms
    'كتب'
    """
    return unicodedata.normalize("NFKC", text)


def collapse_whitespace(text: str) -> str:
    """Collapse multiple consecutive whitespace characters into a single space.

    Example
    -------
    >>> collapse_whitespace("أنا   طالب")
    'أنا طالب'
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


def is_arabic_text(text: str, threshold: float = 0.5) -> bool:
    """Return True when more than *threshold* fraction of characters are Arabic.

    Parameters
    ----------
    text:
        Input string.
    threshold:
        Arabic character fraction required (0.0–1.0, default 0.5).

    Example
    -------
    >>> is_arabic_text("مرحبا hello")
    True
    """
    if not text:
        return False
    arabic_count = len(_ARABIC_RANGE.findall(text))
    non_space = len(text.replace(" ", ""))
    if non_space == 0:
        return False
    return (arabic_count / non_space) >= threshold


def strip_punctuation(text: str) -> str:
    """Strip Arabic and Latin punctuation from text boundaries.

    Example
    -------
    >>> strip_punctuation("؟ النص الجميل!")
    'النص الجميل'
    """
    return text.strip(".,،؟!؛:()[]{}\"'«»\u2018\u2019\u201C\u201D-–—")


def truncate_repeated_chars(text: str, max_run: int = 2) -> str:
    """Reduce runs of the same character to at most *max_run* repetitions.

    Example
    -------
    >>> truncate_repeated_chars("يااااا سلام", max_run=2)
    'يا سلام'
    """
    pattern = re.compile(r"(.)\1{" + str(max_run) + r",}")
    return pattern.sub(r"\1" * max_run, text)


def count_arabic_words(text: str) -> int:
    """Return the number of Arabic-script word tokens in *text*.

    Example
    -------
    >>> count_arabic_words("مرحبا hello world")
    1
    """
    return sum(1 for t in text.split() if _ARABIC_RANGE.search(t))


def extract_arabic_words(text: str) -> List[str]:
    """Return a list of Arabic-script tokens from *text*.

    Example
    -------
    >>> extract_arabic_words("مرحبا hello سلام world")
    ['مرحبا', 'سلام']
    """
    return [t for t in text.split() if _ARABIC_RANGE.search(t)]


def char_ngrams(text: str, n: int = 3) -> List[str]:
    """Return all character n-grams of length *n* from *text*.

    Useful for fuzzy matching and language-model feature extraction.

    Parameters
    ----------
    text:
        Input string (spaces and punctuation included).
    n:
        N-gram length (default 3).

    Example
    -------
    >>> char_ngrams("كتاب", n=3)
    ['كتا', 'تاب']
    """
    if len(text) < n:
        return [text] if text else []
    return [text[i: i + n] for i in range(len(text) - n + 1)]


def word_ngrams(tokens: List[str], n: int = 2) -> List[str]:
    """Return all word-level n-grams of length *n* from *tokens*.

    Parameters
    ----------
    tokens:
        Pre-tokenised list of words.
    n:
        N-gram length (default 2 = bigrams).

    Example
    -------
    >>> word_ngrams(["أنا", "أحب", "اللغة"], n=2)
    ['أنا أحب', 'أحب اللغة']
    """
    if len(tokens) < n:
        return [" ".join(tokens)] if tokens else []
    return [" ".join(tokens[i: i + n]) for i in range(len(tokens) - n + 1)]


def levenshtein(s1: str, s2: str) -> int:
    """Compute the Levenshtein (edit) distance between two strings.

    Pure-Python O(m×n) implementation — sufficient for short Arabic words.

    Parameters
    ----------
    s1, s2:
        Input strings.

    Example
    -------
    >>> levenshtein("كتاب", "كتب")
    1
    """
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1, 1):
        curr = [i]
        for j, c2 in enumerate(s2, 1):
            curr.append(min(prev[j] + 1, curr[-1] + 1, prev[j - 1] + (0 if c1 == c2 else 1)))
        prev = curr
    return prev[-1]


def fuzzy_match(
    query: str,
    candidates: List[str],
    max_distance: int = 2,
) -> List[str]:
    """Return candidates whose Levenshtein distance to *query* is ≤ *max_distance*.

    Parameters
    ----------
    query:
        Reference word.
    candidates:
        List of candidate words.
    max_distance:
        Maximum edit distance (default 2).

    Example
    -------
    >>> fuzzy_match("كتاب", ["كتب", "كتاب", "اكتب"])
    ['كتاب', 'كتب']
    """
    return sorted(
        [c for c in candidates if levenshtein(query, c) <= max_distance],
        key=lambda c: levenshtein(query, c),
    )
