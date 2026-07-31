"""Text chunking utilities for processing long Arabic documents.

Splits large texts into manageable chunks while respecting sentence and
word boundaries, making them suitable for LLM context windows, batch NLP
pipelines, and streaming processing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Generator, List, Optional

_SENTENCE_ENDS = re.compile(r"[.!?؟…]+|\n{2,}", re.UNICODE)


@dataclass
class TextChunk:
    """One chunk of a larger text.

    Attributes
    ----------
    text:
        The chunk content.
    index:
        Zero-based position in the chunk sequence.
    char_start:
        Start character offset in the original text.
    char_end:
        End character offset (exclusive) in the original text.
    token_count:
        Approximate whitespace-token count for this chunk.
    is_last:
        ``True`` for the final chunk.
    """

    text: str
    index: int
    char_start: int
    char_end: int
    token_count: int
    is_last: bool = False


class TextChunker:
    """Split long Arabic texts into overlapping or non-overlapping chunks.

    Parameters
    ----------
    max_tokens:
        Maximum whitespace-separated tokens per chunk.
    overlap_tokens:
        Number of tokens to repeat at the start of the next chunk
        (sliding-window / context overlap). Default is 0 (no overlap).
    respect_sentences:
        When *True* (default), avoid splitting mid-sentence when possible.

    Example
    -------
    >>> chunker = TextChunker(max_tokens=100, overlap_tokens=10)
    >>> chunks = chunker.chunk("نص طويل جداً …")
    >>> for chunk in chunks:
    ...     print(chunk.index, chunk.token_count)
    """

    def __init__(
        self,
        max_tokens: int = 512,
        overlap_tokens: int = 0,
        respect_sentences: bool = True,
    ) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if overlap_tokens < 0 or overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be >= 0 and < max_tokens")
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.respect_sentences = respect_sentences

    # ── Public API ────────────────────────────────────────────────────────

    def chunk(self, text: str) -> List[TextChunk]:
        """Return a list of :class:`TextChunk` objects for *text*.

        The final chunk always has :attr:`TextChunk.is_last` set to ``True``.
        """
        chunks = list(self._iter_chunks(text))
        if chunks:
            # Ensure the last chunk always carries the is_last flag regardless
            # of which branch (sentence-split vs. hard-split) produced it.
            last = chunks[-1]
            if not last.is_last:
                chunks[-1] = TextChunk(
                    text=last.text,
                    index=last.index,
                    char_start=last.char_start,
                    char_end=last.char_end,
                    token_count=last.token_count,
                    is_last=True,
                )
        return chunks

    def chunk_iter(self, text: str) -> Generator[TextChunk, None, None]:
        """Yield :class:`TextChunk` objects one at a time (memory-efficient)."""
        yield from self._iter_chunks(text)

    def chunk_texts(self, texts: List[str]) -> List[List[TextChunk]]:
        """Chunk each text independently.

        Parameters
        ----------
        texts:
            List of document strings.
        """
        return [self.chunk(t) for t in texts]

    # ── Private ───────────────────────────────────────────────────────────

    def _iter_chunks(self, text: str) -> Generator[TextChunk, None, None]:
        if not text or not text.strip():
            return

        if self.respect_sentences:
            units = self._split_sentences(text)
        else:
            units = text.split()

        current_tokens: List[str] = []
        char_offset = 0
        chunk_idx = 0
        i = 0
        while i < len(units):
            unit = units[i]
            unit_tokens = unit.split()

            if len(current_tokens) + len(unit_tokens) > self.max_tokens:
                if current_tokens:
                    chunk_text = " ".join(current_tokens)
                    start = text.find(current_tokens[0], char_offset)
                    end = start + len(chunk_text)
                    yield TextChunk(
                        text=chunk_text,
                        index=chunk_idx,
                        char_start=start,
                        char_end=end,
                        token_count=len(current_tokens),
                    )
                    chunk_idx += 1
                    char_offset = end
                    # Overlap: keep tail tokens for next chunk
                    if self.overlap_tokens > 0:
                        current_tokens = current_tokens[-self.overlap_tokens :]
                    else:
                        current_tokens = []
                    # Don't advance i — retry the same unit with overlap context
                    continue
                else:
                    # Single unit longer than max_tokens: hard-split
                    while unit_tokens:
                        batch = unit_tokens[: self.max_tokens]
                        unit_tokens = unit_tokens[self.max_tokens :]
                        chunk_text = " ".join(batch)
                        start = text.find(batch[0], char_offset)
                        end = start + len(chunk_text)
                        yield TextChunk(
                            text=chunk_text,
                            index=chunk_idx,
                            char_start=start,
                            char_end=end,
                            token_count=len(batch),
                        )
                        chunk_idx += 1
                        char_offset = end
                    i += 1
                    continue

            current_tokens.extend(unit_tokens)
            i += 1

        if current_tokens:
            chunk_text = " ".join(current_tokens)
            start = text.find(current_tokens[0], char_offset)
            end = start + len(chunk_text)
            last = TextChunk(
                text=chunk_text,
                index=chunk_idx,
                char_start=max(0, start),
                char_end=min(len(text), end),
                token_count=len(current_tokens),
                is_last=True,
            )
            yield last

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentence-level units."""
        raw = _SENTENCE_ENDS.split(text)
        return [s.strip() for s in raw if s.strip()]


# ── Convenience function ───────────────────────────────────────────────────────

def chunk_text(
    text: str,
    max_tokens: int = 512,
    overlap_tokens: int = 0,
) -> List[str]:
    """Return a list of chunk strings for *text*.

    Convenience wrapper around :class:`TextChunker`.
    """
    chunker = TextChunker(max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    return [c.text for c in chunker.chunk(text)]
