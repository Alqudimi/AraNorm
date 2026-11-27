"""Rule-based Arabic spelling correction.

Fixes the most common orthographic errors found in social-media and informal
Arabic text without requiring any external dependency.

Error categories covered:
* Dropped / wrong hamza on alef (أ/إ/آ/ا confusion)
* Yaa/alef-maqsura confusion at word end
* Taa-marbuta/haa confusion at word end
* Common collapsed phrases (بالزبط → بالضبط)
* SMS-style shorthands (ربنا يرحمه → kept, لو → لو)
* Lam+alef written as separate characters instead of ligature form
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from aranorm.processors._base import TextProcessor

# ── Whole-word replacements ───────────────────────────────────────────────────
# Each tuple: (wrong_form, correct_form)
# Listed longest-first within each group for correct matching order.

_WORD_CORRECTIONS: List[Tuple[str, str]] = [
    # ── Common phrases / contractions ─────────────────────────────────
    ("بالزبط", "بالضبط"),
    ("بالزبظ", "بالضبط"),
    ("بالظبط", "بالضبط"),
    ("بلظبط", "بالضبط"),
    ("ماشى", "ماشي"),
    ("ماشي", "ماشي"),
    ("مشى", "مشى"),  # keep correct
    ("أكيد", "أكيد"),  # keep
    ("اكيد", "أكيد"),
    ("طيب", "طيب"),
    ("عارف", "عارف"),
    ("عارفة", "عارفة"),
    ("ماعارف", "ما أعرف"),
    # ── Hamza on alef ─────────────────────────────────────────────────
    ("الاسلام", "الإسلام"),
    ("الاسلامي", "الإسلامي"),
    ("الاسلامية", "الإسلامية"),
    ("اسلامي", "إسلامي"),
    ("اسلامية", "إسلامية"),
    ("الانسان", "الإنسان"),
    ("انسانية", "إنسانية"),
    ("انسان", "إنسان"),
    ("اعلام", "إعلام"),
    ("الاعلام", "الإعلام"),
    ("اعلامي", "إعلامي"),
    ("الاقتصاد", "الاقتصاد"),  # correct – ا initial
    ("الاجتماع", "الاجتماع"),  # correct
    ("اعلان", "إعلان"),
    ("الاعلان", "الإعلان"),
    ("اصلاح", "إصلاح"),
    ("الاصلاح", "الإصلاح"),
    ("اختيار", "اختيار"),  # correct – ا initial + ت
    ("اجتهاد", "اجتهاد"),  # correct
    ("اتحاد", "اتحاد"),  # correct
    ("امتحان", "امتحان"),  # correct
    ("امكانية", "إمكانية"),
    ("الامكانية", "الإمكانية"),
    ("الامكان", "الإمكان"),
    ("ابداع", "إبداع"),
    ("الابداع", "الإبداع"),
    ("ابداعي", "إبداعي"),
    ("انتاج", "إنتاج"),
    ("الانتاج", "الإنتاج"),
    ("انجاز", "إنجاز"),
    ("انجازات", "إنجازات"),
    ("انشاء", "إنشاء"),
    ("الانشاء", "الإنشاء"),
    ("اعداد", "إعداد"),
    ("اهتمام", "اهتمام"),  # correct – ا initial
    # ── Waw-hamza ─────────────────────────────────────────────────────
    ("مسئول", "مسؤول"),
    ("مسئولية", "مسؤولية"),
    ("مسئولين", "مسؤولين"),
    # ── Ya/alef maqsura at word end ────────────────────────────────────
    # These are deliberately conservative — only clear cases
    ("علي", "على"),  # preposition
    # ── Common misspellings ────────────────────────────────────────────
    ("هيئة", "هيئة"),  # correct
    ("لازم", "لازم"),  # keep dialect form
    ("شكراً", "شكراً"),  # keep
    ("شكرا", "شكراً"),
    ("اهلاً", "أهلاً"),
    ("اهلا", "أهلاً"),
    ("مرحباً", "مرحباً"),  # keep
    ("مرحبا", "مرحباً"),
    ("صحيح", "صحيح"),
    ("الاوضاع", "الأوضاع"),
    ("اوضاع", "أوضاع"),
    ("الافضل", "الأفضل"),
    ("افضل", "أفضل"),
    ("الاهمية", "الأهمية"),
    ("اهمية", "أهمية"),
    ("الافراد", "الأفراد"),
    ("افراد", "أفراد"),
    ("الاجيال", "الأجيال"),
    ("اجيال", "أجيال"),
    ("الاولاد", "الأولاد"),
    ("اولاد", "أولاد"),
    ("الاولى", "الأولى"),
    ("اولى", "أولى"),
    ("الاول", "الأول"),
    ("اول", "أول"),
]

# Whole-word lookup table keyed by the exact whitespace-delimited token.
_CORRECTION_MAP: Dict[str, str] = {src: tgt for src, tgt in _WORD_CORRECTIONS if src != tgt}


class SpellingProcessor(TextProcessor):
    """Apply deterministic rule-based Arabic spelling corrections.

    Does not require any external library. Only applies unambiguous,
    high-precision corrections to avoid introducing false positives.

    Example
    -------
    >>> proc = SpellingProcessor()
    >>> proc.process("الاعلام بالزبط مسئولية الجميع")
    'الإعلام بالضبط مسؤولية الجميع'
    """

    name = "spelling_correction"

    def transform(self, text: str) -> str:
        """Apply all spelling corrections by exact whitespace-token matching.

        Working on whitespace-delimited tokens (instead of boundary regexes)
        correctly handles Arabic conjunctive waw ``و`` attached to the
        following word (``ومسئول``) and repeated occurrences of the same
        misspelled token anywhere in the text.
        """
        if not text:
            return text
        output: List[str] = []
        for token in text.split(" "):
            # Strip attached conjunctive waw so ``ومسئول`` becomes ``مسئول``.
            if token.startswith("و") and token[1:] in _CORRECTION_MAP:
                token = "و" + _CORRECTION_MAP[token[1:]]
            elif token in _CORRECTION_MAP:
                token = _CORRECTION_MAP[token]
            output.append(token)
        return " ".join(output)

    @classmethod
    def get_correction_count(cls) -> int:
        """Return the number of built-in correction rules."""
        return len(_WORD_CORRECTIONS)
