"""Lexicon-based Arabic sentiment analysis.

Provides a fully dependency-free, rule-based sentiment classifier that works
on Modern Standard Arabic and the major dialects.  The classifier uses a
manually curated lexicon of positive, negative, and intensifier words, plus
negation-handling logic, to assign a polarity score and label.

Architecture
------------
* :class:`SentimentAnalyzer` — main public class.
* :class:`SentimentResult` — immutable result dataclass.
* :data:`SENTIMENT_LEXICON` — the built-in word-level lexicon.

Score range: -1.0 (very negative) to +1.0 (very positive).  0.0 is neutral.
Label: ``"positive"``, ``"negative"``, ``"neutral"``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Set, Tuple

# ── Lexicon ────────────────────────────────────────────────────────────────────

# Format: word → raw score  (+1.0 positive, -1.0 negative, fractional for weak)
_POSITIVE_WORDS: Dict[str, float] = {
    # Strong positive (1.0)
    "ممتاز": 1.0,
    "رائع": 1.0,
    "مذهل": 1.0,
    "عظيم": 1.0,
    "جميل": 0.9,
    "سعيد": 0.9,
    "سعادة": 0.9,
    "فرحان": 0.9,
    "فرح": 0.8,
    "فرحة": 0.8,
    "أحب": 0.8,
    "حب": 0.8,
    "محبة": 0.8,
    "عشق": 0.9,
    "شكر": 0.8,
    "شكرًا": 0.9,
    "شكراً": 0.9,
    "ممنون": 0.8,
    "ممنونة": 0.8,
    "نجح": 0.9,
    "نجاح": 0.9,
    "نجاحات": 0.9,
    "فاز": 0.9,
    "فوز": 0.9,
    "بديع": 0.9,
    "روعة": 0.9,
    "إبداع": 0.9,
    "إبداعي": 0.9,
    "تفوق": 0.9,
    "متفوق": 0.9,
    "تميز": 0.9,
    "مميز": 0.9,
    "مفيد": 0.7,
    "مفيدة": 0.7,
    "نافع": 0.7,
    "فائدة": 0.7,
    "صحيح": 0.6,
    "صح": 0.6,
    "صواب": 0.6,
    "دقيق": 0.6,
    "آمن": 0.7,
    "أمان": 0.7,
    "سلامة": 0.7,
    "طمأنينة": 0.7,
    "راحة": 0.7,
    "مريح": 0.7,
    "هدوء": 0.6,
    "هادئ": 0.6,
    "قوي": 0.7,
    "قوة": 0.7,
    "شجاع": 0.8,
    "شجاعة": 0.8,
    "ذكي": 0.7,
    "ذكاء": 0.7,
    "موهبة": 0.8,
    "موهوب": 0.8,
    "حلو": 0.8,
    "حلوة": 0.8,
    "لطيف": 0.7,
    "لطيفة": 0.7,
    "لطف": 0.7,
    "طيب": 0.8,
    "طيبة": 0.8,
    "كريم": 0.8,
    "كرم": 0.8,
    "مبارك": 0.8,
    "بركة": 0.8,
    "خير": 0.8,
    "بخير": 0.7,
    "تقدم": 0.7,
    "تطور": 0.7,
    "تحسن": 0.7,
    "أفضل": 0.7,
    "جيد": 0.7,
    "زين": 0.7,
    "منيح": 0.7,
    "مزيان": 0.7,
    "تمام": 0.6,
    "عادي": 0.4,
    "ماشي": 0.5,
    "حلال": 0.6,
    "صادق": 0.8,
    "أمين": 0.8,
    "صبور": 0.7,
    "صبر": 0.6,
    "وفاء": 0.8,
    "وفي": 0.8,
    "إنجاز": 0.8,
    "انتصار": 0.9,
    "انتصر": 0.9,
    "نصر": 0.9,
    "محبوب": 0.8,
    "مرغوب": 0.7,
    "مقبول": 0.6,
    "ضحك": 0.7,
    "ضحكة": 0.7,
    "ابتسامة": 0.8,
    "ابتسم": 0.7,
    "أمل": 0.7,
    "تفاؤل": 0.8,
    "متفائل": 0.8,
    "شهيد": 0.6,
    "بطل": 0.8,
    "بطولة": 0.8,
    "نظيف": 0.7,
    "حضاري": 0.7,
    "متحضر": 0.7,
    "متعاون": 0.7,
    "تعاون": 0.7,
    "تضامن": 0.7,
    "وفر": 0.6,
    "اقتصاد": 0.5,
    "ربح": 0.8,
    "ربحية": 0.8,
    "رضا": 0.8,
    "رضي": 0.7,
    "مرضٍ": 0.7,
    "يرضي": 0.7,
    "ثقة": 0.7,
    "موثوق": 0.8,
    "موثوقية": 0.8,
    "ممتن": 0.8,
    "امتنان": 0.8,
    "عرفان": 0.7,
    "منعم": 0.7,
    "نعمة": 0.7,
    "بركات": 0.8,
    "واو": 0.8,
    "رهيب": 0.9,
    "جنان": 0.9,  # Egyptian praise
    "يسلم": 0.8,
    "يعطيك العافية": 0.8,
    "وناسة": 0.9,
    "ونيس": 0.8,
    "حماس": 0.7,
    "متحمس": 0.7,
    "اشتقت": 0.7,
    "اشتياق": 0.7,
}

_NEGATIVE_WORDS: Dict[str, float] = {
    # Strong negative (-1.0)
    "سيء": -0.9,
    "سيئة": -0.9,
    "فظيع": -1.0,
    "فظيعة": -1.0,
    "مروع": -1.0,
    "مروعة": -1.0,
    "كارثة": -1.0,
    "كارثي": -1.0,
    "حزن": -0.8,
    "حزين": -0.8,
    "حزينة": -0.8,
    "يحزن": -0.8,
    "ألم": -0.8,
    "مؤلم": -0.9,
    "مؤلمة": -0.9,
    "أوجاع": -0.8,
    "خوف": -0.7,
    "خائف": -0.7,
    "مخيف": -0.8,
    "رعب": -0.9,
    "غضب": -0.8,
    "غاضب": -0.8,
    "غضبان": -0.8,
    "تعصب": -0.8,
    "كره": -0.9,
    "كراهية": -0.9,
    "يكره": -0.9,
    "فشل": -0.9,
    "فاشل": -0.9,
    "إخفاق": -0.9,
    "أخفق": -0.9,
    "خسر": -0.8,
    "خسارة": -0.9,
    "هزيمة": -0.9,
    "هُزم": -0.9,
    "مشكلة": -0.6,
    "مشاكل": -0.7,
    "أزمة": -0.8,
    "أزمات": -0.8,
    "خطأ": -0.7,
    "غلط": -0.7,
    "خطيئة": -0.8,
    "ذنب": -0.7,
    "ظلم": -0.9,
    "ظالم": -0.9,
    "فساد": -0.9,
    "فاسد": -0.9,
    "كذب": -0.9,
    "كاذب": -0.9,
    "خداع": -0.9,
    "نفاق": -0.9,
    "ضعيف": -0.6,
    "ضعف": -0.6,
    "تراجع": -0.6,
    "انهيار": -0.9,
    "مزعج": -0.7,
    "إزعاج": -0.7,
    "ضجر": -0.7,
    "ممل": -0.6,
    "خطر": -0.8,
    "خطير": -0.8,
    "خطيرة": -0.8,
    "تهديد": -0.8,
    "تعب": -0.6,
    "مرهق": -0.7,
    "إرهاق": -0.7,
    "إجهاد": -0.7,
    "مريض": -0.7,
    "مرض": -0.7,
    "وجع": -0.7,
    "أوجع": -0.7,
    "مات": -0.9,
    "موت": -0.9,
    "وفاة": -0.8,
    "حادثة": -0.7,
    "تعذيب": -1.0,
    "أذى": -0.8,
    "أذية": -0.8,
    "قلق": -0.7,
    "قلقان": -0.7,
    "توتر": -0.7,
    "ضغط": -0.6,
    "إحباط": -0.8,
    "محبط": -0.8,
    "يأس": -0.9,
    "يائس": -0.9,
    "سقط": -0.7,
    "سقوط": -0.7,
    "ضاع": -0.7,
    "ضياع": -0.7,
    "سرق": -0.9,
    "سرقة": -0.9,
    "نهب": -0.9,
    "احتيال": -0.9,
    "إهانة": -0.9,
    "أهان": -0.9,
    "تحقير": -0.9,
    "ذل": -0.8,
    "عنصرية": -0.9,
    "تمييز": -0.8,
    "إقصاء": -0.8,
    "إرهاب": -1.0,
    "إرهابي": -1.0,
    "جريمة": -0.9,
    "مجرم": -0.9,
    "منبوذ": -0.8,
    "مرفوض": -0.7,
    "بكاء": -0.7,
    "بكى": -0.7,
    "دموع": -0.7,
    "وحيد": -0.7,
    "وحدة": -0.6,
    "غربة": -0.7,
    "صعب": -0.6,
    "صعوبة": -0.6,
    "عسير": -0.7,
    "فقر": -0.8,
    "فقير": -0.7,
    "عوز": -0.7,
    "هم": -0.7,
    "غم": -0.7,
    "كئيب": -0.8,
    "اكتئاب": -0.9,
    "بشع": -0.8,
    "قبيح": -0.8,
    "وحش": -0.7,  # dialectal
    "زبالة": -0.8,
    "قذر": -0.8,
    "وقح": -0.8,
    "فاجر": -0.8,
    "تعيس": -0.8,
    "شقي": -0.7,
}

# Intensifiers — multiply the nearby score
_INTENSIFIERS: Dict[str, float] = {
    "جداً": 1.5,
    "جدا": 1.5,
    "كثيراً": 1.4,
    "كثيرا": 1.4,
    "للغاية": 1.6,
    "بشكل كبير": 1.4,
    "كبيراً": 1.3,
    "كبير جداً": 1.6,
    "أوي": 1.5,
    "وايد": 1.4,
    "برشا": 1.4,
    "ياسر": 1.4,
    "بزاف": 1.4,
    "شديد": 1.4,
    "شديداً": 1.5,
    "قوي": 1.3,
    "قوياً": 1.4,
    "تماماً": 1.2,
    "تمام": 1.1,
    "خالص": 1.3,
    "ما شاء الله": 1.5,
    "والله": 1.2,
    "بالله": 1.2,
    "أكيد": 1.1,
    "بالتأكيد": 1.2,
    "حتماً": 1.2,
    "مرة": 1.3,  # Gulf: مرة زين (very good)
    "كتير": 1.3,
    "وايد": 1.4,
}

# Negation words — flip the polarity of the following sentiment word
_NEGATION_WORDS: FrozenSet[str] = frozenset(
    {
        "لا",
        "لن",
        "لم",
        "ليس",
        "ليست",
        "لست",
        "لسنا",
        "لستم",
        "مش",
        "مو",
        "ما",
        "مب",
        "موب",  # dialectal negations
        "غير",
        "بدون",
        "دون",
        "لا يوجد",
        "لا توجد",
        "ليس هناك",
        "لا شيء",
        "لم يكن",
        "لم تكن",
    }
)

# Negation scope: how many tokens after a negation word are affected
_NEGATION_WINDOW = 3

# ── Result dataclass


@dataclass
class SentimentResult:
    """Result of lexicon-based Arabic sentiment analysis.

    Attributes
    ----------
    text:
        Original input text.
    score:
        Composite sentiment score in [-1.0, 1.0].
    label:
        ``"positive"``, ``"negative"``, or ``"neutral"``.
    confidence:
        Heuristic confidence in [0.0, 1.0] — higher when more sentiment words
        were found and their scores are consistent.
    positive_words:
        Positive sentiment words found.
    negative_words:
        Negative sentiment words found.
    intensifiers_found:
        Intensifier words that modified nearby sentiment words.
    negated_words:
        Words whose polarity was flipped by a preceding negation.
    sentence_scores:
        Per-sentence breakdown ``[(sentence_text, score), …]``.
    """

    text: str
    score: float
    label: str
    confidence: float
    positive_words: List[str] = field(default_factory=list)
    negative_words: List[str] = field(default_factory=list)
    intensifiers_found: List[str] = field(default_factory=list)
    negated_words: List[str] = field(default_factory=list)
    sentence_scores: List[Tuple[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dictionary."""
        return {
            "score": self.score,
            "label": self.label,
            "confidence": self.confidence,
            "positive_words": self.positive_words,
            "negative_words": self.negative_words,
            "intensifiers_found": self.intensifiers_found,
            "negated_words": self.negated_words,
        }


# ── Analyzer ──────────────────────────────────────────────────────────────────

_SENTENCE_SPLIT = re.compile(r"[.!?؟…؛\n]+")
_CLEAN_TOKEN = re.compile(r"[\u064B-\u0652\u0640]")  # strip diacritics


def _clean(word: str) -> str:
    return _CLEAN_TOKEN.sub("", word).strip(".,،؟!؛:()[]{}\"'«»")


class SentimentAnalyzer:
    """Lexicon-based Arabic sentiment analyzer.

    Fully dependency-free.  Works for Modern Standard Arabic and common
    Egyptian, Gulf, and North African dialect vocabulary.

    Parameters
    ----------
    negation_window:
        Number of tokens after a negation word whose polarity is inverted.
    neutral_threshold:
        Absolute score below which the label is ``"neutral"`` (default 0.05).
    sentence_level:
        When *True*, also populate :attr:`SentimentResult.sentence_scores`.

    Example
    -------
    >>> analyzer = SentimentAnalyzer()
    >>> result = analyzer.analyze("أنا سعيد جداً بهذا النجاح")
    >>> result.label
    'positive'
    >>> result.score > 0.5
    True
    >>> result2 = analyzer.analyze("هذا الفيلم ليس جيداً")
    >>> result2.label
    'negative'
    """

    def __init__(
        self,
        negation_window: int = _NEGATION_WINDOW,
        neutral_threshold: float = 0.05,
        sentence_level: bool = True,
    ) -> None:
        self.negation_window = negation_window
        self.neutral_threshold = neutral_threshold
        self.sentence_level = sentence_level
        # Combine lexicons
        self._pos: Dict[str, float] = _POSITIVE_WORDS
        self._neg: Dict[str, float] = _NEGATIVE_WORDS
        self._int: Dict[str, float] = _INTENSIFIERS
        self._negations: FrozenSet[str] = _NEGATION_WORDS

    # ── Public API ────────────────────────────────────────────────────────

    def analyze(self, text: str) -> SentimentResult:
        """Analyze the sentiment of *text*.

        Parameters
        ----------
        text:
            Arabic (or mixed) input string.

        Returns
        -------
        SentimentResult
        """
        if not text or not text.strip():
            return self._empty_result(text)

        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
        sentence_scores: List[Tuple[str, float]] = []
        all_pos: List[str] = []
        all_neg: List[str] = []
        all_int: List[str] = []
        all_ngt: List[str] = []
        total_score = 0.0
        total_weight = 0.0

        for sent in sentences:
            score, pos, neg, ints, ngts = self._score_sentence(sent)
            sentence_scores.append((sent, round(score, 4)))
            weight = len(sent.split()) or 1
            total_score += score * weight
            total_weight += weight
            all_pos.extend(pos)
            all_neg.extend(neg)
            all_int.extend(ints)
            all_ngt.extend(ngts)

        final_score = round(total_score / total_weight, 4) if total_weight else 0.0
        final_score = max(-1.0, min(1.0, final_score))
        label = self._label(final_score)
        confidence = self._confidence(all_pos, all_neg, final_score)

        return SentimentResult(
            text=text,
            score=final_score,
            label=label,
            confidence=confidence,
            positive_words=sorted(set(all_pos)),
            negative_words=sorted(set(all_neg)),
            intensifiers_found=sorted(set(all_int)),
            negated_words=sorted(set(all_ngt)),
            sentence_scores=sentence_scores if self.sentence_level else [],
        )

    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze a list of texts."""
        return [self.analyze(t) for t in texts]

    def get_lexicon_stats(self) -> dict:
        """Return the size of the built-in lexicons."""
        return {
            "positive_words": len(self._pos),
            "negative_words": len(self._neg),
            "intensifiers": len(self._int),
            "negation_words": len(self._negations),
        }

    # ── Private ───────────────────────────────────────────────────────────

    def _score_sentence(self, sentence: str) -> Tuple[float, List[str], List[str], List[str], List[str]]:
        """Score a single sentence; return (score, pos, neg, ints, negated)."""
        tokens = sentence.split()
        cleaned = [_clean(t) for t in tokens]

        pos_words: List[str] = []
        neg_words: List[str] = []
        int_words: List[str] = []
        ngt_words: List[str] = []
        scores: List[float] = []
        negation_counter = 0

        # Check for multi-word intensifiers (up to 3 words)
        intensifier_spans: Set[int] = set()
        for i in range(len(cleaned)):
            for span in (3, 2):
                phrase = " ".join(cleaned[i : i + span])
                if phrase in self._int and len(phrase) > 1:
                    for j in range(i, i + span):
                        intensifier_spans.add(j)
                    int_words.append(phrase)

        multiplier = 1.0
        for i, tok in enumerate(cleaned):
            if not tok:
                continue

            # Check if this token starts a negation
            if tok in self._negations:
                negation_counter = self.negation_window
                continue

            # Track negation countdown
            if negation_counter > 0:
                negation_counter -= 1

            # Intensifier
            if i in intensifier_spans:
                for phrase, factor in self._int.items():
                    if tok == phrase or phrase.startswith(tok):
                        multiplier = factor
                continue

            # Single-word intensifier
            if tok in self._int:
                multiplier = self._int[tok]
                int_words.append(tok)
                continue

            # Sentiment word
            raw_score = self._pos.get(tok) or self._neg.get(tok)
            if raw_score is not None:
                effective = raw_score * multiplier
                if negation_counter > 0:
                    effective = -effective * 0.8  # flip and slightly dampen
                    ngt_words.append(tok)
                if effective > 0:
                    pos_words.append(tok)
                else:
                    neg_words.append(tok)
                scores.append(effective)
                multiplier = 1.0  # reset after use

        if not scores:
            return 0.0, pos_words, neg_words, int_words, ngt_words

        sentence_score = sum(scores) / len(scores)
        return sentence_score, pos_words, neg_words, int_words, ngt_words

    def _label(self, score: float) -> str:
        if score >= self.neutral_threshold:
            return "positive"
        if score <= -self.neutral_threshold:
            return "negative"
        return "neutral"

    def _confidence(self, pos: List[str], neg: List[str], score: float) -> float:
        """Heuristic confidence: more sentiment evidence → higher confidence."""
        n_evidence = len(pos) + len(neg)
        if n_evidence == 0:
            return 0.0
        # Confidence grows with evidence and score magnitude
        base = min(1.0, n_evidence / 5.0)
        magnitude = min(1.0, abs(score) * 2)
        return round((base * 0.6 + magnitude * 0.4), 4)

    def _empty_result(self, text: str) -> SentimentResult:
        return SentimentResult(text=text, score=0.0, label="neutral", confidence=0.0)
