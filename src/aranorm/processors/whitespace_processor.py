"""Whitespace normalization."""

import re

from aranorm.processors._base import TextProcessor


class WhitespaceProcessor(TextProcessor):
    """Collapse whitespace and trim text."""

    name = "normalize_whitespace"

    def transform(self, text: str) -> str:
        """Collapse all whitespace runs."""
        return re.sub(r"\s+", " ", text).strip()
