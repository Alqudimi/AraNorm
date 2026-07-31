"""Arabic presentation-form ligature normalization."""

from aranorm.processors._base import TextProcessor


class LigaturesProcessor(TextProcessor):
    """Expand common lam-alef ligatures."""

    name = "normalize_ligatures"
    _mapping = str.maketrans(
        {
            "ﻻ": "لا",
            "ﻷ": "لأ",
            "ﻹ": "لإ",
            "ﻵ": "لآ",
        }
    )

    def transform(self, text: str) -> str:
        """Expand common Arabic ligatures."""
        return text.translate(self._mapping)
