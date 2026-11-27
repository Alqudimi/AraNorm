"""Rule-based named entity analysis for Arabic texts.

Identifies person names, locations, organizations, countries, numeric
entities (money, dates, phone numbers) and capitalised Arabic-anchored
markers in normalised Arabic text, returning typed spans with character
offsets suitable for highlighting or downstream NLP pipelines.

Deterministic, dependency-free, and consistent with the rest of the
``aranorm.analysis`` family (``dataclass`` results, ``to_dict``/JSON APIs).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

_ARABIC_LETTERS = r"\u0621-\u064A\u0671-\u06D3"
_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")

# Arabic money patterns: 1,234.56 / ١٢٣٤٫٥٦ with currency word prefix/suffix.
_DIGITS = r"0-9\u0660-\u0669"
_CURRENCY_WORDS = "ريال|جنيه|درهم|دولار|يورو|ليرة|دينار|شيكل|دولارات|دراهم|دنانير"
# Money: a number that is NOT a 4-digit standalone year. Years are detected
# by the date detector when adjacent to a month name or slash separators.
_MONEY_RE = re.compile(
    r"\b(?<!\d)(?:\d{1,3}(?:[,.]\d{3})+(?:\.\d+)?|(?:\d{1,3}|\d{5,})(?:\.\d+)?|\d{1,3})"
    r"(?:\s+(?:ألف|مليون|مليار|مئات|آلاف))?"
    r"(?:\s+(?:" + _CURRENCY_WORDS + r"))?\b"
)

_DATE_PATTERNS = (
    # 15 رمضان 1445هـ / 2025/03/15 / 15-03-2025
    r"\d{1,2}\s+(?:رمضان|محرم|صفر|ربيع|جمادى|رجب|شعبان|شوال|ذو\s(?:الحجة|القعدة))\s+\d{4}",
    r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}",
    r"\d{4}[/\-]\d{1,2}[/\-]\d{1,2}",
)
_DATE_RE = re.compile("|".join(_DATE_PATTERNS))

# Phone: 8+ consecutive digits optionally prefixed with + and allowing
# separators, anchored so plain year-like numbers are not absorbed.
_PHONE_RE = re.compile(r"(?:\+?[\d۰-۹](?:[\d۰-۹][ .\-()]{0,2}){7,19}[\d۰-۹])")

# Person-name title markers that introduce a full name span afterwards.
_NAME_TITLES = (
    "الأمير",
    "الأميرة",
    "السيد",
    "السيدة",
    "الدكتور",
    "الدكتورة",
    "المهندس",
    "المهندسة",
    "الرئيس",
    "الرئيسة",
    "الملك",
    "الملكة",
    "الشيخ",
    "الشيخة",
    "الوزير",
    "الوزيرة",
    "البروفيسور",
    "الأستاذ",
    "الأستاذة",
    "النائب",
    "النائبة",
    "السفير",
    "السفيرة",
    "الفريق",
    "اللواء",
    "الجنرال",
    "الحاج",
    "الحاجة",
    "الإمام",
    "العلامة",
    "الفنان",
    "الفنانة",
    "الشاعر",
    "الشاعرة",
    "الكاتب",
    "الكاتبة",
    "الصحفي",
    "الصحفية",
    "اللاعب",
    "اللاعبة",
    "القائد",
    "القائدة",
    "الحاكم",
    "الحاكمة",
    "الأمير",
    "البابا",
    "الكاردينال",
)
_TITLE_STOP_TOKENS = (
    "و قال قالا في من إلى على عن أن الذي التي إن فإن حيث لكن بينما أو ثم بعد قبل خلال "
    "حضر حضرا حضروا حضرت زار زاروا زيارة التقى التقيا ذهب ذهبوا سافر وصل اجتمع "
    "يوم شهر سنة عام صباح مساء الليلة غدا اليوم أمس "
    "التقى تلتقي استقبل استقبلت أعلنت قالت يقول يضيف صرح أكد أوضح "
    "الوفد وفد الوفد الرسمي الوفود "
    "بغداد الرياض القاهرة دمشق بيروت عمان الدوحة الكويت"
).split()

# Title marker followed by 1-6 name tokens, terminating at sentence
# punctuation, a stop-token connective, or end of string.
_NAME_TOKEN = r"[\w\u0621-\u064A\u0671-\u06D3]+"
_TITLE_ALT = "|".join(re.escape(t) for t in _NAME_TITLES)
_STOP_ALT = "|".join(_TITLE_STOP_TOKENS)
# Title followed by the longest run of name tokens (1-6) that ends before
# a stop-token connective, sentence punctuation, or end of string.
# Build the name-body as a sequence of tokens, each token NOT allowed to be
# a stop connective, so the run ends exactly where a connective begins.
_STOP_TOKENS_SET = set(_TITLE_STOP_TOKENS)
_NAME_TOKEN_NOT_STOP = r"(?!(?:" + _STOP_ALT + r")\b)" + _NAME_TOKEN
_TITLE_RE = re.compile(
    r"(?:" + _TITLE_ALT + r")\s+"
    r"(?P<name>"
    + _NAME_TOKEN_NOT_STOP
    + r"(?:\s+"
    + _NAME_TOKEN_NOT_STOP
    + r"){0,5})(?=\s+(?:"
    + _STOP_ALT
    + r")\b|،|\.|,|؛|$)"
)

# Well-known Arabic location and organisation markers — deterministic seed
# dictionaries covering the most frequent entities in MSA media text. The
# lists are deliberately small, fast to scan, and user-extendable.
LOCATIONS: Set[str] = {
    "مكة",
    "المدينة",
    "الرياض",
    "جدة",
    "دمشق",
    "بغداد",
    "القاهرة",
    "الكويت",
    "المنامة",
    "أبوظبي",
    "الدوحة",
    "مسقط",
    "عمان",
    "الخرطوم",
    "صنعاء",
    "بيروت",
    "القدس",
    "الرباط",
    "تونس",
    "الجزائر",
    "نواكشوط",
    "القاهرة",
    "الإسكندرية",
    "مراكش",
    "فاس",
    "الدار البيضاء",
    "المنامة",
    "الدوحة",
    "غزة",
    "الخليل",
    "نابلس",
    "بغداد",
    "البصرة",
    "أربيل",
    "السليمانية",
    "موصل",
    "مصر",
    "السعودية",
    "الإمارات",
    "العراق",
    "سوريا",
    "لبنان",
    "الأردن",
    "اليمن",
    "الكويت",
    "البحرين",
    "قطر",
    "عمان",
    "فلسطين",
    "تونس",
    "الجزائر",
    "المغرب",
    "ليبيا",
    "السودان",
    "موريتانيا",
    "الصومال",
    "جيبوتي",
    "تركيا",
    "إيران",
    "أمريكا",
    "ألمانيا",
    "فرنسا",
    "بريطانيا",
    "الصين",
    "اليابان",
    "الهند",
    "روسيا",
    "إيطاليا",
    "إسبانيا",
}

ORGANIZATIONS: Set[str] = {
    "الأمم المتحدة",
    "جامعة الدول العربية",
    "مجلس التعاون الخليجي",
    "منظمة الصحة العالمية",
    "صندوق النقد الدولي",
    "البنك الدولي",
    "اليونسكو",
    "اليونيسف",
    "منظمة التجارة العالمية",
    "المحكمة الدولية",
    "الاتحاد الأوروبي",
    "الناتو",
    "أوبك",
    "أرامكو",
    "الاتصالات السعودية",
    "طيران الإمارات",
    "الخطوط القطرية",
    "الهيئة الملكية",
    "وزارة الخارجية",
    "وزارة الصحة",
    "وزارة التعليم",
    "وزارة الداخلية",
    "وزارة الدفاع",
    "مجلس النواب",
    "مجلس الشورى",
    "البنك المركزي",
    "هيئة النقد",
    "وكالة الأنباء",
    "وزارة الإعلام",
    "هيئة الطيران",
    "هيئة الغذاء",
}

PERSON_MARKERS: Set[str] = {
    "محمد",
    "أحمد",
    "علي",
    "حسن",
    "حسين",
    "خالد",
    "عمر",
    "فاطمة",
    "مريم",
    "عائشة",
    "نور",
    "سارة",
    "سلطان",
    "فيصل",
    "تركي",
    "عبدالله",
    "عبدالعزيز",
    "عبدالله",
    "محمود",
    "يوسف",
    "إبراهيم",
    "إسماعيل",
    "موسى",
    "عيسى",
    "سليمان",
    "داود",
    "هارون",
    "آدم",
    "نوح",
    "زكريا",
    "يحيى",
    "بلال",
    "حمزة",
    "مصعب",
    "زيد",
    "أنس",
    "جابر",
    "طلال",
    "بندر",
    "ماجد",
    "ناصر",
    "سعود",
    "فهد",
    "ماجد",
    "بدر",
    "مشعل",
    "متعب",
    "لولوة",
    "هيفاء",
    "مها",
    "هند",
    "لمى",
    "دانة",
    "شيماء",
    "رقية",
    "زينب",
    "خديجة",
    "أمينة",
}

# Compound location prefixes where the next capitalised token is absorbed.
_LOCATION_PREFIXES = ("مدينة", "جبل", "خليج", "بحر", "نهر", "جزيرة", "صحراء", "وادي", "قرية", "بلدة", "ولاية", "مقاطعة")

ENTITY_TYPES = ("person", "location", "organization", "money", "date", "phone")


@dataclass
class EntitySpan:
    """A single detected entity with its character offsets inside the text."""

    text: str
    start: int
    end: int
    entity_type: str  # person | location | organization | money | date | phone
    confidence: float  # 0.0-1.0 deterministic score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "entity_type": self.entity_type,
            "confidence": self.confidence,
        }


@dataclass
class EntityAnalysisResult:
    """Result of rule-based entity analysis for one text."""

    original_text: str
    entities: List[EntitySpan] = field(default_factory=list)
    by_type: Dict[str, List[EntitySpan]] = field(default_factory=dict)
    entity_count: int = 0
    person_count: int = 0
    location_count: int = 0
    organization_count: int = 0
    money_count: int = 0
    date_count: int = 0
    phone_count: int = 0
    coverage_ratio: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "entities": [e.to_dict() for e in self.entities],
            "by_type": {k: [e.to_dict() for e in v] for k, v in self.by_type.items()},
            "entity_count": self.entity_count,
            "person_count": self.person_count,
            "location_count": self.location_count,
            "organization_count": self.organization_count,
            "money_count": self.money_count,
            "date_count": self.date_count,
            "phone_count": self.phone_count,
            "coverage_ratio": self.coverage_ratio,
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def _strip_diacritics(text: str) -> str:
    return _DIA_RE.sub("", text)


class EntityAnalyzer:
    """Deterministic Arabic named entity analyzer.

    Detects six entity classes in Arabic text without external models:

    * ``person`` — tokens following title markers (السيد، الدكتور، الأميرة…)
      and frequent Arabic personal names.
    * ``location`` — seed dictionary of well-known cities/countries plus
      geo-prefix absorption (مدينة، جبل، خليج…).
    * ``organization`` — seed dictionary of institutions, ministries and
      companies common in MSA media text.
    * ``money`` — numeric amounts optionally bracketed by currency words.
    * ``date`` — Gregorian and Hijri calendar patterns.
    * ``phone`` — international and national phone number patterns.

    All detections are anchored with character offsets so callers can
    highlight or redact spans directly.

    Parameters
    ----------
    detect_types:
        Entity classes to run; defaults to all six.
    name_threshold:
        Minimum title-marker run length (in tokens) to accept a person
        span; default 1.
    location_override:
        Optional extra locations to merge into the built-in dictionary.
    organization_override:
        Optional extra organizations to merge into the built-in dictionary.

    Example
    -------
    >>> analyzer = EntityAnalyzer()
    >>> result = analyzer.analyze("زار الرئيس القاهرة صباح اليوم")
    >>> result.location_count
    1
    """

    def __init__(
        self,
        detect_types: Optional[List[str]] = None,
        name_threshold: int = 1,
        location_override: Optional[List[str]] = None,
        organization_override: Optional[List[str]] = None,
    ) -> None:
        self.detect_types = list(detect_types or ENTITY_TYPES)
        self.name_threshold = max(1, name_threshold)
        self.locations = set(LOCATIONS)
        self.organizations = set(ORGANIZATIONS)
        if location_override:
            self.locations.update(location_override)
        if organization_override:
            self.organizations.update(organization_override)
        self._location_prefix_re = re.compile(
            r"(?:" + "|".join(re.escape(p) for p in _LOCATION_PREFIXES) + r")\s+[\w\u0621-\u064A\u0671-\u06D3]+",
        )

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _find_regex_entities(
        self, text: str, pattern: re.Pattern, entity_type: str, confidence: float
    ) -> List[EntitySpan]:
        spans: List[EntitySpan] = []
        for match in pattern.finditer(text):
            matched = match.group(0).strip()
            if matched:
                spans.append(
                    EntitySpan(
                        text=matched,
                        start=match.start(),
                        end=match.end(),
                        entity_type=entity_type,
                        confidence=confidence,
                    )
                )
        return spans

    def _find_title_persons(self, text: str) -> List[EntitySpan]:
        spans: List[EntitySpan] = []
        clean = _strip_diacritics(text)
        for match in _TITLE_RE.finditer(clean):
            head = match.group(0).strip()
            title = head.split(None, 1)[0]
            name_part = head[len(title) :].strip()
            tokens = name_part.split()
            if len(tokens) >= self.name_threshold and title in _NAME_TITLES:
                # map back to original text offsets
                idx = clean.find(head)
                if idx == -1:
                    continue
                spans.append(
                    EntitySpan(
                        text=name_part,
                        start=idx + len(title) + 1,
                        end=idx + len(head),
                        entity_type="person",
                        confidence=0.85,
                    )
                )
        return spans

    def _find_name_cluster_persons(self, text: str) -> List[EntitySpan]:
        """Two-or-more consecutive known person names count as a person span."""
        spans: List[EntitySpan] = []
        tokens = re.findall(r"[\w\u0621-\u064A\u0671-\u06D3]+", _strip_diacritics(text))
        if len(tokens) < 2:
            return spans
        cluster: List[str] = []
        for token in tokens:
            bare = token[1:] if token.startswith(("و", "ف", "ب", "ك", "ل")) and len(token) > 2 else token
            if token in PERSON_MARKERS or bare in PERSON_MARKERS:
                cluster.append(token)
            else:
                if len(cluster) >= 2:
                    first = cluster[0]
                    last = cluster[-1]
                    a = text.find(first)
                    b = text.rfind(last)
                    spans.append(
                        EntitySpan(
                            text=" ".join(cluster), start=a, end=b + len(last), entity_type="person", confidence=0.75
                        )
                    )
                cluster = []
        if len(cluster) >= 2:
            first = cluster[0]
            last = cluster[-1]
            a = text.find(first)
            b = text.rfind(last)
            spans.append(
                EntitySpan(text=" ".join(cluster), start=a, end=b + len(last), entity_type="person", confidence=0.75)
            )
        return spans

    def _find_dictionary_entities(
        self, text: str, dictionary: Set[str], entity_type: str, confidence: float
    ) -> List[EntitySpan]:
        spans: List[EntitySpan] = []
        clean = _strip_diacritics(text)
        # longest-first matching keeps multi-word entities intact
        ordered = sorted(dictionary, key=len, reverse=True)
        consumed: Set[int] = set()
        for term in ordered:
            if len(term) > len(clean):
                continue
            index = clean.find(term)
            while index != -1:
                if not any(i in consumed for i in range(index, index + len(term))):
                    spans.append(
                        EntitySpan(
                            text=term,
                            start=index,
                            end=index + len(term),
                            entity_type=entity_type,
                            confidence=confidence,
                        )
                    )
                    for i in range(index, index + len(term)):
                        consumed.add(i)
                    index = clean.find(term, index + len(term))
                else:
                    index = clean.find(term, index + 1)
        return spans

    def _find_location_prefix_entities(self, text: str) -> List[EntitySpan]:
        spans: List[EntitySpan] = []
        clean = _strip_diacritics(text)
        for match in self._location_prefix_re.finditer(clean):
            matched = match.group(0).strip()
            spans.append(
                EntitySpan(text=matched, start=match.start(), end=match.end(), entity_type="location", confidence=0.7)
            )
        return spans

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, text: str) -> EntityAnalysisResult:
        """Run all configured detectors over *text* and merge the spans."""
        if not (text or "").strip():
            return EntityAnalysisResult(original_text=text)

        all_spans: List[EntitySpan] = []
        if "date" in self.detect_types:
            all_spans.extend(self._find_regex_entities(text, _DATE_RE, "date", 0.9))
        if "phone" in self.detect_types:
            all_spans.extend(self._find_regex_entities(text, _PHONE_RE, "phone", 0.9))
        if "money" in self.detect_types:
            all_spans.extend(self._find_regex_entities(text, _MONEY_RE, "money", 0.9))
        if "person" in self.detect_types:
            all_spans.extend(self._find_title_persons(text))
            all_spans.extend(self._find_name_cluster_persons(text))
        if "location" in self.detect_types:
            all_spans.extend(self._find_dictionary_entities(text, self.locations, "location", 0.8))
            all_spans.extend(self._find_location_prefix_entities(text))
        if "organization" in self.detect_types:
            all_spans.extend(self._find_dictionary_entities(text, self.organizations, "organization", 0.8))

        # merge overlapping spans (keep higher-confidence, then earlier)
        all_spans.sort(key=lambda s: (s.start, -s.confidence))
        merged: List[EntitySpan] = []
        used = 0
        for span in all_spans:
            if span.start < used:
                continue
            merged.append(span)
            used = max(used, span.end)
        merged.sort(key=lambda s: (s.start, -s.confidence))

        by_type: Dict[str, List[EntitySpan]] = {}
        for span in merged:
            by_type.setdefault(span.entity_type, []).append(span)

        counts = {t: len(by_type.get(t, [])) for t in ("person", "location", "organization", "money", "date", "phone")}
        total_chars = len(text)
        covered = sum((s.end - s.start) for s in merged)
        coverage = (covered / total_chars) if total_chars else 0.0

        return EntityAnalysisResult(
            original_text=text,
            entities=merged,
            by_type=by_type,
            entity_count=len(merged),
            person_count=counts["person"],
            location_count=counts["location"],
            organization_count=counts["organization"],
            money_count=counts["money"],
            date_count=counts["date"],
            phone_count=counts["phone"],
            coverage_ratio=coverage,
        )

    def analyze_batch(self, texts: List[str]) -> List[EntityAnalysisResult]:
        return [self.analyze(text) for text in texts]
