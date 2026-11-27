"""Platform-specific normalization processors.

Handles Twitter/X, WhatsApp, and general chat text cleanup.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, cast

from aranorm.processors._base import TextProcessor

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def _load_chat_abbreviations() -> Dict[str, str]:
    """Load chat abbreviations mapping (cached on first call)."""
    path = _DATA_DIR / "chat_abbreviations.json"
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
        if not isinstance(payload, dict):
            raise ValueError("Chat abbreviations must be a JSON object")
        return cast(Dict[str, str], payload)


def _whole_word_replace(text: str, source: str, target: str) -> str:
    """Replace *source* with *target* only at word boundaries."""
    pattern = r"(?<!\S)" + re.escape(source) + r"(?!\S)"
    return re.sub(pattern, target, text)


# Pre-compiled patterns
_RT_PREFIX = re.compile(r"^RT\s+@[\w\u0600-\u06FF]+:\s*", re.IGNORECASE)
_VIA_PATTERN = re.compile(r"\s+via\s+@[\w\u0600-\u06FF]+", re.IGNORECASE)
_TWITTER_MENTION = re.compile(r"(?<!\w)@[\w\u0600-\u06FF]+")
_TWITTER_HASHTAG = re.compile(r"(?<!\w)#(\S+)")
_TWITTER_THREAD_INDICATOR = re.compile(r"\(\d+/\d+\)\s*")
_MULTI_WHITESPACE = re.compile(r"\s{2,}")
_BOLD_FORMAT = re.compile(r"\*([^*]+)\*")
_ITALIC_FORMAT = re.compile(r"_([^_]+)_")
_STRIKETHROUGH = re.compile(r"~([^~]+)~")
_AUDIO_NOTE = re.compile(r"\[(?:صوت|voice note|audio)\]", re.IGNORECASE)
_IMAGE_NOTE = re.compile(r"\[(?:صورة|image|photo)\]", re.IGNORECASE)
_VIDEO_NOTE = re.compile(r"\[(?:فيديو|video)\]", re.IGNORECASE)
_STICKER_NOTE = re.compile(r"\[(?:ملصق|sticker)\]", re.IGNORECASE)
_LAUGHTER_AR = re.compile(r"(?:هه)+هه+", re.UNICODE)
_HAHA_EN = re.compile(r"\b(?:haha|hahaha|lol|lool|looool)\b", re.IGNORECASE)
_ELLIPSIS = re.compile(r"\.{4,}")
_REPEATED_DOTS = re.compile(r"[.,،]{4,}")


class TwitterNormalizer(TextProcessor):
    """Normalize Twitter/X posts for NLP tasks.

    Removes RT prefixes, expands hashtags, strips mentions, and handles
    Twitter-specific conventions.
    """

    name = "normalize_twitter"

    def __init__(
        self,
        remove_rt: bool = True,
        expand_hashtags: bool = True,
        remove_mentions: bool = True,
        remove_via: bool = True,
        remove_thread_markers: bool = True,
    ) -> None:
        self.remove_rt = remove_rt
        self.expand_hashtags = expand_hashtags
        self.remove_mentions = remove_mentions
        self.remove_via = remove_via
        self.remove_thread_markers = remove_thread_markers

    def transform(self, text: str) -> str:
        """Apply Twitter-specific normalization."""
        if self.remove_rt:
            text = _RT_PREFIX.sub("", text)
        if self.remove_via:
            text = _VIA_PATTERN.sub("", text)
        if self.remove_thread_markers:
            text = _TWITTER_THREAD_INDICATOR.sub("", text)
        if self.expand_hashtags:
            text = _TWITTER_HASHTAG.sub(r"\1", text)
        if self.remove_mentions:
            text = _TWITTER_MENTION.sub(" ", text)
        return _MULTI_WHITESPACE.sub(" ", text).strip()


class WhatsAppNormalizer(TextProcessor):
    """Normalize WhatsApp messages for NLP tasks.

    Expands common Arabic chat abbreviations and handles WhatsApp formatting.
    """

    name = "normalize_whatsapp"

    def __init__(
        self,
        expand_abbreviations: bool = True,
        remove_media_markers: bool = True,
        remove_formatting: bool = True,
    ) -> None:
        self.expand_abbreviations = expand_abbreviations
        self.remove_media_markers = remove_media_markers
        self.remove_formatting = remove_formatting

    def transform(self, text: str) -> str:
        """Apply WhatsApp-specific normalization."""
        if self.remove_media_markers:
            text = _AUDIO_NOTE.sub(" ", text)
            text = _IMAGE_NOTE.sub(" ", text)
            text = _VIDEO_NOTE.sub(" ", text)
            text = _STICKER_NOTE.sub(" ", text)
        if self.remove_formatting:
            text = _BOLD_FORMAT.sub(r"\1", text)
            text = _ITALIC_FORMAT.sub(r"\1", text)
            text = _STRIKETHROUGH.sub(r"\1", text)
        if self.expand_abbreviations:
            text = self._expand_abbreviations(text)
        return _MULTI_WHITESPACE.sub(" ", text).strip()

    def _expand_abbreviations(self, text: str) -> str:
        """Replace known whole-word chat abbreviations with expanded forms."""
        abbreviations = _load_chat_abbreviations()
        # Sort by length descending to match longer forms first.
        for abbr, expanded in sorted(abbreviations.items(), key=lambda kv: len(kv[0]), reverse=True):
            text = _whole_word_replace(text, abbr, expanded)
        return text


class ChatNormalizer(TextProcessor):
    """Normalize informal Arabic chat text.

    Handles common spelling shortcuts, elongation, and informal conventions
    shared across various Arabic chat platforms.
    """

    name = "normalize_chat"

    def __init__(
        self,
        normalize_laughter: bool = True,
        expand_abbreviations: bool = True,
        fix_common_errors: bool = True,
    ) -> None:
        self.normalize_laughter = normalize_laughter
        self.expand_abbreviations = expand_abbreviations
        self.fix_common_errors = fix_common_errors

    def transform(self, text: str) -> str:
        """Apply chat-specific normalization."""
        if self.normalize_laughter:
            text = _LAUGHTER_AR.sub("هه", text)
            text = _HAHA_EN.sub("", text)
        if self.fix_common_errors:
            text = self._fix_common_errors(text)
        if self.expand_abbreviations:
            text = self._expand_abbreviations(text)
        text = _ELLIPSIS.sub("...", text)
        text = _REPEATED_DOTS.sub(".", text)
        return _MULTI_WHITESPACE.sub(" ", text).strip()

    def _fix_common_errors(self, text: str) -> str:
        """Fix frequently occurring informal spelling errors."""
        corrections: Dict[str, str] = {
            "اللة": "الله",
        }
        for wrong, right in corrections.items():
            text = _whole_word_replace(text, wrong, right)
        return text

    def _expand_abbreviations(self, text: str) -> str:
        """Replace known whole-word chat abbreviations with expanded forms."""
        abbreviations = _load_chat_abbreviations()
        for abbr, expanded in sorted(abbreviations.items(), key=lambda kv: len(kv[0]), reverse=True):
            text = _whole_word_replace(text, abbr, expanded)
        return text
