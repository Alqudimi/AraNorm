"""Arabic filler and defective-repetition analysis engine.
Locates two distinct stylistic weaknesses in Arabic prose:
+-------------------------+----------------------------------------------------+
| Signal                  | Detection approach                                 |
+-------------------------+----------------------------------------------------+
| filler phrases          | Fixed Arabic hedging / rhetorical padding         |
|                         | phrases (في الحقيقة، جدير بالذكر، لا شك أن...)   |
|                         | scanned verbatim with character offsets.          |
+-------------------------+----------------------------------------------------+
| word repetition         | An identical content word repeated within a       |
|                         | 5-word window — a sign of defective (لغوية)      |
|                         | repetition rather than intentional emphasis.      |
+-------------------------+----------------------------------------------------+
Returns both density figures normalised against content words plus a
qualitative ``label`` (``"filler_heavy"`` / ``"repetitive"`` / ``"clean"``).
Deterministic, dependency-free, and consistent with the
``aranorm.analysis`` family (dataclass results with ``to_dict``/JSON APIs).
Example
-------
>>> from aranorm.analysis.filler_analyzer import analyze_fillers
>>> result = analyze_fillers('في الحقيقة، هذا النص في الحقيقة ضعيف.')
>>> len(result.filler_spans) >= 1
True
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List

# ── Filler phrase lexicon (35+ high-frequency Arabic padding phrases) ────────
_FILLER_PHRASES: List[str] = [
    "في الحقيقة",
    "حقيقة الأمر",
    "بكل صراحة",
    "صراحة",
    "من ناحية أخرى",
    "من جهة أخرى",
    "لا شك أن",
    "لا شك في أن",
    "لا ريب أن",
    "جدير بالذكر",
    "من الجدير بالذكر",
    "في الواقع",
    "الواقع أن",
    "عمليا",
    "بمعنى آخر",
    "بعبارة أخرى",
    "يعني",
    "أي أن",
    "أي بمعنى",
    "والحقيقة أن",
    "والحقيقة",
    "في نهاية المطاف",
    "في الأخير",
    "على أي حال",
    "على العموم",
    "بشكل عام",
    "بصفة عامة",
    "إجمالا",
    "في المجمل",
    "بصورة عامة",
    "كما هو معلوم",
    "كما هو معروف",
    "مما لا شك فيه",
    "مما لا ريب فيه",
    "من المعروف أن",
    "من البديهي أن",
    "بالطبع",
    "بطبيعة الحال",
    "على الرغم من ذلك",
    "ومع ذلك",
    "في المقابل",
    "وبالإضافة إلى ذلك",
    "علاوة على ذلك",
    "ناهيك عن",
    "ناهيك أن",
    "والجدير بالذكر",
]
# Deduplicate and drop non-Arabic artefacts.
_FILLER_PHRASES = sorted(
    {phrase for phrase in _FILLER_PHRASES if all(char == " " or "\u0621" <= char <= "\u064a" for char in phrase)}
)
# ── Tokenisation helpers ─────────────────────────────────────────────────────
_WORD_RE = re.compile(r"[\u0621-\u0652\u0660-\u06690-9A-Za-z]+")
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640\u064E\u064F\u0650\u0651]")
_ALEF_NORMALISE = str.maketrans("أإآا", "اااا")


def _normalize_token(token: str) -> str:
    """Strip diacritics and normalise alef forms for comparison."""
    normalised = _DIACRITICS.sub("", token)
    return normalised.translate(_ALEF_NORMALISE)


def _span_for_phrase(text: str, phrase: str) -> List[int]:
    """Return start offsets of every verbatim occurrence of *phrase* in *text*.
    Comparison ignores diacritics and alef variants so that
    ``في الحقيقةِ`` still matches the entry ``في الحقيقة``.
    """
    norm_text = _normalize_token(text)
    norm_phrase = _normalize_token(phrase)
    offsets: List[int] = []
    index = 0
    while True:
        found = norm_text.find(norm_phrase, index)
        if found < 0:
            break
        offsets.append(found)
        index = found + len(norm_phrase)
    return offsets


@dataclass
class FillerSpan:
    """A filler phrase occurrence located in the source text.
    Attributes
    ----------
    text:
        The filler phrase as it appears in the source.
    start:
        Character offset of the span start.
    end:
        Character offset of the span end.
    """

    text: str
    start: int
    end: int

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "start": self.start, "end": self.end}


@dataclass
class RepetitionSpan:
    """A defective word repetition located in the source text.
    Attributes
    ----------
    word:
        The repeated content word.
    first_start:
        Character offset of the first occurrence.
    second_start:
        Character offset of the second occurrence.
    second_end:
        Character offset of the second occurrence's end.
    """

    word: str
    first_start: int
    second_start: int
    second_end: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "first_start": self.first_start,
            "second_start": self.second_start,
            "second_end": self.second_end,
        }


@dataclass
class FillerResult:
    """Consolidated filler / repetition analysis for a single Arabic text.
    Attributes
    ----------
    filler_spans:
        Detected filler phrases with character offsets.
    repetition_spans:
        Defective same-word repetitions with character offsets.
    filler_count:
        Number of filler phrases found.
    repetition_count:
        Number of defective repetitions found.
    filler_density:
        Filler phrases per content word (0.0–1.0).
    repetition_density:
        Repetitions per content word (0.0–1.0).
    word_count:
        Total content words used for density computation.
    label:
        ``"filler_heavy"`` (dense padding), ``"repetitive"`` (defective
        repetition), or ``"clean"`` (no significant weakness).
    """

    filler_spans: List[FillerSpan]
    repetition_spans: List[RepetitionSpan]
    filler_count: int
    repetition_count: int
    filler_density: float
    repetition_density: float
    word_count: int
    label: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filler_spans": [span.to_dict() for span in self.filler_spans],
            "repetition_spans": [span.to_dict() for span in self.repetition_spans],
            "filler_count": self.filler_count,
            "repetition_count": self.repetition_count,
            "filler_density": round(self.filler_density, 4),
            "repetition_density": round(self.repetition_density, 4),
            "word_count": self.word_count,
            "label": self.label,
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


@dataclass
class FillerAnalyzer:
    """Arabic filler / defective-repetition detection over prose.
    Parameters
    ----------
    filler_threshold:
        Filler density at or above which the text is labelled
        ``"filler_heavy"``.
    repetition_threshold:
        Repetition density at or above which the text is labelled
        ``"repetitive"``.
    repetition_window:
        Maximum distance (in words) between two occurrences before they
        stop counting as a defective repetition.
    """

    filler_threshold: float = 0.10
    repetition_threshold: float = 0.05
    repetition_window: int = 5

    def analyze(self, text: str) -> FillerResult:
        """Detect fillers and defective repetitions in *text*."""
        # ── Filler phrases ───────────────────────────────────────────────
        spans: List[FillerSpan] = []
        for phrase in _FILLER_PHRASES:
            for start in _span_for_phrase(text, phrase):
                spans.append(
                    FillerSpan(
                        text=text[start : start + len(phrase)],
                        start=start,
                        end=start + len(phrase),
                    )
                )
        spans.sort(key=lambda span: span.start)
        # ── Word repetitions within a window ─────────────────────────────
        words = [(match.group(), match.start(), match.end()) for match in _WORD_RE.finditer(text)]
        reported: set = set()
        repetitions: List[RepetitionSpan] = []
        for index, (word, start, end) in enumerate(words):
            normalised = _normalize_token(word)
            if len(normalised) <= 2:
                continue  # two-letter words repeat legitimately (و، في، من...).
            for lookback in range(1, min(self.repetition_window, index) + 1):
                candidate, candidate_start, candidate_end = words[index - lookback]
                if _normalize_token(candidate) == normalised:
                    anchor = (candidate_start, start)
                    if anchor in reported:
                        continue
                    reported.add(anchor)
                    repetitions.append(
                        RepetitionSpan(
                            word=word,
                            first_start=candidate_start,
                            second_start=start,
                            second_end=end,
                        )
                    )
                    break
        word_count = len(words) if words else 0
        filler_density = len(spans) / word_count if word_count else 0.0
        repetition_density = len(repetitions) / word_count if word_count else 0.0
        # Trim repetitions whose first occurrence sits inside a filler span
        # (e.g. ``في الحقيقة ... الحقيقة`` — the repeated word belongs to
        # the padding phrase itself, not to defective prose repetition).
        if spans:
            filler_ranges = [(span.start, span.end) for span in spans]
            repetitions = [
                repetition
                for repetition in repetitions
                if not any(start <= repetition.first_start < end for start, end in filler_ranges)
            ]
            repetition_density = len(repetitions) / word_count if word_count else 0.0
        if filler_density >= self.filler_threshold:
            label = "filler_heavy"
        elif repetition_density >= self.repetition_threshold:
            label = "repetitive"
        else:
            label = "clean"
        return FillerResult(
            filler_spans=spans,
            repetition_spans=repetitions,
            filler_count=len(spans),
            repetition_count=len(repetitions),
            filler_density=filler_density,
            repetition_density=repetition_density,
            word_count=word_count,
            label=label,
        )

    def analyze_batch(self, texts: List[str]) -> List[FillerResult]:
        """Analyze a list of texts independently."""
        return [self.analyze(text) for text in texts]


def analyze_fillers(text: str) -> FillerResult:
    """Convenience function analysing fillers / repetition in *text*.
    Example
    -------
    >>> result = analyze_fillers("في الحقيقة هذا النص في الحقيقة ضعيف.")
    >>> result.filler_count >= 1
    True
    """
    return FillerAnalyzer().analyze(text)
