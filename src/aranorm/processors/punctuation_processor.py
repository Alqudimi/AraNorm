"""Arabic punctuation normalization."""

from aranorm.processors._base import TextProcessor
from aranorm.utils.constants import PUNCTUATION_REPLACEMENTS


class PunctuationProcessor(TextProcessor):
    """Normalize Arabic punctuation to predictable ASCII punctuation."""

    name = "normalize_punctuation"

    def transform(self, text: str) -> str:
        """Replace punctuation variants."""
        return "".join(PUNCTUATION_REPLACEMENTS.get(char, char) for char in text)
