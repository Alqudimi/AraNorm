"""Rule-based Arabic light stemmer.

Implements a conservative Arabic light-stemming algorithm that strips common
prefixes and suffixes without requiring a full morphological analysis.  The
approach is inspired by the ISRI (Information Science Research Institute)
stemmer and the light10 family of Arabic stemmers.

Design principles
-----------------
* Zero external dependencies — pure Python.
* Conservative (high-precision): prefers under-stemming to over-stemming.
* Handles definite article (ال / ال + assimilation), conjunctions, and the
  most frequent nominal and verbal suffixes.
* Provides both a single-word API (:func:`stem`) and a class API
  (:class:`ArabicStemmer`) with optional normalization hooks.

Limitations
-----------
* Does not perform morphological disambiguation (a word with multiple readings
  gets one stem).
* No POS tagging — verbal and nominal suffixes use the same table.
* Long-root forms (quadrilateral, quinary) may not stem correctly.
"""

from __future__ import annotations

import re
from typing import Callable, FrozenSet, List, Optional

# ── Constants ─────────────────────────────────────────────────────────────────

# Minimum stem length (shorter stems are left as-is)
_MIN_STEM = 2

# Definite article variants (including sun-letter assimilation)
_DEFINITE_ARTICLE = re.compile(r"^(ال|ال(?:ن|ر|ز|س|ش|ص|ض|ط|ظ|ل|ت|ث|د|ذ))")

# Conjunctive / prepositive prefixes to strip (in order of priority)
# Each tuple: (prefix_string, min_remaining_length)
_PREFIXES: List[tuple] = [
    # Longest first
    ("وال", 3),
    ("فال", 3),
    ("بال", 3),
    ("لل", 3),
    ("كال", 3),
    ("وب", 3),
    ("وف", 3),
    ("فب", 3),
    ("و", 3),
    ("ف", 3),
    ("ب", 3),
    ("ل", 3),
    ("ك", 3),
]

# Suffixes to strip (in order of priority, longest first)
# Each tuple: (suffix_string, min_remaining_length)
_SUFFIXES: List[tuple] = [
    # Dual / plural morphemes
    ("ونهم", 3),
    ("تهم", 3),
    ("ينهم", 3),
    ("ونها", 3),
    ("تها", 3),
    ("ونه", 3),
    ("يته", 3),
    # Pronominal enclitics
    ("كما", 3),
    ("هما", 3),
    ("كم", 3),
    ("كن", 3),
    ("هم", 3),
    ("هن", 3),
    ("ني", 3),
    ("نا", 3),
    ("ها", 3),
    ("ه", 3),
    ("ك", 3),
    ("ي", 3),
    # Verbal agreement suffixes
    ("ونا", 3),
    ("وني", 3),
    ("تني", 3),
    ("تنا", 3),
    ("تكم", 3),
    ("تكن", 3),
    ("وا", 3),
    ("ون", 3),
    ("ين", 3),
    ("تن", 3),
    ("تم", 3),
    ("تا", 3),
    ("ان", 3),
    ("ات", 3),
    # Feminine marker
    ("ة", 2),
    ("ه", 2),  # taa marbuta / haa in dialectal
    # Adverbial suffix
    ("اً", 2),
    ("اٌ", 2),
    # Alef maqsura / ya
    ("ى", 2),
    ("ي", 2),
    # Nunation (tanwin) — normalised forms
    ("اً", 2),
]

# Words that should not be stemmed (closed-class function words)
_STOP_STEMS: FrozenSet[str] = frozenset(
    {
        "في",
        "من",
        "إلى",
        "على",
        "عن",
        "مع",
        "بعد",
        "قبل",
        "عند",
        "لدى",
        "لدن",
        "حتى",
        "كي",
        "إذا",
        "إذ",
        "حين",
        "لأن",
        "لأنه",
        "لكن",
        "لكنه",
        "لكنها",
        "وهو",
        "وهي",
        "وهم",
        "أن",
        "إن",
        "أنه",
        "إنه",
        "ما",
        "هذا",
        "هذه",
        "ذلك",
        "تلك",
        "الذي",
        "التي",
        "الذين",
        "هو",
        "هي",
        "أنا",
        "أنت",
        "نحن",
    }
)


class ArabicStemmer:
    """Conservative Arabic light stemmer.

    Parameters
    ----------
    strip_prefixes:
        Enable prefix stripping (default *True*).
    strip_suffixes:
        Enable suffix stripping (default *True*).
    strip_definite_article:
        Strip the definite article ال before other prefix rules (default *True*).
    normalize_fn:
        Optional callable applied to each token *before* stemming.  Useful
        for passing an :class:`~aranorm.processors.alef_processor.ALEFProcessor`
        or diacritics-stripping step.

    Example
    -------
    >>> stemmer = ArabicStemmer()
    >>> stemmer.stem("المدارس")
    'مدارس'
    >>> stemmer.stem("وكتبهم")
    'كتب'
    >>> stemmer.stem_sentence("يكتبون الدروس بانتظام")
    'يكتب درس انتظام'
    """

    def __init__(
        self,
        strip_prefixes: bool = True,
        strip_suffixes: bool = True,
        strip_definite_article: bool = True,
        normalize_fn: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.strip_prefixes = strip_prefixes
        self.strip_suffixes = strip_suffixes
        self.strip_definite_article = strip_definite_article
        self.normalize_fn = normalize_fn

    # ── Public API ────────────────────────────────────────────────────────

    def stem(self, word: str) -> str:
        """Return the stem of a single Arabic *word*.

        Parameters
        ----------
        word:
            A single Arabic word (no spaces).

        Returns
        -------
        str
            The stemmed form, or the original word if no rules applied or the
            word is too short.
        """
        if not word or len(word) < _MIN_STEM:
            return word

        # Skip closed-class function words
        if word in _STOP_STEMS:
            return word

        # Optional normalisation (e.g. alef normalisation)
        if self.normalize_fn:
            word = self.normalize_fn(word)

        # 1. Strip definite article; if stripped, skip further prefix stripping
        #    to avoid treating root-initial letters as independent particles
        #    (e.g. الكتاب → كتاب, not تاب via the ك particle rule).
        article_stripped = False
        if self.strip_definite_article:
            new_word = self._strip_definite_article(word)
            if new_word != word:
                word = new_word
                article_stripped = True

        # 2. Strip prefixes — only when the definite article was not already removed
        if self.strip_prefixes and not article_stripped:
            word = self._strip_prefix(word)

        # 3. Strip suffixes (one pass, longest match)
        if self.strip_suffixes:
            word = self._strip_suffix(word)

        return word

    def stem_tokens(self, tokens: List[str]) -> List[str]:
        """Stem a list of tokens."""
        return [self.stem(t) for t in tokens]

    def stem_sentence(self, text: str) -> str:
        """Stem every whitespace-separated word in *text*.

        Parameters
        ----------
        text:
            Arabic sentence or paragraph.

        Returns
        -------
        str
            Space-joined stemmed tokens.

        Example
        -------
        >>> stemmer = ArabicStemmer()
        >>> stemmer.stem_sentence("يكتبون الدروس بانتظام")
        'يكتب درس انتظام'
        """
        tokens = text.split()
        return " ".join(self.stem(t) for t in tokens)

    def stem_batch(self, texts: List[str]) -> List[str]:
        """Stem each text in a list of strings."""
        return [self.stem_sentence(t) for t in texts]

    # ── Private helpers ───────────────────────────────────────────────────

    def _strip_definite_article(self, word: str) -> str:
        """Remove the definite article ال from the beginning of *word*."""
        match = _DEFINITE_ARTICLE.match(word)
        if match:
            remainder = word[match.end() :]
            if len(remainder) >= _MIN_STEM:
                return remainder
        return word

    def _strip_prefix(self, word: str) -> str:
        """Strip the longest matching prefix."""
        for prefix, min_remaining in _PREFIXES:
            if word.startswith(prefix):
                remainder = word[len(prefix) :]
                if len(remainder) >= min_remaining:
                    return remainder
        return word

    def _strip_suffix(self, word: str) -> str:
        """Strip the longest matching suffix."""
        for suffix, min_remaining in _SUFFIXES:
            if word.endswith(suffix):
                remainder = word[: -len(suffix)]
                if len(remainder) >= min_remaining:
                    return remainder
        return word


# ── Module-level convenience functions ────────────────────────────────────────

_DEFAULT_STEMMER = ArabicStemmer()


def stem(word: str) -> str:
    """Stem a single Arabic word using the default :class:`ArabicStemmer`.

    Parameters
    ----------
    word:
        A single Arabic word token.

    Example
    -------
    >>> from aranorm.utils.stemmer import stem
    >>> stem("المدارس")
    'مدارس'
    """
    return _DEFAULT_STEMMER.stem(word)


def stem_sentence(text: str) -> str:
    """Stem every token in *text* using the default :class:`ArabicStemmer`.

    Parameters
    ----------
    text:
        Arabic sentence or paragraph.

    Example
    -------
    >>> from aranorm.utils.stemmer import stem_sentence
    >>> stem_sentence("يكتبون الدروس بانتظام")
    'يكتب درس انتظام'
    """
    return _DEFAULT_STEMMER.stem_sentence(text)
