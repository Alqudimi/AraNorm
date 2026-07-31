"""Taa marbuta normalization."""

from aranorm.processors._base import TextProcessor


class TaaMarbutaProcessor(TextProcessor):
    """Map taa marbuta to haa for dialect-friendly normalization."""

    name = "normalize_taa_marbuta"

    def transform(self, text: str) -> str:
        """Replace ة with ه."""
        return text.replace("ة", "ه")
