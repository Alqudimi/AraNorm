"""Arabic anaphora & cohesion reference detection.

Determines how a text ties its sentences together through pronominal
references and lexical re-mention: attached pronouns (ـه/ـها/ـهم/ـنا/ـي),
independent pronouns (هو/هي/هما/هم/هن/أنا/نحن/أنت...), demonstratives
(هذا/هذه/ذلك/تلك/هؤلاء...), relative reference (الذي/التي), and explicit
lexical re-mention of content words across sentences.

Deterministic, dependency-free, and consistent with the ``aranorm.analysis``
family (dataclass results with ``to_dict``/JSON APIs).

Design notes
------------
- Reference spans are character-offset based and de-duplicated so the same
  word is never double-counted (e.g. ``هو`` counted once per mention).
- Lexical re-mention requires the same normalised content word to appear in
  *two different sentences*, which is the classic definition of cohesion by
  repetition rather than mere word frequency.
- Attached pronouns are detected through a suffix lexicon applied to every
  token; multi-suffix stacking (``-هاها`` nonsense) is rejected by requiring
  the stem to be at least two characters long.

Output
------
+-----------------------------+------------------------------------------------+
| Field                       | Description                                    |
+-----------------------------+------------------------------------------------+
| attached_pronouns           | Attached clitic pronoun mentions (ـه، ـها،     |
|                             | ـهم...).                                        |
| independent_pronouns        | Independent pronoun mentions (هو، هي...).      |
| demonstratives              | Demonstrative reference (هذا، تلك...).         |
| relative_references         | Relative-link reference (الذي، التي...).       |
| lexical_rementions          | Content words re-mentioned across sentences.   |
| reference_density           | Reference mentions per 100 words.              |
| cohesion_score              | 0.0–1.0 composite of mention variety +         |
|                             | re-mention coverage.                           |
| label                       | ``"tightly-cohesive"`` / ``"moderate"`` /      |
|                             | ``"loose"``.                                   |
+-----------------------------+------------------------------------------------+

Example
-------
>>> from aranorm.analysis.anaphora_analyzer import analyze_anaphora
>>> result = analyze_anaphora("جاء الرجل. هو يمشي بسرعة. كتابه مفيد.")
>>> result.independent_pronouns
1
"""

from __future__ import annotations

import json
import re as _re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# ── Shared normalisation constants ──────────────────────────────────────────
_WORD_RE = _re.compile(r"[\u0621-\u064A\u0660-\u06690-9A-Za-z]+")
_SENTENCE_END_RE = _re.compile(r"[.?!،؛\u061F\u061B]|(?:\.\.\.)")
_DIACRITICS = _re.compile(r"[\u064B-\u0652\u0670\u0640\u064E\u064F\u0650\u0651]")
_ALEF_NORMALISE = str.maketrans("أإآ", "ااا")

# Suffix lexicon: ``(suffix, description)`` applied after normalisation.
# Ordered by length so the longest suffix wins.
_ATTACHED_PRONOUN_SUFFIXES: List[Tuple[str, str]] = [
    ("هما", "dual"),
    ("هم", "masculine-plural"),
    ("هن", "feminine-plural"),
    ("نا", "first-person-plural"),
    ("ها", "feminine-singular"),
    ("ه", "masculine-singular"),
    ("ي", "first-person-singular"),
]

# Independent pronouns and reference words (normalised forms).
_INDEPENDENT_PRONOUNS = (
    "هو",
    "هي",
    "هما",
    "هم",
    "هن",
    "أنا",
    "انت",
    "أنت",
    "انتما",
    "أنتما",
    "انتم",
    "أنتم",
    "انتن",
    "أنتن",
    "نحن",
)

_DEMONSTRATIVES = (
    "هذا",
    "هذه",
    "هذان",
    "هذين",
    "هاتان",
    "هاتين",
    "هؤلاء",
    "ذلك",
    "تلك",
    "ذانك",
    "تانك",
    "اولئك",
    "اولائك",
)

_RELATIVE_LINKS = (
    "الذي",
    "التي",
    "اللذان",
    "اللتان",
    "اللذين",
    "اللتين",
    "الذين",
    "اللاتي",
    "اللواتي",
    "اللذي",
    "اللتيا",
)

# Verbs whose final ``ي`` belongs to the root pattern (``يمشي``, ``يرمي``,
# ``يبني``...) rather than an attached first-person pronoun.
_VERBAL_YA_EXCEPTIONS = frozenset(
    [
        "يمشي",
        "رمي",
        "نبني",
        "تبني",
        "يمشي",
        "أمشي",
        "نمشي",
        "نجري",
        "أجري",
        "يجي",
        "تجي",
        "نجي",
        "أجي",
        "يحيي",
        "نحيي",
        "تحيي",
        "أحيي",
        "ينهي",
        "تنهي",
        "أنهي",
        "ننهي",
        "يسمي",
        "تسمي",
        "أسمي",
        "نسمي",
    ]
)

# Stop-like short words that should not count as lexical re-mentions.
_REMENTION_STOP = frozenset(
    [
        "في",
        "من",
        "إلى",
        "الى",
        "عن",
        "على",
        "علي",
        "مع",
        "عند",
        "بين",
        "بعد",
        "قبل",
        "دون",
        "حتى",
        "غير",
        "كل",
        "بعض",
        "ذو",
        "ذات",
        "كان",
        "كانت",
        "يكون",
        "يكونوا",
        "أن",
        "ان",
        "إن",
        "هو",
        "هي",
        "هم",
        "هن",
        "هما",
        "هذا",
        "هذه",
        "ذلك",
        "تلك",
        "الذي",
        "التي",
        "الذين",
        "و",
        "ف",
        "ب",
        "ل",
        "ك",
        "ما",
        "لا",
        "لم",
        "لن",
        "قد",
        "أي",
        "أو",
        "ا",
    ]
)


def _normalize_word(word: str) -> str:
    """Strip diacritics/tatweel and normalise alef variants."""
    return _DIACRITICS.sub("", word).translate(_ALEF_NORMALISE)


def _split_sentences(text: str) -> List[Tuple[str, int, int]]:
    """Split *text* into sentences with character offsets."""
    if not text.strip():
        return []
    sentences: List[Tuple[str, int, int]] = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(text):
        end = match.end()
        segment = text[start:end].strip()
        if segment:
            sentences.append((segment, start, end))
        start = end
    if start < len(text):
        segment = text[start:].strip()
        if segment:
            sentences.append((segment, start, len(text)))
    return sentences


@dataclass
class AnaphoraMention:
    """A single reference mention with its character span."""

    text: str
    mention_type: str
    start: int
    end: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "mention_type": self.mention_type,
            "start": self.start,
            "end": self.end,
        }


@dataclass
class AnaphoraResult:
    """Consolidated anaphora / cohesion analysis for a single Arabic text.

    Attributes
    ----------
    attached_pronouns:
        Attached clitic pronoun mentions (e.g. كتابُ*ـه*).
    independent_pronouns:
        Independent pronoun mentions (هو، هي...).
    demonstratives:
        Demonstrative reference mentions (هذا، تلك...).
    relative_references:
        Relative-link mentions (الذي، التي...).
    lexical_rementions:
        Content words re-mentioned in two or more sentences.
    reference_density:
        Total reference mentions per 100 words.
    cohesion_score:
        0.0–1.0 composite measuring cohesion variety and coverage.
    word_count:
        Total words used for density computation.
    sentence_count:
        Number of detected sentences.
    label:
        ``"tightly-cohesive"`` / ``"moderate"`` / ``"loose"``.
    """

    attached_pronouns: List[AnaphoraMention]
    independent_pronouns: List[AnaphoraMention]
    demonstratives: List[AnaphoraMention]
    relative_references: List[AnaphoraMention]
    lexical_rementions: List[str]
    reference_density: float
    cohesion_score: float
    word_count: int
    sentence_count: int
    label: str

    @property
    def attached_pronoun_count(self) -> int:
        """Number of attached pronoun mentions."""
        return len(self.attached_pronouns)

    @property
    def independent_pronoun_count(self) -> int:
        """Number of independent pronoun mentions."""
        return len(self.independent_pronouns)

    @property
    def demonstrative_count(self) -> int:
        """Number of demonstrative reference mentions."""
        return len(self.demonstratives)

    @property
    def relative_reference_count(self) -> int:
        """Number of relative-link mentions."""
        return len(self.relative_references)

    @property
    def lexical_remention_count(self) -> int:
        """Number of distinct content words re-mentioned across sentences."""
        return len(self.lexical_rementions)

    @property
    def mention_count(self) -> int:
        """Total reference mentions of all kinds."""
        return (
            self.attached_pronoun_count
            + self.independent_pronoun_count
            + self.demonstrative_count
            + self.relative_reference_count
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attached_pronouns": [m.to_dict() for m in self.attached_pronouns],
            "independent_pronouns": [m.to_dict() for m in self.independent_pronouns],
            "demonstratives": [m.to_dict() for m in self.demonstratives],
            "relative_references": [m.to_dict() for m in self.relative_references],
            "lexical_rementions": self.lexical_rementions,
            "reference_density": round(self.reference_density, 4),
            "cohesion_score": round(self.cohesion_score, 4),
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "label": self.label,
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


@dataclass
class AnaphoraAnalyzer:
    """Arabic anaphora & cohesion reference detection over prose.

    Parameters
    ----------
    dense_threshold:
        Cohesion score at or above which the text is labelled
        ``"tightly-cohesive"``.
    moderate_threshold:
        Cohesion score at or above which the text is labelled ``"moderate"``;
        below this the label is ``"loose"``.
    """

    dense_threshold: float = 0.45
    moderate_threshold: float = 0.15

    def _find_mention(
        self,
        text: str,
        global_start: int,
        needle: str,
        seen: set,
        mention_type: str,
    ) -> Optional[AnaphoraMention]:
        """Register the next non-overlapping occurrence of *needle* in *text*."""
        index = 0
        while True:
            found = text.find(needle, index)
            if found == -1:
                return None
            start = global_start + found
            if start not in seen:
                seen.add(start)
                return AnaphoraMention(text=needle, mention_type=mention_type, start=start, end=start + len(needle))
            index = found + len(needle)
        return None

    def analyze(self, text: str) -> AnaphoraResult:
        """Detect reference mentions and cohesion in *text*."""
        sentences = _split_sentences(text)
        sentence_count = len(sentences)

        attached: List[AnaphoraMention] = []
        independent: List[AnaphoraMention] = []
        demonstratives: List[AnaphoraMention] = []
        relatives: List[AnaphoraMention] = []

        seen_spans: set = set()
        words: List[Tuple[str, int, int]] = []

        for _segment, seg_start, _seg_end in sentences:
            for match in _WORD_RE.finditer(text, seg_start, _seg_end if _seg_end else len(text)):
                # Avoid double indexing words that straddle segment boundaries.
                if any(w[1] == match.start() for w in words):
                    continue
                words.append((match.group(), match.start(), match.end()))

        # ── Word-level mention detection ─────────────────────────────────────
        for word, start, end in words:
            clean_word = _normalize_word(word)
            if clean_word in _INDEPENDENT_PRONOUNS:
                if start not in seen_spans:
                    seen_spans.add(start)
                    independent.append(
                        AnaphoraMention(text=word, mention_type="independent_pronoun", start=start, end=end)
                    )
            elif clean_word in _DEMONSTRATIVES:
                if start not in seen_spans:
                    seen_spans.add(start)
                    demonstratives.append(
                        AnaphoraMention(text=word, mention_type="demonstrative", start=start, end=end)
                    )
            elif clean_word in _RELATIVE_LINKS:
                if start not in seen_spans:
                    seen_spans.add(start)
                    relatives.append(AnaphoraMention(text=word, mention_type="relative_link", start=start, end=end))
            # Attached pronoun suffixes (longest suffix first).
            # Final ``ي`` in verbal patterns (``يمشي``, ``يرمي``) is part of
            # the root, not a first-person pronoun.
            else:
                if clean_word in _VERBAL_YA_EXCEPTIONS:
                    continue
                for suffix, suffix_kind in _ATTACHED_PRONOUN_SUFFIXES:
                    if clean_word.endswith(suffix) and len(clean_word) - len(suffix) >= 2:
                        # Same token may carry only one pronoun suffix.
                        if start not in seen_spans:
                            seen_spans.add(start)
                            attached.append(
                                AnaphoraMention(
                                    text=word, mention_type=f"attached_pronoun_{suffix_kind}", start=start, end=end
                                )
                            )
                        break

        # ── Lexical re-mention across sentences ──────────────────────────────
        rementions: List[str] = []
        if sentence_count >= 2:
            word_sentences: Dict[str, set] = {}
            for seg_index, (segment, _seg_start, _seg_end) in enumerate(sentences):
                for match in _WORD_RE.finditer(segment):
                    clean = _normalize_word(match.group())
                    if clean in _REMENTION_STOP or len(clean) <= 2:
                        continue
                    word_sentences.setdefault(clean, set()).add(seg_index)
            rementions = sorted(word for word, sentence_indexes in word_sentences.items() if len(sentence_indexes) >= 2)

        # ── Density, cohesion score and label ────────────────────────────────
        word_count = len(words) if words else 0
        mention_count = len(attached) + len(independent) + len(demonstratives) + len(relatives)
        density = (mention_count / word_count) * 100.0 if word_count else 0.0

        # Cohesion score combines mention variety (kinds present) with
        # re-mention coverage relative to sentences.
        variety = (
            (len(attached) > 0) + (len(independent) > 0) + (len(demonstratives) > 0) + (len(relatives) > 0)
        ) / 4.0
        coverage = min(len(rementions) / max(sentence_count, 1), 1.0)
        cohesion = variety * 0.6 + coverage * 0.4

        if cohesion >= self.dense_threshold:
            label = "tightly-cohesive"
        elif cohesion >= self.moderate_threshold:
            label = "moderate"
        else:
            label = "loose"

        return AnaphoraResult(
            attached_pronouns=attached,
            independent_pronouns=independent,
            demonstratives=demonstratives,
            relative_references=relatives,
            lexical_rementions=rementions,
            reference_density=density,
            cohesion_score=cohesion,
            word_count=word_count,
            sentence_count=sentence_count,
            label=label,
        )

    def analyze_batch(self, texts: List[str]) -> List[AnaphoraResult]:
        """Run :meth:`analyze` over multiple texts."""
        return [self.analyze(text) for text in texts]


def analyze_anaphora(text: str) -> AnaphoraResult:
    """Module-level convenience wrapper for :class:`AnaphoraAnalyzer`."""
    return AnaphoraAnalyzer().analyze(text)


__all__ = [
    "AnaphoraAnalyzer",
    "AnaphoraMention",
    "AnaphoraResult",
    "analyze_anaphora",
]
