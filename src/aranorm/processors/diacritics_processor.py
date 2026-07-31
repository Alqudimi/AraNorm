"""Arabic diacritic removal."""

from aranorm.processors._base import TextProcessor
from aranorm.utils.constants import DIACRITICS


class DiacriticsProcessor(TextProcessor):
    """Remove Arabic vowel marks, shadda, sukun, and kashida."""

    name = "normalize_diacritics"

    def transform(self, text: str) -> str:
        """Remove known Arabic marks."""
        return "".join(char for char in text if char not in DIACRITICS)
