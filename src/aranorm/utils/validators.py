"""Input validation helpers."""

from aranorm.exceptions import InvalidTextError


def validate_text(text: str) -> str:
    """Validate and return text suitable for processing.

    Args:
        text: Candidate input value.

    Raises:
        InvalidTextError: If text is not a string.
    """
    if not isinstance(text, str):
        raise InvalidTextError(f"text must be str, got {type(text).__name__}")
    return text
