"""Arabic and international currency normalization.

Replaces currency symbols and common Arabic currency words with their
canonical ISO-4217 code or removes them entirely, depending on the mode.
"""

from __future__ import annotations

import re
from typing import Optional

from aranorm.core.base import ProcessorContext
from aranorm.processors._base import TextProcessor

# ── Symbol → ISO code map ─────────────────────────────────────────────────────
_SYMBOL_MAP = {
    # Latin symbols
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₺": "TRY",
    "₹": "INR",
    "₩": "KRW",
    "₪": "ILS",
    "﷼": "SAR",
}

# Arabic currency words → ISO code
_ARABIC_CURRENCY_MAP = {
    "ريال": "SAR",
    "ريالات": "SAR",
    "ريال سعودي": "SAR",
    "ريال قطري": "QAR",
    "ريال إماراتي": "AED",
    "درهم": "AED",
    "دراهم": "AED",
    "دينار": "KWD",
    "دنانير": "KWD",
    "دينار كويتي": "KWD",
    "دينار أردني": "JOD",
    "دينار عراقي": "IQD",
    "دينار بحريني": "BHD",
    "دينار تونسي": "TND",
    "دينار ليبي": "LYD",
    "دينار جزائري": "DZD",
    "جنيه": "EGP",
    "جنيهات": "EGP",
    "جنيه مصري": "EGP",
    "جنيه سوداني": "SDG",
    "جنيه سوري": "SYP",
    "جنيه لبناني": "LBP",
    "ليرة": "SYP",
    "ليرات": "SYP",
    "ليرة سورية": "SYP",
    "ليرة تركية": "TRY",
    "ليرة لبنانية": "LBP",
    "شلن": "SOS",
    "شلنات": "SOS",
    "شلن صومالي": "SOS",
    "يورو": "EUR",
    "دولار": "USD",
    "دولارات": "USD",
    "دولار أمريكي": "USD",
    "إسترليني": "GBP",
    "جنيه إسترليني": "GBP",
    "فلس": "",  # sub-unit only
    "هللة": "",  # sub-unit only
    "قرش": "",
}

# Number + currency pattern: "100 ريال" or "ريال 100"
_NUMBER_BEFORE = re.compile(r"\b(\d[\d,\.]*)\s*(" + "|".join(re.escape(k) for k in sorted(_ARABIC_CURRENCY_MAP, key=len, reverse=True)) + r")\b")
_NUMBER_AFTER = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(_ARABIC_CURRENCY_MAP, key=len, reverse=True)) + r")\s*(\d[\d,\.]*)\b")

# Symbol patterns
_SYMBOL_PATTERN = re.compile(
    "(" + "|".join(re.escape(s) for s in _SYMBOL_MAP) + r")(\d[\d,\.]*|\s*\d[\d,\.]*)"
)


class CurrencyProcessor(TextProcessor):
    """Normalize or remove currency symbols and words.

    Parameters
    ----------
    mode:
        ``"normalize"`` – replace with ``{ISO_CODE}`` placeholder (default).
        ``"remove"``    – delete currency references entirely.
        ``"keep"``      – leave text unchanged (no-op, for pipeline symmetry).

    Example
    -------
    >>> proc = CurrencyProcessor(mode="normalize")
    >>> proc.process("اشتريت بـ 50 ريال")
    'اشتريت بـ 50 SAR'
    >>> CurrencyProcessor(mode="remove").process("السعر 200 دولار فقط")
    'السعر فقط'
    """

    name = "normalize_currency"

    def __init__(self, mode: str = "normalize") -> None:
        valid = {"normalize", "remove", "keep"}
        if mode not in valid:
            raise ValueError(f"mode must be one of {sorted(valid)}, got {mode!r}")
        self.mode = mode

    def transform(self, text: str) -> str:
        """Apply currency normalization."""
        if self.mode == "keep":
            return text

        # Replace Latin symbols first
        for symbol, iso in _SYMBOL_MAP.items():
            if symbol in text:
                if self.mode == "normalize":
                    text = text.replace(symbol, iso)
                else:
                    text = text.replace(symbol, " ")

        # Replace multi-word Arabic currencies (longest match first)
        for arabic_word, iso in sorted(_ARABIC_CURRENCY_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if arabic_word in text:
                replacement = iso if (self.mode == "normalize" and iso) else " "
                text = text.replace(arabic_word, replacement)

        # Collapse extra spaces
        return re.sub(r" {2,}", " ", text).strip()
