"""Domain-specific stop-words processor.

Certain Arabic NLP domains (legal, medical, news, religious) have high-frequency
functional vocabulary that is domain-specific noise rather than content.
This processor loads domain word lists and strips them from the text.
"""

from __future__ import annotations

import os
from typing import FrozenSet, Optional, Set

from aranorm.core.base import Processor, ProcessorContext
from aranorm.core.stop_words_registry import StopWordsRegistry

_DOMAIN_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "stopwords", "domains")

_SUPPORTED_DOMAINS: FrozenSet[str] = frozenset({"legal", "medical", "news", "religious"})


def _load_domain(domain: str) -> Set[str]:
    path = os.path.join(_DOMAIN_DIR, f"{domain}.txt")
    if not os.path.isfile(path):
        return set()
    with open(path, encoding="utf-8") as fh:
        return {line.strip() for line in fh if line.strip() and not line.startswith("#")}


class DomainStopProcessor(Processor):
    """Remove domain-specific stop words on top of a base universal list.

    Parameters
    ----------
    domains:
        One or more domain names: ``"legal"``, ``"medical"``,
        ``"news"``, ``"religious"``.
    include_universal:
        Also remove universal (MSA + dialect) stop words (default *True*).
    registry:
        Optional shared :class:`~aranorm.core.stop_words_registry.StopWordsRegistry`.

    Example
    -------
    >>> proc = DomainStopProcessor(domains=["legal"], include_universal=False)
    >>> proc.process("وفقاً للمادة الثانية يُعد ذلك باطلاً")
    'للمادة الثانية يُعد ذلك'
    """

    name = "domain_stop_processor"

    def __init__(
        self,
        domains: list,
        include_universal: bool = True,
        registry: Optional[StopWordsRegistry] = None,
    ) -> None:
        self.domains = [d.lower() for d in domains]
        unknown = set(self.domains) - _SUPPORTED_DOMAINS
        if unknown:
            import warnings

            warnings.warn(
                f"Unknown domain(s) {unknown!r}; supported: {sorted(_SUPPORTED_DOMAINS)}",
                stacklevel=2,
            )
        self.registry = registry or StopWordsRegistry()
        self._stop_set: Set[str] = set()

        if include_universal:
            self._stop_set |= self.registry.get_words("universal")

        for domain in self.domains:
            self._stop_set |= _load_domain(domain)

    @classmethod
    def get_supported_domains(cls) -> FrozenSet[str]:
        """Return the set of built-in domain names."""
        return _SUPPORTED_DOMAINS

    @classmethod
    def get_domain_words(cls, domain: str) -> Set[str]:
        """Return stop words for a specific domain without creating a processor."""
        return _load_domain(domain.lower())

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Remove domain-specific and (optionally) universal stop words."""
        if not text or not text.strip():
            return text
        tokens = text.split()
        kept = [t for t in tokens if t.strip(".,،؟!؛:") not in self._stop_set]
        self._record(context)
        return " ".join(kept)
