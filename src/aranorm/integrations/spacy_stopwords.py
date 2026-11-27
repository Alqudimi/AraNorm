"""spaCy compatibility adapter for AraNorm stop words."""

from __future__ import annotations

from typing import Any, Optional, Set

from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.exceptions import IntegrationUnavailableError


class SpacyStopWordsAdapter:
    """Expose AraNorm stop words to spaCy.

    Parameters
    ----------
    registry:
        A :class:`~aranorm.core.stop_words_registry.StopWordsRegistry` instance.

    Example
    -------
    >>> from aranorm.integrations import SpacyStopWordsAdapter
    >>> adapter = SpacyStopWordsAdapter()
    >>> nlp = adapter.enrich_spacy(nlp)
    """

    def __init__(self, registry: Optional[StopWordsRegistry] = None) -> None:
        self.registry = registry or StopWordsRegistry()

    def to_spacy_set(self, scope: str = "universal") -> Set[str]:
        """Return stop words as a set compatible with spaCy."""
        return self.registry.get_words(scope)

    def enrich_spacy(self, nlp: Any, scope: str = "universal") -> Any:
        """Add AraNorm stop words to a spaCy *nlp* model's default stop words.

        Parameters
        ----------
        nlp:
            A loaded spaCy ``Language`` object (e.g. from ``spacy.load``).
        scope:
            Which scope to use (default: ``"universal"``).

        Returns
        -------
        The same *nlp* object, mutated in place.

        Raises
        ------
        IntegrationUnavailableError
            If spaCy is not installed.
        """
        try:
            import spacy  # noqa: F401
        except ImportError as exc:
            raise IntegrationUnavailableError("spaCy is not installed. Run: pip install spacy") from exc

        words = self.to_spacy_set(scope)
        try:
            lang = nlp.Defaults
            lang.stop_words |= words
            for word in words:
                if hasattr(nlp, "vocab") and word in nlp.vocab:
                    nlp.vocab[word].is_stop = True
        except AttributeError as exc:
            raise IntegrationUnavailableError("Provided object does not appear to be a spaCy Language model.") from exc

        return nlp
