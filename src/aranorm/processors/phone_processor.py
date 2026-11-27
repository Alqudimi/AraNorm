"""Phone number detection and normalization for Arabic text.

Handles Gulf, Levantine, North African, and international phone formats.
"""

from __future__ import annotations

import re

from aranorm.processors._base import TextProcessor

# ── Phone number patterns ──────────────────────────────────────────────────────
# International prefix: +966, 00966, +1, etc.
_INTL_PREFIX = r"(?:\+|00)\d{1,3}"

# Saudi: +966 5X XXX XXXX or 05X XXX XXXX
# Egypt: +20 1X XXXX XXXX
# UAE:   +971 5X XXX XXXX
# Jordan: +962 7X XXXX XXXX
# General Arab mobile: starts with 05/07/09/011/010/012

_PHONE_PATTERN = re.compile(
    r"(?:"
    # International format
    r"(?:\+|00)\d{1,3}[\s\-\.]?\(?\d{1,4}\)?[\s\-\.]?\d{2,4}[\s\-\.]?\d{2,4}[\s\-\.]?\d{0,4}" r"|"
    # Local Gulf/Arab format: 05xxxxxxxx or 5xxxxxxxx
    r"\b0?[5789]\d[\s\-\.]?\d{3}[\s\-\.]?\d{4}\b" r"|"
    # Egypt: 010/011/012/015
    r"\b0[01]\d[\s\-\.]?\d{4}[\s\-\.]?\d{4}\b" r"|"
    # Landlines: 0X XXXX XXXX
    r"\b0\d[\s\-\.]?\d{4}[\s\-\.]?\d{4}\b" r")",
    re.VERBOSE,
)


class PhoneProcessor(TextProcessor):
    """Remove or mask phone numbers from text.

    Parameters
    ----------
    mode:
        ``"remove"``   – delete phone numbers (default).
        ``"mask"``     – replace with the placeholder ``[PHONE]``.
        ``"normalize"``– replace with a canonical ``+XXXXXXXXXX`` form.

    Example
    -------
    >>> proc = PhoneProcessor(mode="mask")
    >>> proc.process("تواصل معي على 0501234567")
    'تواصل معي على [PHONE]'
    """

    name = "remove_phone_numbers"

    def __init__(self, mode: str = "remove") -> None:
        valid = {"remove", "mask", "normalize"}
        if mode not in valid:
            raise ValueError(f"mode must be one of {sorted(valid)}, got {mode!r}")
        self.mode = mode

    def transform(self, text: str) -> str:
        """Apply phone-number transformation."""
        if self.mode == "remove":
            result = _PHONE_PATTERN.sub(" ", text)
        elif self.mode == "mask":
            result = _PHONE_PATTERN.sub("[PHONE]", text)
        else:  # normalize — strip spaces/dashes and keep digits

            def _canonicalize(match: re.Match) -> str:
                digits = re.sub(r"[^\d+]", "", match.group(0))
                return digits

            result = _PHONE_PATTERN.sub(_canonicalize, text)

        return re.sub(r" {2,}", " ", result).strip()
