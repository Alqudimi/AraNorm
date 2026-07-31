"""Arabizi stop-words processor.

Arabizi (Arabic written in Latin characters with digits) tokens such as
``2na`` (أنا), ``3nd`` (عند), ``7aga`` (حاجة) are treated as stop words when
they convey function-word meaning.
"""

from __future__ import annotations

import re
from typing import Optional, Set

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.stop_words_registry import StopWordsRegistry

# Tokens consisting only of digits are treated as Arabizi stand-alone stops
_DIGIT_ONLY_RE = re.compile(r"^\d+$")


class ArabiziStopProcessor(Processor):
    """Strip Arabizi stop-word tokens from mixed-script Arabic text.

    Example
    -------
    >>> proc = ArabiziStopProcessor()
    >>> proc.process("2na 3ndy 7aga")
    '7aga'
    """

    name = "arabizi_stop_processor"

    def __init__(self, registry: Optional[StopWordsRegistry] = None) -> None:
        self.registry = registry or StopWordsRegistry()
        self._stop_set: Set[str] = self.registry.get_words("arabizi")

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Remove Arabizi stop words from *text*."""
        if not text or not text.strip():
            return text
        tokens = text.split()
        kept = []
        for token in tokens:
            raw = token.strip(".,،؟!؛:").lower()
            if raw in self._stop_set or _DIGIT_ONLY_RE.match(raw):
                continue
            kept.append(token)
        self._record(context)
        return " ".join(kept)
