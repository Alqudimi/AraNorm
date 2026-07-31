"""Unicode normalization."""

import unicodedata

from aranorm.processors._base import TextProcessor


class UnicodeProcessor(TextProcessor):
    """Apply NFKC normalization and remove compatibility artifacts."""

    name = "normalize_unicode"

    def transform(self, text: str) -> str:
        """Normalize text with Unicode compatibility decomposition."""
        return unicodedata.normalize("NFKC", text)
