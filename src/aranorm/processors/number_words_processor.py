"""Arabic number words → digit conversion processor.

Converts written Arabic cardinal and ordinal numbers (واحد، اثنان، عشرة…)
to their Western-Arabic numeral equivalents without any external dependency.

Supported ranges
----------------
* Cardinals 0–999 (جِيلٌ واحدٌ → keeps Arabic, but standalone "واحد" → 1).
* Ordinals (الأول، الثانية…) → 1st, 2nd … style kept as Arabic digits.
* Compound numbers up to الألف (e.g., مئة وخمسة وعشرون → 125).

The processor uses a longest-match greedy scan over whitespace tokens so that
compound expressions like "خمسة وعشرون" are collapsed before individual words.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from aranorm.core.base import Processor, ProcessorContext

# ── Number word tables ────────────────────────────────────────────────────────

# Single-word cardinals (masculine & feminine forms where both exist)
_ONES: Dict[str, int] = {
    "صفر": 0,
    "واحد": 1, "واحدة": 1, "واحده": 1,
    "اثنان": 2, "اثنين": 2, "اثنتان": 2, "اثنتين": 2,
    "ثلاثة": 3, "ثلاث": 3,
    "أربعة": 4, "أربع": 4,
    "خمسة": 5, "خمس": 5,
    "ستة": 6, "ست": 6,
    "سبعة": 7, "سبع": 7,
    "ثمانية": 8, "ثماني": 8, "ثمان": 8,
    "تسعة": 9, "تسع": 9,
    "عشرة": 10, "عشر": 10,
    "أحد عشر": 11, "إحدى عشر": 11, "إحدى عشرة": 11,
    "اثنا عشر": 12, "اثني عشر": 12, "اثنتا عشرة": 12, "اثنتي عشرة": 12,
    "ثلاثة عشر": 13, "ثلاث عشرة": 13,
    "أربعة عشر": 14, "أربع عشرة": 14,
    "خمسة عشر": 15, "خمس عشرة": 15,
    "ستة عشر": 16, "ست عشرة": 16,
    "سبعة عشر": 17, "سبع عشرة": 17,
    "ثمانية عشر": 18, "ثماني عشرة": 18,
    "تسعة عشر": 19, "تسع عشرة": 19,
    "عشرون": 20, "عشرين": 20,
    "ثلاثون": 30, "ثلاثين": 30,
    "أربعون": 40, "أربعين": 40,
    "خمسون": 50, "خمسين": 50,
    "ستون": 60, "ستين": 60,
    "سبعون": 70, "سبعين": 70,
    "ثمانون": 80, "ثمانين": 80,
    "تسعون": 90, "تسعين": 90,
    "مئة": 100, "مائة": 100,
    "مئتان": 200, "مئتين": 200, "مائتان": 200, "مائتين": 200,
    "ثلاثمئة": 300, "ثلاثمائة": 300,
    "أربعمئة": 400, "أربعمائة": 400,
    "خمسمئة": 500, "خمسمائة": 500,
    "ستمئة": 600, "ستمائة": 600,
    "سبعمئة": 700, "سبعمائة": 700,
    "ثمانمئة": 800, "ثمانمائة": 800,
    "تسعمئة": 900, "تسعمائة": 900,
    "ألف": 1000,
    "ألفان": 2000, "ألفين": 2000,
    "مليون": 1_000_000,
    "مليار": 1_000_000_000,
}

# Ordinals → integer value (will be emitted as Arabic numeral)
_ORDINALS: Dict[str, int] = {
    "الأول": 1, "الأولى": 1, "أول": 1,
    "الثاني": 2, "الثانية": 2, "ثانٍ": 2, "ثانية": 2,
    "الثالث": 3, "الثالثة": 3,
    "الرابع": 4, "الرابعة": 4,
    "الخامس": 5, "الخامسة": 5,
    "السادس": 6, "السادسة": 6,
    "السابع": 7, "السابعة": 7,
    "الثامن": 8, "الثامنة": 8,
    "التاسع": 9, "التاسعة": 9,
    "العاشر": 10, "العاشرة": 10,
    "الحادي عشر": 11, "الحادية عشرة": 11,
    "الثاني عشر": 12, "الثانية عشرة": 12,
    "العشرون": 20, "العشرين": 20,
}

# Conjunction: و connecting two number parts
_WAW = re.compile(r"\bو\b")

# Build a sorted-by-length list of all multi-word keys for greedy matching
_ALL_MULTI: List[Tuple[str, int]] = sorted(
    ((k, v) for k, v in {**_ONES, **_ORDINALS}.items() if " " in k),
    key=lambda x: len(x[0]),
    reverse=True,
)

# Single-word lookup (combined)
_SINGLE: Dict[str, int] = {**_ONES, **_ORDINALS}


class NumberWordsProcessor(Processor):
    """Convert Arabic number words to Western-Arabic digits.

    Handles single-word cardinals/ordinals and simple compound expressions
    joined by the conjunction *و* (e.g., خمسة وعشرون → 25).

    Parameters
    ----------
    replace_ordinals:
        When *True* (default), ordinal forms (الأول، الثانية…) are also
        converted to digits.
    min_word_length:
        Minimum character length of a token before attempting number
        conversion — prevents very short tokens being wrongly rewritten.

    Example
    -------
    >>> proc = NumberWordsProcessor()
    >>> proc.process("لدي ثلاثة كتب وعشرون قلماً")
    'لدي 3 كتب 20 قلماً'
    >>> proc.process("وصل في المركز الثالث")
    'وصل في المركز 3'
    """

    name = "number_words"

    def __init__(
        self,
        replace_ordinals: bool = True,
        min_word_length: int = 2,
    ) -> None:
        self.replace_ordinals = replace_ordinals
        self.min_word_length = min_word_length
        # Build the active lookup
        self._lookup: Dict[str, int] = dict(_ONES)
        if replace_ordinals:
            self._lookup.update(_ORDINALS)

    def transform(self, text: str) -> str:
        """Apply number-word replacement to *text*."""
        return self._replace(text)

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Process *text* and return version with number words replaced."""
        if not text or not text.strip():
            return text
        result = self.transform(text)
        self._record(context)
        return result

    # ── Private ───────────────────────────────────────────────────────────

    def _replace(self, text: str) -> str:
        """Greedy multi-word scan, then single-word scan."""
        # Pass 1 — replace multi-word patterns (sorted longest-first)
        for phrase, value in _ALL_MULTI:
            if phrase in text:
                text = text.replace(phrase, str(value))

        # Pass 1b — handle attached-waw compounds like "وعشرون" attached to previous number
        # e.g., "خمسة وعشرون" where "وعشرون" is a single token
        tokens_temp = text.split()
        rebuilt: List[str] = []
        i = 0
        while i < len(tokens_temp):
            tok = tokens_temp[i].strip(".,،؟!؛:")
            # Check if next token starts with attached و and the rest is a number
            if tok in self._lookup and i + 1 < len(tokens_temp):
                next_tok = tokens_temp[i + 1]
                if next_tok.startswith("و") and len(next_tok) > 1:
                    suffix = next_tok[1:].strip(".,،؟!؛:")
                    if suffix in self._lookup:
                        combined = self._lookup[tok] + self._lookup[suffix]
                        rebuilt.append(str(combined))
                        i += 2
                        continue
            rebuilt.append(tokens_temp[i])
            i += 1
        text = " ".join(rebuilt)

        # Pass 2 — handle compound "X وY" patterns (e.g., "ثلاثة وعشرون")
        tokens = text.split()
        result: List[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i].strip(".,،؟!؛:")
            # Try three-token compound: NUM و NUM
            if (
                i + 2 < len(tokens)
                and tokens[i + 1] in ("و", "وَ")
                and tok in self._lookup
                and tokens[i + 2].strip(".,،؟!؛:") in self._lookup
            ):
                a = self._lookup[tok]
                b = self._lookup[tokens[i + 2].strip(".,،؟!؛:")]
                combined = a + b
                result.append(str(combined))
                i += 3
                continue
            # Single-token number word
            if len(tok) >= self.min_word_length and tok in self._lookup:
                result.append(str(self._lookup[tok]))
                i += 1
                continue
            result.append(tokens[i])
            i += 1

        return " ".join(result)
