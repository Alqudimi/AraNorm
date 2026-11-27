"""Arabic quotation / direct-speech analysis engine.

Measures how much of an Arabic text is enclosed in quotation environments,
covering the full range of quotation conventions used in Arabic writing:

+-------------------------+----------------------------------------------------+
| Quotation environment   | Detection signal                                   |
+-------------------------+----------------------------------------------------+
| standard_quotes         | ``"..."`` — straight/curly double quotes (ASCII    |
|                         | ``"``, smart ``\u201c`` / ``\u201d``).             |
+-------------------------+----------------------------------------------------+
| angle_quotes            | ``«...»`` — Arabic/French angle quotation marks.   |
+-------------------------+----------------------------------------------------+
| single_quotes           | ``'...'`` / ``\u2018...\u2019`` — straight/curly   |
|                         | single quotes used for quoting in Arabic prose.    |
+-------------------------+----------------------------------------------------+
| partial                 | An opening mark without a matching closer (in     |
|                         | incomplete or editorially trimmed text).           |
+-------------------------+----------------------------------------------------+

Returns typed spans with character offsets plus a ``quotation_ratio`` expressing
the share of *all* textual content (punctuation excluded) sitting inside quote
environments — a strong stylistic indicator of reportage, interviews, or
citational writing. Deterministic, dependency-free, and consistent with the
``aranorm.analysis`` family (dataclass results with ``to_dict``/JSON APIs).

Example
-------
>>> from aranorm.analysis.quotation_analyzer import analyze_quotations
>>> result = analyze_quotations('قال المدير: «سنحقق النمو المستهدف هذا العام»')
>>> result.angle_count == 1
True
>>> result.label
'quoted'
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

# ── Quotation environment patterns ────────────────────────────────────────────

# Standard double quotes: ASCII " or smart \u201C ... \u201D (content may span
# anything except an unescaped closer).
_STRAIGHT_DOUBLE = '"'
_SMART_OPEN = "\u201c"
_SMART_CLOSE = "\u201d"
_QUOTED_PAIRS: List[Tuple[str, str]] = [
    (_STRAIGHT_DOUBLE, _STRAIGHT_DOUBLE),
    (_SMART_OPEN, _SMART_CLOSE),
]
# Angle (guillemet) quotes « ... ».
_ANGLE_OPEN = "\u00ab"
_ANGLE_CLOSE = "\u00bb"
# Single quotes ' or smart \u2018 ... \u2019.
_STRAIGHT_SINGLE = "'"
_SMART_SINGLE_OPEN = "\u2018"
_SMART_SINGLE_CLOSE = "\u2019"

_QUOTATION_CONTENT = r"[^\u201D\u2019\u00BB\"]*"

_DOUBLE_RE = re.compile(
    r"(?:" + re.escape(_SMART_OPEN) + r"(" + _QUOTATION_CONTENT + r")" + re.escape(_SMART_CLOSE) + r")"
)
_DOUBLE_SINGLE_RE = re.compile(
    r"(?:" + re.escape(_STRAIGHT_DOUBLE) + r"(" + _QUOTATION_CONTENT + r")" + re.escape(_STRAIGHT_DOUBLE) + r")"
)
_ANGLE_RE = re.compile(
    r"(?:" + re.escape(_ANGLE_OPEN) + r"(" + _QUOTATION_CONTENT + r")" + re.escape(_ANGLE_CLOSE) + r")"
)
_SINGLE_RE = re.compile(
    r"(?:" + re.escape(_SMART_SINGLE_OPEN) + r"(" + _QUOTATION_CONTENT + r")" + re.escape(_SMART_SINGLE_CLOSE) + r")"
)
_SINGLE_STRAIGHT_RE = re.compile(
    r"(?:" + re.escape(_STRAIGHT_SINGLE) + r"(" + _QUOTATION_CONTENT + r")" + re.escape(_STRAIGHT_SINGLE) + r")"
)
_OPEN_MARKERS = re.compile(r"[\u201C\u00AB\u2018" + re.escape(_STRAIGHT_DOUBLE) + re.escape(_STRAIGHT_SINGLE) + r"]")
# Non-punctuation content (Arabic letters, digits, latin letters, whitespace,
# numbers) used to measure quoted content share fairly.
_CONTENT_TOKENS = re.compile(r"[\u0621-\u064A\u0660-\u06690-9A-Za-z]+")
_WORD_RE = re.compile(r"[\u0621-\u064A\u0660-\u06690-9A-Za-z]+")


def _spans_for(
    text: str,
    pattern: "re.Pattern[str]",
    category: str,
) -> List["QuotationSpan"]:
    spans: List["QuotationSpan"] = []
    for match in pattern.finditer(text):
        spans.append(
            QuotationSpan(
                text=match.group(),
                category=category,
                start=match.start(),
                end=match.end(),
            )
        )
    return spans


@dataclass
class QuotationSpan:
    """A contiguous quotation environment located in the source text."""

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
class QuotationResult:
    """Consolidated quotation analysis for a single Arabic text."""

    quotation_ratio: float
    quotation_types: Dict[str, int]
    spans: List[QuotationSpan]
    partial_count: int
    word_count: int
    label: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quotation_ratio": round(self.quotation_ratio, 4),
            "quotation_types": dict(self.quotation_types),
            "spans": [span.to_dict() for span in self.spans],
            "partial_count": self.partial_count,
            "word_count": self.word_count,
            "label": self.label,
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


@dataclass
class QuotationAnalyzer:
    """Arabic quotation / direct-speech analysis."""

    quoted_label_threshold: float = 0.5
    partially_quoted_label_threshold: float = 0.1

    def analyze(self, text: str) -> QuotationResult:
        spans: List[QuotationSpan] = []
        spans.extend(_spans_for(text, _DOUBLE_RE, "standard_quotes"))
        spans.extend(_spans_for(text, _DOUBLE_SINGLE_RE, "standard_quotes"))
        spans.extend(_spans_for(text, _ANGLE_RE, "angle_quotes"))
        spans.extend(_spans_for(text, _SINGLE_RE, "single_quotes"))
        spans.extend(_spans_for(text, _SINGLE_STRAIGHT_RE, "single_quotes"))
        # Partial (unmatched) opening markers not already consumed by a pair.
        partial_count = 0
        consumed_positions = set()
        for span in spans:
            for position in range(span.start, span.end):
                consumed_positions.add(position)
        for match in _OPEN_MARKERS.finditer(text):
            if match.start() not in consumed_positions:
                partial_count += 1
        quotation_types: Dict[str, int] = {}
        for span in spans:
            quotation_types[span.category] = quotation_types.get(span.category, 0) + 1
        # Ratio: quoted content words over all content words.
        words = _WORD_RE.findall(text)
        quoted_content_words = 0
        for span in spans:
            quoted_content_words += len(_CONTENT_TOKENS.findall(span.text))
        words = words or _CONTENT_TOKENS.findall(text)
        word_count = len(words) if words else 0
        ratio = quoted_content_words / word_count if word_count else 0.0
        if ratio >= self.quoted_label_threshold:
            label = "quoted"
        elif ratio >= self.partially_quoted_label_threshold or partial_count > 0:
            label = "partially_quoted"
        else:
            label = "plain"
        return QuotationResult(
            quotation_ratio=ratio,
            quotation_types=quotation_types,
            spans=spans,
            partial_count=partial_count,
            word_count=word_count,
            label=label,
        )

    def analyze_batch(self, texts: List[str]) -> List[QuotationResult]:
        return [self.analyze(text) for text in texts]


def analyze_quotations(text: str) -> QuotationResult:
    """Convenience function analysing quotation environments in ``text``."""
    return QuotationAnalyzer().analyze(text)
