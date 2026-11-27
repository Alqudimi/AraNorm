"""Arabic date and time normalization.

Normalizes Arabic date formats, Hijri month names, and common temporal
expressions to a standardized form or removes them.
"""

from __future__ import annotations

import re

from aranorm.processors._base import TextProcessor

# ── Hijri month names ──────────────────────────────────────────────────────────
_HIJRI_MONTHS = {
    "محرم": "01",
    "صفر": "02",
    "ربيع الأول": "03",
    "ربيع الثاني": "04",
    "جمادى الأولى": "05",
    "جمادى الآخرة": "06",
    "جمادى الأخرة": "06",
    "رجب": "07",
    "شعبان": "08",
    "رمضان": "09",
    "شوال": "10",
    "ذو القعدة": "11",
    "ذو الحجة": "12",
}

# Gregorian month names in Arabic
_GREGORIAN_MONTHS = {
    "يناير": "01",
    "كانون الثاني": "01",
    "فبراير": "02",
    "شباط": "02",
    "مارس": "03",
    "آذار": "03",
    "أبريل": "04",
    "نيسان": "04",
    "مايو": "05",
    "أيار": "05",
    "يونيو": "06",
    "حزيران": "06",
    "يوليو": "07",
    "تموز": "07",
    "أغسطس": "08",
    "آب": "08",
    "سبتمبر": "09",
    "أيلول": "09",
    "أكتوبر": "10",
    "تشرين الأول": "10",
    "نوفمبر": "11",
    "تشرين الثاني": "11",
    "ديسمبر": "12",
    "كانون الأول": "12",
}

# Temporal expressions to normalize
_TEMPORAL_MAP = {
    "اليوم": "TODAY",
    "الأمس": "YESTERDAY",
    "أمس": "YESTERDAY",
    "غداً": "TOMORROW",
    "غدا": "TOMORROW",
    "الآن": "NOW",
    "الان": "NOW",
    "صباحاً": "AM",
    "صباحا": "AM",
    "مساءً": "PM",
    "مساءا": "PM",
    "ليلاً": "NIGHT",
    "ليلا": "NIGHT",
    "الصباح": "MORNING",
    "المساء": "EVENING",
    "الليل": "NIGHT",
    "الفجر": "DAWN",
    "الظهر": "NOON",
    "العصر": "AFTERNOON",
    "المغرب": "SUNSET",
    "العشاء": "NIGHT",
}

# Numeric date patterns: DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b")

# Time pattern: HH:MM or HH:MM:SS
_TIME_PATTERN = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")

# Remove patterns (standalone year mentions like "عام 2024")
_YEAR_MENTION = re.compile(r"\b(?:عام|سنة|في)\s+(\d{4})\b")


class DateTimeProcessor(TextProcessor):
    """Normalize or remove Arabic date and time expressions.

    Parameters
    ----------
    mode:
        ``"normalize"`` – replace with standardized tokens (default).
        ``"remove"``    – delete date/time expressions entirely.

    Example
    -------
    >>> proc = DateTimeProcessor(mode="normalize")
    >>> proc.process("ولد في يناير عام 1990")
    'ولد في MONTH_01 YEAR_1990'
    """

    name = "normalize_datetime"

    def __init__(self, mode: str = "normalize") -> None:
        valid = {"normalize", "remove"}
        if mode not in valid:
            raise ValueError(f"mode must be one of {sorted(valid)}, got {mode!r}")
        self.mode = mode

    def transform(self, text: str) -> str:
        """Normalize date/time references in *text*."""
        if self.mode == "remove":
            return self._remove_all(text)
        return self._normalize_all(text)

    def _normalize_all(self, text: str) -> str:
        """Replace dates and times with normalized tokens."""
        # Numeric dates
        text = _NUMERIC_DATE.sub(r"DATE_\3-\2-\1", text)
        # Time patterns
        text = _TIME_PATTERN.sub(r"TIME_\1:\2", text)
        # Year mentions
        text = _YEAR_MENTION.sub(r"YEAR_\1", text)
        # Multi-word month names first (longest)
        for name, num in sorted(
            {**_HIJRI_MONTHS, **_GREGORIAN_MONTHS}.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        ):
            text = text.replace(name, f"MONTH_{num}")
        # Temporal expressions
        for expr, token in sorted(_TEMPORAL_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            text = re.sub(r"(?<!\S)" + re.escape(expr) + r"(?!\S)", token, text)
        return re.sub(r" {2,}", " ", text).strip()

    def _remove_all(self, text: str) -> str:
        """Remove date/time patterns from *text*."""
        text = _NUMERIC_DATE.sub(" ", text)
        text = _TIME_PATTERN.sub(" ", text)
        text = _YEAR_MENTION.sub(" ", text)
        for name in sorted(
            {**_HIJRI_MONTHS, **_GREGORIAN_MONTHS}.keys(),
            key=len,
            reverse=True,
        ):
            text = text.replace(name, " ")
        for expr in sorted(_TEMPORAL_MAP.keys(), key=len, reverse=True):
            text = re.sub(r"(?<!\S)" + re.escape(expr) + r"(?!\S)", " ", text)
        return re.sub(r" {2,}", " ", text).strip()
