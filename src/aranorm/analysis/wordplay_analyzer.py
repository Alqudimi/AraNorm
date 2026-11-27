"""Arabic wordplay detection: paronomasia (jinās), saj' (rhymed prose) and puns.

Detects lexical play across an Arabic text using normalised phonetic
similarity (vowel-less, alef- and hamza-normalised stems). Two distinct
content words whose skeletons are near-identical count as a **paronomasia
pair** (jinās tām when the skeletons match fully, jinās nāqiṣ otherwise).
Repeated identical or near-identical sentence-final tokens across line
boundaries count as **saj'** (التصريع / سجّع النثر). A per-word **pun
density** and an overall label complete the report.

Supported categories:

+-------------------+---------------------------------------------------------+
| Category          | Detection signal                                        |
+-------------------+---------------------------------------------------------+
| paronomasia       | Two distinct words whose normalised skeletons share     |
|                   | ``>=80%`` similarity (full match = ``jinās_tām``).      |
+-------------------+---------------------------------------------------------+
| saj               | Two or more consecutive sentences whose last content    |
|                   | word shares the same normalised skeleton, plus          |
|                   | balanced segment counts.                                |
+-------------------+---------------------------------------------------------+
| pun               | A single word whose skeleton matches *two* distinct     |
|                   | neighbours of different meanings (semantic hint:        |
|                   | word carries ≥2 distinct neighbours within a window).   |
+-------------------+---------------------------------------------------------+

Returns typed mentions with character offsets and a composite ``label``
(``"playful"`` / ``"moderate"`` / ``"literal"``). Deterministic, dependency-
free, consistent with the ``aranorm.analysis`` family.

Example
-------
>>> from aranorm.analysis.wordplay_analyzer import analyze_wordplay
>>> result = analyze_wordplay("قُلْ هُوَ اللهُ أحد، اللهُ الصمد")
>>> result.label in ("playful", "moderate", "literal")
True
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

# ── Constants ────────────────────────────────────────────────────────────────

_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_ALEF_MAP = str.maketrans("أإآ", "ااا")
_HAMZA_CLEAN = re.compile(r"[ء]")
_WORD_RE = re.compile(r"[\u0621-\u064A\u0671-\u06D3]+")
_SENTENCE_SPLIT = re.compile(r"[.!?؟؛]+|\s{2,}|\n+")
_MIN_WORD_LEN = 3
_SIMILARITY_THRESHOLD = 0.8  # jinās nāqiṣ floor (tām requires 1.0)
_PUN_WINDOW = 6  # neighbour window (words on each side)
_SAJ_THRESHOLD = 2  # minimum rhymed sentence-final repetitions


def _skeleton(word: str) -> str:
    """Derive the consonant skeleton of *word*.

    Strips diacritics, shadda, tatweel, hamza carriers and the definite
    article ``ال`` along with attached proclitics (``و`` / ``ف`` / ``ب`` /
    ``ك`` / ``ل``) so that clitic-bound forms such as ``والقلب`` share a
    skeleton with ``القلب``. Converts ``ى/ئ/ؤ`` to their base letters so
    that ``قُلْ`` and ``قيل`` share a recognisable core.
    """
    base = _DIACRITICS.sub("", word)
    base = _HAMZA_CLEAN.sub("", base)
    base = base.translate(_ALEF_MAP)
    base = base.replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    # Strip attached proclitics (و/ف/ب/ك/ل) with up to three iterations,
    # mirroring the normalisation used across the analysis family.
    for _ in range(3):
        stripped = False
        for prefix in ("وال", "فال", "بال", "كال", "لل", "و", "ف", "ب", "ك", "ل"):
            if base.startswith(prefix) and len(base) - len(prefix) >= 2:
                base = base[len(prefix) :]
                stripped = True
                break
        if not stripped:
            break
    if base.startswith("ال") and len(base) > 3:
        base = base[2:]
    return base


def _skeleton_similarity(left: str, right: str) -> float:
    """Length-normalised character overlap between two skeletons."""
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    overlap = len(set(left) & set(right))
    union = len(set(left) | set(right))
    if union == 0:
        return 0.0
    length_ratio = min(len(left), len(right)) / max(len(left), len(right))
    return (overlap / union) * length_ratio


@dataclass(frozen=True)
class WordplayMention:
    """One detected wordplay unit with character offsets."""

    text: str
    kind: str  # "paronomasia" | "jinās_tām" | "saj" | "pun"
    pair: Tuple[str, str]
    start: int
    end: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "kind": self.kind,
            "pair": list(self.pair),
            "start": self.start,
            "end": self.end,
        }


@dataclass(frozen=True)
class WordplayResult:
    """Consolidated wordplay analysis for a single Arabic text.

    Attributes
    ----------
    mentions:
        Detected wordplay units (paronomasia, saj', puns) with offsets.
    paronomasia_pairs:
        Distinct near-homophone word pairs (jinās tām + nāqiṣ).
    tamm_pairs:
        Exact-skeleton jinās pairs (jinās tām).
    saj_lines:
        Number of rhymed sentence-final words forming saj' runs.
    pun_words:
        Words that act as puns over two distinct neighbours.
    wordplay_density:
        Wordplay mentions per 100 words (0.0 if no words).
    label:
        ``"playful"`` / ``"moderate"`` / ``"literal"``.
    word_count:
        Total words used for density computation.
    """

    mentions: List[WordplayMention]
    paronomasia_pairs: List[Tuple[str, str]]
    tamm_pairs: List[Tuple[str, str]]
    saj_lines: int
    pun_words: List[str]
    wordplay_density: float
    label: str
    word_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mentions": [mention.to_dict() for mention in self.mentions],
            "paronomasia_pairs": [list(pair) for pair in self.paronomasia_pairs],
            "tamm_pairs": [list(pair) for pair in self.tamm_pairs],
            "saj_lines": self.saj_lines,
            "pun_words": self.pun_words,
            "wordplay_density": round(self.wordplay_density, 4),
            "label": self.label,
            "word_count": self.word_count,
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)


@dataclass
class WordPlayAnalyzer:
    """Arabic wordplay (jinās / saj' / pun) detector.

    Parameters
    ----------
    similarity_threshold:
        Skeleton-similarity floor for a jinās nāqiṣ pair. Exact matches
        (1.0) always count as jinās tām regardless of the threshold.
    saj_threshold:
        Minimum consecutive sentence-final rhyme repetitions to label
        the text as carrying saj'.
    """

    similarity_threshold: float = _SIMILARITY_THRESHOLD
    saj_threshold: int = _SAJ_THRESHOLD

    def analyze(self, text: str) -> WordplayResult:
        """Analyze *text* and return a :class:`WordplayResult`."""
        words: List[Tuple[str, int, int]] = [
            (match.group(), match.start(), match.end()) for match in _WORD_RE.finditer(text)
        ]
        content_words = [(word, start, end) for word, start, end in words if len(word) >= _MIN_WORD_LEN]
        words_count = len(words) if words else 0

        mentions: List[WordplayMention] = []
        paronomasia_pairs: List[Tuple[str, str]] = []
        tamm_pairs: List[Tuple[str, str]] = []
        seen_pairs = set()

        # ── Paronomasia (jinās tām + nāqiṣ): compare distinct stems ───────────
        for index, (word_a, start_a, end_a) in enumerate(content_words):
            skeleton_a = _skeleton(word_a)
            if len(skeleton_a) < 2:
                continue
            for word_b, start_b, end_b in content_words[index + 1 :]:
                if _normalize_key(word_a) == _normalize_key(word_b):
                    continue  # same word — repetition, not wordplay
                skeleton_b = _skeleton(word_b)
                similarity = _skeleton_similarity(skeleton_a, skeleton_b)
                if similarity >= self.similarity_threshold:
                    pair_key = (skeleton_a, skeleton_b) if skeleton_a <= skeleton_b else (skeleton_b, skeleton_a)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    kind = "jinās_tām" if similarity == 1.0 else "paronomasia"
                    pair = (word_a, word_b)
                    if kind == "jinās_tām":
                        tamm_pairs.append(pair)
                    paronomasia_pairs.append(pair)
                    mentions.append(
                        WordplayMention(
                            text=f"{word_a} / {word_b}",
                            kind=kind,
                            pair=pair,
                            start=start_a,
                            end=end_b,
                        )
                    )

        # ── Saj' (تصريع/سجّع): rhymed sentence-final content words ──────────
        # Rhyme is measured on the final *letter group* of each segment's last
        # content word, matched fuzzily against the preceding run so that
        # ``ورد / سرد / فرد`` (all ending in ``ـرد``) register as saj'.
        saj_lines = 0
        final_skeletons: List[Tuple[str, int, int]] = []
        for segment in _SENTENCE_SPLIT.split(text):
            segment_words = _WORD_RE.findall(segment)
            tail_words = [word for word in segment_words if len(word) >= _MIN_WORD_LEN]
            if tail_words:
                final_skeletons.append((_skeleton(tail_words[-1]), len(tail_words), len(segment)))
            else:
                final_skeletons.append(("", 0, 0))

        def _rhymes(base: str, candidate: str) -> bool:
            """True when candidate's skeleton ends like base's skeleton."""
            if not base or not candidate:
                return False
            if base == candidate:
                return True
            # suffix-rhyme: last 2 letters of both skeletons match (e.g. ورد/سرد)
            if len(base) >= 2 and len(candidate) >= 2 and base[-2:] == candidate[-2:]:
                return True
            # fuzzy overlap fallback
            return _skeleton_similarity(base, candidate) >= self.similarity_threshold

        if len(final_skeletons) >= 2:
            run = 1
            last_skeleton = final_skeletons[0][0]
            for skeleton, word_count, length in final_skeletons[1:]:
                if skeleton and last_skeleton and _rhymes(last_skeleton, skeleton) and word_count >= 1:
                    run += 1
                else:
                    if run >= self.saj_threshold:
                        saj_lines += run
                    run = 1
                    last_skeleton = skeleton
            if run >= self.saj_threshold:
                saj_lines += run
        if saj_lines > 0:
            # Emit a single saj mention over the full text span.
            text = text  # noqa: PLW0127 (keep reference for offsets)
            mentions.append(
                WordplayMention(
                    text=text[:40] + "…",
                    kind="saj",
                    pair=("", ""),
                    start=0,
                    end=len(text),
                )
            )

        # ── Puns: one word flanked by two semantically distinct neighbours ────
        pun_words: List[str] = []
        for index, (word_a, start_a, end_a) in enumerate(content_words):
            skeleton_a = _skeleton(word_a)
            if len(skeleton_a) < 2:
                continue
            neighbours: List[str] = []
            for offset in range(1, _PUN_WINDOW + 1):
                for candidate in (index - offset, index + offset):
                    if 0 <= candidate < len(content_words):
                        neighbour = content_words[candidate][0]
                        if _normalize_key(neighbour) != _normalize_key(word_a):
                            neighbours.append(neighbour)
            distinct_neighbours = {skeleton for skeleton in (_skeleton(neighbour) for neighbour in neighbours)}
            near = sum(
                1
                for neighbour in neighbours
                if _skeleton_similarity(skeleton_a, _skeleton(neighbour)) >= self.similarity_threshold
            )
            if near >= 2 and len(distinct_neighbours) >= 2 and word_a not in pun_words:
                pun_words.append(word_a)
                mentions.append(
                    WordplayMention(
                        text=word_a,
                        kind="pun",
                        pair=(word_a, word_a),
                        start=start_a,
                        end=end_a,
                    )
                )

        density = len(mentions) / words_count * 100.0 if words_count else 0.0
        label = _classify_label(saj_lines, tamm_pairs, paronomasia_pairs, pun_words, density)
        return WordplayResult(
            mentions=mentions,
            paronomasia_pairs=paronomasia_pairs,
            tamm_pairs=tamm_pairs,
            saj_lines=saj_lines,
            pun_words=pun_words,
            wordplay_density=density,
            label=label,
            word_count=words_count,
        )

    def analyze_batch(self, texts: List[str]) -> List[WordplayResult]:
        """Run the analysis over multiple texts independently."""
        return [self.analyze(text) for text in texts]


def _normalize_key(word: str) -> str:
    """Full normalisation key for identity comparisons."""
    cleaned = _DIACRITICS.sub("", word)
    cleaned = _HAMZA_CLEAN.sub("", cleaned)
    cleaned = cleaned.translate(_ALEF_MAP)
    return cleaned.replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")


def _classify_label(
    saj_lines: int,
    tamm_pairs: List[Tuple[str, str]],
    paronomasia_pairs: List[Tuple[str, str]],
    pun_words: List[str],
    density: float,
) -> str:
    """Derive the overall wordplay label from the detected signals."""
    score = 0
    score += min(3, saj_lines)
    score += min(3, len(tamm_pairs))
    score += min(2, len(paronomasia_pairs) - len(tamm_pairs))
    score += min(2, len(pun_words))
    if density >= 3.0:
        score += 1
    if score >= 4:
        return "playful"
    if score >= 1:
        return "moderate"
    return "literal"


def analyze_wordplay(text: str) -> WordplayResult:
    """Module-level convenience wrapper over :class:`WordPlayAnalyzer`."""
    return WordPlayAnalyzer().analyze(text)
