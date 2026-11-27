"""Arabic attached-pronoun (clitic) segmentation and analysis.

Arabic words carry attached pronouns and clitics that encode the subject,
object, and possession inside a single token — e.g. ``كتابهم`` = كتاب + هم,
``يكتبانه`` = ي + كتب + ان + ه.  This module decomposes tokens into their
clitic anatomy using a deterministic right-to-left segmentation of the
suffix inventory (possessive/object pronouns, verbal suffixes) and a
left-to-right prefix inventory (conjunctive waw, prepositions, question
particles, the definite article, future marker).

Useful as a preprocessing step for morphology-aware pipelines, text
statistics, and dialect analysis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_ARABIC = re.compile(r"^[\u0621-\u064A\u0671-\u06D3]+$")
_DIA_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")

# Right-to-left suffix inventory (longest-first).  Each entry maps the
# suffix string to a human-readable grammatical role.
_SUFFIXES: List[tuple] = [
    # verbal verbal-suffixes (plural/dual subject markers)
    ("ونَ", "ضمير الفاعل الجماعي المرفوع (واو الجماعة)"),
    ("ون", "ضمير الفاعل الجماعي المرفوع (واو الجماعة)"),
    ("ينَ", "ضمير الفاعل المثنى/المنصوب (ياء المخاطبة/المتكلم)"),
    ("ين", "ضمير الفاعل المثنى/المنصوب"),
    ("انِ", "ضمير الفاعل المثنى المرفوع (ألف الاثنين)"),
    ("ان", "ضمير الفاعل المثنى المرفوع"),
    # attached object/possessive pronouns
    ("هما", "ضمير الغائبين المثنى المتصل"),
    ("هم", "ضمير الغائبين الجمع المتصل"),
    ("هنّ", "ضمير الغائبات الجمع المتصل"),
    ("هن", "ضمير الغائبات الجمع المتصل"),
    ("كما", "ضمير المخاطبين المثنى المتصل"),
    ("كم", "ضمير المخاطبين الجمع المتصل"),
    ("كنّ", "ضمير المخاطبات الجمع المتصل"),
    ("كن", "ضمير المخاطبات الجمع المتصل"),
    ("ها", "ضمير الغائبة المفردة المتصل"),
    ("نا", "ضمير المتكلمين الجمع المتصل"),
    ("يَ", "ضمير المتكلم المفرد المتصل"),
    ("ي", "ضمير المتكلم المفرد المتصل"),
    ("كَ", "ضمير المخاطب المفرد المتصل"),
    ("كِ", "ضمير المخاطبة المفردة المتصل"),
    ("ك", "ضمير المخاطب المفرد المتصل"),
    ("هُ", "ضمير الغائب المفرد المتصل"),
    ("هِ", "ضمير الغائب المفرد المتصل"),
    ("ه", "ضمير الغائب المفرد المتصل"),
]

# Left-to-right prefix inventory.
_PREFIXES: List[tuple] = [
    ("وال", "الواو العاطف + أل التعريف"),
    ("فال", "فاء السببية + أل التعريف"),
    ("بال", "الباء + أل التعريف"),
    ("كال", "الكاف + أل التعريف"),
    ("لل", "اللام + أل التعريف"),
    ("أف", "همزة الاستفهام + فاء"),
    ("أ", "همزة الاستفهام"),
    ("است", "سين/سين+تاء المستقبل"),
    ("ست", "سين المستقبل"),
    ("س", "سين المستقبل"),
    ("وال", "الواو العاطف + أل"),
    ("و", "الواو العاطف"),
    ("ف", "فاء السببية/العطف"),
    ("أ", "همزة الاستفهام"),
]

# Bare prepositional prefixes (ب/ك/ل) are only meaningful when attached to
# a definite noun, so they are accepted solely before an ``ال`` stem.
_DEFINITE_PREPOSITIONS = ("بال", "كال", "لل")

_SUFFIX_SORTED = sorted(_SUFFIXES, key=lambda t: -len(t[0]))
_PREFIX_SORTED = sorted(_PREFIXES, key=lambda t: -len(t[0]))


@dataclass
class CliticSegment:
    """One segment (prefix/stem/suffix) of a decomposed token."""

    text: str
    role: str  # prefix | stem | suffix
    grammar: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "role": self.role, "grammar": self.grammar}


@dataclass
class PronounAnalysisResult:
    """Decomposition result for one token."""

    original_token: str
    segments: List[CliticSegment] = field(default_factory=list)
    stem: str = ""
    prefixes: List[str] = field(default_factory=list)
    suffixes: List[str] = field(default_factory=list)
    has_pronoun: bool = False
    pronoun_role: str = ""
    _suffix_clitics: List[CliticSegment] = field(default_factory=list, repr=False)

    @property
    def is_simple(self) -> bool:
        return not self.prefixes and not self.suffixes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_token": self.original_token,
            "segments": [s.to_dict() for s in self.segments],
            "stem": self.stem,
            "prefixes": self.prefixes,
            "suffixes": self.suffixes,
            "has_pronoun": self.has_pronoun,
            "pronoun_role": self.pronoun_role,
            "is_simple": self.is_simple,
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def _strip(text: str) -> str:
    return _DIA_RE.sub("", text)


class PronounAnalyzer:
    """Deterministic Arabic clitic decomposer.

    Segments a token into optional prefixes, a stem, and optional suffixes
    (including attached pronouns) by greedy longest-match in both
    directions, keeping a minimum stem length of two characters so the
    analysis never collapses a whole word into affixes.

    Parameters
    ----------
    min_stem_length:
        Minimum stem length in characters (default 2).

    Example
    -------
    >>> analyzer = PronounAnalyzer()
    >>> result = analyzer.analyze("وكتابهم")
    >>> result.prefixes
    ['و']
    >>> result.suffixes
    ['هم']
    >>> result.stem
    'كتاب'
    """

    def __init__(self, min_stem_length: int = 2) -> None:
        self.min_stem_length = max(1, min_stem_length)

    def _prefix_valid(self, prefix: str, stem: str) -> bool:
        """Decide whether *prefix* is legitimately attached to *stem*."""
        if prefix in ("ب", "ك", "ل"):
            # bare prepositions only attach to definite nouns (بالكتاب).
            return stem.startswith("ال")
        if prefix in _DEFINITE_PREPOSITIONS:
            return True
        if prefix in ("و", "ف", "أ", "اف", "س", "ست", "است"):
            return len(stem) >= self.min_stem_length
        return True

    def analyze(self, token: str) -> PronounAnalysisResult:
        """Decompose a single Arabic token."""
        token = token.strip()
        result = PronounAnalysisResult(original_token=token)

        if not token or not _ARABIC.match(token):
            result.segments = [CliticSegment(text=token, role="stem", grammar="نص غير عربي أو فارغ")]
            result.stem = token
            return result

        clean = _strip(token)

        # --- prefixes (left to right, greedy longest) ---
        prefixes: List[CliticSegment] = []
        remaining = clean
        position = 0
        changed = True
        while changed:
            changed = False
            for prefix, grammar in _PREFIX_SORTED:
                if remaining.startswith(prefix):
                    rest = remaining[len(prefix) :]
                    if len(rest) >= self.min_stem_length and self._prefix_valid(prefix, rest):
                        prefixes.append(CliticSegment(text=prefix, role="prefix", grammar=grammar))
                        remaining = rest
                        position += len(prefix)
                        changed = True
                        break

        # --- suffixes (right to left, greedy longest) ---
        suffixes: List[CliticSegment] = []
        changed = True
        while changed:
            changed = False
            for suffix, grammar in _SUFFIX_SORTED:
                if remaining.endswith(suffix):
                    rest = remaining[: -len(suffix)]
                    if len(rest) >= self.min_stem_length:
                        suffixes.append(CliticSegment(text=suffix, role="suffix", grammar=grammar))
                        remaining = rest
                        changed = True
                        break

        result.prefixes = [p.text for p in prefixes]
        result.suffixes = [s.text for s in suffixes]
        result._suffix_clitics = suffixes
        result.stem = remaining
        result.segments = prefixes + [CliticSegment(text=remaining, role="stem", grammar="جذر الكلمة")] + suffixes

        if suffixes:
            result.has_pronoun = True
            result.pronoun_role = suffixes[-1].grammar
        return result

    def analyze_tokens(self, tokens: List[str]) -> List[PronounAnalysisResult]:
        return [self.analyze(t) for t in tokens]

    def pronoun_statistics(self, texts: List[str]) -> Dict[str, Any]:
        """Aggregate pronoun-attachment statistics over many texts."""
        from aranorm.utils.tokenizer import ArabicTokenizer

        tokenizer = ArabicTokenizer()
        total_tokens = 0
        tokens_with_pronouns = 0
        by_role: Dict[str, int] = {}
        for text in texts:
            for tok in tokenizer.tokenize(text):
                total_tokens += 1
                analysis = self.analyze(tok)
                if analysis.has_pronoun:
                    tokens_with_pronouns += 1
                    if analysis._suffix_clitics:
                        role = analysis._suffix_clitics[-1].grammar
                        by_role[role] = by_role.get(role, 0) + 1
        return {
            "total_tokens": total_tokens,
            "tokens_with_pronouns": tokens_with_pronouns,
            "pronoun_ratio": (tokens_with_pronouns / total_tokens) if total_tokens else 0.0,
            "by_role": by_role,
        }
