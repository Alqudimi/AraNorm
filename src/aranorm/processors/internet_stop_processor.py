"""Internet / leet-speak stop-words processor."""

from __future__ import annotations

import re
from typing import Optional, Set

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.stop_words_registry import StopWordsRegistry

# Pattern to detect bare URLs / domains
_URL_RE = re.compile(
    r"(https?://\S+|www\.\S+|\S+\.(com|net|org|io|co|ae|sa|eg|ma)\b)",
    re.IGNORECASE,
)


class InternetStopProcessor(Processor):
    """Strip Internet slang, leet acronyms, and bare URL fragments.

    Example
    -------
    >>> proc = InternetStopProcessor()
    >>> proc.process("شوف الموقع www.example.com lol")
    'شوف الموقع'
    """

    name = "internet_stop_processor"

    def __init__(self, registry: Optional[StopWordsRegistry] = None) -> None:
        self.registry = registry or StopWordsRegistry()
        self._stop_set: Set[str] = self.registry.get_words("internet")

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Remove Internet stop-word tokens and bare URLs from *text*."""
        if not text or not text.strip():
            return text
        # First strip full URLs
        text = _URL_RE.sub("", text)
        tokens = text.split()
        kept = []
        for token in tokens:
            raw = token.strip(".,،؟!؛:/").lower()
            if raw in self._stop_set:
                continue
            kept.append(token)
        self._record(context)
        return " ".join(kept).strip()
