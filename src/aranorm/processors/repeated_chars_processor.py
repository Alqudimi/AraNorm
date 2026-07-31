"""Repeated character reduction."""

import re

from aranorm.processors._base import TextProcessor
from aranorm.utils.constants import DEFAULT_REPEATED_CHAR_LIMIT


class RepeatedCharsProcessor(TextProcessor):
    """Reduce expressive character runs while keeping two characters."""

    name = "normalize_repeated_chars"

    def __init__(self, limit: int = DEFAULT_REPEATED_CHAR_LIMIT) -> None:
        if limit < 1:
            raise ValueError("limit must be positive")
        self.limit = limit

    def transform(self, text: str) -> str:
        """Limit repeated non-whitespace characters."""
        pattern = re.compile(r"(.)\1{" + str(self.limit) + r",}")
        return pattern.sub(lambda match: match.group(1) * self.limit, text)
