"""Phrase-level (multi-word) stop words processor.

Arabic has many multi-word stop expressions that single-token processing
misses, e.g. "إن شاء الله", "من جهة أخرى", "في الحقيقة".  This processor
uses a sliding-window search over the token stream.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from aranorm.core.base import Processor, ProcessorContext

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "stopwords")


def _read_phrases(path: str) -> List[Tuple[str, ...]]:
    """Read a phrase file and return (token, token, …) tuples."""
    if not os.path.isfile(path):
        return []
    phrases = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                tokens = tuple(line.split())
                if len(tokens) >= 2:  # single-token entries belong in other lists
                    phrases.append(tokens)
    return phrases


class PhraseStopProcessor(Processor):
    """Remove multi-word Arabic stop phrases from text using sliding-window matching.

    Parameters
    ----------
    extra_phrases:
        Additional phrases supplied at construction time (each phrase is a
        whitespace-separated string, e.g. ``"في الحقيقة"``).
    replace_with:
        What to replace a matched phrase with (default: empty string → remove).
    mode:
        ``"remove"`` | ``"highlight"`` | ``"tag"``.
        *highlight* wraps the phrase in ``{{…}}``;
        *tag* wraps it in ``<phrase>…</phrase>``.
    registry:
        Optional external phrase registry (list of phrase tuples).

    Example
    -------
    >>> proc = PhraseStopProcessor()
    >>> proc.process("هذا في الحقيقة رأيي")
    'هذا رأيي'
    """

    name = "phrase_stop_processor"
    _VALID_MODES = frozenset({"remove", "highlight", "tag"})

    def __init__(
        self,
        extra_phrases: Optional[List[str]] = None,
        replace_with: str = "",
        mode: str = "remove",
        registry: Optional[List[Tuple[str, ...]]] = None,
    ) -> None:
        if mode not in self._VALID_MODES:
            raise ValueError("mode must be one of: remove, highlight, tag")
        self.mode = mode
        self.replace_with = replace_with
        self._phrases: List[Tuple[str, ...]] = list(
            registry if registry is not None else _read_phrases(os.path.join(_DATA_DIR, "phrases.txt"))
        )
        if extra_phrases:
            for p in extra_phrases:
                toks = tuple(p.split())
                if len(toks) >= 2 and toks not in self._phrases:
                    self._phrases.append(toks)

        # Build a lookup dict keyed by first token → [(phrase_tuple, …)] for O(1) first-match
        self._index: Dict[str, List[Tuple[str, ...]]] = {}
        for phrase in self._phrases:
            self._index.setdefault(phrase[0], []).append(phrase)
        # Sort longest-first so greedy matching takes the longest match
        for k in self._index:
            self._index[k].sort(key=len, reverse=True)

    # ── Core ─────────────────────────────────────────────────────────────

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Remove / mark stop phrases from *text*."""
        if not text or not text.strip():
            return text
        tokens = text.split()
        result: List[str] = []
        i = 0
        while i < len(tokens):
            raw = tokens[i].strip(".,،؟!؛:")
            matched = False
            if raw in self._index:
                for phrase in self._index[raw]:
                    n = len(phrase)
                    if i + n > len(tokens):
                        continue
                    window = tuple(t.strip(".,،؟!؛:") for t in tokens[i : i + n])
                    if window == phrase:
                        if self.mode == "highlight":
                            result.append("{{" + " ".join(tokens[i : i + n]) + "}}")
                        elif self.mode == "tag":
                            result.append("<phrase>" + " ".join(tokens[i : i + n]) + "</phrase>")
                        elif self.replace_with:
                            result.append(self.replace_with)
                        # else remove → append nothing
                        i += n
                        matched = True
                        break
            if not matched:
                result.append(tokens[i])
                i += 1
        self._record(context)
        return " ".join(result).strip()

    def get_phrases_found(self, text: str) -> List[str]:
        """Return a list of stop phrases found in *text* (without modifying it)."""
        tokens = text.split()
        found: List[str] = []
        i = 0
        while i < len(tokens):
            raw = tokens[i].strip(".,،؟!؛:")
            if raw in self._index:
                for phrase in self._index[raw]:
                    n = len(phrase)
                    if i + n > len(tokens):
                        continue
                    window = tuple(t.strip(".,،؟!؛:") for t in tokens[i : i + n])
                    if window == phrase:
                        found.append(" ".join(phrase))
                        i += n
                        break
                else:
                    i += 1
            else:
                i += 1
        return found

    @property
    def phrase_count(self) -> int:
        """Total number of registered stop phrases."""
        return len(self._phrases)
