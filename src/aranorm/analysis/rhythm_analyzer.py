"""Arabic rhythm and rhetorical-cadence analysis.
Measures *rhythmic signal strength* in Arabic prose/poetry texts through
four deterministic, rule-based indicators:

+----------------------+--------------------------------------------------------+
| Indicator            | Rationale                                              |
+----------------------+--------------------------------------------------------+
| saj_signals          | Paired clause endings sharing the final 2-3 radicals   |
|                      | (سجع / rhymed prose), detected by stripping common     |
|                      | suffixes/punctuation and comparing trailing stems.     |
+----------------------+--------------------------------------------------------+
| parallel_balance     | Near-equal sentence-length runs (balance coefficient   |
|                      | close to 1.0) suggest deliberate symmetrical drafting. |
+----------------------+--------------------------------------------------------+
| repetition_density   | Whole-word repetition beyond functional repetition     |
|                      | (stop words / pronouns) signals refrain-like rhythm.   |
+----------------------+--------------------------------------------------------+
| poetic_line_ratio    | Ratio of short line breaks (< ~12 tokens) to total     |
|                      | lines; elevated ratios flag verse-like formatting.     |
+----------------------+--------------------------------------------------------+

The combined ``rhythm_index`` is a weighted blend of the normalised indicators
and maps to labels ``"rhythmic"``, ``"semi_rhythmic"``, ``"flat"``. All inputs
are diacritics-stripped and hamza-normalised for robust matching.

Example
-------
>>> from aranorm.analysis.rhythm_analyzer import analyze_rhythm
>>> result = analyze_rhythm("كتبَ، فتعلم. وعلمَ، فنفع. ونفعَ، فانتفع")
>>> result.label == "rhythmic"
True
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_WORD_RE = re.compile(r"[\u0621-\u064A\u0671-\u06D30-9]+")
# Suffixes that do not change the rhyming stem when trailing a word.
_TAIL_SUFFIXES = ("ات", "تان", "ين", "ون", "وا", "ي", "ها", "ه", "نا", "كما", "كم")
_SAJ_MIN_CLAUSE_WORDS = 1
_SAJ_MIN_STEM = 2  # minimum trailing-stem length (letters) to count as saj.


@dataclass(frozen=True)
class SajPair:
    """A detected saj (rhymed-prose) pair with character offsets."""

    clause_a: str
    clause_b: str
    shared_stem: str
    start: int
    end: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clause_a": self.clause_a,
            "clause_b": self.clause_b,
            "shared_stem": self.shared_stem,
            "start": self.start,
            "end": self.end,
        }


@dataclass(frozen=True)
class RhythmResult:
    """Result of rhythm analysis over an Arabic text."""

    rhythm_index: float
    label: str
    saj_signals: int
    saj_pairs: List[SajPair]
    parallel_balance: float
    repetition_density: float
    poetic_line_ratio: float
    sentence_count: int
    word_count: int
    traces: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rhythm_index": round(self.rhythm_index, 4),
            "label": self.label,
            "saj_signals": self.saj_signals,
            "saj_pairs": [pair.to_dict() for pair in self.saj_pairs],
            "parallel_balance": round(self.parallel_balance, 4),
            "repetition_density": round(self.repetition_density, 4),
            "poetic_line_ratio": round(self.poetic_line_ratio, 4),
            "sentence_count": self.sentence_count,
            "word_count": self.word_count,
            "traces": self.traces,
        }


def _normalize(token: str) -> str:
    """Strip diacritics and unify hamza/alef forms for robust matching."""
    cleaned = _DIA_RE.sub("", token)
    return cleaned.translate(str.maketrans("أإآ", "ااا"))


def _strip_trailing_suffixes(token: str) -> str:
    """Remove common clitic suffixes to expose the rhyming stem."""
    normalized = _normalize(token)
    if not normalized:
        return ""
    for suffix in _TAIL_SUFFIXES:
        if normalized.endswith(suffix) and len(normalized) > len(suffix) + 1:
            return normalized[: -len(suffix)]
    return normalized


def _leading_prefixes_stripped(token: str) -> str:
    """Strip conjunctive prefixes (و، ف، ب، ك) from a clause-final token."""
    word = _normalize(token)
    # Repeatedly peel a single conjunctive prefix when the remainder is
    # long enough to still be a content word.
    while len(word) > 3 and word and word[0] in "وبلفك":
        word = word[1:]
    return word


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"[.!?؟\n]+", text)
    return [part.strip() for part in parts if part.strip()]


def _words(text: str) -> List[str]:
    return _WORD_RE.findall(text)


def _saj_pairs_for_clauses(clauses: List[str]) -> List[SajPair]:
    """Pair consecutive clause *pairs* whose trailing stems rhyme (classic saj)."""
    pairs: List[SajPair] = []
    # Classic saj rhymes the ends of two balanced halves; pair clauses two by two.
    paired = list(zip(clauses[0::2], clauses[1::2]))
    for first, second in paired:
        first_words = _words(first)
        second_words = _words(second)
        if len(first_words) < _SAJ_MIN_CLAUSE_WORDS or len(second_words) < _SAJ_MIN_CLAUSE_WORDS:
            continue
        stem_a = _strip_trailing_suffixes(_leading_prefixes_stripped(first_words[-1]))
        stem_b = _strip_trailing_suffixes(_leading_prefixes_stripped(second_words[-1]))
        if not stem_a or not stem_b:
            continue
        # Require at least two shared trailing letters to count as saj.
        overlap = 0
        for letter_a, letter_b in zip(reversed(stem_a), reversed(stem_b)):
            if letter_a == letter_b:
                overlap += 1
            else:
                break
        if overlap >= _SAJ_MIN_STEM:
            pairs.append(
                SajPair(
                    clause_a=first.strip(),
                    clause_b=second.strip(),
                    shared_stem=stem_a[-overlap:],
                    start=len(first) - len(first_words[-1]),
                    end=len(first) + 1 + len(second),
                )
            )
    return pairs


def _parallel_balance_coefficient(sentences: List[str]) -> float:
    """Ratio of the smaller sentence length to the larger (mean of pairwise)."""
    lengths = [len(_words(sentence)) for sentence in sentences]
    if len(lengths) < 2:
        return 0.0
    total = 0.0
    pairs = 0
    for length_a, length_b in zip(lengths, lengths[1:]):
        maximum = max(length_a, length_b)
        if maximum == 0:
            continue
        total += min(length_a, length_b) / maximum
        pairs += 1
    return total / pairs if pairs else 0.0


def _repetition_density(words: List[str]) -> float:
    """Non-functional word repetition ratio against unique content words."""
    stop_words = {
        "و",
        "في",
        "من",
        "إلى",
        "على",
        "عن",
        "مع",
        "ال",
        "أن",
        "إن",
        "ثم",
        "أو",
        "ما",
        "لا",
        "هو",
        "هي",
        "هم",
        "هن",
        "ذلك",
        "هذه",
        "هذا",
        "به",
        "بها",
        "كان",
        "يكون",
        "هو",
        "وهي",
        "بين",
        "حتى",
        "كل",
        "أي",
        "غير",
        "عند",
        "بعد",
        "قبل",
        "فإن",
    }
    content = [_normalize(word) for word in words if word not in stop_words]
    if len(content) < 4:
        return 0.0
    from collections import Counter

    counts = Counter(content)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return repeated / len(content)


def _poetic_line_ratio(text: str) -> float:
    """Fraction of text lines short enough to resemble verse lines."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) < 2:
        return 0.0
    short_lines = sum(1 for line in lines if len(_words(line)) <= 12)
    return short_lines / len(lines)


@dataclass
class RhythmAnalyzer:
    """Arabic rhythm and rhetorical-cadence analysis."""

    saj_weight: float = 0.40
    balance_weight: float = 0.25
    repetition_weight: float = 0.20
    line_weight: float = 0.15

    def analyze(self, text: str) -> RhythmResult:
        sentences = _split_sentences(text)
        words = _words(text)
        clauses = [clause.strip() for clause in re.split(r"[،,]", text) if clause.strip()]
        saj_pairs = _saj_pairs_for_clauses(clauses)
        balance = _parallel_balance_coefficient(sentences)
        repetition = _repetition_density(words)
        line_ratio = _poetic_line_ratio(text)
        index = (
            self.saj_weight * min(1.0, saj_pairs and (len(saj_pairs) / max(1, len(sentences) - 1)) * 2 or 0.0)
            + self.balance_weight * balance
            + self.repetition_weight * min(1.0, repetition * 4)
            + self.line_weight * line_ratio
        )
        if index >= 0.35:
            label = "rhythmic"
        elif index >= 0.18:
            label = "semi_rhythmic"
        else:
            label = "flat"
        return RhythmResult(
            rhythm_index=round(index, 4),
            label=label,
            saj_signals=len(saj_pairs),
            saj_pairs=saj_pairs,
            parallel_balance=balance,
            repetition_density=repetition,
            poetic_line_ratio=line_ratio,
            sentence_count=len(sentences),
            word_count=len(words),
            traces={
                "saj_weight": self.saj_weight,
                "balance_weight": self.balance_weight,
                "repetition_weight": self.repetition_weight,
                "line_weight": self.line_weight,
            },
        )

    def analyze_batch(self, texts: List[str]) -> List[RhythmResult]:
        return [self.analyze(text) for text in texts]


def analyze_rhythm(text: str) -> RhythmResult:
    """Convenience function analysing rhythm signals in ``text``."""
    return RhythmAnalyzer().analyze(text)
