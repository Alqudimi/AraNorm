"""Sentence-level and text-level normalization helpers.

Contains processors that work at a higher granularity than individual
character transformations:

* :class:`SentenceNormalizerProcessor` — normalize spacing, capitalization
  artefacts, and mixed-direction issues within Arabic sentences.
* :class:`RedundancyProcessor` — collapse redundant whitespace and
  normalize zero-width / invisible characters.
"""

from __future__ import annotations

import re
from typing import Optional

from aranorm.core.base import Processor, ProcessorContext

# ── Patterns ──────────────────────────────────────────────────────────────────

# Zero-width and invisible Unicode characters that often appear in scraped text
_INVISIBLE = re.compile(
    r"[\u200B\u200C\u200D\u200E\u200F"  # ZW space, ZW non-joiner/joiner, LRM, RLM
    r"\u202A\u202B\u202C\u202D\u202E"  # embedding / override / pop
    r"\u2060\u2061\u2062\u2063\u2064"  # word joiner, invisible operators
    r"\uFEFF"  # BOM / ZWNBSP
    r"]+",
    re.UNICODE,
)

# Multiple consecutive spaces / tabs (but not newlines — preserved by default)
_MULTI_SPACE = re.compile(r"[ \t]{2,}")

# Normalize Arabic tatweel / kashida runs to a single kashida
_TATWEEL_RUN = re.compile(r"\u0640{2,}")

# Mixed LTR/RTL marks that can strand Arabic characters
_DIRECTIONAL_MARKS = re.compile(r"[\u200E\u200F\u202A-\u202E]+")

# Space before Arabic closing punctuation (،  ؟  ؛) — should not have space before
_SPACE_BEFORE_PUNC = re.compile(r"\s+([،؟؛!])")

# Missing space after sentence-ending punctuation
_NO_SPACE_AFTER_PUNC = re.compile(r"([.؟!؛])\s*([^\s])")

# Normalize Arabic-Indic and Persian digits inline (quick path)
_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


class RedundancyProcessor(Processor):
    """Remove invisible Unicode characters and collapse redundant whitespace.

    This is a lightweight pass that runs quickly and should always be included
    near the beginning of a pipeline to prevent downstream processors from
    being confused by zero-width or invisible characters.

    Example
    -------
    >>> proc = RedundancyProcessor()
    >>> proc.process("أنا\u200b طالب\u200d")
    'أنا طالب'
    """

    name = "redundancy_cleaner"

    def transform(self, text: str) -> str:
        """Strip invisible chars and collapse extra spaces."""
        text = _INVISIBLE.sub("", text)
        text = _MULTI_SPACE.sub(" ", text)
        text = _TATWEEL_RUN.sub("\u0640", text)  # keep at most one kashida
        return text.strip()

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        if not text:
            return text
        result = self.transform(text)
        self._record(context)
        return result


class SentenceNormalizerProcessor(Processor):
    """Normalize sentence-level spacing and punctuation placement.

    Fixes common issues in Arabic text extracted from web pages, PDFs, and
    OCR outputs:

    * Removes directional marks (LRM / RLM) that corrupt character ordering.
    * Removes illegal space before closing Arabic punctuation (،  ؟  ؛).
    * Adds a missing space after sentence-ending punctuation when the next
      character is an Arabic letter.

    Parameters
    ----------
    fix_punctuation_spacing:
        Correct spacing around Arabic punctuation (default *True*).
    remove_directional_marks:
        Strip LTR/RTL Unicode embedding marks (default *True*).

    Example
    -------
    >>> proc = SentenceNormalizerProcessor()
    >>> proc.process("كيف حالك ؟ أنا بخير")
    'كيف حالك؟ أنا بخير'
    """

    name = "sentence_normalizer"

    def __init__(
        self,
        fix_punctuation_spacing: bool = True,
        remove_directional_marks: bool = True,
    ) -> None:
        self.fix_punctuation_spacing = fix_punctuation_spacing
        self.remove_directional_marks = remove_directional_marks

    def transform(self, text: str) -> str:
        if self.remove_directional_marks:
            text = _DIRECTIONAL_MARKS.sub("", text)
        if self.fix_punctuation_spacing:
            # Remove space before closing punctuation
            text = _SPACE_BEFORE_PUNC.sub(r"\1", text)
            # Ensure space after sentence-ending punctuation
            text = _NO_SPACE_AFTER_PUNC.sub(r"\1 \2", text)
        return text.strip()

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        if not text:
            return text
        result = self.transform(text)
        self._record(context)
        return result
