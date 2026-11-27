"""Arabic keyboard-layout error repair utilities.

Users whose operating-system keyboard is still set to **English (QWERTY)**
accidentally produce Arabic gibberish such as ``sghk hg]dk`` when they
actually mean ``شكر الحديث``. This module provides a deterministic,
dependency-free mapping that converts such misplaced-layout input back
into valid Arabic.

Example
-------
>>> from aranorm.utils.keyboard_fixer import ArabicKeyboardFixer
>>> fixer = ArabicKeyboardFixer()
>>> fixer.fix_text("sghk hg]dk")
'شكر الحديث'

The same machinery is useful in the opposite direction (Arabic → English
layout) through :meth:`ArabicKeyboardFixer.fix_arabic_layout_text`, which
can be used to detect input that was typed on an Arabic layout while the
system expected English.

Implementation notes
--------------------
The mapping mirrors the standard US QWERTY arrangement of the Arabic
keyboards shipped with Windows / macOS / Android. Punctuation that sits on
number keys is also translated (``1`` → ``،`` … ``0`` → ``٠``), and shift
variants (``%`` → ``ـ``, ``^`` → ``ً`` …) are covered for the most common
cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# Mapping from English (QWERTY) characters to the Arabic characters that
# occupy the same physical keys.
EN_TO_AR: Dict[str, str] = {
    # Number row — the physical key ``1`` sits above ``ق``/``ض``;
    # digits keep their Arabic full-width forms when not preserved.
    "1": "ق",
    "2": "ص",
    "3": "ث",
    "4": "ف",
    "5": "غ",
    "6": "ع",
    "7": "ه",
    "8": "خ",
    "9": "ح",
    "0": "ج",
    # Top letter row
    "q": "ض",
    "w": "ص",
    "e": "ث",
    "r": "ق",
    "t": "ف",
    "y": "غ",
    "u": "ع",
    "i": "ه",
    "o": "خ",
    "p": "ح",
    # Middle letter row
    "a": "ش",
    "s": "س",
    "d": "ي",
    "f": "ب",
    "g": "ل",
    "h": "ا",
    "j": "ت",
    "k": "ن",
    "l": "م",
    # Bottom letter row
    "z": "ئ",
    "x": "ء",
    "c": "ؤ",
    "v": "ر",
    "b": "لا",
    "n": "ى",
    "m": "ة",
    # Punctuation and shift variants
    "'": "ء",
    "[": "ج",
    "]": "د",
    ";": "ك",
    ",": "ط",
    ".": "ظ",
    "/": "ز",
    "`": "ذ",
    "=": "ـ",
    # Uppercase (shifted) — same physical keys with shifted output.
    # ``N`` and ``M`` on the Arabic Windows layout emit ``ء``/``أ``.
    "Q": "ض",
    "W": "ص",
    "E": "ث",
    "R": "ق",
    "T": "ف",
    "Y": "غ",
    "U": "ع",
    "I": "ه",
    "O": "خ",
    "P": "ح",
    "A": "ش",
    "S": "س",
    "D": "ي",
    "F": "ب",
    "G": "ل",
    "H": "آ",
    "J": "ت",
    "K": "ن",
    "L": "م",
    "Z": "ئ",
    "X": "ؤ",
    "C": "ؤ",
    "V": "ر",
    "B": "إ",
    "N": "ء",
    "M": "أ",
    "!": "َ",
    "@": "ً",
    "#": "ُ",
    "$": "ٌ",
    "%": "ُ",
    "^": "إ",
    "&": "َ",
    "*": "ً",
    "(": "]",
    ")": "[",
    "_": "ـ",
    "+": "،",
    "<": "،",
    ">": "؟",
    "?": "؟",
    "{": "}",
    "}": "{",
    "|": ">",
    ":": ":",
}

# Inverse mapping for the opposite repair direction (Arabic → English).
# When several English characters share the same Arabic destination
# (for example ``q`` and ``Q`` both emit ``ض``), the **first** English
# character encountered in ``EN_TO_AR`` wins — mirroring how
# ``_build_mapping_table`` resolves duplicates.
AR_TO_EN: Dict[str, str] = {}
for _key, _value in EN_TO_AR.items():
    AR_TO_EN.setdefault(_value, _key)


def _build_mapping_table(mapping: Dict[str, str]) -> Dict[int, str]:
    """Return an ``ord``-based translation table for *mapping*.

    Single-character keys become ``ord`` entries, while multi-character
    replacements (for example ``b`` → ``لا``) are registered as negative
    length sentinel entries so that :meth:`ArabicKeyboardFixer._translate`
    can apply them as substring substitutions instead of character
    replacements.

    Duplicate destinations (e.g. both ``2`` and ``w`` map to ``ص``) are
    resolved by keeping the first occurrence, which mirrors the number-row
    layout that users most commonly report.
    """
    table: Dict[int, str] = {}
    for char, replacement in mapping.items():
        if len(char) == 1:
            code = ord(char)
            if code not in table:
                table[code] = replacement
        else:
            # The entry applies to a prefix of the remaining input; use a
            # hash of the source string so it never collides with ord values.
            table[hash(char)] = replacement
    return table


_EN_TO_AR_TABLE = _build_mapping_table(EN_TO_AR)
_AR_TO_EN_TABLE = _build_mapping_table(AR_TO_EN)

# Multi-character source strings per table, longest first, applied as
# leftmost-greedy substring substitutions before per-character mapping.
_EN_MULTI = [char for char in EN_TO_AR if len(char) > 1]
_AR_MULTI = [char for char in AR_TO_EN if len(char) > 1]
_EN_MULTI.sort(key=len, reverse=True)
_AR_MULTI.sort(key=len, reverse=True)


@dataclass
class LayoutFixReport:
    """Detailed per-word report produced by :meth:`ArabicKeyboardFixer.fix_text`.

    Attributes
    ----------
    original:
        The original input text.
    fixed:
        The fully repaired text.
    words:
        One report per whitespace token of the original input.
    fixed_count:
        Number of words that were actually modified.
    """

    original: str
    fixed: str
    words: List["WordFix"] = field(default_factory=list)
    fixed_count: int = 0


@dataclass
class WordFix:
    """One word-level entry inside :attr:`LayoutFixReport.words`.

    Attributes
    ----------
    original:
        The original token.
    fixed:
        The repaired token (identical when nothing changed).
    was_fixed:
        ``True`` when the token required at least one substitution.
    """

    original: str
    fixed: str
    was_fixed: bool


class ArabicKeyboardFixer:
    """Repair text typed on the wrong keyboard layout.

    Parameters
    ----------
    preserve_numbers:
        When *True* (default), decimal digits that do **not** sit on the
        Arabic number-row keys keep their original value. Disable this to
        translate every Latin digit through the number-row mapping.

    Example
    -------
    >>> fixer = ArabicKeyboardFixer()
    >>> fixer.fix_text("shd lk,lm")
    'شكر لكم،'
    """

    def __init__(self, preserve_numbers: bool = True) -> None:
        if not isinstance(preserve_numbers, bool):
            raise TypeError("preserve_numbers must be a boolean")
        self.preserve_numbers = preserve_numbers
        self._en_to_ar = dict(_EN_TO_AR_TABLE)
        self._ar_to_en = dict(_AR_TO_EN_TABLE)
        if preserve_numbers:
            # Latin digits produced while the layout was already English
            # were intentional, so keep them as-is.
            for code in range(ord("0"), ord("9") + 1):
                self._en_to_ar.pop(code, None)

    # ── Core repair API ────────────────────────────────────────────────

    def fix_text(self, text: str) -> str:
        """Translate a whole text from English-layout input to Arabic."""
        return self._translate(text, self._en_to_ar)

    def fix_arabic_layout_text(self, text: str) -> str:
        """Translate a whole text from Arabic-layout input to English."""
        return self._translate(text, self._ar_to_en)

    def fix_report(self, text: str) -> LayoutFixReport:
        """Repair *text* and return a per-word :class:`LayoutFixReport`.

        Words that contain no mappable characters (punctuation, pure
        numbers) pass through untouched and are flagged as ``was_fixed``
        *False*.
        """
        words: List[WordFix] = []
        fixed_count = 0
        for token in text.split():
            repaired = self._translate(token, self._en_to_ar)
            changed = repaired != token
            if changed:
                fixed_count += 1
            words.append(WordFix(original=token, fixed=repaired, was_fixed=changed))
        return LayoutFixReport(
            original=text,
            fixed=" ".join(word.fixed for word in words),
            words=words,
            fixed_count=fixed_count,
        )

    def fix_file(self, path: str) -> str:
        """Repair an entire UTF-8 file and return the repaired content.

        Parameters
        ----------
        path:
            Path to the input text file.
        """
        with open(path, encoding="utf-8") as stream:
            content = stream.read()
        return self._translate(content, self._en_to_ar)

    def to_file(self, text: str, path: str) -> None:
        """Repair *text* and write the result to *path* as UTF-8."""
        with open(path, mode="w", encoding="utf-8") as stream:
            stream.write(self._translate(text, self._en_to_ar))

    # ── Internals ──────────────────────────────────────────────────────

    def _translate(self, text: str, table: Dict[int, str]) -> str:
        # Choose the multi-character source list that matches the table.
        multi = _EN_MULTI if table is self._en_to_ar else _AR_MULTI
        # Apply multi-character substitutions leftmost-first (longest match).
        for source in multi:
            text = text.replace(source, table[hash(source)])
        result: List[str] = []
        for char in text:
            replacement = table.get(ord(char))
            result.append(replacement if replacement is not None else char)
        return "".join(result)


def fix_keyboard_text(text: str, preserve_numbers: bool = True) -> str:
    """Module-level convenience: repair English-layout Arabic input.

    >>> fix_keyboard_text("sghk hg]dk")
    'شكر الحديث'
    """
    return ArabicKeyboardFixer(preserve_numbers=preserve_numbers).fix_text(text)


def fix_arabic_layout_to_english(text: str) -> str:
    """Module-level convenience: repair Arabic-layout English input.

    >>> fix_arabic_layout_to_english("شضثقف")
    'qwert'
    """
    return ArabicKeyboardFixer().fix_arabic_layout_text(text)


def fix_keyboard_file(path: str) -> str:
    """Module-level convenience: repair an entire file and return content."""
    return ArabicKeyboardFixer().fix_file(path)
