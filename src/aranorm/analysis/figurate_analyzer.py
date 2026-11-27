"""Arabic rhetorical-figure (figurative language) detection.
A deterministic, rule-based detector for common Arabic rhetorical figures
found in prose and poetry, returning typed occurrences with offsets:

+------------------------+----------------------------------------------------+
| Figure                 | Detection signal                                   |
+------------------------+----------------------------------------------------+
| tashbih (simile)       | ``كما`` / ``مثل`` / ``كـأنّ`` bridges connecting   |
|                        | two content phrases.                               |
+------------------------+----------------------------------------------------+
| tibaq (antithesis)     | Known antonym pairs (خير/شر، نور/ظلام، ...)        |
|                        | co-occurring in the same sentence.                 |
+------------------------+----------------------------------------------------+
| taraduf (synonymy)     | Known synonym pairs co-occurring in one sentence   |
|                        | (عظيم/كبير، جميل/حسن، ...).                        |
+------------------------+----------------------------------------------------+
| takrir (refrain)       | A content word repeated three or more times        |
|                        | across the text.                                   |
+------------------------+----------------------------------------------------+

The ``figure_index`` is a normalised 0-1 blend and maps to labels
``"rich"``, ``"moderate"``, ``"plain"``. Diacritics are stripped and
hamza forms unified so inflected variants match reliably.

Example
-------
>>> from aranorm.analysis.figurate_analyzer import analyze_figurative
>>> result = analyze_figurative("العلم نور، والجهل ظلام")
>>> "tibaq" in result.figures
True
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Tuple

_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_WORD_RE = re.compile(r"[\u0621-\u064A\u0671-\u06D30-9]+")
# Bridge words introducing a simile (تشبيه).
_SIMILE_BRIDGES = frozenset(["كما", "مثل", "كأن", "كأنه", "كأنها", "كن", "كال", "كالذي"])
# Known antonym pairs (طباق) — normalised stems.
_ANTONYM_PAIRS = (
    ("خير", "شر"),
    ("نور", "ظلام"),
    ("حرب", "سلام"),
    ("ليل", "نهار"),
    ("قريب", "بعيد"),
    ("كبير", "صغير"),
    ("قليل", "كثير"),
    ("صاحب", "عدو"),
    ("فرح", "حزن"),
    ("صيف", "شتاء"),
    ("صواب", "خطأ"),
    ("صدق", "كذب"),
    ("عالم", "جاهل"),
    ("غني", "فقير"),
    ("قوة", "ضعف"),
    ("ربح", "خسارة"),
    ("حياة", "موت"),
    ("بدء", "نهاية"),
    ("أعلى", "أسفل"),
    ("يمين", "شمال"),
)
# Known synonym pairs (ترادف) — normalised stems.
_SYNONYM_PAIRS = (
    ("عظيم", "كبير"),
    ("جميل", "حسن"),
    ("سريع", "عاجل"),
    ("خائف", "خشية"),
    ("حزن", "غم"),
    ("فرح", "سرور"),
    ("علم", "معرفة"),
    ("بيت", "منزل"),
    ("طريق", "سبيل"),
    ("قول", "كلام"),
)
_STOP_WORDS = frozenset(
    [
        "و",
        "في",
        "من",
        "إلى",
        "على",
        "عن",
        "مع",
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
        "بين",
        "حتى",
        "كل",
        "أي",
        "غير",
        "عند",
        "بعد",
        "قبل",
        "فإن",
    ]
)
_TAKRIR_MIN = 3


def _normalize(token: str) -> str:
    cleaned = _DIA_RE.sub("", token)
    normalised = cleaned.translate(str.maketrans("أإآ", "ااا"))
    # Strip the attached conjunction/preposition prefixes (و، ب، ل، ك، ف)
    # before checking for the definite article.
    while normalised and normalised[0] in "وبلفك" and len(normalised) > 3:
        normalised = normalised[1:]
    return normalised[2:] if normalised.startswith("ال") and len(normalised) > 3 else normalised


@dataclass(frozen=True)
class FigureOccurrence:
    """A single detected rhetorical figure with character offsets."""

    figure: str
    words: List[str]
    start: int
    end: int

    def to_dict(self) -> Dict[str, Any]:
        return {"figure": self.figure, "words": self.words, "start": self.start, "end": self.end}


@dataclass(frozen=True)
class FigurativeResult:
    """Result of rhetorical-figure detection over an Arabic text."""

    figure_index: float
    label: str
    figures: List[str]
    occurrences: List[FigureOccurrence]
    simile_count: int
    tibaq_count: int
    taraduf_count: int
    takrir_count: int
    takrir_words: List[str]
    word_count: int
    traces: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "figure_index": round(self.figure_index, 4),
            "label": self.label,
            "figures": self.figures,
            "occurrences": [occurrence.to_dict() for occurrence in self.occurrences],
            "simile_count": self.simile_count,
            "tibaq_count": self.tibaq_count,
            "taraduf_count": self.taraduf_count,
            "takrir_count": self.takrir_count,
            "takrir_words": self.takrir_words,
            "word_count": self.word_count,
            "traces": self.traces,
        }


def _words(text: str) -> List[str]:
    return _WORD_RE.findall(text)


def _word_spans(text: str) -> Iterator[Tuple[str, int, int]]:
    """Yield (normalised word, start, end) triples."""
    for match in _WORD_RE.finditer(text):
        yield _normalize(match.group()), match.start(), match.end()


def _find_similes(text: str) -> List[FigureOccurrence]:
    """Locate simile bridges followed by a content phrase within a window."""
    occurrences: List[FigureOccurrence] = []
    for match in _WORD_RE.finditer(text):
        token = _DIA_RE.sub("", match.group()).translate(str.maketrans("أإآ", "ااا"))
        if token not in _SIMILE_BRIDGES and not any(
            token.startswith(bridge) for bridge in ("كما", "مثل", "كأن", "كال")
        ):
            continue
        start = match.start()
        window_text = text[match.end() : match.end() + 80]
        window_words = _words(window_text)
        content = [word for word in window_words[:4] if word not in _STOP_WORDS]
        if content:
            occurrences.append(
                FigureOccurrence(
                    figure="tashbih",
                    words=[match.group(), *content],
                    start=start,
                    end=match.end() + 80,
                )
            )
    return occurrences


def _find_tibaq(sentences: List[str], text: str) -> List[FigureOccurrence]:
    occurrences: List[FigureOccurrence] = []
    for sentence in sentences:
        normalised = {_normalize(word) for word in _words(sentence)}
        for first, second in _ANTONYM_PAIRS:
            if first in normalised and second in normalised:
                start = text.find(sentence)
                occurrences.append(
                    FigureOccurrence(figure="tibaq", words=[first, second], start=start, end=start + len(sentence))
                )
    return occurrences


def _find_taraduf(sentences: List[str], text: str) -> List[FigureOccurrence]:
    occurrences: List[FigureOccurrence] = []
    for sentence in sentences:
        normalised = {_normalize(word) for word in _words(sentence)}
        for first, second in _SYNONYM_PAIRS:
            if first in normalised and second in normalised:
                start = text.find(sentence)
                occurrences.append(
                    FigureOccurrence(figure="taraduf", words=[first, second], start=start, end=start + len(sentence))
                )
    return occurrences


def _find_takrir(text: str) -> List[FigureOccurrence]:
    """Content words repeated three or more times (refrain signal)."""
    counts: Dict[str, List[int]] = {}
    for normalised, start, end in _word_spans(text):
        if normalised in _STOP_WORDS or len(normalised) < 3:
            continue
        counts.setdefault(normalised, []).append(start)
    occurrences: List[FigureOccurrence] = []
    for word, positions in counts.items():
        if len(positions) >= _TAKRIR_MIN:
            occurrences.append(
                FigureOccurrence(
                    figure="takrir",
                    words=[word] * len(positions),
                    start=positions[0],
                    end=positions[-1],
                )
            )
    return occurrences


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"[.!?؟\n]+", text)
    return [part.strip() for part in parts if part.strip()]


@dataclass
class FigurateAnalyzer:
    """Arabic rhetorical-figure detection."""

    simile_weight: float = 0.35
    tibaq_weight: float = 0.35
    taraduf_weight: float = 0.35
    takrir_weight: float = 0.35

    def analyze(self, text: str) -> FigurativeResult:
        words = _words(text)
        sentences = _split_sentences(text)
        simile_occurrences = _find_similes(text)
        tibaq_occurrences = _find_tibaq(sentences, text)
        taraduf_occurrences = _find_taraduf(sentences, text)
        takrir_occurrences = _find_takrir(text)
        all_occurrences = simile_occurrences + tibaq_occurrences + taraduf_occurrences + takrir_occurrences
        word_pool = max(1, len(words))
        figure_density = round(len(all_occurrences) / word_pool, 4)
        index = (
            self.simile_weight * min(1.0, len(simile_occurrences) * 0.5)
            + self.tibaq_weight * min(1.0, len(tibaq_occurrences) * 0.4)
            + self.taraduf_weight * min(1.0, len(taraduf_occurrences) * 0.4)
            + self.takrir_weight * min(1.0, len(takrir_occurrences) * 0.5)
        )
        if index >= 0.35:
            label = "rich"
        elif index >= 0.13:
            label = "moderate"
        else:
            label = "plain"
        takrir_words = [occurrence.words[0] for occurrence in takrir_occurrences]
        return FigurativeResult(
            figure_index=round(index, 4),
            label=label,
            figures=list({occurrence.figure for occurrence in all_occurrences}),
            occurrences=all_occurrences,
            simile_count=len(simile_occurrences),
            tibaq_count=len(tibaq_occurrences),
            taraduf_count=len(taraduf_occurrences),
            takrir_count=len(takrir_occurrences),
            takrir_words=takrir_words,
            word_count=len(words),
            traces={
                "simile_weight": self.simile_weight,
                "tibaq_weight": self.tibaq_weight,
                "taraduf_weight": self.taraduf_weight,
                "figure_density": figure_density,
                "takrir_weight": self.takrir_weight,
            },
        )

    def analyze_batch(self, texts: List[str]) -> List[FigurativeResult]:
        return [self.analyze(text) for text in texts]


def analyze_figurative(text: str) -> FigurativeResult:
    """Convenience function detecting rhetorical figures in ``text``."""
    return FigurateAnalyzer().analyze(text)
