"""Rule-based Arabic trilateral root extractor.

Attempts to extract the three-letter (trilateral) root of an Arabic word
using pattern-matching against common Arabic verb and noun morphological
patterns (أوزان الصرفية).

Limitations
-----------
* Covers the 20 most productive trilateral patterns only.
* Does not handle quadrilateral roots.
* No disambiguation: the first matching pattern wins.
* This is a heuristic tool — for production-grade root extraction use
  CAMeL Tools or Farasa via the :class:`~aranorm.stages.morphological.MorphologicalProcessor`.

Usage
-----
>>> from aranorm.utils.root_extractor import extract_root
>>> extract_root("مكتبة")
'كتب'
>>> extract_root("يكتبون")
'كتب'
"""

from __future__ import annotations

import re
from typing import Any, Callable, List, Optional, Tuple

# ── Arabic letter inventory ────────────────────────────────────────────────────
_ARABIC_LETTER = re.compile(r"[\u0621-\u064A]")

# Root-letter placeholder: any Arabic consonant (not alef/waw/ya in most patterns)
_C = r"[\u0621-\u064A]"

# ── Pattern table ─────────────────────────────────────────────────────────────
# Each entry: (regex, root_extractor_fn)
# The regex must match the full word (after stripping diacritics).
# The extractor fn maps the regex groups to the three root consonants.

# fmt: off
_PATTERNS: List[Tuple[re.Pattern[str], Callable[[Any], Any]]] = [
    # فَعَلَ / يَفْعَلُ — basic verb stems
    (re.compile(r"^(" + _C + r")(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                  # فعل
    (re.compile(r"^ي(" + _C + r")(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                 # يفعل
    (re.compile(r"^ت(" + _C + r")(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                 # تفعل
    (re.compile(r"^أ(" + _C + r")(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                 # أفعل
    (re.compile(r"^ن(" + _C + r")(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                 # نفعل

    # Verb + plural / dual suffixes
    (re.compile(r"^ي(" + _C + r")(" + _C + r")(" + _C + r")ون$"), lambda m: m.group(1, 2, 3)),               # يفعلون
    (re.compile(r"^ي(" + _C + r")(" + _C + r")(" + _C + r")ان$"), lambda m: m.group(1, 2, 3)),               # يفعلان
    (re.compile(r"^(" + _C + r")(" + _C + r")(" + _C + r")وا$"), lambda m: m.group(1, 2, 3)),                # فعلوا

    # Masdar patterns: فِعَال، فُعُول، مَفْعَل
    (re.compile(r"^(" + _C + r")(" + _C + r")(" + _C + r")ات$"), lambda m: m.group(1, 2, 3)),                # فعلات  # noqa: E501
    (re.compile(r"^(" + _C + r")(" + _C + r")(" + _C + r")ة$"), lambda m: m.group(1, 2, 3)),                 # فعلة   # noqa: E501
    (re.compile(r"^م(" + _C + r")(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                 # مفعل   # noqa: E501
    (re.compile(r"^م(" + _C + r")(" + _C + r")(" + _C + r")ة$"), lambda m: m.group(1, 2, 3)),                # مفعلة  # noqa: E501
    (re.compile(r"^ا(" + _C + r")(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                 # افعل (imperative)
    (re.compile(r"^(" + _C + r")ا(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                 # فاعل (agent)
    (re.compile(r"^(" + _C + r")(" + _C + r")ا(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                 # فعال (masdar)
    (re.compile(r"^ت(" + _C + r")ا(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                # تفاعل
    (re.compile(r"^ان(" + _C + r")(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),                # انفعل
    (re.compile(r"^است(" + _C + r")(" + _C + r")(" + _C + r")$"), lambda m: m.group(1, 2, 3)),               # استفعل
    (re.compile(r"^(" + _C + r")(" + _C + r")(" + _C + r")ي$"), lambda m: m.group(1, 2, 3)),                 # فعلي (nisba)
    (re.compile(r"^(" + _C + r")(" + _C + r")(" + _C + r")ين$"), lambda m: m.group(1, 2, 3)),                # فعلين
]
# fmt: on

# Diacritics and hamza-on-alef normalisation before pattern matching
_DIACRITICS_RE = re.compile(r"[\u064B-\u0652\u0640\u0670]")
_HAMZA_RE = re.compile(r"[أإآٱ]")


def _preprocess(word: str) -> str:
    """Strip diacritics and normalize alef variants for pattern matching."""
    word = _DIACRITICS_RE.sub("", word)
    word = _HAMZA_RE.sub("ا", word)
    return word.strip(".,،؟!؛:")


class RootExtractor:
    """Heuristic trilateral Arabic root extractor.

    Example
    -------
    >>> extractor = RootExtractor()
    >>> extractor.extract("مكتبة")
    'كتب'
    >>> extractor.extract("يكتبون")
    'كتب'
    >>> extractor.extract("استخرج")
    'خرج'
    """

    def __init__(self) -> None:
        self._patterns = _PATTERNS

    def extract(self, word: str) -> Optional[str]:
        """Extract the trilateral root of *word*, or return *None* if unknown.

        Parameters
        ----------
        word:
            A single Arabic word (may contain diacritics).

        Returns
        -------
        str or None
            Three-letter root string, or *None* if no pattern matched.
        """
        if not word or not _ARABIC_LETTER.search(word):
            return None
        normalized = _preprocess(word)
        for pattern, extractor in self._patterns:
            m = pattern.fullmatch(normalized)
            if m:
                root_letters = extractor(m)
                root = "".join(root_letters)
                if len(root) == 3 and all("\u0621" <= c <= "\u064a" for c in root):
                    return root
        return None

    def extract_batch(self, words: List[str]) -> List[Optional[str]]:
        """Extract roots for a list of words."""
        return [self.extract(w) for w in words]


# ── Module-level convenience ──────────────────────────────────────────────────

_DEFAULT_EXTRACTOR = RootExtractor()


def extract_root(word: str) -> Optional[str]:
    """Extract the trilateral root of a single Arabic *word*.

    Convenience wrapper around :class:`RootExtractor`.

    Parameters
    ----------
    word:
        A single Arabic word (diacritics allowed).

    Returns
    -------
    str or None
        Three-letter root, or *None* if no pattern matched.

    Example
    -------
    >>> from aranorm.utils.root_extractor import extract_root
    >>> extract_root("مكتبة")
    'كتب'
    """
    return _DEFAULT_EXTRACTOR.extract(word)
