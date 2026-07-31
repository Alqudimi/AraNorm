"""Dialect-aware stop-words processor."""

from __future__ import annotations

from typing import FrozenSet, Optional, Sequence, Set

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.stop_words_registry import StopWordsRegistry


class DialectStopProcessor(Processor):
    """Remove stop words that belong to one or more Arabic dialects.

    The processor combines the MSA universal list with the dialect-specific
    lists for every dialect in *dialects*.

    Parameters
    ----------
    dialects:
        One or more dialect codes: ``EGY``, ``GLF``, ``LEV``, ``IRQ``,
        ``NOR``, ``TUN``, ``YEM``.
    registry:
        Optional pre-built registry; a fresh one is created when omitted.

    Example
    -------
    >>> proc = DialectStopProcessor(dialects=["EGY", "GLF"])
    >>> proc.process("أنا كده الحين سعيد")
    'سعيد'
    """

    name = "dialect_stop_processor"

    def __init__(
        self,
        dialects: Sequence[str],
        registry: Optional[StopWordsRegistry] = None,
    ) -> None:
        self.dialects: FrozenSet[str] = frozenset(d.upper() for d in dialects)
        self.registry = registry or StopWordsRegistry()
        self._stop_set: Set[str] = self._build_stop_set()

    def _build_stop_set(self) -> Set[str]:
        base = self.registry.get_words("universal")
        for code in self.dialects:
            base |= self.registry.get_words("dialect", frozenset([code]))
        return base

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Strip dialect-specific stop words from *text*."""
        if not text or not text.strip():
            return text
        tokens = text.split()
        kept = [t for t in tokens if t.strip(".,،؟!؛:") not in self._stop_set]
        self._record(context)
        return " ".join(kept)
