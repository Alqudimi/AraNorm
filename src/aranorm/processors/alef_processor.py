"""Alef-family normalization."""

from aranorm.processors._base import TextProcessor


class ALEFProcessor(TextProcessor):
    """Map alef variants to bare alef."""

    name = "normalize_alef"
    _mapping = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})

    def transform(self, text: str) -> str:
        """Normalize alef variants."""
        return text.translate(self._mapping)


class AlefMaqsuraProcessor(TextProcessor):
    """Map alef maqsura to ya."""

    name = "normalize_alef_maqsura"

    def transform(self, text: str) -> str:
        """Replace ى with ي."""
        return text.replace("ى", "ي")
