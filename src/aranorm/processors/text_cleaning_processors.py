"""Content cleaning processors."""

import re

from aranorm.processors._base import TextProcessor
from aranorm.utils.constants import ARABIC_LETTERS
from aranorm.utils.patterns import (
    EMAIL_PATTERN,
    HASHTAG_PATTERN,
    HTML_PATTERN,
    MENTION_PATTERN,
    URL_PATTERN,
)


class URLProcessor(TextProcessor):
    """Remove HTTP, HTTPS, and www URLs."""

    name = "remove_urls"

    def transform(self, text: str) -> str:
        """Remove URLs."""
        return URL_PATTERN.sub(" ", text)


class EmailProcessor(TextProcessor):
    """Remove email addresses."""

    name = "remove_emails"

    def transform(self, text: str) -> str:
        """Remove email addresses."""
        return EMAIL_PATTERN.sub(" ", text)


class MentionProcessor(TextProcessor):
    """Remove social media mentions."""

    name = "remove_mentions"

    def transform(self, text: str) -> str:
        """Remove @mentions."""
        return MENTION_PATTERN.sub(" ", text)


class HashtagProcessor(TextProcessor):
    """Remove hashtag markers while preserving their words."""

    name = "remove_hashtags"

    def transform(self, text: str) -> str:
        """Turn #topic into topic."""
        return HASHTAG_PATTERN.sub(r"\1", text)


class HTMLProcessor(TextProcessor):
    """Remove simple HTML tags."""

    name = "remove_html_tags"

    def transform(self, text: str) -> str:
        """Remove tags without touching their contents."""
        return HTML_PATTERN.sub(" ", text)


class NonArabicProcessor(TextProcessor):
    """Keep Arabic characters and optionally digits/punctuation."""

    name = "remove_non_arabic"

    def __init__(self, keep_digits: bool = True, keep_punctuation: bool = True) -> None:
        self.keep_digits = keep_digits
        self.keep_punctuation = keep_punctuation

    def transform(self, text: str) -> str:
        """Remove non-Arabic letters while preserving configured symbols."""
        allowed = set(ARABIC_LETTERS) | set(" \t\n")
        if self.keep_digits:
            allowed.update("0123456789")
        if self.keep_punctuation:
            allowed.update(",.;:!?%؟،؛-()[]")
        return "".join(char if char in allowed else " " for char in text)


class EnglishProcessor(TextProcessor):
    """Remove Latin words and letters."""

    name = "remove_english"

    def transform(self, text: str) -> str:
        """Remove Latin alphabet characters."""
        return re.sub(r"[A-Za-z]+", " ", text)
