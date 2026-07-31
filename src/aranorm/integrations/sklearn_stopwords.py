"""scikit-learn compatibility adapter for AraNorm stop words."""

from __future__ import annotations

from typing import FrozenSet, Optional, Set

from aranorm.core.stop_words_registry import StopWordsRegistry


class SklearnStopWordsAdapter:
    """Expose AraNorm stop words to scikit-learn vectorisers.

    Parameters
    ----------
    registry:
        A :class:`~aranorm.core.stop_words_registry.StopWordsRegistry` instance.

    Example
    -------
    >>> from aranorm.integrations import SklearnStopWordsAdapter
    >>> adapter = SklearnStopWordsAdapter()
    >>> stop_words = adapter.to_sklearn_set()
    >>> # TfidfVectorizer(stop_words=stop_words)
    """

    def __init__(self, registry: Optional[StopWordsRegistry] = None) -> None:
        self.registry = registry or StopWordsRegistry()

    def to_sklearn_set(self, scope: str = "universal") -> FrozenSet[str]:
        """Return a *frozenset* of stop words compatible with scikit-learn.

        scikit-learn's ``TfidfVectorizer`` and ``CountVectorizer`` accept a
        collection of strings for their ``stop_words`` parameter.  Using a
        :class:`frozenset` avoids ordering issues and is safe to reuse across
        vectoriser instances.
        """
        return frozenset(self.registry.get_words(scope))

    def to_sklearn_list(self, scope: str = "universal") -> list:
        """Return a sorted list for scikit-learn (some versions prefer lists)."""
        return sorted(self.registry.get_words(scope))
