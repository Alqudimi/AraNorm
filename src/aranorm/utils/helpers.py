"""Small, dependency-free helpers."""

from functools import lru_cache
from typing import Iterable

from aranorm.utils.constants import ARABIC_LETTERS


@lru_cache(maxsize=4096)
def contains_arabic(text: str) -> bool:
    """Return whether text contains at least one Arabic letter."""
    return any(char in ARABIC_LETTERS for char in text)


def is_arabic_char(char: str) -> bool:
    """Return whether a character belongs to the Arabic letter set."""
    return char in ARABIC_LETTERS


def join_nonempty(parts: Iterable[str], separator: str = " ") -> str:
    """Join non-empty string parts while avoiding duplicate separators."""
    return separator.join(part.strip() for part in parts if part and part.strip())
