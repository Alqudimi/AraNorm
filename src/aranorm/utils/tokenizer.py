"""Arabic-aware text tokenization utilities.

Provides sentence splitting and word tokenization without external
dependencies, relying on Unicode ranges and Arabic-specific punctuation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

# ── Arabic Unicode ranges ──────────────────────────────────────────────────────
_ARABIC_RANGE = r"\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF"
_ARABIC_WORD = re.compile(r"[" + _ARABIC_RANGE + r"]+")

# ── Sentence boundary characters ───────────────────────────────────────────────
# Arabic sentence-final punctuation + common Western equivalents
_SENTENCE_ENDS = re.compile(
    r"[.!?؟…]+"  # period / bang / question / ellipsis
    r"|[،؛:]\s{2,}"  # comma/semicolon followed by significant whitespace
    r"|\n{2,}",  # paragraph breaks
    re.UNICODE,
)

# ── Clitic prefixes/suffixes to split off ─────────────────────────────────────
# This is a conservative list; only unambiguous clitics.
_CLITIC_PREFIXES = re.compile(r"^(و|ف|ب|ل|ك|وال|فال|بال|لل|وب|وف|فب)(.*)", re.UNICODE)
_CLITIC_SUFFIXES = re.compile(r"(.*?)(ها|هم|هن|هما|كم|كن|كما|ني|نا|ي|ه)$", re.UNICODE)


@dataclass
class Token:
    """Represents a single tokenized unit.

    Attributes
    ----------
    text:
        Surface form of the token.
    start:
        Character offset in the original string.
    end:
        Exclusive character offset in the original string.
    is_arabic:
        True when the token contains Arabic characters.
    is_punctuation:
        True when the token is punctuation-only.
    normalized:
        Lower-cased / stripped form (same as *text* for Arabic).
    """

    text: str
    start: int
    end: int
    is_arabic: bool
    is_punctuation: bool
    normalized: str


@dataclass
class Sentence:
    """Represents a single detected sentence.

    Attributes
    ----------
    text:
        Surface form of the sentence.
    tokens:
        List of :class:`Token` objects (populated when ``tokenize=True``).
    index:
        Zero-based sentence index within the original text.
    """

    text: str
    tokens: List[Token] = field(default_factory=list)
    index: int = 0


# ── Tokenizer ──────────────────────────────────────────────────────────────────


class ArabicTokenizer:
    """Tokenize Arabic text into sentences and/or words.

    This is a rule-based tokenizer with no external dependencies. For
    production-grade morphological tokenization, inject a CAMeL-Tools or
    Farasa-based analyzer via :class:`~aranorm.stages.morphological.MorphologicalProcessor`.

    Parameters
    ----------
    split_clitics:
        When *True*, attempt to split common clitic prefixes and suffixes
        (و/ف/ب + the stem, pronominal suffixes).  Conservative; disabled by
        default to avoid precision loss.
    keep_punctuation:
        When *True*, punctuation tokens are included in the word token list.

    Example
    -------
    >>> tok = ArabicTokenizer()
    >>> sents = tok.split_sentences("أهلاً بكم. كيف حالكم؟")
    >>> [s.text for s in sents]
    ['أهلاً بكم.', 'كيف حالكم؟']
    >>> tok.tokenize("أنا أحب اللغة العربية")
    ['أنا', 'أحب', 'اللغة', 'العربية']
    """

    def __init__(
        self,
        split_clitics: bool = False,
        keep_punctuation: bool = False,
    ) -> None:
        self.split_clitics = split_clitics
        self.keep_punctuation = keep_punctuation

    # ── Public API ────────────────────────────────────────────────────────

    def tokenize(self, text: str) -> List[str]:
        """Return a flat list of word tokens.

        Parameters
        ----------
        text:
            Arabic (or mixed) input string.
        """
        return [t.text for t in self._word_tokens(text)]

    def tokenize_detailed(self, text: str) -> List[Token]:
        """Return a list of :class:`Token` objects with offsets.

        Parameters
        ----------
        text:
            Input string.
        """
        return self._word_tokens(text)

    def split_sentences(self, text: str, tokenize: bool = False) -> List[Sentence]:
        """Split *text* into sentences.

        Parameters
        ----------
        text:
            Input text.
        tokenize:
            When *True*, also populate :attr:`Sentence.tokens` for each sentence.
        """
        if not text or not text.strip():
            return []

        # Split on sentence-final marks, keeping the delimiter with the segment
        segments = _SENTENCE_ENDS.split(text)
        # Re-attach the delimiters
        delimiters = _SENTENCE_ENDS.findall(text)

        sentences: List[Sentence] = []
        for i, seg in enumerate(segments):
            seg = seg.strip()
            if not seg:
                continue
            delimiter = delimiters[i] if i < len(delimiters) else ""
            surface = (seg + delimiter).strip()
            sentence = Sentence(
                text=surface,
                index=len(sentences),
            )
            if tokenize:
                sentence.tokens = self._word_tokens(surface)
            sentences.append(sentence)
        return sentences

    def split_into_chunks(self, text: str, max_tokens: int = 512) -> List[str]:
        """Split *text* into chunks of at most *max_tokens* words.

        Preserves sentence boundaries when possible.

        Parameters
        ----------
        text:
            Input text.
        max_tokens:
            Maximum number of whitespace-separated tokens per chunk.
        """
        sentences = self.split_sentences(text)
        chunks: List[str] = []
        current_tokens: List[str] = []

        for sent in sentences:
            words = sent.text.split()
            if len(current_tokens) + len(words) > max_tokens:
                if current_tokens:
                    chunks.append(" ".join(current_tokens))
                    current_tokens = []
                # If single sentence is too long, hard-split it
                while len(words) > max_tokens:
                    chunks.append(" ".join(words[:max_tokens]))
                    words = words[max_tokens:]
            current_tokens.extend(words)

        if current_tokens:
            chunks.append(" ".join(current_tokens))
        return chunks

    # ── Private ───────────────────────────────────────────────────────────

    def _word_tokens(self, text: str) -> List[Token]:
        """Tokenize *text* into :class:`Token` objects."""
        tokens: List[Token] = []
        # Simple whitespace split with offset tracking
        offset = 0
        for raw in text.split():
            start = text.find(raw, offset)
            end = start + len(raw)
            offset = end

            is_arabic = bool(_ARABIC_WORD.search(raw))
            is_punct = not bool(re.search(r"\w", raw, re.UNICODE))

            if is_punct and not self.keep_punctuation:
                continue

            surfaces = [raw]
            if self.split_clitics and is_arabic and len(raw) > 3:
                surfaces = self._split_clitics(raw)

            for surface in surfaces:
                tokens.append(
                    Token(
                        text=surface,
                        start=start,
                        end=start + len(surface),
                        is_arabic=bool(_ARABIC_WORD.search(surface)),
                        is_punctuation=not bool(re.search(r"\w", surface, re.UNICODE)),
                        normalized=surface.lower(),
                    )
                )
        return tokens

    def _split_clitics(self, word: str) -> List[str]:
        """Attempt to split one clitic prefix/suffix from *word*."""
        parts: List[str] = []
        prefix_match = _CLITIC_PREFIXES.match(word)
        if prefix_match and len(prefix_match.group(2)) >= 2:
            parts.append(prefix_match.group(1))
            word = prefix_match.group(2)
        parts.append(word)
        return parts


# ── Convenience function ───────────────────────────────────────────────────────


def word_tokenize(text: str, split_clitics: bool = False) -> List[str]:
    """Tokenize *text* into a list of Arabic word strings.

    Convenience wrapper around :class:`ArabicTokenizer`.

    Parameters
    ----------
    text:
        Input string.
    split_clitics:
        Split clitic prefixes/suffixes.
    """
    return ArabicTokenizer(split_clitics=split_clitics).tokenize(text)


def sent_tokenize(text: str) -> List[str]:
    """Split *text* into a list of sentence strings.

    Convenience wrapper around :class:`ArabicTokenizer`.
    """
    return [s.text for s in ArabicTokenizer().split_sentences(text)]
