"""Arabic loanword and foreign-word detection engine.

Flags two complementary signals of non-native vocabulary inside Arabic text:

+---------------------------+---------------------------------------------------+
| Signal                    | Detection strategy                                |
+---------------------------+---------------------------------------------------+
| transliterated_loans      | Well-known Arabicised loanwords matched via a    |
|                           | curated dictionary (نورمال، أوكيه، تليفون، ...).  |
+---------------------------+---------------------------------------------------+
| latin_fragments           | Contiguous Latin-script runs inside the Arabic   |
|                           | text (code-switching, brand names, URLs).        |
+---------------------------+---------------------------------------------------+

Returns typed spans with character offsets, per-signal densities, and a label
(``pure_arabic`` / ``loanwords`` / ``mixed``) describing the overall
foreign-vocabulary load. Deterministic, dependency-free, and consistent with
the ``aranorm.analysis`` family (dataclass results with ``to_dict``/JSON APIs).

Example
-------
>>> from aranorm.analysis.loanword_analyzer import analyze_loanwords
>>> result = analyze_loanwords("الموضوع نورمال تماماً وأوكيه")
>>> result.loanword_count == 2
True
>>> result.label
'loanwords'
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List

# Curated Arabicised loanwords (transliterated foreign words used in Arabic
# prose and digital registers). Normalised via hamza/diacritic/ta-marbuta
# strip and alef unification for robust matching.
_LOANWORDS: List[str] = [
    "نورمال",
    "عادي",
    "تليفون",
    "تلفون",
    "تلفزيون",
    "راديو",
    "سكوتر",
    "باص",
    "بوت",
    "برواز",
    "أوكيه",
    "اوكيه",
    "أوبشن",
    "اوبشن",
    "موديل",
    "نموذج",
    "كمبيوتر",
    "لابتوب",
    "موبايل",
    "موبيل",
    "موبايلات",
    "انترنت",
    "أنترنت",
    "اونلاين",
    "أونلاين",
    "اوفلاين",
    "أوفلاين",
    "تشات",
    "شات",
    "ميتنج",
    "اجتماع",
    "بريزنتيشن",
    "داتا",
    "بيانات",
    "فيديو",
    "فوتو",
    "أوتوماتيك",
    "اوتوماتيك",
    "إلكتروني",
    "الكتروني",
    "إكسبرس",
    "اكسبرس",
    "بريميوم",
    "تخفيض",
    "برومو",
    "كوبون",
    "كوبونات",
    "سوشيال",
    "سوشيال ميديا",
    "ميديا",
    "تكنلوجيا",
    "تكنولوجيا",
    "تقنية",
    "سيكيورتي",
    "أمن",
    "سبورت",
    "سبورتس",
    "جيم",
    "نادي",
    "ماراثون",
    "ماراثونات",
    "موتيف",
    "ديزاين",
    "تصميم",
    "لوكيشن",
    "موقع",
    "روتين",
    "روتين يومي",
    "هابي",
    "سعيد",
    "فرند",
    "صديق",
    "فاميلي",
    "عائلة",
    "بيبسي",
    "كوكاكولا",
    "ماكدونالدز",
    "ستاربكس",
    "آيفون",
    "ايفون",
    "سامسونج",
    "تويتر",
    "انستجرام",
    "انستغرام",
    "فيسبوك",
    "يوتيوب",
    "تيك توك",
    "واتساب",
    "واتس اب",
    "زوم",
    "غوغل",
    "قوقل",
    "ايميل",
    "إيميل",
    "ايميلات",
    "لينك",
    "رابط",
    "سبام",
    "بروكسي",
    "سيرفر",
    "كلاود",
    "ابل",
    "مايكروسوفت",
    "تيسلا",
    "نوكيا",
    "هواوي",
    "أوبو",
    "اوبو",
]
# Token pattern capturing Arabic/digit/latin sequences (latin runs are the
# second signal, so we must be able to see them as tokens).
_WORD_RE = re.compile(r"[\u0621-\u064A\u0660-\u06690-9A-Za-z]+")
_LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9._/-]{0,}|\b[A-Za-z]{2,}\b")
_LATIN_RUN_RE = re.compile(r"[A-Za-z][A-Za-z0-9._/-]*")
# Normalisation: strip diacritics, unify alef forms, and remove hamza.
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0674]")
_ALEF_VARIANTS = re.compile(r"[\u0622\u0623\u0624\u0625\u0629\u0671]")
_ALEF_NORMALISED = "\u0627"


def _normalise_token(token: str) -> str:
    without_diacritics = _DIACRITICS.sub("", token)
    without_hamza = without_diacritics.replace("\u0621", "")
    return _ALEF_VARIANTS.sub(_ALEF_NORMALISED, without_hamza).lower()


def _build_loan_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for word in _LOANWORDS:
        mapping.setdefault(_normalise_token(word), word)
    return mapping


_LOAN_MAP: Dict[str, str] = _build_loan_map()


def _strip_attached_prefixes(token: str) -> str:
    """Strip common attached Arabic conjunction prefixes (waw, fa, ba, kaf, lam).

    Loanwords in running Arabic prose frequently pick up a conjunctive prefix
    (``ونورمال``، ``فأوكيه``) that must be removed before dictionary lookup.
    """
    if not token:
        return token
    for prefix in ("و", "ف", "ب", "ك", "ل"):
        if token.startswith(prefix) and len(token) > 3:
            return token[1:]
    return token


@dataclass
class LoanwordSpan:
    """A foreign-word span located in the source text."""

    text: str
    category: str
    start: int
    end: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "category": self.category,
            "start": self.start,
            "end": self.end,
        }


@dataclass
class LoanwordResult:
    """Consolidated loanword analysis for a single Arabic text."""

    loanword_count: int
    loanword_ratio: float
    latin_count: int
    latin_ratio: float
    foreign_density: float
    spans: List[LoanwordSpan]
    samples: List[str]
    word_count: int
    label: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "loanword_count": self.loanword_count,
            "loanword_ratio": round(self.loanword_ratio, 4),
            "latin_count": self.latin_count,
            "latin_ratio": round(self.latin_ratio, 4),
            "foreign_density": round(self.foreign_density, 4),
            "spans": [span.to_dict() for span in self.spans],
            "samples": self.samples,
            "word_count": self.word_count,
            "label": self.label,
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


@dataclass
class LoanwordAnalyzer:
    """Arabic loanword and foreign-word analysis."""

    loanword_label_threshold: float = 0.1
    latin_label_threshold: float = 0.05
    mixed_label_threshold: float = 0.15

    def analyze(self, text: str) -> LoanwordResult:
        tokens = _WORD_RE.findall(text)
        spans: List[LoanwordSpan] = []
        samples: List[str] = []
        # Signal 1: transliterated loanwords via dictionary.
        for match in _WORD_RE.finditer(text):
            normalised = _normalise_token(_strip_attached_prefixes(match.group()))
            loanword = _LOAN_MAP.get(normalised)
            if loanword is not None:
                spans.append(
                    LoanwordSpan(
                        text=match.group(),
                        category="transliterated_loan",
                        start=match.start(),
                        end=match.end(),
                    )
                )
                if loanword not in samples:
                    samples.append(loanword)
        # Signal 2: latin-script runs (code-switching / brands / URLs).
        for match in _LATIN_RUN_RE.finditer(text):
            span_text = match.group()
            # Skip trivially short runs that could be incidental.
            if len(span_text) < 2:
                continue
            spans.append(
                LoanwordSpan(
                    text=span_text,
                    category="latin_fragment",
                    start=match.start(),
                    end=match.end(),
                )
            )
        loanword_spans = [span for span in spans if span.category == "transliterated_loan"]
        latin_spans = [span for span in spans if span.category == "latin_fragment"]
        word_count = len(tokens) or 1
        foreign_tokens = len(loanword_spans) + len(latin_spans)
        density = foreign_tokens / word_count
        loanword_ratio = len(loanword_spans) / word_count
        latin_ratio = len(latin_spans) / word_count
        if latin_ratio >= self.latin_label_threshold:
            label = "mixed"
        elif loanword_ratio >= self.loanword_label_threshold:
            label = "loanwords"
        else:
            label = "pure_arabic"
        return LoanwordResult(
            loanword_count=len(loanword_spans),
            loanword_ratio=loanword_ratio,
            latin_count=len(latin_spans),
            latin_ratio=latin_ratio,
            foreign_density=density,
            spans=spans,
            samples=samples,
            word_count=len(tokens),
            label=label,
        )

    def analyze_batch(self, texts: List[str]) -> List[LoanwordResult]:
        return [self.analyze(text) for text in texts]


def analyze_loanwords(text: str) -> LoanwordResult:
    """Convenience function analysing loanwords in ``text``."""
    return LoanwordAnalyzer().analyze(text)
