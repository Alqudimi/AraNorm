"""Punctuation spacing processors."""

import re

from aranorm.processors._base import TextProcessor
from aranorm.utils.patterns import REPEATED_PUNCTUATION_PATTERN


class RepeatedPunctuationProcessor(TextProcessor):
    """Collapse repeated punctuation while preserving one mark."""

    name = "remove_extra_punctuation"

    def transform(self, text: str) -> str:
        """Collapse punctuation runs such as ``؟؟؟`` and ``!!!``."""
        return REPEATED_PUNCTUATION_PATTERN.sub(r"\1", text)


class SpacingProcessor(TextProcessor):
    """Normalize spaces around punctuation."""

    name = "fix_spacing"

    def transform(self, text: str) -> str:
        """Remove spaces before punctuation and ensure one after it."""
        value = re.sub(r"\s+([!?.,،؛:؟])", r"\1", text)
        return re.sub(r"([!?.,،؛:؟])(?=[^\s!?.,،؛:؟])", r"\1 ", value)
