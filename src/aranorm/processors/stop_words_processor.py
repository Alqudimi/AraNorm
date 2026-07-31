"""Main stop-words processor: remove, extract, highlight, or count."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.core.stop_words_registry import StopWordsRegistry


@dataclass
class StopWordsResult:
    """Detailed stop-words processing result."""

    original_text: str
    processed_text: str            # text after mode applied
    stop_words_removed: str        # convenience: text with stop words removed
    stop_words_found: Set[str]
    stop_words_stats: Dict[str, Any]
    stop_words_by_category: Dict[str, List[str]]
    stop_words_by_dialect: Dict[str, List[str]]
    applied_stop_words_steps: List[str]


_REGISTRY_SINGLETON: Optional[StopWordsRegistry] = None


def _get_registry() -> StopWordsRegistry:
    global _REGISTRY_SINGLETON
    if _REGISTRY_SINGLETON is None:
        _REGISTRY_SINGLETON = StopWordsRegistry()
    return _REGISTRY_SINGLETON


class StopWordsProcessor(Processor):
    """Remove / extract / highlight / count Arabic stop words.

    Inherits from the project's :class:`~aranorm.core.base.Processor` ABC.

    Parameters
    ----------
    config:
        :class:`~aranorm.core.stop_words_config.StopWordsConfig` instance
        that controls behaviour.  Defaults to ``StopWordsConfig()`` (remove,
        universal scope).
    registry:
        Optional pre-built :class:`~aranorm.core.stop_words_registry.StopWordsRegistry`.
        A process-level singleton is used when omitted.
    """

    name = "stop_words_processor"

    def __init__(
        self,
        config: Optional[StopWordsConfig] = None,
        registry: Optional[StopWordsRegistry] = None,
    ) -> None:
        self.config = config or StopWordsConfig()
        self.registry = registry or _get_registry()
        self._active_set = self._build_active_set()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build_active_set(self) -> Set[str]:
        cfg = self.config
        scope = cfg.scope

        if scope == "custom":
            base: Set[str] = set(cfg.custom_stop_words or frozenset())
        elif scope == "msa_only":
            base = self.registry.get_words("msa")
        elif scope == "dialect_aware":
            base = self.registry.get_words("dialect", cfg.dialects)
        else:  # universal
            base = self.registry.get_words("universal")

        # Optional extras
        if cfg.remove_filler:
            base |= self.registry.get_words("filler")
        if cfg.remove_arabizi:
            base |= self.registry.get_words("arabizi")
        if cfg.remove_internet:
            base |= self.registry.get_words("internet")
        if cfg.remove_numbers:
            base |= self.registry.get_words("numbers")

        # Custom additions
        if cfg.custom_stop_words:
            base |= set(cfg.custom_stop_words)

        # Exclusions
        if cfg.excluded_stop_words:
            base -= set(cfg.excluded_stop_words)

        # Preserve special categories
        if cfg.preserve_negation:
            negation = self.registry.get_by_category("negation")
            base -= negation
        if cfg.preserve_prepositions:
            preps = self.registry.get_by_category("prepositions")
            base -= preps

        return base

    # ── Core ─────────────────────────────────────────────────────────────

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Apply stop-words transformation and return the processed text."""
        if not text or not text.strip():
            return text
        result = self.process_detailed(text)
        self._record(context)
        return result.processed_text

    def process_detailed(self, text: str) -> StopWordsResult:
        """Full processing returning a :class:`StopWordsResult` with rich metadata."""
        tokens = text.split()
        mode = self.config.mode

        found: Set[str] = set()
        by_category: Dict[str, List[str]] = {}
        by_dialect: Dict[str, List[str]] = {}
        steps: List[str] = []

        # Categorization helpers (loaded lazily once per call)
        _categories = None

        def _categorise(word: str) -> None:
            nonlocal _categories
            if _categories is None:
                _categories = {}
                for cat in [
                    "prepositions", "pronouns", "conjunctions", "interrogatives",
                    "demonstratives", "relative_pronouns", "negation", "emphasis",
                    "particles", "adverbs", "filler", "social_media", "internet",
                    "arabizi", "numbers",
                ]:
                    for w in self.registry.get_by_category(cat):
                        _categories[w] = cat
            cat = _categories.get(word, "other")
            by_category.setdefault(cat, []).append(word)

        kept_tokens = []
        for token in tokens:
            # Check context-sensitive overrides for emphasis particles
            clean_token = token.strip(".,،؟!؛:")
            if clean_token in self._active_set:
                found.add(clean_token)
                _categorise(clean_token)
                if mode == "highlight":
                    kept_tokens.append(f"[[{token}]]")
                elif mode in ("remove", "extract"):
                    pass  # drop from output
                else:  # count
                    kept_tokens.append(token)
            else:
                if mode == "extract":
                    pass  # only keep stop words
                else:
                    kept_tokens.append(token)

        if mode == "extract":
            processed = " ".join(sorted(found))
        else:
            processed = " ".join(kept_tokens)

        # Dialect attribution
        for code in self.config.dialects:
            dialect_words = self.registry.get_words("dialect", frozenset([code]))
            hits = list(found & dialect_words)
            if hits:
                by_dialect[code] = hits
                steps.append(f"dialect:{code}")

        steps.append(f"scope:{self.config.scope}")
        steps.append(f"mode:{self.config.mode}")

        total_tokens = len(tokens)
        pct = (len(found) / total_tokens * 100) if total_tokens else 0.0

        stats: Dict[str, Any] = {
            "count": len(found),
            "total_tokens": total_tokens,
            "percentage": round(pct, 2),
            "by_category": {k: len(v) for k, v in by_category.items()},
        }

        removed_text = " ".join(
            t for t in tokens if t.strip(".,،؟!؛:") not in self._active_set
        )

        return StopWordsResult(
            original_text=text,
            processed_text=processed,
            stop_words_removed=removed_text,
            stop_words_found=found,
            stop_words_stats=stats,
            stop_words_by_category=by_category,
            stop_words_by_dialect=by_dialect,
            applied_stop_words_steps=steps,
        )
