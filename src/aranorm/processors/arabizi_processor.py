"""Rule-based Arabizi transliteration."""

import re
from typing import Dict

from aranorm.processors._base import TextProcessor
from aranorm.utils.patterns import ARABIZI_WORD_PATTERN


class ArabiziProcessor(TextProcessor):
    """Convert common Arabizi digits and Latin letters to Arabic."""

    name = "normalize_arabizi"
    _mapping: Dict[str, str] = {
        "2": "ء",
        "3": "ع",
        "4": "ش",
        "5": "خ",
        "6": "ط",
        "7": "ح",
        "8": "ق",
        "9": "ص",
        "@": "ع",
        "$": "ش",
    }
    _letter_mapping: Dict[str, str] = {
        "a": "ا",
        "b": "ب",
        "t": "ت",
        "j": "ج",
        "d": "د",
        "r": "ر",
        "s": "س",
        "f": "ف",
        "k": "ك",
        "l": "ل",
        "m": "م",
        "n": "ن",
        "h": "ه",
        "w": "و",
        "y": "ي",
        "i": "ي",
        "e": "ي",
    }

    def transform(self, text: str) -> str:
        """Transliterate recognizable Arabizi tokens."""
        return ARABIZI_WORD_PATTERN.sub(self._transliterate_token, text)

    def _transliterate_token(self, match: re.Match) -> str:
        """Transliterate one token using longest common digraphs first."""
        token = match.group(0).lower()
        if token == "eh":
            return "ه"
        token = token.replace("sh", "ش").replace("kh", "خ").replace("gh", "غ")
        return "".join(self._mapping.get(char, self._letter_mapping.get(char, char)) for char in token)
