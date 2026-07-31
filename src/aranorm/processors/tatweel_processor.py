"""Tatweel removal."""

from aranorm.processors._base import TextProcessor


class TatweelProcessor(TextProcessor):
    """Remove Arabic tatweel/kashida characters."""

    name = "normalize_tatweel"

    def transform(self, text: str) -> str:
        """Remove tatweel."""
        return text.replace("ـ", "")
