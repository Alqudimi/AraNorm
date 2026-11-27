"""Stop words configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Optional


@dataclass(frozen=True)
class StopWordsConfig:
    """Immutable configuration for stop-words processing.

    Parameters
    ----------
    mode:
        ``"remove"``    – strip stop words from the text (default).
        ``"extract"``   – return only the stop words found.
        ``"highlight"`` – wrap stop words with ``[[…]]`` markers.
        ``"count"``     – leave text unchanged; only populate stats.
    scope:
        ``"universal"``      – all stop words (MSA + all dialects + modern).
        ``"msa_only"``       – Modern Standard Arabic only.
        ``"dialect_aware"``  – MSA plus the dialects listed in *dialects*.
        ``"custom"``         – only the *custom_stop_words* set.
    dialects:
        Active dialect codes when ``scope="dialect_aware"``.
        Supported: ``EGY``, ``GLF``, ``LEV``, ``IRQ``, ``NOR``, ``TUN``, ``YEM``.
    preserve_negation:
        Keep negation particles (لا، لم، لن) even when they are otherwise
        stop words.
    preserve_emphasis:
        Keep emphasis / conditional particles (إن، أن) when they appear in
        an emphatic/conditional context.
    preserve_prepositions:
        When *False* (default), prepositions are removed.  Set to *True* to
        keep them.
    remove_filler:
        Strip colloquial filler words (يعني، والله، خلاص …).
    remove_arabizi:
        Strip Arabizi tokens (``2na``、``3nd`` …).
    remove_internet:
        Strip Internet/leet tokens (``www``、``lol``、``http`` …).
    remove_numbers:
        Strip Western-Arabic digit tokens (0–9).
    custom_stop_words:
        Additional words to treat as stop words on top of the chosen *scope*.
    excluded_stop_words:
        Words that should *never* be removed, even if they appear in the
        active stop-words set.
    """

    mode: str = "remove"
    scope: str = "universal"
    dialects: FrozenSet[str] = field(default_factory=frozenset)
    preserve_negation: bool = True
    preserve_emphasis: bool = False
    preserve_prepositions: bool = False
    remove_filler: bool = True
    remove_arabizi: bool = False
    remove_internet: bool = False
    remove_numbers: bool = False
    custom_stop_words: Optional[FrozenSet[str]] = None
    excluded_stop_words: Optional[FrozenSet[str]] = None

    # ── validation ────────────────────────────────────────────────────────
    def __post_init__(self) -> None:
        valid_modes = {"remove", "extract", "highlight", "count"}
        if self.mode not in valid_modes:
            raise ValueError(f"Invalid mode {self.mode!r}. Choose from {sorted(valid_modes)}.")
        valid_scopes = {"universal", "msa_only", "dialect_aware", "custom"}
        if self.scope not in valid_scopes:
            raise ValueError(f"Invalid scope {self.scope!r}. Choose from {sorted(valid_scopes)}.")
        valid_dialects = {"EGY", "GLF", "LEV", "IRQ", "NOR", "TUN", "YEM", "MSA"}
        bad = set(self.dialects) - valid_dialects
        if bad:
            raise ValueError(f"Unknown dialect code(s): {bad!r}")

    # ── helpers ───────────────────────────────────────────────────────────
    @classmethod
    def for_social_media(cls) -> "StopWordsConfig":
        """Preset: aggressively remove filler + internet + Arabizi."""
        return cls(
            mode="remove",
            scope="universal",
            remove_filler=True,
            remove_arabizi=True,
            remove_internet=True,
            remove_numbers=True,
        )

    @classmethod
    def for_dialect(cls, *dialect_codes: str) -> "StopWordsConfig":
        """Preset: dialect-aware removal for specified dialects."""
        return cls(
            mode="remove",
            scope="dialect_aware",
            dialects=frozenset(d.upper() for d in dialect_codes),
        )

    @classmethod
    def count_only(cls) -> "StopWordsConfig":
        """Preset: count stop words without modifying text."""
        return cls(mode="count", scope="universal")
