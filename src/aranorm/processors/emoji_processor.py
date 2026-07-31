"""Emoji removal without requiring an external package."""

from aranorm.processors._base import TextProcessor


class EmojiProcessor(TextProcessor):
    """Remove common Unicode emoji ranges."""

    name = "remove_emojis"

    def transform(self, text: str) -> str:
        """Remove emoji and pictographic code points."""
        return "".join(char for char in text if not self._is_emoji(char))

    @staticmethod
    def _is_emoji(char: str) -> bool:
        """Return whether a character lies in common emoji ranges."""
        codepoint = ord(char)
        return (
            0x1F000 <= codepoint <= 0x1FAFF
            or 0x2600 <= codepoint <= 0x27BF
            or 0xFE0F == codepoint
        )
