"""Arabic register (style) analysis: formal vs informal vs digital signals.

An Arabic text's *register* reveals who the intended audience is and how the
author presents themselves. This module scores three independent signal
families and derives a single style index:

+--------------------+--------------------------------------------------------+
| Signal family      | Rationale                                              |
+--------------------+--------------------------------------------------------+
| formal_markers     | Modern Standard Arabic markers: hamza-carrying forms,  |
|                    | classical particles (إذ، كي، لذا، حيثما), tanween and   |
|                    | long classical words signal prepared / literary prose. |
+--------------------+--------------------------------------------------------+
| colloquial_markers | Dialectal/colloquial vocabulary tokens (شكو، هيك،      |
|                    | إيش، دحين، وين، حلوين, ...) pull the text toward       |
|                    | informal speech.                                       |
+--------------------+--------------------------------------------------------+
| digital_signals    | Digital-native cues: emoji density, character          |
|                    | elongation (ممتازاااا), internet slang markers (555,    |
|                    | lol transliterations), all suggest chat/social-media   |
|                    | register.                                              |
+--------------------+--------------------------------------------------------+

The overall ``style_index`` is a weighted blend:

    style_index = 0.45 * formal - 0.40 * colloquial - 0.35 * digital

and is mapped to a label in ``[-1, 1]``: ``"formal"``, ``"semi_formal"``,
``"informal"``, or ``"digital"``. An index near zero means ``"mixed"``.

Example
-------
>>> from aranorm.analysis.style_analyzer import analyze_style
>>> result = analyze_style("حيثما وجدت الإمكانية، ينبغي الاستغلال الأمثل لها")
>>> result.label == "formal"
True
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Words / particles strongly associated with Modern Standard Arabic.
_FORMAL_MARKERS = frozenset(
    [
        "إذ",
        "كي",
        "لذا",
        "بالتالي",
        "علاوة",
        "حيثما",
        "أية",
        "كلا",
        "أيضاً",
        "حسبما",
        "بموجب",
        "بناءً",
        "وفقاً",
        "حيث",
        "لدي",
        "بينما",
        "رغم",
        "بالرغم",
        "المنظمة",
        "التنمية",
        "استراتيجية",
        "الاستراتيجية",
        "التقارير",
        "التوصيات",
        "اجتماع",
        "الرئيس",
    ]
)

# Common dialectal / colloquial vocabulary tokens across major dialects.
_COLLOQUIAL_MARKERS = frozenset(
    [
        "شكو",
        "شلكم",
        "هيك",
        "هيكولا",
        "إيش",
        "شنو",
        "واش",
        "دحين",
        "الحين",
        "هسا",
        "وين",
        "فوق",
        "حلوين",
        "حلوين",
        "شو",
        "شلون",
        "إزيك",
        "عامل",
        "يعني",
        "بس",
        "إله",
        "ديري",
        "ديري",
        "حبيبي",
        "يلا",
        "خلاص",
        "ماشي",
        "تماما",
        "زبالة",
    ]
)

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map
    "\U0001f1e0-\U0001f1ff"  # flags
    "\U00002702-\U000027b0"
    "\U0000fe00-\U0000fe0f"
    "\U0001f900-\U0001f9ff"
    "]",
    flags=re.UNICODE,
)

# Elongated character runs such as ممتااااااز or هههههه.
_ELONGATION_PATTERN = re.compile(r"([\u0621-\u064A\u0671-\u06D3])\1{3,}")

# Chat-specific slang markers (transliterated laughter, internet shorthands).
_CHAT_SLANG_PATTERNS = [
    re.compile(r"\b555+\b"),
    re.compile(r"\b5+ه+\b"),
    re.compile(r"\bxddd?\b", flags=re.IGNORECASE),
    re.compile(r"\blol+\b", flags=re.IGNORECASE),
    re.compile(r"\b[اأ]وووو+\b"),
]

_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u0671-\u06D3]{2,}")
_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")


def _normalize(word: str) -> str:
    """Strip diacritics/tatweel and normalize alef-hamza for matching."""
    cleaned = _DIA_RE.sub("", word)
    mapping = str.maketrans("أإآ", "ااا")
    return cleaned.translate(mapping)


@dataclass
class StyleSignals:
    """Normalized signal intensities for the three register families."""

    formal_markers: float
    colloquial_markers: float
    digital_signals: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "formal_markers": self.formal_markers,
            "colloquial_markers": self.colloquial_markers,
            "digital_signals": self.digital_signals,
        }


@dataclass
class StyleAnalysisResult:
    """Result of a style/register analysis over Arabic text."""

    text: str
    style_index: float
    label: str
    signals: StyleSignals
    formal_words: List[str]
    colloquial_words: List[str]
    elongations: List[str]
    emoji_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "style_index": self.style_index,
            "label": self.label,
            "signals": self.signals.to_dict(),
            "formal_words": self.formal_words,
            "colloquial_words": self.colloquial_words,
            "elongations": self.elongations,
            "emoji_count": self.emoji_count,
        }

    def to_json(self, indent: Optional[int] = 2, ensure_ascii: bool = False) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


def _label_for(index: float) -> str:
    if index >= 0.12:
        return "formal"
    if index >= 0.03:
        return "semi_formal"
    if index <= -0.25:
        return "informal"
    if index <= -0.03:
        return "mixed"
    return "digital"


class StyleAnalyzer:
    """Register (style) analysis for Arabic text.

    Example
    -------
    >>> analyzer = StyleAnalyzer()
    >>> result = analyzer.analyze("يلا حبيبي شو الجديد")
    >>> result.label in ("informal", "digital", "mixed")
    True
    """

    def __init__(
        self,
        formal_weight: float = 0.45,
        colloquial_weight: float = 0.40,
        digital_weight: float = 0.35,
    ) -> None:
        self._formal_weight = formal_weight
        self._colloquial_weight = colloquial_weight
        self._digital_weight = digital_weight

    # ── Internals ────────────────────────────────────────────────────────────

    def _extract_words(self, text: str) -> List[str]:
        return [word for word in _ARABIC_WORD.findall(text)]

    def _formal_signal(self, words: List[str]) -> Tuple[float, List[str]]:
        if not words:
            return 0.0, []
        matched = [word for word in words if _normalize(word) in _FORMAL_MARKERS]
        return len(matched) / len(words), matched

    def _colloquial_signal(self, words: List[str]) -> Tuple[float, List[str]]:
        if not words:
            return 0.0, []
        matched = [word for word in words if _normalize(word) in _COLLOQUIAL_MARKERS]
        return len(matched) / len(words), matched

    def _digital_signal(self, text: str, words: List[str]) -> Tuple[float, List[str]]:
        signals: List[str] = []
        emoji_count = len(_EMOJI_PATTERN.findall(text))
        if emoji_count > 0:
            signals.append(f"emoji:{emoji_count}")
        elongations = [match.group(0) for match in _ELONGATION_PATTERN.finditer(text)]
        if elongations:
            signals.append(f"elongation:{len(elongations)}")
        slang_hits = sum(1 for pattern in _CHAT_SLANG_PATTERNS if pattern.search(text))
        if slang_hits:
            signals.append(f"slang:{slang_hits}")
        if not signals:
            return 0.0, []
        total_chars = len(text) or 1
        density = len(signals) / (total_chars / 100.0)
        return min(density, 1.0), signals

    # ── Public API ───────────────────────────────────────────────────────────

    def analyze(self, text: str) -> StyleAnalysisResult:
        """Score the register signals of *text* and return a style result."""
        words = self._extract_words(text)
        formal, formal_words = self._formal_signal(words)
        colloquial, colloquial_words = self._colloquial_signal(words)
        digital, elongations = self._digital_signal(text, words)

        style_index = (
            self._formal_weight * formal - self._colloquial_weight * colloquial - self._digital_weight * digital
        )
        emoji_count = len(_EMOJI_PATTERN.findall(text))
        return StyleAnalysisResult(
            text=text,
            style_index=style_index,
            label=_label_for(style_index),
            signals=StyleSignals(
                formal_markers=formal,
                colloquial_markers=colloquial,
                digital_signals=digital,
            ),
            formal_words=formal_words,
            colloquial_words=colloquial_words,
            elongations=elongations,
            emoji_count=emoji_count,
        )

    def analyze_batch(self, texts: List[str]) -> List[StyleAnalysisResult]:
        """Analyze a list of texts independently."""
        return [self.analyze(text) for text in texts]


def analyze_style(text: str) -> StyleAnalysisResult:
    """Module-level convenience wrapper over :class:`StyleAnalyzer`."""
    return StyleAnalyzer().analyze(text)
