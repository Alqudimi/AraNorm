"""Arabic numeric expression analysis.
Extracts and classifies every numeric expression in an Arabic text, covering
all three common numeral systems and their compound forms:

+------------------------+----------------------------------------------------+
| Expression class       | Detection signal                                   |
+------------------------+----------------------------------------------------+
| western_digits         | ``123``, ``1,234.56`` — Latin digits with optional |
|                        | grouping and decimal separators.                   |
+------------------------+----------------------------------------------------+
| arabic_indic_digits    | ``١٢٣``, ``١٬٢٣٤٫٥٦`` — Arabic-Indic digits with |
|                        | Arabic grouping/decimal separators.                |
+------------------------+----------------------------------------------------+
| written_numbers        | ``ألف``، ``خمسمائة``، ``مليون ونصف`` — Arabic      |
|                        | number words including multiples and fractions.    |
+------------------------+----------------------------------------------------+
| percentages            | ``25%``, ``٢٥٪`` — any digit system plus the       |
|                        | percent sign.                                      |
+------------------------+----------------------------------------------------+
| currencies             | Money amounts with currency words (ريال، درهم،     |
|                        | دولار, ...).                                       |
+------------------------+----------------------------------------------------+
| time_expression        | Clock times (الساعة الخامسة، ٣:٣٠), day/period    |
|                        | words (اليوم، غدًا، أمس، الليلة), and relative     |
|                        | frames (الأسبوع القادم، الشهر الماضي، بعد الظهر).  |
+------------------------+----------------------------------------------------+
| ordinal                | Written ordinals (الأول، الثانية، العشرون،        |
|                        | الخامسة عشرة) and digit-led forms (١/٢ + أ/ة      |
|                        | or الـ prefix like ``1/1`` context).               |
+------------------------+----------------------------------------------------+

Returns typed spans with character offsets and a ``digit_system_mix`` signal
telling whether the text mixes numeral systems (a style/quality hint).
Deterministic, dependency-free, and consistent with the ``aranorm.analysis``
family (dataclass results with ``to_dict``/JSON APIs).

Example
-------
>>> from aranorm.analysis.numeric_analyzer import analyze_numeric
>>> result = analyze_numeric("حققنا نمواً بنسبة 25% أي ٢٥ بالمئة")
>>> result.percentage_count == 2
True
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

# Western digit span, allowing grouping (1,234) and decimal (1.5).
_WESTERN_NUMBER_RE = re.compile(r"\d{1,3}(?:[,.]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?")
# Arabic-Indic digits ٠-٩ with Arabic separators ٫ (decimal) and ٬ (grouping).
_ARABIC_INDIC_RE = re.compile(r"[\u0660-\u0669]+(?:[٫٬][\u0660-\u0669]+)*")
_PERCENT_SIGNS = "%٪"
_PERCENT_RE = re.compile(r"(?:\d+|[\u0660-\u0669]+)\s*(?:[" + _PERCENT_SIGNS + r"])")
_CURRENCY_WORDS = "ريال|دولار|درهم|جنيه|يورو|ليرة|دينار|شيكل|دراهم|دنانير|دولارات"
_CURRENCY_RE = re.compile(
    r"(?:(?:\d+(?:[.,]\d+)?)|(?:[\u0660-\u0669]+(?:[٫٬][\u0660-\u0669]+)?)|(?:[\u0621-\u064A]+))\s*(?:"
    + _CURRENCY_WORDS
    + r")"
)
# Time expressions: clock patterns (الساعة الخامسة، الساعة ٣:٣٠), single
# period words (اليوم، غدًا، الليلة، الآن، الفجر), and framed periods
# (الأسبوع القادم، الشهر الماضي، بعد الظهر، في الصباح).
_TIME_OF_DAY_WORDS = "الفجر|الشروق|الظهر|العصر|المغرب|العشاء|الليل|الظهيرة|منتصف الليل"
_PERIOD_WORDS = (
    "الآن|اليوم|أمس|غدا|غداً|غدًا|الليلة|صباحا|صباحاً|صباحًا|ظهرا|ظهراً|ظهراً"
    "|عصرا|عصراً|عصرًا|مساء|مساءً|مساءا|مساءاً|فجرا|فجراً|فجرًا|عشية|عشيةً"
)
_FRAMED_PERIOD_WORDS = "صباح|ظهر|عصر|مساء|ليل|فجر|عشاء|قرب الغروب"
_SHIFT_WORDS = "الماضي|الماضية|القادم|القادمة|الآتية|الآتي|الجاري|الجارية"
_TIME_EXPRESSION_RE = re.compile(
    r"(?:الساعة\s+(?:[\u0660-\u0669]+|[\d]+)(?::[\u0660-\u0669]+|[\d]+)?(?:\s+(?:دقيقة|دقائق|ونصف|والنصف))?)"
    r"|(?:الساعة\s+(?:الواحدة|الثانية|الثالثة|الرابعة|الخامسة|السادسة|"
    r"السابعة|الثامنة|التاسعة|العاشرة|الحادية عشرة|الثانية عشرة)"
    r"(?:\s+صباحا|\s+صباحاً|\s+صباحًا|\s+مساءً|\s+مساء|\s+ليلا|\s+ليلاً|"
    r"\s+ظهرًا|\s+ظهراً|\s+عصراً|\s+عصرًا|\s+دقيقة|\s+دقائق|\s+ونصف|\s+والنصف)?)"
    r"|(?:(?:ال|)أسبوع|شهر|سنة|سنوات|يوم|أسابيع|أشهر|أيام)\s+(?:" + _SHIFT_WORDS + r")"
    r"|(?:" + _PERIOD_WORDS + r")"
    r"|(?:(?:بعد|قبل)\s+(?:ال|)" + _FRAMED_PERIOD_WORDS + r")"
    r"|(?:" + _TIME_OF_DAY_WORDS + r")"
)
# Compound written numbers: base units, multiples, and fractions.
_WRITTEN_UNITS = (
    "ألف",
    "آلاف",
    "مليون",
    "ملايين",
    "مليار",
    "مليارات",
    "تريليون",
    "نصف",
    "ربع",
    "ثلث",
    "خمس",
    "سبع",
    "ثمن",
    "عشر",
    "ثمانية",
    "تسعة",
    "مائة",
    "مئة",
    "مئتان",
    "مئات",
)
# Two-word compounds written as one token by convention (خمسمائة، ستمائة، ...).
_COMPOUND_WRITTEN_NUMBERS = frozenset(
    [
        "مئتان",
        "ثلاثمائة",
        "أربعمائة",
        "اربعمائة",
        "أربعمئة",
        "اربعمئة",
        "خمسمائة",
        "خمسمئة",
        "ستمائة",
        "ستمئة",
        "سبعمائة",
        "سبعمئة",
        "ثمانمائة",
        "ثمانمئة",
        "تسعمائة",
        "تسعمئة",
        "الألف",
        "الالف",
        "ألفين",
        "الفين",
    ]
)
# Number word tokens (ones/tens/hundreds) recognised for density scoring.
_NUMBER_WORDS = frozenset(
    [
        "واحد",
        "اثنان",
        "ثلاثة",
        "اربعة",
        "أربعة",
        "خمسة",
        "ستة",
        "سبعة",
        "ثمانية",
        "تسعة",
        "عشرة",
        "مئة",
        "مائة",
        "مئتان",
        "مئات",
        "ألف",
        "آلاف",
        "مليون",
        "ملايين",
        "مليار",
        "مليارات",
        "نصف",
        "ربع",
        "ثلث",
        "اثنان",
        "ثلاثة",
        "اربعة",
        "خمسة",
        "ستة",
        "سبعة",
        "ثمانية",
        "تسعة",
        "عشرون",
        "ثلاثون",
        "اربعون",
        "خمسون",
        "ستون",
        "سبعون",
        "ثمانون",
        "تسعون",
        "مئة",
    ]
)
_WORD_RE = re.compile(r"[\u0621-\u064A\u0671-\u06D3]+")
_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")

# Written ordinals: ``الـ + ordinal stem`` plus the bare stems and the
# ``...عشرة/عشر...`` decade forms (التاسعة عشرة، العشرين...).
_ORDINAL_STEMS = (
    "الأول",
    "الاول",
    "الأولى",
    "الاولى",
    "الثاني",
    "الثانية",
    "الثالثة",
    "الثالثة",
    "الرابع",
    "الرابعة",
    "الخامس",
    "الخامسة",
    "السادس",
    "السادسة",
    "السابع",
    "السابعة",
    "الثامن",
    "الثامنة",
    "التاسع",
    "التاسعة",
    "العاشر",
    "العاشرة",
    "الحادي عشر",
    "الحادية عشرة",
    "الثاني عشر",
    "الثانية عشرة",
    "العشرين",
    "الثلاثين",
    "الاربعين",
    "الأربعين",
    "الخمسين",
    "الستين",
    "السبعين",
    "الثمانين",
    "التسعين",
    "الاول",
    "الخامسة عشر",
    "العاشرون",
    "الثانيون",
    "الثالث",
    "التالت",
)
_ORDINAL_WORD_RE = re.compile(
    r"(?:ال|)(?:اول|أول|ثاني|ثانية|ثالث|ثالثة|رابع|رابعة|خامس|خامسة|سادس|سادسة|"
    r"سابع|سابعة|ثامن|ثامنة|تاسع|تاسعة|عاشر|عاشرة|عشرين|ثلاثين|اربعين|أربعين|"
    r"خمسين|ستين|سبعين|ثمانين|تسعين|اولون|أولون)"
    r"(?:ون|ان|ان|ة|ات)?"
)


def _normalize(token: str) -> str:
    cleaned = _DIA_RE.sub("", token)
    normalised = cleaned.translate(str.maketrans("أإآ", "ااا"))
    if normalised.startswith("و") and len(normalised) > 2:
        return normalised[1:]
    return normalised


@dataclass(frozen=True)
class NumericSpan:
    """A detected numeric expression with its class and character offsets."""

    text: str
    category: str
    start: int
    end: int

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "category": self.category, "start": self.start, "end": self.end}


@dataclass(frozen=True)
class NumericResult:
    """Result of numeric expression analysis over an Arabic text."""

    digit_system_mix: bool
    western_count: int
    arabic_indic_count: int
    written_count: int
    percentage_count: int
    currency_count: int
    time_count: int
    ordinal_count: int
    numeric_density: float
    spans: List[NumericSpan]
    word_count: int
    traces: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "digit_system_mix": self.digit_system_mix,
            "western_count": self.western_count,
            "arabic_indic_count": self.arabic_indic_count,
            "written_count": self.written_count,
            "percentage_count": self.percentage_count,
            "currency_count": self.currency_count,
            "time_count": self.time_count,
            "ordinal_count": self.ordinal_count,
            "numeric_density": round(self.numeric_density, 4),
            "spans": [span.to_dict() for span in self.spans],
            "word_count": self.word_count,
            "traces": self.traces,
        }


def _count_written_numbers(text: str) -> int:
    tokens = [_normalize(token) for token in _WORD_RE.findall(text)]
    count = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _NUMBER_WORDS or token in _COMPOUND_WRITTEN_NUMBERS:
            count += 1
        elif index + 1 < len(tokens) and tokens[index + 1] in _WRITTEN_UNITS:
            # ``نصف مليون`` style compounds are scored once.
            count += 1
        index += 1
    return count


def _western_spans(text: str) -> List[NumericSpan]:
    spans: List[NumericSpan] = []
    for match in _WESTERN_NUMBER_RE.finditer(text):
        if any("\u0660" <= character <= "\u0669" for character in match.group()):
            continue
        spans.append(NumericSpan(text=match.group(), category="western_digits", start=match.start(), end=match.end()))
    return spans


def _arabic_indic_spans(text: str) -> List[NumericSpan]:
    spans: List[NumericSpan] = []
    for match in _ARABIC_INDIC_RE.finditer(text):
        spans.append(
            NumericSpan(text=match.group(), category="arabic_indic_digits", start=match.start(), end=match.end())
        )
    return spans


def _percentage_spans(text: str) -> List[NumericSpan]:
    spans: List[NumericSpan] = []
    for match in _PERCENT_RE.finditer(text):
        spans.append(
            NumericSpan(text=match.group().strip(), category="percentage", start=match.start(), end=match.end())
        )
    return spans


def _currency_spans(text: str) -> List[NumericSpan]:
    spans: List[NumericSpan] = []
    for match in _CURRENCY_RE.finditer(text):
        spans.append(NumericSpan(text=match.group().strip(), category="currency", start=match.start(), end=match.end()))
    return spans


def _ordinal_spans(text: str) -> List[NumericSpan]:
    """Detect written ordinal expressions (الأول، الثانية، العشرون...)."""
    spans: List[NumericSpan] = []
    seen_offsets: set = set()
    for match in _ORDINAL_WORD_RE.finditer(text):
        span_text = match.group().strip()
        if not span_text or match.start() in seen_offsets:
            continue
        seen_offsets.add(match.start())
        spans.append(NumericSpan(text=span_text, category="ordinal", start=match.start(), end=match.end()))
    return spans


def _time_expression_spans(text: str) -> List[NumericSpan]:
    """Detect clock times, day references, and relative time frames."""
    spans: List[NumericSpan] = []
    seen_offsets: set = set()
    for match in _TIME_EXPRESSION_RE.finditer(text):
        span_text = match.group().strip()
        if not span_text or len(span_text) < 2:
            continue
        # Avoid counting a token already consumed by a digit-based category.
        has_arabic_indic = any("\u0660" <= character <= "\u0669" for character in span_text)
        if has_arabic_indic or span_text[0].isdigit():
            # Delegate digit-led time phrases to the digit categories only if
            # they are pure digit runs; keep clock phrases like ``٣:٣٠`` here.
            if re.fullmatch(r"[\d\u0660-\u0669.:]+", span_text):
                continue
        if match.start() in seen_offsets:
            continue
        seen_offsets.add(match.start())
        spans.append(NumericSpan(text=span_text, category="time_expression", start=match.start(), end=match.end()))
    return spans


@dataclass
class NumericAnalyzer:
    """Arabic numeric expression analysis."""

    def analyze(self, text: str) -> NumericResult:
        western_spans = _western_spans(text)
        arabic_indic_spans = _arabic_indic_spans(text)
        percent_spans = _percentage_spans(text)
        currency_spans = _currency_spans(text)
        time_spans = _time_expression_spans(text)
        ordinal_spans = _ordinal_spans(text)
        written_count = _count_written_numbers(text)
        digit_system_mix = bool(western_spans) and bool(arabic_indic_spans)
        all_spans = western_spans + arabic_indic_spans + percent_spans + currency_spans + time_spans + ordinal_spans
        words = _WORD_RE.findall(text)
        numeric_tokens = len(western_spans) + len(arabic_indic_spans) + written_count
        density = numeric_tokens / len(words) if words else 0.0
        return NumericResult(
            digit_system_mix=digit_system_mix,
            western_count=len(western_spans),
            arabic_indic_count=len(arabic_indic_spans),
            written_count=written_count,
            percentage_count=len(percent_spans),
            currency_count=len(currency_spans),
            time_count=len(time_spans),
            ordinal_count=len(ordinal_spans),
            numeric_density=density,
            spans=all_spans,
            word_count=len(words),
            traces={"digit_system_mix_threshold": ">=1 each system"},
        )

    def analyze_batch(self, texts: List[str]) -> List[NumericResult]:
        return [self.analyze(text) for text in texts]


def analyze_numeric(text: str) -> NumericResult:
    """Convenience function analysing numeric expressions in ``text``."""
    return NumericAnalyzer().analyze(text)
