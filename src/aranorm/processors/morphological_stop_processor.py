"""Morphological stop-words processor.

Arabic stop words appear in many inflected forms (أنا/أنتَ/هو, كان/كانت/كانوا…).
This processor expands a core stop-word list to all its common morphological
variants using a rule-based suffix/prefix table, so "كنتُ" is treated as a
stop word even if only "كان" is in the base list.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Set

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.stop_words_registry import StopWordsRegistry

# ── Morphological expansion tables ───────────────────────────────────────────

# Pronominal suffixes attached to verbs / prepositions / nouns
_PRONOMINAL_SUFFIXES = (
    "ني", "كَ", "كِ", "كم", "كن", "كما",
    "ه", "ها", "هم", "هن", "هما",
    "نا", "ي",
)

# Common conjugation patterns for auxiliary verbs (كان، ليس…)
_KANA_FORMS: Set[str] = {
    "كان", "كانت", "كانوا", "كنت", "كنتُ", "كنتِ", "كنتم", "كنتن",
    "كنتما", "كنا", "يكون", "تكون", "يكونوا", "تكونوا", "كونوا",
    "أكون", "نكون",
}

_LAYSA_FORMS: Set[str] = {
    "ليس", "ليست", "لست", "لستَ", "لستِ", "لستم", "لستن", "لستما", "لسنا",
    "ليسوا",
}

_QALA_FORMS: Set[str] = {
    "قال", "قالت", "قالوا", "قلت", "قلتَ", "قلتِ", "قلتم", "قلتن",
    "قلتما", "قلنا", "يقول", "تقول", "يقولوا", "تقولوا", "أقول", "نقول",
}

_ANA_FORMS: Set[str] = {
    "أنا", "أنتَ", "أنتِ", "أنتم", "أنتن", "أنتما",
    "هو", "هي", "هم", "هن", "هما", "نحن",
    # Dialectal
    "انا", "انت", "انتي", "انتو", "هو", "هي", "احنا", "إحنا",
}

_PREPOSITION_FORMS: Set[str] = {
    # في + pronouns
    "فيه", "فيها", "فيهم", "فيهن", "فيهما", "فينا", "فيك", "فيكم", "فيكن",
    # من + pronouns
    "منه", "منها", "منهم", "منهن", "منهما", "منا", "منك", "منكم", "منكن",
    # إلى + pronouns
    "إليه", "إليها", "إليهم", "إليهن", "إليهما", "إلينا", "إليك", "إليكم",
    # عن + pronouns
    "عنه", "عنها", "عنهم", "عنهن", "عنهما", "عنا", "عنك", "عنكم",
    # على + pronouns
    "عليه", "عليها", "عليهم", "عليهن", "عليهما", "علينا", "عليك", "عليكم",
    # مع + pronouns
    "معه", "معها", "معهم", "معهن", "معهما", "معنا", "معك", "معكم",
    # ل + pronouns
    "له", "لها", "لهم", "لهن", "لهما", "لنا", "لك", "لكم", "لكن",
    # ب + pronouns
    "به", "بها", "بهم", "بهن", "بهما", "بنا", "بك", "بكم", "بكن",
}

# Complete morphological expansion set (union of all tables)
_ALL_MORPHOLOGICAL_STOPS: Set[str] = (
    _KANA_FORMS | _LAYSA_FORMS | _QALA_FORMS | _ANA_FORMS | _PREPOSITION_FORMS
)

# Definite article variations
_AL_VARIANTS = re.compile(r"^(ال|ال\u0651)")


class MorphologicalStopProcessor(Processor):
    """Remove Arabic stop words including all their morphological variants.

    Combines the registry's base stop-word set with pre-computed morphological
    expansion tables to catch inflected forms.

    Parameters
    ----------
    registry:
        Optional :class:`~aranorm.core.stop_words_registry.StopWordsRegistry`.
    include_clitic_forms:
        When *True* (default), also remove cliticised stop-word forms such as
        "فيه", "معها", "منكم".
    include_verb_forms:
        When *True* (default), remove auxiliary verb forms كان/كانت/ليس…

    Example
    -------
    >>> proc = MorphologicalStopProcessor()
    >>> proc.process("كنت أعمل بجد معهم")
    'أعمل بجد'
    """

    name = "morphological_stop_processor"

    def __init__(
        self,
        registry: Optional[StopWordsRegistry] = None,
        include_clitic_forms: bool = True,
        include_verb_forms: bool = True,
    ) -> None:
        self.registry = registry or StopWordsRegistry()
        base = self.registry.get_words("universal")

        self._stop_set: Set[str] = set(base)
        if include_clitic_forms:
            self._stop_set |= _PREPOSITION_FORMS
        if include_verb_forms:
            self._stop_set |= _KANA_FORMS | _LAYSA_FORMS
        self._stop_set |= _ANA_FORMS

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Remove morphologically-aware stop words from *text*."""
        if not text or not text.strip():
            return text
        tokens = text.split()
        kept = []
        for token in tokens:
            raw = token.strip(".,،؟!؛:")
            # Check raw form
            if raw in self._stop_set:
                continue
            # Check without definite article (e.g. "الكان" → "كان")
            stripped = _AL_VARIANTS.sub("", raw)
            if stripped and stripped in self._stop_set:
                continue
            kept.append(token)
        self._record(context)
        return " ".join(kept)

    @property
    def stop_set_size(self) -> int:
        """Total number of stop word forms in the expanded set."""
        return len(self._stop_set)
