"""Hamza normalization."""

from aranorm.processors._base import TextProcessor


class HamzaProcessor(TextProcessor):
    """Normalize hamza carriers while preserving standalone hamza."""

    name = "normalize_hamza"

    def transform(self, text: str) -> str:
        """Normalize contextual hamza forms."""
        value = text.replace("ؤ", "ء")
        value = value.replace("ئ", "ء")
        return value
