"""Arabic idiom and fixed-expression detector.

Detects common Arabic idioms and fixed expressions — إن شاء الله، ما شاء
الله، الحمد لله، بحمد الله… — in normalised text and reports their spans
and canonical forms.  Crucially, idioms are *not* spelling errors even
when their words would individually look like mistakes (e.g. ``ان شاء
الله`` missing the hamza); the detector supplies a coverage helper that
spell-checking pipelines use to suppress those false positives.

Deterministic, dependency-free, and user-extensible at runtime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u0671-\u06D3]+")

# Canonical idioms: {canonical_form: (category, frozenset(normalised variants))}
# Each idiom maps to a set of acceptable spellings (including common
# misspellings that are nevertheless fixed expressions rather than errors).
_IDIOMS: Dict[str, Tuple[str, List[str]]] = {
    "إن شاء الله": ("دعاء", ["ان شاء الله", "انشاء الله", "إن شاءالله"]),
    "ما شاء الله": ("إعجاب", ["ماشاء الله", "ما شاءالله", "مشاء الله"]),
    "الحمد لله": ("دعاء", ["الحمدلله", "الحمد لله رب العالمين", "الحمد لله"]),
    "بحمد الله": ("إعجاب", ["بحمد الله", "بحمدالله"]),
    "بإذن الله": ("دعاء", ["بإذن الله", "بأذن الله", "بإذنالله", "بأذن الله"]),
    "في الحقيقة": ("توكيد", ["بالحقيقة", "في الحقيقة"]),
    "على أي حال": ("استدراك", ["على أيه حال", "على أي حال"]),
    "مرة أخرى": ("تكرار", ["مره أخرى", "مرة اخرى", "مرة ثانية"]),
    "لا سيما": ("تخصيص", ["لا سيما", "لاسيما"]),
    "أيضاً": ("إضافة", ["أيضا", "ايضاً", "أيضاً"]),
    "بصورة عامة": ("تعميم", ["بصورة عامة", "بصورة عامة", "بشكل عام", "بشكل عاما"]),
    "في الوقت الحالي": ("زمن", ["في الوقت الحالي", "حاليا", "حالياً", "في الوقت الحاضر"]),
    "من ناحية أخرى": ("استدراك", ["من ناحية أخرى", "من ناحية اخرى", "من جانب آخر"]),
    "على سبيل المثال": ("تمثيل", ["على سبيل المثال", "مثلاً", "مثلا"]),
    "في الواقع": ("توكيد", ["في الواقع", "في حقيقة الأمر", "في الحقيقة"]),
    "لدى": ("حيازة", ["لدي", "لديه", "لديهم", "لدينا"]),
    "إن شاء الله تعالى": ("دعاء", ["ان شاء الله تعالى", "انشاء الله تعالى"]),
    "في الحال": ("زمن", ["في الحال", "بالحال", "في الحال الآن"]),
    "على الفور": ("زمن", ["على الفور", "بالفور", "فورا", "فوراً"]),
    "بعد قليل": ("زمن", ["بعد قليل", "بعدين", "بعد شوي"]),
    "من جهة أخرى": ("استدراك", ["من جهة أخرى", "من جهة اخرى"]),
    "بالإضافة إلى": ("إضافة", ["بالاضافة إلى", "بالإضافه إلى", "اضافة إلى"]),
    "على الرغم": ("استدراك", ["على الرغم", "على رغم", "رغم أن", "رغم ان"]),
    "في النهاية": ("زمن", ["في النهايه", "في النهاية"]),
    "من قبل": ("جهة", ["من قبل", "من قبلي", "من قبله"]),
    "في كثير من الأحيان": ("تكرار", ["في كثير من الأحيان", "في كثير من الاحيان", "كثيرا ما", "كثيراً ما"]),
    "بصفة عامة": ("تعميم", ["بصفة عامة", "عموما", "عموماً"]),
    "في الوقت الراهن": ("زمن", ["في الوقت الراهن", "حاليا", "حالياً"]),
    "إلى جانب": ("إضافة", ["الى جانب", "إلى جانب", "بجانب"]),
    "في نفس الوقت": ("زمن", ["في نفس الوقت", "بنفس الوقت", "في نفس ذاته الوقت"]),
    "على وجه الخصوص": ("تخصيص", ["على وجه الخصوص", "على وجه خاص", "على وجه التحديد"]),
    "في ضوء": ("تفسير", ["في ضوء", "في ظل", "بناء على", "بناءً على"]),
    "من حيث": ("تفسير", ["من حيث", "من ناحية", "من حيث المبدأ"]),
    "إلى حد كبير": ("مقدار", ["الى حد كبير", "إلى حد كبير", "إلى حد ما", "الى حد ما"]),
    "بشكل أساسي": ("تفسير", ["بشكل أساسي", "بشكل اساسي", "بشكل رئيسي"]),
}


# Pre-compiled normalised regexes (escaped, longest-first).
def _normalise(text: str) -> str:
    return _DIA_RE.sub("", text)


def _build_patterns(idioms: Dict[str, Tuple[str, List[str]]]) -> List[Tuple[re.Pattern, str, str]]:
    patterns: List[Tuple[re.Pattern, str, str]] = []
    for canonical, (category, variants) in idioms.items():
        entries = [canonical] + list(variants)
        for variant in entries:
            norm = _normalise(variant).strip()
            if not norm:
                continue
            escaped = re.escape(norm)
            patterns.append(
                (
                    re.compile(r"(?<![\u0621-\u064A\u0671-\u06D3])" + escaped + r"(?![\u0621-\u064A\u0671-\u06D3])"),
                    canonical,
                    category,
                )
            )
    patterns.sort(key=lambda p: -len(p[1]))
    return patterns


@dataclass
class IdiomSpan:
    """One detected idiom occurrence with character offsets."""

    text: str  # as it appears in the source text
    canonical: str
    category: str
    start: int
    end: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "canonical": self.canonical,
            "category": self.category,
            "start": self.start,
            "end": self.end,
        }


@dataclass
class IdiomAnalysisResult:
    """Result of idiom analysis for one text."""

    original_text: str
    idioms: List[IdiomSpan] = field(default_factory=list)
    idiom_count: int = 0
    by_category: Dict[str, List[IdiomSpan]] = field(default_factory=dict)
    unique_idioms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "idioms": [i.to_dict() for i in self.idioms],
            "idiom_count": self.idiom_count,
            "by_category": {k: [i.to_dict() for i in v] for k, v in self.by_category.items()},
            "unique_idioms": self.unique_idioms,
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class IdiomAnalyzer:
    """Detects Arabic idioms and fixed expressions in normalised text.

    Parameters
    ----------
    idioms:
        Optional extension dictionary mapping canonical forms to
        ``(category, [variants])`` pairs; merged on top of the built-ins.

    Example
    -------
    >>> analyzer = IdiomAnalyzer()
    >>> result = analyzer.analyze("ان شاء الله نحقق الهدف، ما شاء الله عليه")
    >>> result.idiom_count
    2
    """

    def __init__(self, idioms: Optional[Dict[str, Tuple[str, List[str]]]] = None) -> None:
        merged = dict(_IDIOMS)
        if idioms:
            for canonical, payload in idioms.items():
                merged[canonical] = payload
        self._idioms = merged
        self._patterns = _build_patterns(merged)

    @property
    def canonical_forms(self) -> List[str]:
        return list(self._idioms.keys())

    def add_idiom(self, canonical: str, category: str, variants: Optional[List[str]] = None) -> None:
        """Register a new idiom at runtime."""
        self._idioms[canonical] = (category, list(variants or []))
        self._patterns = _build_patterns(self._idioms)

    def analyze(self, text: str) -> IdiomAnalysisResult:
        """Detect idioms in *text*, returning spans with offsets."""
        if not (text or "").strip():
            return IdiomAnalysisResult(original_text=text)

        clean = _normalise(text)
        # map cleaned offsets back to original offsets
        offset_map = self._build_offset_map(clean, text)

        spans: List[IdiomSpan] = []
        consumed: Set[int] = set()
        for pattern, canonical, category in self._patterns:
            for match in pattern.finditer(clean):
                start, end = match.start(), match.end()
                if any(i in consumed for i in range(start, end)):
                    continue
                spans.append(
                    IdiomSpan(
                        text=match.group(0),
                        canonical=canonical,
                        category=category,
                        start=offset_map[start],
                        end=offset_map[end - 1] + 1,
                    )
                )
                for i in range(start, end):
                    consumed.add(i)
        spans.sort(key=lambda s: s.start)

        by_category: Dict[str, List[IdiomSpan]] = {}
        for span in spans:
            by_category.setdefault(span.category, []).append(span)

        return IdiomAnalysisResult(
            original_text=text,
            idioms=spans,
            idiom_count=len(spans),
            by_category=by_category,
            unique_idioms=list({s.canonical for s in spans}),
        )

    def analyze_batch(self, texts: List[str]) -> List[IdiomAnalysisResult]:
        return [self.analyze(t) for t in texts]

    def is_idiom_covered(self, word_start: int, word_end: int, text: str) -> bool:
        """Return True when the span ``[word_start, word_end)`` lies inside
        a detected idiom — used by spell-checkers to skip idiom words."""
        covered = self.idiom_words(text)
        return bool(covered) and all(i in covered for i in range(word_start, word_end))

    def _build_offset_map(self, clean: str, original: str) -> Dict[int, int]:
        """Map each index in the diacritic-free text to the original text."""
        mapping: Dict[int, int] = {}
        orig_idx = 0
        clean_idx = 0
        while orig_idx < len(original) and clean_idx < len(clean):
            ch = original[orig_idx]
            if _DIA_RE.match(ch):
                orig_idx += 1
                continue
            mapping[clean_idx] = orig_idx
            orig_idx += 1
            clean_idx += 1
        # remaining clean chars (text shorter than expected) fallback
        while clean_idx < len(clean):
            mapping[clean_idx] = min(orig_idx, len(original) - 1)
            clean_idx += 1
        return mapping

    def idiom_words(self, text: str) -> Set[int]:
        """Character positions covered by idioms — for spell-check suppression."""
        result = self.analyze(text)
        covered: Set[int] = set()
        for span in result.idioms:
            for i in range(span.start, span.end):
                covered.add(i)
        return covered
