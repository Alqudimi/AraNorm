"""Arabic dialect-region depth analysis.
Extends :mod:`aranorm.utils.language_detector` with a *regional dialect*
signal: lexical markers strongly associated with one of the four major
Arabic dialect regions are scored independently, producing a regional
profile rather than a hard classification.

+-----------------+-----------------------------------------------------------+
| Region          | Marker examples                                           |
+-----------------+-----------------------------------------------------------+
| gulf            | شلون، ياهلا، دحين، عافاك، أبشر، جالس، هال، وش             |
+-----------------+-----------------------------------------------------------+
| levant          | كيفك، شلونك، مين، إيش، هيك، حلوين، عندي، شو، وين          |
+-----------------+-----------------------------------------------------------+
| egyptian        | إزاي، عاملة إيه، أوي، خالص، يعني، إيه، دلوقتي، كده        |
+-----------------+-----------------------------------------------------------+
| maghrebi        | شنو، ياك، دابا، بزاف، علاش، كيفاش، شحال، مزيان           |
+-----------------+-----------------------------------------------------------+

The region with the highest *density* (marker hits per word) wins the
``dominant_region`` label; a text with no region passing the density
threshold yields ``"none"``. Deterministic and dependency-free.

Example
-------
>>> from aranorm.utils.dialect_depth import analyze_dialect
>>> result = analyze_dialect("شنو دابا، بزاف مزيان ياك")
>>> result.dominant_region == "maghrebi"
True
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

_WORD_RE = re.compile(r"[\u0621-\u064A\u0671-\u06D3]+")
_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")
# Regional markers grouped by dialect region (normalised, without hamza/diacritics).
_REGION_MARKERS: Dict[str, Tuple[str, ...]] = {
    "gulf": (
        "شلون",
        "ياهلا",
        "دحين",
        "عافاك",
        "أبشر",
        "أبشر",
        "جلس",
        "جالس",
        "وش",
        "حال",
        "هال",
        "أشخبار",
        "عنديكم",
        "وشك",
        "تبغى",
        "دريال",
        "أهلا",
        "الله",
        "مرحبا",
    ),
    "levant": (
        "كيفك",
        "شلونك",
        "مين",
        "إيش",
        "هيك",
        "حلوين",
        "عندي",
        "شو",
        "وين",
        "بدك",
        "كتير",
        "هون",
        "هنيك",
        "طيب",
        "عنجد",
        "شباب",
    ),
    "egyptian": (
        "إزاي",
        "إيه",
        "أوي",
        "خالص",
        "يعني",
        "دلوقتي",
        "كده",
        "إنت",
        "حاجة",
        "حاجة",
        "بقى",
        "أوبا",
        "حلو",
        "إزيك",
        "إيه",
        "طب",
    ),
    "maghrebi": (
        "شنو",
        "ياك",
        "دابا",
        "بزاف",
        "علاش",
        "كيفاش",
        "شحال",
        "مزيان",
        "شنو",
        "واش",
        "خويا",
        "ديال",
        "فينا",
        "علاش",
        "بغيت",
    ),
}
_REGION_THRESHOLD = 0.06  # minimum marker density to count as a candidate


def _normalize_token(token: str) -> str:
    cleaned = _DIA_RE.sub("", token)
    return cleaned.translate(str.maketrans("أإآ", "ااا"))


@dataclass(frozen=True)
class DialectResult:
    """Result of regional dialect analysis over an Arabic text."""

    dominant_region: str
    region_scores: Dict[str, float]
    region_hits: Dict[str, int]
    marker_words: List[str]
    word_count: int
    is_dialectal: bool
    dialect_strength: float
    traces: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dominant_region": self.dominant_region,
            "region_scores": {region: round(score, 4) for region, score in self.region_scores.items()},
            "region_hits": self.region_hits,
            "marker_words": self.marker_words,
            "word_count": self.word_count,
            "is_dialectal": self.is_dialectal,
            "dialect_strength": round(self.dialect_strength, 4),
            "traces": self.traces,
        }


def _region_hits_for_tokens(tokens: List[str]) -> Dict[str, List[str]]:
    """Count matched markers per region."""
    normalised = [_normalize_token(token) for token in tokens]
    hits: Dict[str, List[str]] = {region: [] for region in _REGION_MARKERS}
    for token in normalised:
        for region, markers in _REGION_MARKERS.items():
            if token in markers:
                hits[region].append(token)
    return hits


@dataclass
class DialectAnalyzer:
    """Arabic dialect-region depth analysis."""

    region_threshold: float = _REGION_THRESHOLD

    def analyze(self, text: str) -> DialectResult:
        tokens = _WORD_RE.findall(text)
        word_count = len(tokens)
        hits = _region_hits_for_tokens(tokens)
        scores: Dict[str, float] = {}
        for region, region_hits in hits.items():
            density = len(region_hits) / word_count if word_count else 0.0
            scores[region] = round(density, 4)
        marker_words = [word for region_hits in hits.values() for word in region_hits]
        candidates = [region for region, score in scores.items() if score >= self.region_threshold]
        dominant = max(candidates, key=lambda region: scores[region]) if candidates else "none"
        dialect_strength = min(1.0, max(scores.values())) if scores else 0.0
        return DialectResult(
            dominant_region=dominant,
            region_scores=scores,
            region_hits={region: len(region_hits) for region, region_hits in hits.items()},
            marker_words=marker_words,
            word_count=word_count,
            is_dialectal=dominant != "none",
            dialect_strength=dialect_strength,
            traces={"region_threshold": self.region_threshold},
        )

    def analyze_batch(self, texts: List[str]) -> List[DialectResult]:
        return [self.analyze(text) for text in texts]


def analyze_dialect(text: str) -> DialectResult:
    """Convenience function analysing dialect-region signals in ``text``."""
    return DialectAnalyzer().analyze(text)
