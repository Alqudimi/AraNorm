"""Deep word-frequency and vocabulary-diversity profiling for Arabic text.

Provides a single entry point, :class:`WordFrequencyProfiler`, which computes
rich vocabulary metrics over an Arabic text: token/frequency tables,
vocabulary-diversity indices (type-token ratio and its corrected variants),
lexical density over open-class content words, and Zipf-distribution
diagnostics.

All computation is deterministic and dependency-free.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from aranorm.utils.normalizer_utils import collapse_whitespace, normalize_alef, remove_diacritics

# Open-class Arabic words carry lexical meaning; closed-class function words
# (prepositions, conjunctions, articles, pronouns, common verbs of being) are
# excluded from the lexical-density calculation.
_CONTENT_FILTER = re.compile(
    r"^("
    r"في|على|من|إلى|عن|مع|بعد|قبل|بين|عند|حتى|أو|و|ف|أم|بل|لكن|إن|"
    r"أن|أنه|ذلك|هذا|هذه|الذين|التي|هو|هي|هم|هن|أنا|أنت|نحن|"
    r"كان|كانت|يكون|تكون|يتم|تتم|قد|لقد|لا|لم|لن|ما|ليس|ليست|أيضا|"
    r"كل|جميع|بعض|غير|ذو|ذات|حيث|إذا|إذ"
    r")$"
)

_ARTICLE = re.compile(r"^ال")

_HAMZA_MAP = {
    "\u0623": "\u0627",
    "\u0625": "\u0627",
    "\u0622": "\u0627",
    "\u0624": "\u0648",
    "\u0626": "\u064a",
}


def _normalize_pipeline(text: str) -> str:
    """Apply the standard normalization pipeline used across the project."""
    text = remove_diacritics(text)
    for hamza, replacement in _HAMZA_MAP.items():
        text = text.replace(hamza, replacement)
    text = normalize_alef(text)
    text = text.replace("\u0629", "\u0647")  # taa marbuta -> heh
    return collapse_whitespace(text)


@dataclass
class FrequencyEntry:
    """Frequency data for a single word form."""

    word: str
    count: int
    rank: int
    relative_frequency: float
    first_positions: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "count": self.count,
            "rank": self.rank,
            "relative_frequency": round(self.relative_frequency, 6),
            "first_positions": self.first_positions,
        }


@dataclass
class WordFrequencyResult:
    """Output of :meth:`WordFrequencyProfiler.profile`."""

    original_text: str
    total_tokens: int
    unique_types: int
    frequency_table: List[FrequencyEntry]
    type_token_ratio: float
    corrected_ttr: float
    root_ttr: float
    lexical_density: float
    zipf_exponent: Optional[float]
    top_n: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "total_tokens": self.total_tokens,
            "unique_types": self.unique_types,
            "frequency_table": [entry.to_dict() for entry in self.frequency_table],
            "type_token_ratio": round(self.type_token_ratio, 6),
            "corrected_ttr": round(self.corrected_ttr, 6),
            "root_ttr": round(self.root_ttr, 6),
            "lexical_density": round(self.lexical_density, 6),
            "zipf_exponent": self.zipf_exponent,
            "top_n": self.top_n,
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class WordFrequencyProfiler:
    """Profile the vocabulary of an Arabic text.

    The profiler normalizes the text (diacritics removal, hamza normalization,
    alef normalization and taa-marbuta handling are applied via
    :func:`normalize_arabic_text`), extracts word tokens, and computes both raw
    frequency statistics and vocabulary-diversity indices.
    """

    def __init__(
        self,
        *,
        top_n: int = 20,
        min_word_length: int = 2,
        content_words_only_for_density: bool = True,
    ) -> None:
        self.top_n = max(1, top_n)
        self.min_word_length = max(1, min_word_length)
        self._density_filter = content_words_only_for_density

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def profile(self, text: str) -> WordFrequencyResult:
        """Compute vocabulary-frequency metrics for *text*."""
        normalized = _normalize_pipeline(text)
        tokens = re.findall(r"[\w\u0621-\u064A\u0671-\u06D3\u06F0-\u06F9]+", normalized)
        tokens = [token for token in tokens if len(token) >= self.min_word_length]

        if not tokens:
            return WordFrequencyResult(
                original_text=text,
                total_tokens=0,
                unique_types=0,
                frequency_table=[],
                type_token_ratio=0.0,
                corrected_ttr=0.0,
                root_ttr=0.0,
                lexical_density=0.0,
                zipf_exponent=None,
                top_n=self.top_n,
            )

        counts: Dict[str, int] = {}
        first_seen: Dict[str, List[int]] = {}
        for position, token in enumerate(tokens):
            counts[token] = counts.get(token, 0) + 1
            if token not in first_seen:
                first_seen[token] = [position]
            elif len(first_seen[token]) < 3:
                first_seen[token].append(position)

        total_tokens = len(tokens)
        unique_types = len(counts)

        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        table: List[FrequencyEntry] = []
        for rank, (word, count) in enumerate(ranked[: self.top_n], start=1):
            table.append(
                FrequencyEntry(
                    word=word,
                    count=count,
                    rank=rank,
                    relative_frequency=count / total_tokens,
                    first_positions=first_seen.get(word, []),
                )
            )

        ttr = unique_types / total_tokens
        corrected_ttr = self._corrected_ttr(unique_types, total_tokens)
        root_ttr = self._root_ttr(unique_types, total_tokens)
        density = self._lexical_density(tokens)
        zipf_exp = self._zipf_exponent(ranked, total_tokens)

        return WordFrequencyResult(
            original_text=text,
            total_tokens=total_tokens,
            unique_types=unique_types,
            frequency_table=table,
            type_token_ratio=ttr,
            corrected_ttr=corrected_ttr,
            root_ttr=root_ttr,
            lexical_density=density,
            zipf_exponent=zipf_exp,
            top_n=self.top_n,
        )

    # ------------------------------------------------------------------
    # Diversity indices
    # ------------------------------------------------------------------
    @staticmethod
    def _corrected_ttr(unique_types: int, total_tokens: int) -> float:
        """Guiraud's corrected type-token ratio (CTTR)."""
        if total_tokens <= 0:
            return 0.0
        return unique_types / math.sqrt(total_tokens)

    @staticmethod
    def _root_ttr(unique_types: int, total_tokens: int) -> float:
        """Herdan's / Herdan-C log type-token ratio (R)."""
        if total_tokens <= 1:
            return 0.0
        log_tokens = math.log(total_tokens)
        log_types = math.log(unique_types)
        if log_tokens <= 0:
            return 0.0
        return log_types / log_tokens

    # ------------------------------------------------------------------
    # Lexical density
    # ------------------------------------------------------------------
    def _lexical_density(self, tokens: List[str]) -> float:
        """Proportion of open-class content words among tokens."""
        if not tokens:
            return 0.0
        content = 0
        for token in tokens:
            bare = _ARTICLE.sub("", token) if token.startswith("ال") else token
            if self._density_filter and _CONTENT_FILTER.match(bare):
                continue
            content += 1
        return content / len(tokens)

    # ------------------------------------------------------------------
    # Zipf diagnostics
    # ------------------------------------------------------------------
    @staticmethod
    def _zipf_exponent(ranked: List[tuple], total_tokens: int) -> Optional[float]:
        """Estimate the Zipf power-law exponent by least squares on log-log.

        Returns ``None`` when fewer than four distinct types are available
        (the fit would be meaningless).
        """
        if len(ranked) < 4:
            return None
        xs = [math.log(rank) for rank in range(1, len(ranked) + 1)]
        ys = [math.log(count / total_tokens) for _, count in ranked]
        n = len(xs)
        sum_x = sum(xs)
        sum_y = sum(ys)
        sum_xy = sum(a * b for a, b in zip(xs, ys))
        sum_xx = sum(a * a for a in xs)
        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            return None
        return -(n * sum_xy - sum_x * sum_y) / denominator
