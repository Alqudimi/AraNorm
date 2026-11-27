"""Arabic emotion detection across eight Plutchik-style buckets.

While :class:`SentimentAnalyzer` reduces a text to a single polarity number,
readers often want to know *which* emotion a text expresses. This module
tags words against an emotion lexicon organized into eight buckets and
reports the dominant emotion together with the full distribution.

+----------+---------------------------------------------------------------+
| Bucket   | Representative vocabulary                                     |
+----------+---------------------------------------------------------------+
| joy      | سعادة، فرح، بهجة، ابتسامة، رائع، ممتاز، جميل، حب، نجاح،       |
|          | تهنئة، ضحك                                                    |
+----------+---------------------------------------------------------------+
| sadness  | حزن، بكاء، دموع، ألم، فقد، وفاة، كآبة، أسي، شجن، فقدت،      |
|          | خسارة                                                         |
+----------+---------------------------------------------------------------+
| anger    | غضب، عصبية، غاضب، سخط، استياء، احتقان، صراخ، كراهية          |
+----------+---------------------------------------------------------------+
| fear     | خوف، رعب، رهبة، وجل، فزع، ذعر، قلق، هلع، مرعب، مخيف          |
+----------+---------------------------------------------------------------+
| surprise | مفاجأة، الدهشة، استغراب، مستغرب، مفاجئ، صدمة، غير متوقع      |
+----------+---------------------------------------------------------------+
| disgust  | اشمئزاز، مقرف، بغيض، تقزز، مقزز، كريه، منفور                  |
+----------+---------------------------------------------------------------+
| trust    | ثقة، أمان، طمأنينة، اطمئنان، موثوق، صادق، أمانة، مخلص         |
+----------+---------------------------------------------------------------+
| hope     | أمل، تمني، توقع، تفاؤل، متفائل، أمنية، رجاء، منتظر            |
+----------+---------------------------------------------------------------+

The dominant emotion is the bucket with the highest match count; if several
buckets tie, the first one in lexical order wins. An empty result returns
``"neutral"`` with a zeroed distribution.

Example
-------
>>> from aranorm.analysis.emotion_analyzer import analyze_emotions
>>> result = analyze_emotions("سعادتي كبيرة بفرحة النجاح والتهنئة الصادقة")
>>> result.dominant_emotion
'joy'
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u0671-\u06D3]{2,}")

# Each bucket maps canonical tokens to their normalized forms.
_EMOTION_LEXICON: Dict[str, Tuple[str, ...]] = {
    "joy": (
        "سعادة",
        "سعادته",
        "سعادتها",
        "فرح",
        "فرحة",
        "فرحان",
        "بهجة",
        "مبهج",
        "ابتسامة",
        "يبتسم",
        "رائع",
        "رائعة",
        "ممتاز",
        "ممتازة",
        "جميل",
        "جميلة",
        "حب",
        "محبة",
        "يحب",
        "نجاح",
        "ينجح",
        "تهنئة",
        "مبارك",
        "الضحك",
        "ضاحك",
        "مغبوط",
    ),
    "sadness": (
        "حزن",
        "حزين",
        "يحتزن",
        "بكاء",
        "دموع",
        "دمعه",
        "ألم",
        "الم",
        "فقد",
        "فقدت",
        "وفاة",
        "كآبة",
        "اكتئاب",
        "أسى",
        "شجن",
        "كرب",
        "خسارة",
        "كسر",
    ),
    "anger": (
        "غضب",
        "غاضب",
        "عصبية",
        "عصبي",
        "سخط",
        "استياء",
        "احتقان",
        "صراخ",
        "كراهية",
        "بغيض",
        "مقزز",
        "حقد",
        "ضيق",
        "انزعاج",
        "منزعج",
    ),
    "fear": (
        "خوف",
        "خائف",
        "رعب",
        "مرعوب",
        "وجل",
        "رهبة",
        "المرعب",
        "فزع",
        "فزعان",
        "ذعر",
        "قلق",
        "قلقان",
        "هلع",
        "مرعب",
        "مخيف",
        "توتر",
        "متوتر",
        "جزع",
    ),
    "surprise": (
        "مفاجأة",
        "المفاجأة",
        "مفاجئ",
        "مفاجئة",
        "دهشة",
        "مندهش",
        "استغراب",
        "مستغرب",
        "صدمة",
        "مصعوق",
        "غير",
        "متوقع",
    ),
    "disgust": (
        "اشمئزاز",
        "مقرف",
        "مقيت",
        "بغيض",
        "تقزز",
        "مقزز",
        "كريه",
        "منفور",
        "شنيع",
        "فظيع",
        "نتن",
    ),
    "trust": (
        "ثقة",
        "ثقة",
        "أمان",
        "امان",
        "اطمئنان",
        "طمأنينة",
        "موثوق",
        "صادق",
        "صديق",
        "أمانة",
        "امانة",
        "مخلص",
        "إخلاص",
        "اخلاص",
        "وفاء",
        "مصدوق",
    ),
    "hope": (
        "أمل",
        "امل",
        "آمال",
        "تمني",
        "توقع",
        "يتوقع",
        "تفاؤل",
        "متفائل",
        "أمنية",
        "امنية",
        "رجاء",
        "مرجو",
        "منتظر",
        "يرجو",
    ),
}

# Canonical normalized forms per bucket for fast lookup.


def _normalize_tokens(tokens: Tuple[str, ...]) -> List[str]:
    """Strip diacritics and normalize hamza-bearing alef forms."""
    out: List[str] = []
    for token in tokens:
        cleaned = _DIA_RE.sub("", token)
        out.append(cleaned.translate(str.maketrans("أإآ", "ااا")))
    return out


_NORMALIZED_LEXICON: Dict[str, frozenset] = {
    bucket: frozenset(_normalize_tokens(tokens)) for bucket, tokens in _EMOTION_LEXICON.items()
}


@dataclass
class EmotionCounts:
    """Per-bucket match counts found in the analyzed text."""

    joy: int = 0
    sadness: int = 0
    anger: int = 0
    fear: int = 0
    surprise: int = 0
    disgust: int = 0
    trust: int = 0
    hope: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "joy": self.joy,
            "sadness": self.sadness,
            "anger": self.anger,
            "fear": self.fear,
            "surprise": self.surprise,
            "disgust": self.disgust,
            "trust": self.trust,
            "hope": self.hope,
        }

    def total(self) -> int:
        return self.joy + self.sadness + self.anger + self.fear + self.surprise + self.disgust + self.trust + self.hope


@dataclass
class EmotionAnalysisResult:
    """Result of an emotion analysis over Arabic text."""

    text: str
    dominant_emotion: str
    counts: EmotionCounts
    matched_words: Dict[str, List[str]]

    @property
    def confidence(self) -> float:
        """Share of dominant emotion matches among all emotion matches."""
        total = self.counts.total()
        if total == 0:
            return 0.0
        dominant = getattr(self.counts, self.dominant_emotion, 0)
        return dominant / total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "dominant_emotion": self.dominant_emotion,
            "confidence": self.confidence,
            "counts": self.counts.to_dict(),
            "matched_words": self.matched_words,
        }

    def to_json(self, indent: Optional[int] = 2, ensure_ascii: bool = False) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


def _bucket_for(normalized: str) -> Optional[str]:
    """Return the first bucket whose lexicon contains *normalized*."""
    for bucket, forms in _NORMALIZED_LEXICON.items():
        if normalized in forms:
            return bucket
    return None


class EmotionAnalyzer:
    """Plutchik-style emotion detection for Arabic text.

    Example
    -------
    >>> analyzer = EmotionAnalyzer()
    >>> result = analyzer.analyze("خوف وذعر مع رغبة في النجاة")
    >>> result.dominant_emotion in ("fear", "anger", "surprise")
    True
    """

    def __init__(self) -> None:
        self._word_re = _ARABIC_WORD
        self._dia_re = _DIA_RE

    # ── Internals ────────────────────────────────────────────────────────────

    def _normalize_word(self, word: str) -> str:
        cleaned = self._dia_re.sub("", word)
        return cleaned.translate(str.maketrans("أإآ", "ااا"))

    # ── Public API ───────────────────────────────────────────────────────────

    def analyze(self, text: str) -> EmotionAnalysisResult:
        """Detect the emotion distribution of *text*."""
        counts = EmotionCounts()
        matched_words: Dict[str, List[str]] = {bucket: [] for bucket in counts.to_dict()}
        for word in self._word_re.findall(text):
            bucket = _bucket_for(self._normalize_word(word))
            if bucket is None:
                continue
            current = getattr(counts, bucket)
            setattr(counts, bucket, current + 1)
            if word not in matched_words[bucket]:
                matched_words[bucket].append(word)
        total = counts.total()
        dominant = "neutral"
        if total > 0:
            dominant = max(
                (bucket for bucket in counts.to_dict() if getattr(counts, bucket) > 0),
                key=lambda bucket: (getattr(counts, bucket), bucket),
            )
        return EmotionAnalysisResult(
            text=text,
            dominant_emotion=dominant,
            counts=counts,
            matched_words=matched_words,
        )

    def analyze_batch(self, texts: List[str]) -> List[EmotionAnalysisResult]:
        """Analyze a list of texts independently."""
        return [self.analyze(text) for text in texts]


def analyze_emotions(text: str) -> EmotionAnalysisResult:
    """Module-level convenience wrapper over :class:`EmotionAnalyzer`."""
    return EmotionAnalyzer().analyze(text)
