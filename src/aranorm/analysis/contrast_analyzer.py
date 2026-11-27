"""Arabic contrast / antonymy analysis engine.
Detects antonym (tīāb / tīdād — تضاد) relationships in Arabic prose by
scanning for widely-recognised opposite pairs, and reports where they occur
with character offsets:
+-------------------------+----------------------------------------------------+
| Signal                  | Detection approach                                 |
+-------------------------+----------------------------------------------------+
| contrast_pairs          | Each matched antonym pair (a, b) with the         |
|                         | character span of the *second* member — the      |
|                         | member that completes the opposition.             |
+-------------------------+----------------------------------------------------+
| contrast_density        | Ratio of contrast-bearing words (both members)    |
|                         | over all content words.                            |
+-------------------------+----------------------------------------------------+
| label                   | ``"contrastive"`` / ``"moderate"`` / ``"neutral"``|
|                         | derived from the density against thresholds.      |
+-------------------------+----------------------------------------------------+
Deterministic, dependency-free, and consistent with the ``aranorm.analysis``
family (dataclass results with ``to_dict``/JSON APIs).
Example
-------
>>> from aranorm.analysis.contrast_analyzer import analyze_contrast
>>> result = analyze_contrast('الليل والنهار، والصواب والخطأ')
>>> len(result.contrast_pairs) >= 2
True
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import re as _re

_WORD_RE = _re.compile(r"[\u0621-\u064A\u0660-\u06690-9A-Za-z]+")
# ── Antonym pair lexicon (100+ high-confidence Arabic pairs) ─────────────────
# Each entry is a tuple of normalized (no diacritics, alef-normalised) forms.
_CONTRAST_PAIRS: List[Tuple[str, str]] = [
    ("الخير", "الشر"),
    ("النور", "الظلام"),
    ("النور", "الظلمة"),
    ("النهار", "الليل"),
    ("الشمس", "القمر"),
    ("القوة", "الضعف"),
    ("السلام", "الحرب"),
    ("الحياة", "الموت"),
    ("الصحيح", "الخطأ"),
    ("الصواب", "الخطأ"),
    ("الحق", "الباطل"),
    ("الحق", "الظلم"),
    ("الصدق", "الكذب"),
    ("الأمانة", "الخيانة"),
    ("الأمل", "اليأس"),
    ("الفرح", "الحزن"),
    ("السرور", "الحزن"),
    ("السعادة", "الشقاء"),
    ("السعادة", "التعاسة"),
    ("الجمال", "القبح"),
    ("النجاح", "الفشل"),
    ("الفوز", "الخسارة"),
    ("الغني", "الفقير"),
    ("الغنى", "الفقر"),
    ("الشبع", "الجوع"),
    ("الشبع", "العطش"),
    ("الصحة", "المرض"),
    ("الأمان", "الخطر"),
    ("الأمان", "الخطر"),
    ("الراحة", "التعب"),
    ("الراحة", "المشقة"),
    ("الهدوء", "الضجيج"),
    ("الهدوء", "الفوضى"),
    ("النظام", "الفوضى"),
    ("الانتظام", "الاضطراب"),
    ("العقل", "الجنون"),
    ("الحكمة", "الجهل"),
    ("العلم", "الجهل"),
    ("العلم", "الغفلة"),
    ("المعرفة", "الإنكار"),
    ("الوضوح", "الغموض"),
    ("الظهور", "الخفاء"),
    ("الخفاء", "الظهور"),
    ("البداية", "النهاية"),
    ("البداية", "النهاية"),
    ("البداية", "الخاتمة"),
    ("الأول", "الأخير"),
    ("القديم", "الحديث"),
    ("القديم", "الجديد"),
    ("الجديد", "البالي"),
    ("الابتكار", "التقليد"),
    ("الحضارة", "التوحش"),
    ("المدنية", "الهمجية"),
    ("العدل", "الظلم"),
    ("العدل", "الجور"),
    ("الإنصاف", "المحاباة"),
    ("الحرية", "العبودية"),
    ("الحرية", "الاستبداد"),
    ("الاستقلال", "التبعية"),
    ("الكرامة", "الإهانة"),
    ("الشرف", "الذل"),
    ("العزة", "المذلة"),
    ("الرفعة", "السقوط"),
    ("الارتقاء", "الانحدار"),
    ("الصعود", "الهبوط"),
    ("الصعود", "النزول"),
    ("العلو", "السفل"),
    ("السماء", "الأرض"),
    ("الفوق", "التحت"),
    ("الأمام", "الخلف"),
    ("الشرق", "الغرب"),
    ("الشمال", "اليمين"),
    ("الحار", "البارد"),
    ("الحر", "البرد"),
    ("الحرارة", "البرودة"),
    ("الجفاف", "الرطوبة"),
    ("الجفاف", "المطر"),
    ("المطر", "الشمس"),
    ("الليل", "النهار"),
    ("الفجر", "الغسق"),
    ("الضوء", "الظلام"),
    ("الضوء", "العتمة"),
    ("الإشراق", "الإظلام"),
    ("الانطلاق", "التوقف"),
    ("الحركة", "السكون"),
    ("الحركة", "الثبات"),
    ("السرعة", "البطء"),
    ("البطء", "السرعة"),
    ("القرب", "البعد"),
    ("القريب", "البعيد"),
    ("الصغر", "الكبر"),
    ("الصغير", "الكبير"),
    ("القلة", "الكثرة"),
    ("القليل", "الكثير"),
    ("النقصان", "الزيادة"),
    ("النقص", "التمام"),
    ("النقص", "الكمال"),
    ("الكامل", "الناقص"),
    ("التام", "المبتر"),
    ("البناء", "الهدم"),
    ("البناء", "الخراب"),
    ("الإعمار", "التدمير"),
    ("الإصلاح", "الفساد"),
    ("الإصلاح", "الإفساد"),
    ("الصلاح", "الفساد"),
    ("الصالح", "الطالح"),
    ("الربح", "الخسارة"),
    ("الكسب", "الخسران"),
    ("الوفرة", "الندرة"),
    ("الكفاية", "العجز"),
    ("الاكتفاء", "الحاجة"),
    ("الحاجة", "الاكتفاء"),
    ("السداد", "الخطأ"),
    ("الدقة", "الرعونة"),
    ("الجدية", "العبث"),
    ("الجد", "الهزل"),
    ("الصدق", "المجامل"),
    ("الصراحة", "التدليس"),
    ("الصرامة", "التساهل"),
    ("الشدة", "اللين"),
    ("الشدة", "الرفق"),
    ("القوة", "الضعف"),
    ("الصلابة", "الليونة"),
    ("الخشونة", "النعومة"),
    ("النعومة", "الخشونة"),
    ("الحلاوة", "المرارة"),
    ("الحلو", "المر"),
    ("الحار", "البارد"),
    ("المالح", "العذب"),
    ("العمق", "السطح"),
    ("العميق", "الضحل"),
    ("الأصل", "الفرع"),
    ("الجوهر", "الشكل"),
    ("الجوهر", "السطح"),
    ("الباطن", "الظاهر"),
    ("الباطن", "الظاهر"),
    ("السر", "العلن"),
    ("الخصوصية", "العمومية"),
    ("الخاص", "العام"),
    ("الفرد", "الجماعة"),
    ("الأنا", "الآخر"),
    ("الذات", "الموضوع"),
    ("الداخل", "الخارج"),
    ("الدخول", "الخروج"),
    ("القرب", "الابتعاد"),
    ("الوصل", "الفصل"),
    ("الاتصال", "الانقطاع"),
    ("الاتحاد", "الانقسام"),
    ("الجمع", "التفريق"),
    ("التأليف", "التفكيك"),
    ("التأسيس", "الهدم"),
    ("الولادة", "الوفاة"),
    ("الميلاد", "النهاية"),
    ("الصباح", "المساء"),
    ("الشروق", "الغروب"),
    ("الشباب", "الشيخوخة"),
    ("الشاب", "العجوز"),
    ("الطفولة", "الشيخوخة"),
]
# ── Normalisation helpers ────────────────────────────────────────────────────
_DIACRITICS = _re.compile(r"[\u064B-\u0652\u0670\u0640\u064E\u064F\u0650\u0651]")
_ALEF_NORMALISE = str.maketrans("أإآا", "اااا")
_PROCLITICS = _re.compile(r"^(و|ف|ب|ك|ل|لل|فال|بل|كل|فال)")


def _normalize_word(word: str) -> str:
    """Strip diacritics and normalise alef forms for comparison.
    Common Arabic proclitics (و / ف / ب / ل / ك) are also removed so that
    ``والنهار`` still matches the antonym partner ``الليل``. The definite
    article ``ال`` is removed last because some lexicon entries are stored
    with it and others without.
    """
    normalised = _DIACRITICS.sub("", word)
    normalised = normalised.translate(_ALEF_NORMALISE)
    for _ in range(3):
        if len(normalised) <= 2:
            break
        prefix = _PROCLITICS.match(normalised)
        if prefix and len(normalised) - len(prefix.group(1)) >= 2:
            normalised = normalised[len(prefix.group(1)) :]
        else:
            break
    if normalised.startswith("ال") and len(normalised) > 3:
        normalised = normalised[2:]
    return normalised


@dataclass
class ContrastPair:
    """A matched antonym pair located in the source text.
    Attributes
    ----------
    member_a:
        The first (anchor) member of the pair as it appears in the text.
    member_b:
        The second (opposing) member as it appears in the text.
    second_start:
        Character offset of the second member's start.
    second_end:
        Character offset of the second member's end.
    normalised_key:
        The pair's normalised key ``(a, b)`` for grouping identical pairs.
    """

    member_a: str
    member_b: str
    second_start: int
    second_end: int
    normalised_key: Tuple[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "member_a": self.member_a,
            "member_b": self.member_b,
            "second_start": self.second_start,
            "second_end": self.second_end,
            "normalised_key": list(self.normalised_key),
        }


@dataclass
class ContrastResult:
    """Consolidated antonymy / contrast analysis for a single Arabic text.
    Attributes
    ----------
    contrast_pairs:
        Matched antonym pairs in occurrence order.
    contrast_density:
        Ratio of contrast-bearing words to all content words (0.0–1.0).
    unique_pairs:
        Number of distinct (normalised) antonym pairs observed.
    word_count:
        Total content words used for density computation.
    label:
        ``"contrastive"`` (dense opposition), ``"moderate"`` (some contrast),
        or ``"neutral"`` (no meaningful contrast detected).
    """

    contrast_pairs: List[ContrastPair]
    contrast_density: float
    unique_pairs: int
    word_count: int
    label: str

    @property
    def contrast_pairs_count(self) -> int:
        """Number of detected antonym pair occurrences."""
        return len(self.contrast_pairs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contrast_pairs": [pair.to_dict() for pair in self.contrast_pairs],
            "contrast_density": round(self.contrast_density, 4),
            "unique_pairs": self.unique_pairs,
            "word_count": self.word_count,
            "label": self.label,
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


@dataclass
class ContrastAnalyzer:
    """Arabic contrast / antonymy detection over prose.
    Parameters
    ----------
    contrastive_threshold:
        Density at or above which the text is labelled ``"contrastive"``.
    moderate_threshold:
        Density at or above which the text is labelled ``"moderate"``;
        below this the label is ``"neutral"``.
    """

    contrastive_threshold: float = 0.05
    moderate_threshold: float = 0.01

    def analyze(self, text: str) -> ContrastResult:
        """Detect antonym pairs in *text* and return a :class:`ContrastResult`."""
        # Build lookup structures from the lexicon.
        # Register both the stored form and its bare (article-stripped) form so
        # that ``الليل``, ``ليل`` and ``والليل`` all resolve to the same entry.
        pair_lookup: Dict[str, str] = {}  # normalised member -> partner (normalised)
        for first, second in _CONTRAST_PAIRS:
            first = _normalize_word(first)
            second = _normalize_word(second)
            pair_lookup.setdefault(first, second)
            pair_lookup.setdefault(second, first)
            bare_first = first[2:] if first.startswith("ال") and len(first) > 3 else first
            bare_second = second[2:] if second.startswith("ال") and len(second) > 3 else second
            if bare_first != first and bare_second != second:
                pair_lookup.setdefault(bare_first, bare_second)
                pair_lookup.setdefault(bare_second, bare_first)
            else:
                pair_lookup.setdefault(bare_second, bare_first)
            # Also cross-map bare-against-full so that ``ليل`` (no article in
            # the text) matches the partner stored as ``النهار``.
            pair_lookup.setdefault(bare_first, second)
            pair_lookup.setdefault(bare_second, first)
            pair_lookup.setdefault(first, bare_second)
            pair_lookup.setdefault(second, bare_first)
        # Index words with their character offsets.
        words = [(match.group(), match.start(), match.end()) for match in _WORD_RE.finditer(text)]
        recorded_pairs: set = set()  # canonical (sorted) keys already reported
        pairs: List[ContrastPair] = []
        for index, (word, start, end) in enumerate(words):
            normalised = _normalize_word(word)
            if normalised not in pair_lookup:
                continue
            partner_normalised = pair_lookup[normalised]
            # Search a sliding window behind and ahead for the partner.
            window_before = words[max(0, index - 10) : index]
            window_after = words[index + 1 : index + 11]
            partner_found = None
            for candidate, candidate_start, candidate_end in window_before:
                if _normalize_word(candidate) == partner_normalised:
                    partner_found = (candidate, candidate_start, candidate_end)
                    break
            if partner_found is None:
                for candidate, candidate_start, candidate_end in window_after:
                    if _normalize_word(candidate) == partner_normalised:
                        partner_found = (candidate, candidate_start, candidate_end)
                        break
            if partner_found is not None:
                candidate, candidate_start, candidate_end = partner_found
                canonical = tuple(sorted((normalised, partner_normalised)))
                if canonical in recorded_pairs:
                    continue
                recorded_pairs.add(canonical)
                pairs.append(
                    ContrastPair(
                        member_a=word,
                        member_b=candidate,
                        second_start=candidate_start,
                        second_end=candidate_end,
                        normalised_key=(normalised, partner_normalised),
                    )
                )
        word_count = len(words) if words else 0
        # Density reflects words that actually participate in detected pairs
        # rather than every lexicon word that happens to appear in isolation.
        pair_words: set = set()
        for pair in pairs:
            pair_words.add(pair.member_a)
            pair_words.add(pair.member_b)
        bearing_words = sum(1 for word in pair_words)
        density = bearing_words / word_count if word_count else 0.0
        unique_keys = {pair.normalised_key for pair in pairs}
        if density >= self.contrastive_threshold:
            label = "contrastive"
        elif density >= self.moderate_threshold or pairs:
            label = "moderate"
        else:
            label = "neutral"
        return ContrastResult(
            contrast_pairs=pairs,
            contrast_density=density,
            unique_pairs=len(unique_keys),
            word_count=word_count,
            label=label,
        )

    def analyze_batch(self, texts: List[str]) -> List[ContrastResult]:
        """Analyze a list of texts independently."""
        return [self.analyze(text) for text in texts]


def analyze_contrast(text: str) -> ContrastResult:
    """Convenience function analysing antonymy / contrast in *text*.
    Example
    -------
    >>> result = analyze_contrast("الليل والنهار يتعاقبان على الأرض.")
    >>> result.label in ("moderate", "contrastive", "neutral")
    True
    """
    return ContrastAnalyzer().analyze(text)
