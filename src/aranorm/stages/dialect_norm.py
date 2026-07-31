"""Dialect target normalization strategies.

Provides rule-based CODA and MSA normalization (no ML dependency) plus an
optional Transformers-backed Seq2Seq strategy for production-level accuracy.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from aranorm.core.base import ProcessorContext
from aranorm.exceptions import IntegrationUnavailableError, NormalizationError

LOGGER = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Arabic + Latin word-boundary: match only when source is surrounded by
# whitespace, punctuation, or string edges — works for Arabic and Latin.
_NON_SPACE = re.compile(r"\S")


@lru_cache(maxsize=1)
def _load_dialect_mappings() -> Dict[str, Dict[str, str]]:
    """Load dialect ↔ MSA mappings from the bundled data file (cached)."""
    path = _DATA_DIR / "dialect_mappings.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _whole_word_replace(text: str, source: str, target: str) -> str:
    """Replace *source* with *target* only when it stands as a whole word.

    Works for Arabic and Latin by treating any non-whitespace run as a word.
    Uses ``(?<!\\S)`` / ``(?!\\S)`` assertions so that the replacement fires
    only when *source* is surrounded by whitespace or string edges.
    """
    pattern = r"(?<!\S)" + re.escape(source) + r"(?!\S)"
    return re.sub(pattern, target, text)


# ────────────────────────────────────────────────────────────────────────────
# Strategy interface
# ────────────────────────────────────────────────────────────────────────────

class DialectStrategy(ABC):
    """Strategy interface for target dialect normalization."""

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Normalize text to the strategy's target."""


# ────────────────────────────────────────────────────────────────────────────
# Rule-based CODA strategy
# ────────────────────────────────────────────────────────────────────────────

class RuleBasedCODAStrategy(DialectStrategy):
    """Conservative CODA approximation without external dependencies.

    Applies unambiguous orthographic fixes — restoring dropped hamzas,
    correcting common colloquial spelling forms, and normalizing a small set
    of high-frequency words.
    """

    # Ordered list of (source, target) whole-word replacements.
    _REPLACEMENTS: List[Tuple[str, str]] = [
        # Erroneous hamza / alef spellings
        ("هاذا",     "هذا"),
        ("هاذه",     "هذه"),
        ("هاذي",     "هذه"),
        ("هاذان",    "هذان"),
        ("هاذين",    "هذين"),
        # Common colloquial contractions → standard Arabic
        ("انشاءالله", "إن شاء الله"),
        ("انشالله",   "إن شاء الله"),
        ("إنشالله",   "إن شاء الله"),
        ("ماشاءالله", "ما شاء الله"),
        ("ماشاء الله", "ما شاء الله"),
        # Dropped initial hamzas on common words
        ("الاشياء",  "الأشياء"),
        ("الاسرة",   "الأسرة"),
        ("الامر",    "الأمر"),
        ("الاطفال",  "الأطفال"),
        ("الاخ",     "الأخ"),
        ("الاخت",    "الأخت"),
        ("الاب",     "الأب"),
        ("الام",     "الأم"),
        # Dropped initial hamzas on standalone words
        ("اكل",  "أكل"),
        ("امل",  "أمل"),
        ("اكثر", "أكثر"),
        ("اقل",  "أقل"),
        ("اهم",  "أهم"),
    ]

    def normalize(self, text: str) -> str:
        """Apply safe, deterministic CODA corrections."""
        for source, target in self._REPLACEMENTS:
            # Use whole-word replacement to avoid partial matches.
            text = _whole_word_replace(text, source, target)
        return text


# ────────────────────────────────────────────────────────────────────────────
# Rule-based MSA strategy
# ────────────────────────────────────────────────────────────────────────────

class RuleBasedMSAStrategy(DialectStrategy):
    """Conservative MSA normalization using the bundled dialect mappings.

    Covers the most frequent colloquial words across EGY, GLF, LEV, IRQ, NOR,
    and TUN dialects and maps them to their MSA equivalents.

    Replacement is *whole-word* to prevent partial matches inside longer words.
    Longer sources are applied before shorter ones to avoid prefix shadowing.
    """

    def normalize(self, text: str) -> str:
        """Replace dialectal words with MSA equivalents."""
        all_maps = _load_dialect_mappings()
        # Merge all dialect tables into a flat dict, then sort by descending
        # source length so longer patterns are applied first.
        merged: Dict[str, str] = {}
        for dialect_map in all_maps.values():
            merged.update(dialect_map)
        # Sort longest-first to avoid shorter patterns masking longer ones.
        sorted_pairs = sorted(merged.items(), key=lambda kv: len(kv[0]), reverse=True)
        for source, target in sorted_pairs:
            if source in text:
                text = _whole_word_replace(text, source, target)
        return text


# ────────────────────────────────────────────────────────────────────────────
# Transformer-backed strategy (optional)
# ────────────────────────────────────────────────────────────────────────────

class ModelDialectStrategy(DialectStrategy):
    """Lazy Transformers Seq2Seq strategy for CODA/MSA neural normalization.

    Args:
        model_name: HuggingFace model identifier.
        device: Optional ``torch.device`` string (``"cpu"``, ``"cuda:0"``).
        max_new_tokens: Upper bound on generated token count.
    """

    def __init__(
        self,
        model_name: str,
        device: Optional[str] = None,
        max_new_tokens: int = 128,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.max_new_tokens = max_new_tokens
        self._tokenizer = None
        self._model = None

    def normalize(self, text: str) -> str:
        """Run the Transformers model, loading it lazily on first call."""
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as error:
            raise IntegrationUnavailableError(
                "Transformers is required for model-backed normalization; "
                "install with: pip install aranorm[ml]"
            ) from error
        try:
            if self._tokenizer is None:
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            if self._model is None:
                self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
                if self.device:
                    self._model.to(self.device)
            encoded = self._tokenizer(text, return_tensors="pt")
            generated = self._model.generate(
                **encoded,
                max_new_tokens=self.max_new_tokens,
            )
            return self._tokenizer.decode(generated[0], skip_special_tokens=True)
        except Exception as error:
            LOGGER.exception("Dialect model normalization failed: %s", self.model_name)
            raise NormalizationError(
                f"model normalization failed for '{self.model_name}'"
            ) from error


# ────────────────────────────────────────────────────────────────────────────
# Normalizer (strategy router)
# ────────────────────────────────────────────────────────────────────────────

class DialectNormalizer:
    """Select and apply a CODA or MSA normalization strategy.

    Args:
        target: ``"coda"`` or ``"msa"``.
        coda_strategy: Custom strategy for CODA output (default: rule-based).
        msa_strategy:  Custom strategy for MSA output (default: rule-based).

    Example::

        normalizer = DialectNormalizer("msa")
        msa_text = normalizer.process("شلونك وايد زين")
    """

    _VALID_TARGETS = frozenset({"coda", "msa"})

    def __init__(
        self,
        target: str,
        coda_strategy: Optional[DialectStrategy] = None,
        msa_strategy: Optional[DialectStrategy] = None,
    ) -> None:
        self.target = target.lower()
        if self.target not in self._VALID_TARGETS:
            raise ValueError(
                f"unsupported dialect target '{self.target}'; "
                f"choose from {sorted(self._VALID_TARGETS)}"
            )
        self._strategies = {
            "coda": coda_strategy or RuleBasedCODAStrategy(),
            "msa": msa_strategy or RuleBasedMSAStrategy(),
        }

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Normalize text to the configured target and record the step.

        Args:
            text: Text to normalize.
            context: Optional pipeline context for step tracking.

        Returns:
            Normalized text string.
        """
        result = self._strategies[self.target].normalize(text)
        if context is not None:
            context.record(f"normalize_to_{self.target}")
        return result
