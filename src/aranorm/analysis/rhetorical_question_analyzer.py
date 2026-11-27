"""Arabic rhetorical-question (استفهام بلاغي) detection.

A deterministic, rule-based detector that distinguishes questions used for
rhetorical effect (استفهام استنكاري / تقريري) from plain information-seeking
questions, based on interrogative particles, negative-inversion patterns,
and stylistic markers:

+-----------------------------+------------------------------------------------+
| Signal                      | Detection approach                             |
+-----------------------------+------------------------------------------------+
| inversion_questions         | Negative-particle inversions such as          |
|                             | ``أليس`` / ``ألم`` / ``ألا`` / ``أما`` /        |
|                             | ``ألست`` and similar forms that strongly        |
|                             | signal a rhetorical assertion rather than a     |
|                             | genuine information request.                    |
+-----------------------------+------------------------------------------------+
| direct_questions            | Questions formed with the neutral particles    |
|                             | ``هل`` / ``أ`` (أ-الاستفهام) and a closing     |
|                             | Arabic question mark ``؟``.                    |
+-----------------------------+------------------------------------------------+
| rhetorical_markers          | Discourse markers that frequently accompany    |
|                             | rhetorical questions (من ذا / بأي معنى /       |
|                             | كيف يكون / كيف يمكن).                          |
+-----------------------------+------------------------------------------------+
| label                       | ``"interrogative-rich"`` / ``"moderate"`` /     |
|                             | ``"plain"`` derived from density against       |
|                             | thresholds.                                    |
+-----------------------------+------------------------------------------------+

Deterministic, dependency-free, and consistent with the ``aranorm.analysis``
family (dataclass results with ``to_dict``/JSON APIs).

Example
-------
>>> from aranorm.analysis.rhetorical_question_analyzer import analyze_rquestions
>>> result = analyze_rquestions("أليس الوقت قد حان؟ ألم نقل لكم؟ هل تدري؟")
>>> result.inversion_questions >= 2
True
"""

from __future__ import annotations

import json
import re as _re
from dataclasses import dataclass
from typing import Any, Dict, List

# Matches complete Arabic words (diacritics included).
_WORD_RE = _re.compile(r"[\u0621-\u0652\u0660-\u06690-9A-Za-z]+")
# Sentence boundary markers that end a question or statement.
_SENTENCE_END_RE = _re.compile(r"[؟?!.…]+")
_DIACRITICS = _re.compile(r"[\u064B-\u0652\u0670\u0640\u064E\u064F\u0650\u0651]")
_ALEF_NORMALISE = str.maketrans("أإآ", "ااا")


# Interrogative inversions that carry a rhetorical/assertive force.
# ``أليس/ألست/أليست...`` + following verb/predicate usually asserts the
# opposite of the literal question ("is it not true that...?").
_RHETORICAL_INVERSIONS = (
    "أليس",
    "أليست",
    "أليسا",
    "أليستا",
    "أليسوا",
    "أليسوا",
    "أليسن",
    "ألست",
    "ألستم",
    "ألستما",
    "ألستن",
    "ألستِ",
    "ألستُ",
    "ألستُ",
    "ألسن",
)
# Two-word inversion heads that need a second token to be confirmed.
_RHETORICAL_TWO_WORD_HEADS = ("ألم", "ألا", "أما")

# Neutral interrogative particles (genuine information-seeking markers).
_NEUTRAL_PARTICLES = frozenset(
    ["هل", "أ", "أأ", "ماذا", "ما", "من", "أين", "متى", "كيف", "كم", "أي", "أيها", "ماذا", "لم", "لماذا"]
)

# Discourse markers strongly associated with rhetorical questioning.
_RHETORICAL_MARKERS = (
    "من ذا",
    "من ذا الذي",
    "بأي معنى",
    "بأي حال",
    "كيف يكون",
    "كيف يمكن",
    "أين يذهب",
    "متى تتحقق",
    "لم لا",
    "لما لا",
    "وهل",
    "وما",
    "أفلا",
    "أفلم",
    "أفما",
    "أفأنت",
)


def _clean(word: str) -> str:
    """Strip diacritics and normalise alef forms."""
    word = _DIACRITICS.sub("", word)
    return word.translate(_ALEF_NORMALISE)


def _sentences(text: str) -> List[str]:
    """Split *text* into rough sentence units."""
    ends = [match.end() for match in _SENTENCE_END_RE.finditer(text)]
    if not ends:
        return [text] if text.strip() else []
    parts: List[str] = []
    start = 0
    for end in ends:
        parts.append(text[start:end])
        start = end
    if start < len(text) and text[start:].strip():
        parts.append(text[start:])
    return [part for part in parts if part.strip()]


@dataclass(frozen=True)
class RhetoricalQuestion:
    """A detected rhetorical or direct question with character offsets."""

    text: str
    question_type: str  # "inversion" | "direct" | "marker"
    start: int
    end: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "question_type": self.question_type,
            "start": self.start,
            "end": self.end,
        }


@dataclass
class RhetoricalQuestionsResult:
    """Consolidated rhetorical-question analysis for a single Arabic text.

    Attributes
    ----------
    questions:
        Detected questions in occurrence order.
    inversion_questions:
        Count of inversion-style rhetorical questions (أليس/ألم/...).
    direct_questions:
        Count of neutral-particle questions ending with ``؟``.
    rhetorical_markers:
        Count of discourse markers that accompany rhetorical questioning.
    question_density:
        Questions per 100 words (0.0 if no words).
    label:
        ``"interrogative-rich"`` / ``"moderate"`` / ``"plain"``.
    """

    questions: List[RhetoricalQuestion]
    inversion_questions: int
    direct_questions: int
    rhetorical_markers: int
    question_density: float
    label: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "questions": [question.to_dict() for question in self.questions],
            "inversion_questions": self.inversion_questions,
            "direct_questions": self.direct_questions,
            "rhetorical_markers": self.rhetorical_markers,
            "question_density": round(self.question_density, 4),
            "label": self.label,
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


@dataclass
class RhetoricalQuestionAnalyzer:
    """Arabic rhetorical-question detection over prose.

    Parameters
    ----------
    rich_threshold:
        Question density (per 100 words) at or above which the text is
        labelled ``"interrogative-rich"``.
    moderate_threshold:
        Density at or above which the text is labelled ``"moderate"``;
        below this the label is ``"plain"``.
    """

    rich_threshold: float = 10.0
    moderate_threshold: float = 3.0

    def analyze(self, text: str) -> RhetoricalQuestionsResult:
        """Detect rhetorical and direct questions in *text*."""
        questions: List[RhetoricalQuestion] = []
        inversion_count = 0
        direct_count = 0
        marker_count = 0

        # Compound question forms: the interrogative alef ``أ`` may attach to
        # the following word (``أتدري``, ``ألديك``). A leading interrogative
        # ``أ`` attached to a content word is counted as a direct question
        # when the sentence closes with ``؟``. Prefixes are compared after
        # alef normalisation because ``أ-`` is flattened to ``ا``.
        _attached_alef_prefixes = ("ات", "أل")
        # Two-word inversion heads normalised for alef flattening so that
        # ``ألم`` / ``ألا`` / ``أما`` still match after ``_clean``.
        _CLEAN_TWO_WORD_HEADS = frozenset(_clean(word) for word in _RHETORICAL_TWO_WORD_HEADS)
        # Single-word rhetorical inversions (``أليس``, ``ألست``, ``أليست``...)
        # with the two-word heads excluded so that ``ألم`` alone is never
        # counted without its confirming verb.
        inverted_set = frozenset(_clean(word) for word in _RHETORICAL_INVERSIONS)
        words = [(match.group(), match.start(), match.end()) for match in _WORD_RE.finditer(text)]

        # ── Marker phrases (multi-word, checked on the raw text) ─────────────
        lower_text = _DIACRITICS.sub("", text).translate(_ALEF_NORMALISE)
        marker_spans: List[int] = []
        # Attach common proclitics (ب / ف / و) so that ``بأي معنى``,
        # ``فمن ذا``, and ``وأين يذهب`` still match their marker.
        expanded_markers: List[str] = []
        for marker in _RHETORICAL_MARKERS:
            expanded_markers.append(marker)
            first = marker[0]
            if first != "ا":
                for proclitic in ("ب", "ف", "و"):
                    expanded_markers.append(proclitic + marker)
        # Normalise alef variants so that ``بأي معنى`` matches the flattened
        # search text ``باي معنى``.
        expanded_markers = [marker.translate(_ALEF_NORMALISE) for marker in expanded_markers]
        for marker in expanded_markers:
            index = 0
            while True:
                found = lower_text.find(marker, index)
                if found == -1:
                    break
                if not marker_spans or found >= marker_spans[-1]:
                    marker_spans.append(found)
                    marker_count += 1
                    questions.append(
                        RhetoricalQuestion(
                            text=text[found : found + len(marker)],
                            question_type="marker",
                            start=found,
                            end=found + len(marker),
                        )
                    )
                index = found + len(marker)

        # ── Word-level interrogation analysis ────────────────────────────────
        seen_inversions: set = set()
        index = 0
        while index < len(words):
            word, start, end = words[index]
            clean_word = _clean(word)
            # Inversion questions: single-word heads (أليس، ألست، أليست...).
            if clean_word in inverted_set and clean_word not in _CLEAN_TWO_WORD_HEADS:
                if start not in seen_inversions:
                    seen_inversions.add(start)
                    inversion_count += 1
                    questions.append(
                        RhetoricalQuestion(
                            text=word,
                            question_type="inversion",
                            start=start,
                            end=end,
                        )
                    )
            # Two-word heads: ``ألم يكن/تكن/يكون/يكنوا`` — check next token.
            # Heads listed in ``_RHETORICAL_TWO_WORD_HEADS`` are always
            # resolved through the two-word path so they are never counted
            # as incomplete single-word inversions.
            elif clean_word in _CLEAN_TWO_WORD_HEADS and index + 1 < len(words):
                next_word = _clean(words[index + 1][0])
                if next_word in ("يكن", "تكن", "يكون", "يكنوا", "كنّ", "يكنوا"):
                    combined_start = start
                    combined_end = words[index + 1][2]
                    combined_span = (combined_start, combined_end)
                    if combined_span not in seen_inversions:
                        seen_inversions.add(combined_span)
                        inversion_count += 1
                        questions.append(
                            RhetoricalQuestion(
                                text=text[combined_start:combined_end],
                                question_type="inversion",
                                start=combined_start,
                                end=combined_end,
                            )
                        )
            # Neutral-particle direct questions: ``هل`` / ``أ`` ... ``؟``
            # A question particle followed somewhere in the same sentence by
            # an Arabic question mark is counted as a direct question.
            elif clean_word in ("هل", "أ", "أأ", "ماذا", "من", "أين", "متى", "كيف", "كم", "أي"):
                if clean_word in _NEUTRAL_PARTICLES:
                    if clean_word not in ("ما",):
                        sentence_end = len(text)
                        for match in _SENTENCE_END_RE.finditer(text):
                            if match.start() >= end:
                                sentence_end = match.end()
                                break
                        if "؟" in text[end:sentence_end] or "?" in text[end:sentence_end]:
                            if start not in seen_inversions:
                                seen_inversions.add(start)
                                direct_count += 1
                                questions.append(
                                    RhetoricalQuestion(
                                        text=word,
                                        question_type="direct",
                                        start=start,
                                        end=end,
                                    )
                                )
            # Attached interrogative alef: ``أتدري``, ``أأنتم``, ``ألديك``
            # are interrogative inversions of the direct form.
            else:
                for prefix in _attached_alef_prefixes:
                    if clean_word.startswith(prefix) and len(clean_word) > len(prefix) + 1:
                        sentence_end = len(text)
                        for match in _SENTENCE_END_RE.finditer(text):
                            if match.start() >= end:
                                sentence_end = match.end()
                                break
                        if "؟" in text[end:sentence_end] or "?" in text[end:sentence_end]:
                            if start not in seen_inversions:
                                seen_inversions.add(start)
                                direct_count += 1
                                questions.append(
                                    RhetoricalQuestion(
                                        text=word,
                                        question_type="direct",
                                        start=start,
                                        end=end,
                                    )
                                )
                        break
            index += 1

        # ── Density and label ────────────────────────────────────────────────
        word_count = len(words) if words else 0
        total_questions = len(questions)
        density = (total_questions / word_count) * 100.0 if word_count else 0.0
        if density >= self.rich_threshold:
            label = "interrogative-rich"
        elif density >= self.moderate_threshold or questions:
            label = "moderate"
        else:
            label = "plain"
        return RhetoricalQuestionsResult(
            questions=questions,
            inversion_questions=inversion_count,
            direct_questions=direct_count,
            rhetorical_markers=marker_count,
            question_density=density,
            label=label,
        )

    def analyze_batch(self, texts: List[str]) -> List[RhetoricalQuestionsResult]:
        """Analyze a list of texts independently."""
        return [self.analyze(text) for text in texts]


def analyze_rquestions(text: str) -> RhetoricalQuestionsResult:
    """Detect Arabic rhetorical questions in *text*."""
    return RhetoricalQuestionAnalyzer().analyze(text)
