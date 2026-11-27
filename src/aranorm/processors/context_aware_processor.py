"""Context-aware stop-words processor.

Handles ambiguous Arabic particles (لا، إن …) by inspecting the surrounding
token context before deciding whether to remove or keep them.
"""

from __future__ import annotations

from typing import Optional, Set

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.stop_words_registry import StopWordsRegistry

# ── Negation patterns ─────────────────────────────────────────────────────────
# "لا" followed by a verb-like word → true negation → keep
_NEGATION_PARTICLES: Set[str] = {"لا", "لم", "لن", "لست", "ليس", "ليست", "لسنا", "لستم"}

# Idiomatic phrases where "لا" is NOT a negation and should be removed
_IDIOMATIC_LA: Set[str] = {
    "لا شك",
    "لا بد",
    "لا ريب",
    "لا سيما",
    "لا محالة",
    "لا سبيل",
    "لا غرو",
    "لا جرم",
}

# ── Emphasis / conditional particles ─────────────────────────────────────────
_EMPHASIS_PARTICLES: Set[str] = {"إن", "أن", "إنه", "إنها", "إنهم", "إنهن", "إننا"}

# Words that typically follow emphasis "إن" (NOT a conditional if-clause)
# We keep إن when followed by a noun/pronoun (emphatic use)
_CONDITIONAL_INDICATORS: Set[str] = {
    "تحسنوا",
    "تفعل",
    "تأتِ",
    "تجتهد",
    "تنجح",
    "شاء",
    "أراد",
    "أردت",
    "كنت",
    "جاء",
}


class ContextAwareProcessor(Processor):
    """Remove stop words intelligently based on surrounding context.

    Parameters
    ----------
    preserve_negation:
        Keep negation particles (لا، لم، لن …) that clearly negate a verb.
    preserve_emphasis:
        Keep emphatic إن/أن when followed by a noun/pronoun.
    registry:
        Optional :class:`~aranorm.core.stop_words_registry.StopWordsRegistry`.
    """

    name = "context_aware_stop_words"

    def __init__(
        self,
        preserve_negation: bool = True,
        preserve_emphasis: bool = False,
        registry: Optional[StopWordsRegistry] = None,
    ) -> None:
        self.preserve_negation = preserve_negation
        self.preserve_emphasis = preserve_emphasis
        self.registry = registry or StopWordsRegistry()
        self._stop_set = self.registry.get_words("universal")

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Return *text* with context-sensitive stop-word removal applied."""
        if not text or not text.strip():
            return text

        tokens = text.split()
        result = []

        i = 0
        while i < len(tokens):
            token = tokens[i]
            raw = token.strip(".,،؟!؛:")

            # ── "لا" context check ──────────────────────────────────────
            if raw in _NEGATION_PARTICLES and self.preserve_negation:
                # Check for idiomatic phrase (bigram)
                bigram = raw + " " + (tokens[i + 1].strip(".,،؟!؛:") if i + 1 < len(tokens) else "")
                if bigram in _IDIOMATIC_LA:
                    # idiomatic → remove "لا" (not a real negation)
                    i += 1
                    continue
                else:
                    # true negation → keep
                    result.append(token)
                    i += 1
                    continue

            # ── إن/أن emphasis check ────────────────────────────────────
            if raw in _EMPHASIS_PARTICLES and self.preserve_emphasis:
                next_tok = tokens[i + 1].strip(".,،؟!؛:") if i + 1 < len(tokens) else ""
                if next_tok in _CONDITIONAL_INDICATORS:
                    # conditional إن → remove
                    i += 1
                    continue
                else:
                    # emphatic إن → keep
                    result.append(token)
                    i += 1
                    continue

            # ── Standard stop-word check ────────────────────────────────
            if raw in self._stop_set:
                i += 1
                continue  # drop

            result.append(token)
            i += 1

        text_out = " ".join(result)
        self._record(context)
        return text_out
