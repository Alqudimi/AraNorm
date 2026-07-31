"""Arabic and Persian digit normalization."""

from aranorm.processors._base import TextProcessor
from aranorm.utils.constants import ARABIC_INDIC_DIGITS, PERSIAN_DIGITS, WESTERN_DIGITS


class DigitsProcessor(TextProcessor):
    """Map Arabic-Indic and Persian digits to Western digits."""

    name = "normalize_digits"
    _mapping = str.maketrans(
        ARABIC_INDIC_DIGITS + PERSIAN_DIGITS,
        WESTERN_DIGITS + WESTERN_DIGITS,
    )

    def transform(self, text: str) -> str:
        """Normalize digit scripts."""
        return text.translate(self._mapping)
