"""NLTK compatibility adapter for AraNorm stop words.

Provides :class:`NLTKStopWordsAdapter` which exposes the AraNorm stop-word
registry as a plain Python list or frozenset that can be passed wherever NLTK
expects a stop-word collection.

The adapter also provides :meth:`filter_tokens` for convenience — it accepts a
pre-tokenized token list and removes all AraNorm stop words without requiring
NLTK to be installed.

Example
-------
>>> from aranorm.integrations import NLTKStopWordsAdapter
>>> adapter = NLTKStopWordsAdapter()
>>> words = adapter.to_nltk_list()          # sorted list ready for NLTK
>>> filtered = adapter.filter_tokens(["أنا", "سعيد", "اليوم"])
['سعيد']
"""

from __future__ import annotations

from typing import FrozenSet, List, Optional, Set

from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.exceptions import IntegrationUnavailableError


class NLTKStopWordsAdapter:
    """Expose AraNorm stop words to NLTK-based workflows.

    Parameters
    ----------
    registry:
        A :class:`~aranorm.core.stop_words_registry.StopWordsRegistry` instance.
        A new singleton is created automatically when omitted.

    Example
    -------
    >>> from aranorm.integrations import NLTKStopWordsAdapter
    >>> adapter = NLTKStopWordsAdapter()
    >>> words = adapter.to_nltk_list()
    >>> len(words) > 100
    True
    """

    def __init__(self, registry: Optional[StopWordsRegistry] = None) -> None:
        self.registry: StopWordsRegistry = registry or StopWordsRegistry()

    # ── Core converters ───────────────────────────────────────────────────

    def to_nltk_list(self, scope: str = "universal") -> List[str]:
        """Return AraNorm stop words as a sorted list.

        The list is compatible with any NLTK API that accepts a ``list``
        of stop-word strings.

        Parameters
        ----------
        scope:
            One of ``"universal"``, ``"msa"``, ``"filler"``, ``"social"``,
            ``"arabizi"``, ``"internet"``, ``"numbers"``.
        """
        return sorted(self.registry.get_words(scope))

    def to_frozenset(self, scope: str = "universal") -> FrozenSet[str]:
        """Return AraNorm stop words as a :class:`frozenset`.

        Suitable for O(1) membership tests in custom NLTK pipelines.

        Parameters
        ----------
        scope:
            Stop-word scope (same options as :meth:`to_nltk_list`).
        """
        return frozenset(self.registry.get_words(scope))

    # ── Convenience ───────────────────────────────────────────────────────

    def filter_tokens(
        self,
        tokens: List[str],
        scope: str = "universal",
    ) -> List[str]:
        """Remove AraNorm stop words from a pre-tokenized list.

        Does **not** require NLTK to be installed.

        Parameters
        ----------
        tokens:
            A list of Arabic word strings (e.g. from NLTK's ``word_tokenize``
            or AraNorm's own tokenizer).
        scope:
            Stop-word scope to use for filtering.

        Returns
        -------
        List[str]
            Tokens with stop words removed, preserving original order.

        Example
        -------
        >>> adapter = NLTKStopWordsAdapter()
        >>> adapter.filter_tokens(["أنا", "سعيد", "جداً", "اليوم"])
        ['سعيد']
        """
        stop_set: Set[str] = self.registry.get_words(scope)
        return [t for t in tokens if t not in stop_set]

    def merge_with_nltk(self, scope: str = "universal") -> List[str]:
        """Return the union of AraNorm and NLTK's built-in Arabic stop words.

        Requires NLTK *and* the ``stopwords`` corpus to be installed
        (``nltk.download('stopwords')``).

        Parameters
        ----------
        scope:
            AraNorm scope to merge.

        Returns
        -------
        List[str]
            Sorted union list.

        Raises
        ------
        IntegrationUnavailableError
            When NLTK is not installed.
        """
        try:
            from nltk.corpus import stopwords as nltk_sw
        except ImportError as exc:
            raise IntegrationUnavailableError("NLTK is not installed. Run: pip install nltk") from exc

        aranorm_words: Set[str] = self.registry.get_words(scope)
        try:
            nltk_words: Set[str] = set(nltk_sw.words("arabic"))
        except OSError:
            # Corpus not downloaded yet — use only AraNorm words
            nltk_words = set()

        return sorted(aranorm_words | nltk_words)

    def register_with_nltk(self, scope: str = "universal") -> List[str]:
        """Merge AraNorm stop words with NLTK's Arabic stop-word list.

        This method merges AraNorm's stop words with any existing NLTK Arabic
        stop words and stores the result on the adapter as
        ``self._registered_words``.  The merged list is also returned for
        inspection or direct use.

        .. note::
            NLTK's corpus reader does not expose a stable public API for adding
            words at runtime.  This method returns the merged list rather than
            patching NLTK internals, which would be brittle across NLTK versions.
            Pass the returned list (or :meth:`merge_with_nltk`) directly to any
            NLTK API that accepts a custom stop-word list.

        Parameters
        ----------
        scope:
            AraNorm scope to include.

        Returns
        -------
        List[str]
            Sorted merged list of stop words.

        Raises
        ------
        IntegrationUnavailableError
            When NLTK is not installed.

        Example
        -------
        >>> merged = adapter.register_with_nltk()
        >>> # Use merged directly:
        >>> filtered = [t for t in tokens if t not in set(merged)]
        """
        merged = self.merge_with_nltk(scope)
        self._registered_words: List[str] = merged
        return merged
