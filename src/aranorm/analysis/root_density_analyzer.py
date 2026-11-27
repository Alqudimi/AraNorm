"""Arabic root-derivation density analysis engine.

Measures how richly an Arabic text derives its vocabulary from distinct
trilateral roots, reusing the deterministic pattern-matching root extractor
already embedded in :mod:`aranorm.utils.root_extractor`:

+-----------------------------+-------------------------------------------------+
| Indicator                   | Meaning                                          |
+-----------------------------+-------------------------------------------------+
| root_count                  | Total word count examined for roots.             |
+-----------------------------+-------------------------------------------------+
| unique_roots                | Distinct three-letter roots actually extracted.  |
+-----------------------------+-------------------------------------------------+
| hapax_ratio                 | Share of roots appearing exactly once (lexical  |
|                             | breadth signal — high in literary prose).       |
+-----------------------------+-------------------------------------------------+
| top_root                    | Most frequent root with its occurrence count.   |
+-----------------------------+-------------------------------------------------+
| diversity_index            | Normalised root-diversity index (0–1) blending   |
|                             | unique-root coverage and hapax breadth.          |
+-----------------------------+-------------------------------------------------+

Deterministic, dependency-free, and consistent with the ``aranorm.analysis``
family (dataclass results with ``to_dict``/JSON APIs).

Example
-------
>>> from aranorm.analysis.root_density_analyzer import analyze_root_density
>>> result = analyze_root_density("يكتب الكاتب كتاباً ويقرأ القارئ قراءة")
>>> result.unique_roots >= 3
True
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from aranorm.utils.root_extractor import extract_root

# Content tokens (Arabic letters, arabic-indic and western digits, latin).
_WORD_RE = re.compile(r"[\u0621-\u064A\u0660-\u06690-9A-Za-z]+")
# Tokens that never yield meaningful roots (stop-words / particles skipped).
_CONNECTIVE_PREFIXES = ("و", "ف", "ب", "ل", "ك")


def _strip_prefixes(token: str) -> str:
    """Strip connective prefixes (و/ف/ب/ل/ك) before article/pattern stripping.

    Conjunctive tokens like ``ويقرأ`` or ``فكاتب`` carry the coordinating ``واو``
    (or other proclitics) fused onto the word, which prevents the deterministic
    :func:`extract_root` from matching its inner pattern. Removing leading
    proclitics restores productive root matches while leaving the original
    token intact for frequency counting.
    """
    stripped = token
    for prefix in _CONNECTIVE_PREFIXES:
        if stripped.startswith(prefix) and len(stripped) > 4:
            stripped = stripped[1:]
    return stripped


def _strip_article(token: str) -> str:
    """Strip the definite article ``ال`` before root extraction.

    The embedded :func:`extract_root` matches whole-word patterns, so tokens
    carrying the definite article (الكاتب، المدرسة) fail to yield their root.
    Removing the leading ``ال`` restores productive matches while leaving the
    original token intact for frequency counting.
    """
    if token.startswith("ال") and len(token) > 4:
        return token[2:]
    return token


_SKIP_TOKENS = frozenset(
    [
        "في",
        "من",
        "على",
        "الى",
        "إلى",
        "عن",
        "مع",
        "و",
        "او",
        "أو",
        "لا",
        "لم",
        "لن",
        "هو",
        "هي",
        "هم",
        "هن",
        "هو",
        "انا",
        "أنا",
        "نحن",
        "انت",
        "أنت",
        "انتم",
        "أنتم",
        "هذا",
        "هذه",
        "ذلك",
        "تلك",
        "التي",
        "الذي",
        "كل",
        "ليس",
        "اذا",
        "إذا",
        "حيث",
        "بين",
        "قبل",
        "بعد",
        "عند",
        "حول",
        "تحت",
        "فوق",
        "حتى",
        "اي",
        "أي",
        "ما",
        "ال",
        "به",
        "لها",
        "له",
        "بها",
        "منه",
        "منها",
        "عنه",
        "عنها",
        "انه",
        "إنه",
        "انها",
        "إنها",
    ]
)


@dataclass
class RootDensityResult:
    """Consolidated root-derivation analysis for a single Arabic text."""

    root_count: int
    unique_roots: int
    hapax_ratio: float
    top_root: Optional[Dict[str, Any]]
    diversity_index: float
    label: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_count": self.root_count,
            "unique_roots": self.unique_roots,
            "hapax_ratio": round(self.hapax_ratio, 4),
            "top_root": self.top_root,
            "diversity_index": round(self.diversity_index, 4),
            "label": self.label,
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


@dataclass
class RootDensityAnalyzer:
    """Arabic root-derivation density analysis."""

    root_diversity_threshold: float = 0.6
    root_sparse_threshold: float = 0.3
    minimum_words: int = 3

    def analyze(self, text: str) -> RootDensityResult:
        tokens = [
            token
            for token in _WORD_RE.findall(text)
            if token not in _SKIP_TOKENS and len(token) >= 3 and re.search(r"[\u0621-\u064A]", token)
        ]
        roots: List[Tuple[str, str]] = []
        for token in tokens:
            root = extract_root(_strip_article(_strip_prefixes(token)))
            if root:
                roots.append((token, root))
        root_count = len(tokens)
        if root_count < self.minimum_words:
            return RootDensityResult(
                root_count=root_count,
                unique_roots=0,
                hapax_ratio=0.0,
                top_root=None,
                diversity_index=0.0,
                label="sparse",
            )
        root_frequencies = Counter(root for _, root in roots)
        unique_roots = len(root_frequencies)
        hapax = sum(1 for frequency in root_frequencies.values() if frequency == 1)
        hapax_ratio = hapax / unique_roots if unique_roots else 0.0
        if root_frequencies:
            top_root_token, top_frequency = root_frequencies.most_common(1)[0]
            top_root: Optional[Dict[str, Any]] = {"root": top_root_token, "frequency": top_frequency}
        else:
            top_root = None
        # Diversity: ratio of unique roots among extractable-root words blended
        # with the hapax breadth (vocabulary richness).
        extractable_words = len(roots) or 1
        coverage = unique_roots / extractable_words
        diversity_index = 0.7 * coverage + 0.3 * hapax_ratio
        if diversity_index >= self.root_diversity_threshold:
            label = "root_rich"
        elif unique_roots == 0 or diversity_index < self.root_sparse_threshold:
            label = "sparse"
        else:
            label = "moderate"
        return RootDensityResult(
            root_count=root_count,
            unique_roots=unique_roots,
            hapax_ratio=hapax_ratio,
            top_root=top_root,
            diversity_index=diversity_index,
            label=label,
        )

    def analyze_batch(self, texts: List[str]) -> List[RootDensityResult]:
        return [self.analyze(text) for text in texts]


def analyze_root_density(text: str) -> RootDensityResult:
    """Convenience function analysing root derivation density in ``text``."""
    return RootDensityAnalyzer().analyze(text)
