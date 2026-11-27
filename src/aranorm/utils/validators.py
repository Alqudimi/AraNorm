"""Input validation helpers."""

from typing import Optional

from aranorm.exceptions import InvalidTextError


def validate_text(
    text: str,
    *,
    max_length: Optional[int] = None,
    reject_null_bytes: bool = False,
) -> str:
    """Validate and return text suitable for processing.

    Args:
        text: Candidate input value.
        max_length: Optional inclusive Unicode code-point limit.
        reject_null_bytes: Reject embedded ``\\x00`` characters when enabled.

    Raises:
        InvalidTextError: If text is not a string or violates a supplied limit.
    """
    if not isinstance(text, str):
        raise InvalidTextError(f"text must be str, got {type(text).__name__}")
    if max_length is not None and len(text) > max_length:
        raise InvalidTextError(f"text length {len(text)} exceeds maximum allowed length {max_length}")
    if reject_null_bytes and "\x00" in text:
        raise InvalidTextError("text contains a null byte")
    return text
