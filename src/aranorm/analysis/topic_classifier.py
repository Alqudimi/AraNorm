"""Deterministic Arabic topic classification using lexical feature scoring.

Classifies Arabic texts into well-defined topic domains by scoring each
topic's seeded lexicon against the document and aggregating per-word
evidence.  Fully deterministic (no external models, no weights that need
training) and consistent with the ``aranorm.analysis`` result conventions.

Supported topics: news, social, legal, medical, religious, sport,
technology, economy, education, history, environment, culture,
community, general.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u0671-\u06D3]{2,}")
_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")

# Seed lexicons — deliberately high-precision markers per topic.  Lists can
# be extended by callers via ``add_terms`` or by subclassing.
_TOPIC_LEXICON: Dict[str, List[str]] = {
    "news": [
        "الصحافة",
        "الإعلام",
        "التقارير",
        "المراسل",
        "الأخبار",
        "وكالة الأنباء",
        "المتحدث",
        "مصادر مطلعة",
        "بيان",
        "تصريح",
        "التحقيقات",
        "المحقق",
        "الصحفي",
        "الصحفية",
        "نشرة",
        "بث",
        "قناة",
        "المراسلة",
        "المتحدث",
    ],
    "social": [
        "تغريدة",
        "منشور",
        "متابعين",
        "الإعجاب",
        "تعليق",
        "هاشتاج",
        "منشن",
        "ستوري",
        "ريلز",
        "بث مباشر",
        "المحتوى الرقمي",
        "فيديو",
        "المشاهدات",
        "المعجبين",
        "التفاعل",
        "الإحصائيات",
        "المتابعون",
        "الفيديوهات",
        "الحساب",
        "الحسابات",
    ],
    "legal": [
        "المحكمة",
        "القاضي",
        "القانون",
        "المادة",
        "الدعوى",
        "المتهم",
        "النيابة",
        "المحامي",
        "المحاماة",
        "العقوبة",
        "الحبس",
        "التعويض",
        "الشرعية",
        "الدستور",
        "التشريعات",
        "اللوائح",
        "الحكم القضائي",
        "الاستئناف",
        "الادعاء",
        "البراءة",
        "المخالفة",
        "الجريمة",
        "الجنائية",
        "المدنية",
        "التحكيم",
        "العقود",
        "الالتزامات",
    ],
    "medical": [
        "الطبيب",
        "الطبيبة",
        "المستشفى",
        "العيادة",
        "العلاج",
        "المرض",
        "الأعراض",
        "الدواء",
        "الأدوية",
        "الوصفة",
        "التشخيص",
        "الجراحة",
        "العملية",
        "التمريض",
        "التمريضية",
        "الصحة",
        "المرضى",
        "الحمى",
        "اللقاح",
        "التطعيم",
        "الفحوصات",
        "المخبر",
        "الأشعة",
        "الصيدلية",
        "الصرافة",
        "الجرعة",
        "العلاج الطبيعي",
        "الأمراض المزمنة",
    ],
    "religious": [
        "الصلاة",
        "الصيام",
        "الزكاة",
        "الحج",
        "العمرة",
        "المسجد",
        "القرآن",
        "السنة",
        "الحديث",
        "الفتوى",
        "المفتي",
        "الخطيب",
        "الدعاء",
        "الذكر",
        "التلاوة",
        "العبادة",
        "الإمام",
        "المؤذن",
        "الأذان",
        "رمضان",
        "العيد",
        "الفطر",
        "الأضحى",
        "التراويح",
        "الفقه",
        "العقيدة",
        "التفسير",
    ],
    "sport": [
        "المباراة",
        "اللاعب",
        "اللاعبة",
        "المدرب",
        "المدربة",
        "النادي",
        "البطولة",
        "الكأس",
        "الدوري",
        "الهدف",
        "الأهداف",
        "الركلات",
        "التمرير",
        "الهجوم",
        "الدفاع",
        "الحارس",
        "الحكم",
        "الملعب",
        "الجمهور",
        "المشجعين",
        "التدريب",
        "المنتخب",
        "المنتخبات",
        "الرياضة",
        "الرياضي",
        "الرياضية",
        "الأولمبياد",
        "المدالية",
    ],
    "technology": [
        "التقنية",
        "البرمجيات",
        "البرمجة",
        "الخوارزمية",
        "الذكاء الاصطناعي",
        "التعلم الآلي",
        "البيانات",
        "الحاسوب",
        "الحوسبة",
        "الشبكة",
        "الإنترنت",
        "التطبيق",
        "التطبيقات",
        "الهاتف الذكي",
        "الرقمنة",
        "الأمن السيبراني",
        "البروتوكول",
        "النظام التشغيل",
        "السحابة",
        "الحوسبة السحابية",
        "الابتكار",
        "الناشئة",
        "ريادة الأعمال",
    ],
    "economy": [
        "الاقتصاد",
        "السوق",
        "الأسواق",
        "الاستثمار",
        "المستثمر",
        "البنوك",
        "البنك المركزي",
        "التضخم",
        "العملات",
        "البورصة",
        "الأسهم",
        "السندات",
        "الميزانية",
        "الإيرادات",
        "الصادرات",
        "الواردات",
        "التجارة",
        "الشركات",
        "الربحية",
        "الناتج المحلي",
        "الفائدة",
        "القروض",
        "التمويل",
        "الاقتصادي",
        "الاقتصادية",
    ],
    "education": [
        "المدرسة",
        "الجامعة",
        "الطالب",
        "الطالبة",
        "المعلم",
        "المعلمة",
        "الأستاذ",
        "الأستاذة",
        "التعليم",
        "التعلم",
        "الامتحان",
        "الامتحانات",
        "الشهادة",
        "الدرجات",
        "المنهج",
        "المناهج",
        "الفصل الدراسي",
        "الدرجة العلمية",
        "الدكتوراه",
        "الماجستير",
        "البحث العلمي",
        "المؤتمر العلمي",
        "الأكاديمية",
        "الطلاب",
    ],
    "history": [
        "الحضارة",
        "الحضارات",
        "الآثار",
        "القرن",
        "القرون",
        "العصر القديم",
        "العصر الحديث",
        "الدولة العباسية",
        "الدولة الأموية",
        "الدولة العثمانية",
        "الفتوحات",
        "الحروب الصليبية",
        "الحرب العالمية",
        "الاستقلال",
        "الاستعمار",
        "الملوك",
        "العهد",
        "العصور",
        "الممالك",
        "التاريخ",
    ],
    "environment": [
        "البيئة",
        "البيئية",
        "المناخ",
        "التغير المناخي",
        "الاحتباس الحراري",
        "الانبعاثات",
        "الطاقة المتجددة",
        "الطاقة الشمسية",
        "التلوث",
        "الغابات",
        "التصحر",
        "الجفاف",
        "الزلازل",
        "الأعاصير",
        "التنوع البيولوجي",
        "الانقراض",
        "المحميات",
        "إعادة التدوير",
    ],
    "culture": [
        "الثقافة",
        "الثقافية",
        "التراث",
        "التراث الشعبي",
        "الأدب",
        "الشعر",
        "الشاعر",
        "الشعراء",
        "القصيدة",
        "الرواية",
        "الفنون",
        "الموسيقى",
        "المسرح",
        "السينما",
        "المعارض",
        "الحرف",
        "المتاحف",
        "الهوية",
        "العادات",
        "التقاليد",
    ],
    "community": [
        "المجتمع",
        "الاجتماعية",
        "الأسرة",
        "العائلة",
        "الأطفال",
        "الطفولة",
        "الشباب",
        "المرأة",
        "العمل التطوعي",
        "التطوع",
        "الجمعيات",
        "الجمعيات الخيرية",
        "الفقر",
        "التكافل",
        "التربية",
        "الحياة الاجتماعية",
        "القيم",
        "الأخلاق",
    ],
}

_DEFAULT_TOPICS = tuple(_TOPIC_LEXICON.keys())


@dataclass
class TopicScore:
    """Per-topic evidence for a single classification run."""

    topic: str
    score: float  # raw evidence score 0.0+
    matched_terms: List[str] = field(default_factory=list)
    coverage: float = 0.0  # fraction of topic lexicon matched

    def to_dict(self) -> Dict[str, object]:
        return {
            "topic": self.topic,
            "score": self.score,
            "matched_terms": self.matched_terms,
            "coverage": self.coverage,
        }


@dataclass
class TopicClassificationResult:
    """Result of topic classification for one text."""

    original_text: str
    primary_topic: str  # topic with the highest score
    primary_score: float
    confidence: float  # normalised 0.0-1.0 gap between top-2 scores
    scores: List[TopicScore] = field(default_factory=list)
    top_topics: List[str] = field(default_factory=list)  # top-3 topic names
    word_count: int = 0
    topic_word_count: int = 0  # words that matched any topic lexicon

    def to_dict(self) -> Dict[str, object]:
        return {
            "original_text": self.original_text,
            "primary_topic": self.primary_topic,
            "primary_score": self.primary_score,
            "confidence": self.confidence,
            "scores": [s.to_dict() for s in self.scores],
            "top_topics": self.top_topics,
            "word_count": self.word_count,
            "topic_word_count": self.topic_word_count,
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def _normalise(word: str) -> str:
    return _DIA_RE.sub("", word).strip()


class TopicClassifier:
    """Lexicon-based Arabic topic classifier.

    Scores each topic's seeded lexicon against the document's words and
    ranks topics by accumulated evidence.  Confidence is derived from the
    normalised gap between the best and the runner-up score: a text whose
    best topic clearly outruns the rest yields high confidence, while a
    text with several near-equal topic scores yields a low confidence —
    exactly the semantics callers want when deciding whether to trust the
    primary label.

    Parameters
    ----------
    topics:
        Topics to classify against; defaults to all built-in topics.
    min_word_length:
        Minimum word length to count as evidence (default 3).

    Example
    -------
    >>> classifier = TopicClassifier()
    >>> result = classifier.classify("المحامي حضر جلسة المحكمة بعد الاطلاع على القانون")
    >>> result.primary_topic
    'legal'
    """

    def __init__(
        self,
        topics: Optional[List[str]] = None,
        min_word_length: int = 3,
    ) -> None:
        self.topics = list(topics or _DEFAULT_TOPICS)
        for topic in self.topics:
            if topic not in _TOPIC_LEXICON:
                raise ValueError(f"unknown topic {topic!r}; known: {sorted(_TOPIC_LEXICON)}")
        self.min_word_length = max(2, min_word_length)
        # per-topic lexicon as normalised sets for fast membership
        self._lexicons: Dict[str, Set[str]] = {
            topic: {_normalise(t) for t in _TOPIC_LEXICON[topic]} for topic in self.topics
        }
        self._extra: Dict[str, Set[str]] = {topic: set() for topic in self.topics}

    def add_terms(self, topic: str, terms: List[str]) -> None:
        """Add custom lexicon terms to a topic at runtime."""
        if topic not in self._lexicons:
            raise ValueError(f"unknown topic {topic!r}")
        self._extra[topic].update(_normalise(t) for t in terms)

    def classify(self, text: str) -> TopicClassificationResult:
        """Classify *text* into the configured topics."""
        if not (text or "").strip():
            return TopicClassificationResult(
                original_text=text,
                primary_topic="general",
                primary_score=0.0,
                confidence=0.0,
            )

        words = [_normalise(w) for w in _ARABIC_WORD.findall(text)]
        words = [w for w in words if len(w) >= self.min_word_length]
        word_counts: Dict[str, int] = {}
        for w in words:
            word_counts[w] = word_counts.get(w, 0) + 1

        scores: List[TopicScore] = []
        topic_word_matches: Set[str] = set()
        for topic in self.topics:
            lexicon = self._lexicons[topic] | self._extra[topic]
            matched: List[str] = []
            raw = 0.0
            for term in sorted(lexicon):
                if term in word_counts:
                    matched.append(term)
                    raw += word_counts[term] * (1.0 + len(term) * 0.05)
                    topic_word_matches.add(term)
            coverage = (len(matched) / len(lexicon)) if lexicon else 0.0
            scores.append(TopicScore(topic=topic, score=raw, matched_terms=matched[:20], coverage=coverage))

        scores.sort(key=lambda s: (-s.score, s.topic))
        top_scores = scores[:3]
        primary = scores[0]

        # normalised confidence: gap between best and runner-up over best
        runner = scores[1].score if len(scores) > 1 else 0.0
        if primary.score > 0.0:
            confidence = min(1.0, (primary.score - runner) / primary.score)
        else:
            confidence = 0.0
            primary = TopicScore(topic="general", score=0.0)
            scores = [primary] + [s for s in scores if s.topic != "general"]

        return TopicClassificationResult(
            original_text=text,
            primary_topic=primary.topic,
            primary_score=primary.score,
            confidence=confidence,
            scores=scores,
            top_topics=[s.topic for s in top_scores],
            word_count=len(words),
            topic_word_count=len(topic_word_matches),
        )

    def classify_batch(self, texts: List[str]) -> List[TopicClassificationResult]:
        return [self.classify(text) for text in texts]

    def distribution(self, texts: List[str]) -> Dict[str, int]:
        """Count primary-topic assignments over a batch of texts."""
        counts: Dict[str, int] = {}
        for result in self.classify_batch(texts):
            counts[result.primary_topic] = counts.get(result.primary_topic, 0) + 1
        return counts
