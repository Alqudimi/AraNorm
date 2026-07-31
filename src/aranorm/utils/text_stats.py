"""Arabic text statistics and readability metrics.

Provides lightweight, dependency-free statistics for Arabic text:
character counts, word density, sentence complexity estimates,
and a heuristic readability score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

# ── Arabic character ranges ────────────────────────────────────────────────────
_ARABIC_LETTER = re.compile(r"[\u0621-\u064A\u0671-\u06D3]")
_ARABIC_WORD_RE = re.compile(r"[\u0621-\u064A\u0671-\u06D3\u0660-\u0669\u06F0-\u06F9]+")
_DIACRITIC_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_SENTENCE_END = re.compile(r"[.!?؟…]+|\n{2,}")
_DIGIT_RE = re.compile(r"\d")
_LATIN_RE = re.compile(r"[A-Za-z]")


@dataclass
class TextStats:
    """Statistics for a single Arabic (or mixed) text.

    Attributes
    ----------
    char_count:
        Total number of characters (including spaces).
    char_count_no_spaces:
        Character count excluding whitespace.
    arabic_char_count:
        Number of Arabic letter code points.
    latin_char_count:
        Number of Latin letter code points.
    digit_count:
        Number of digit characters.
    diacritic_count:
        Number of Arabic diacritic marks.
    word_count:
        Number of whitespace-separated tokens.
    arabic_word_count:
        Tokens containing at least one Arabic letter.
    sentence_count:
        Estimated number of sentences.
    avg_word_length:
        Average characters per Arabic word.
    avg_sentence_length:
        Average words per sentence.
    vocabulary_size:
        Number of unique word forms.
    type_token_ratio:
        vocabulary_size / word_count (lexical diversity).
    diacritic_ratio:
        diacritic_count / arabic_char_count (0 = undiacritized text).
    arabic_ratio:
        arabic_char_count / char_count_no_spaces (language mix indicator).
    readability_score:
        Heuristic score 0–100 (higher = easier to read).
    readability_label:
        ``"very_easy"``, ``"easy"``, ``"moderate"``, ``"difficult"``, ``"very_difficult"``.
    word_frequency:
        Frequency table of all word forms.
    top_words:
        Top-10 words by frequency as ``[(word, count), …]``.
    """

    char_count: int
    char_count_no_spaces: int
    arabic_char_count: int
    latin_char_count: int
    digit_count: int
    diacritic_count: int

    word_count: int
    arabic_word_count: int
    sentence_count: int

    avg_word_length: float
    avg_sentence_length: float
    vocabulary_size: int
    type_token_ratio: float
    diacritic_ratio: float
    arabic_ratio: float

    readability_score: float
    readability_label: str

    word_frequency: Dict[str, int]
    top_words: List[Tuple[str, int]]


def compute_stats(text: str, top_n: int = 10) -> TextStats:
    """Compute statistics for *text*.

    Parameters
    ----------
    text:
        Arabic or mixed-language input string.
    top_n:
        Number of top words to include in :attr:`TextStats.top_words`.

    Example
    -------
    >>> stats = compute_stats("أنا أحب اللغة العربية")
    >>> stats.word_count
    4
    >>> stats.arabic_ratio
    1.0
    """
    if not text:
        return _empty_stats()

    # ── Character-level counts ────────────────────────────────────────────
    chars = len(text)
    chars_no_spaces = len(text.replace(" ", "").replace("\t", "").replace("\n", ""))
    arabic_chars = len(_ARABIC_LETTER.findall(text))
    latin_chars = len(_LATIN_RE.findall(text))
    digit_chars = len(_DIGIT_RE.findall(text))
    diacritics = len(_DIACRITIC_RE.findall(text))

    # ── Word-level counts ─────────────────────────────────────────────────
    raw_tokens = text.split()
    word_count = len(raw_tokens)
    arabic_words = [t for t in raw_tokens if _ARABIC_LETTER.search(t)]
    arabic_word_count = len(arabic_words)

    # Sentence count
    sentence_parts = [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]
    sentence_count = max(1, len(sentence_parts))

    # Average word length (Arabic words only)
    arab_lengths = [len(_DIACRITIC_RE.sub("", w).replace("ـ", "")) for w in arabic_words]
    avg_word_length = round(sum(arab_lengths) / len(arab_lengths), 2) if arab_lengths else 0.0

    avg_sentence_length = round(word_count / sentence_count, 2) if sentence_count else 0.0

    # Vocabulary
    cleaned_tokens = [
        _DIACRITIC_RE.sub("", t).strip(".,،؟!؛:()[]{}\"'«»")
        for t in raw_tokens
    ]
    freq: Dict[str, int] = {}
    for w in cleaned_tokens:
        if w:
            freq[w] = freq.get(w, 0) + 1

    vocab_size = len(freq)
    ttr = round(vocab_size / word_count, 4) if word_count else 0.0

    diacritic_ratio = round(diacritics / arabic_chars, 4) if arabic_chars else 0.0
    arabic_ratio = round(arabic_chars / chars_no_spaces, 4) if chars_no_spaces else 0.0

    # Readability: simple heuristic based on avg sentence/word length
    # Short words, short sentences → easy; long words, long sentences → hard
    score = 100.0
    score -= max(0, avg_word_length - 4) * 8   # penalize long words
    score -= max(0, avg_sentence_length - 8) * 3  # penalize long sentences
    score -= max(0, diacritic_ratio * 10)        # diacritized text is often formal
    score = max(0.0, min(100.0, round(score, 1)))

    label = _readability_label(score)

    top_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]

    return TextStats(
        char_count=chars,
        char_count_no_spaces=chars_no_spaces,
        arabic_char_count=arabic_chars,
        latin_char_count=latin_chars,
        digit_count=digit_chars,
        diacritic_count=diacritics,
        word_count=word_count,
        arabic_word_count=arabic_word_count,
        sentence_count=sentence_count,
        avg_word_length=avg_word_length,
        avg_sentence_length=avg_sentence_length,
        vocabulary_size=vocab_size,
        type_token_ratio=ttr,
        diacritic_ratio=diacritic_ratio,
        arabic_ratio=arabic_ratio,
        readability_score=score,
        readability_label=label,
        word_frequency=freq,
        top_words=top_words,
    )


def compare_stats(text_a: str, text_b: str) -> Dict[str, object]:
    """Return a side-by-side comparison dict for two texts."""
    a = compute_stats(text_a)
    b = compute_stats(text_b)
    return {
        "text_a": _stats_summary(a),
        "text_b": _stats_summary(b),
        "delta": {
            "word_count": b.word_count - a.word_count,
            "avg_word_length": round(b.avg_word_length - a.avg_word_length, 2),
            "readability_score": round(b.readability_score - a.readability_score, 1),
            "type_token_ratio": round(b.type_token_ratio - a.type_token_ratio, 4),
        },
    }


# ── Private helpers ────────────────────────────────────────────────────────────

def _readability_label(score: float) -> str:
    if score >= 80:
        return "very_easy"
    if score >= 60:
        return "easy"
    if score >= 40:
        return "moderate"
    if score >= 20:
        return "difficult"
    return "very_difficult"


def _stats_summary(s: TextStats) -> Dict[str, object]:
    return {
        "word_count": s.word_count,
        "avg_word_length": s.avg_word_length,
        "readability_score": s.readability_score,
        "readability_label": s.readability_label,
        "type_token_ratio": s.type_token_ratio,
        "arabic_ratio": s.arabic_ratio,
    }


def _empty_stats() -> TextStats:
    return TextStats(
        char_count=0, char_count_no_spaces=0, arabic_char_count=0,
        latin_char_count=0, digit_count=0, diacritic_count=0,
        word_count=0, arabic_word_count=0, sentence_count=0,
        avg_word_length=0.0, avg_sentence_length=0.0, vocabulary_size=0,
        type_token_ratio=0.0, diacritic_ratio=0.0, arabic_ratio=0.0,
        readability_score=0.0, readability_label="very_difficult",
        word_frequency={}, top_words=[],
    )
