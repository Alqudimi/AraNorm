"""Pairwise similarity analysis across a collection of Arabic texts.

The :class:`TextSimilarityMatrix` computes the full pairwise similarity
between every two texts in a corpus and exposes the results as a score
matrix, ranked pairs, and duplicate clusters.  It composes the token-based
metrics of :class:`TextComparator`, so it inherits stop-word filtering and
the composite ``overall_similarity`` verdict.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from aranorm.analysis.text_comparator import SimilarityResult, TextComparator


@dataclass(frozen=True)
class ClosestPair:
    """A ranked pair of similar texts.

    Attributes
    ----------
    index_a, index_b:
        Indices of the two texts in the input collection.
    similarity:
        The composite ``overall_similarity`` score (0-1).
    verdict:
        Human-readable similarity band.
    result:
        The full :class:`SimilarityResult` for the pair.
    """

    index_a: int
    index_b: int
    similarity: float
    verdict: str
    result: SimilarityResult

    def to_dict(self) -> Dict[str, object]:
        """Return a plain dictionary representation."""
        return {
            "index_a": self.index_a,
            "index_b": self.index_b,
            "similarity": self.similarity,
            "verdict": self.verdict,
            "text_a": self.result.text_a,
            "text_b": self.result.text_b,
        }


@dataclass(frozen=True)
class SimilarityMatrixResult:
    """Result of a pairwise similarity analysis over a text collection.

    Attributes
    ----------
    text_count:
        Number of texts in the input collection.
    pair_count:
        Number of unique pairs that were compared.
    matrix:
        Symmetric similarity scores; ``matrix[i][j]`` is the composite score
        between text *i* and text *j* (1.0 on the diagonal).
    pairs:
        All unique pairs with their full :class:`SimilarityResult` objects.
    closest:
        ``pairs`` sorted by descending ``overall_similarity``.
    duplicate_pairs:
        Pairs whose composite score equals exactly 1.0.
    """

    text_count: int
    pair_count: int
    matrix: List[List[float]]
    pairs: List[ClosestPair]
    closest: List[ClosestPair]
    duplicate_pairs: List[ClosestPair]

    def find_closest_pairs(self, threshold: float = 0.0, top_n: Optional[int] = None) -> List[ClosestPair]:
        """Return pairs whose composite score meets *threshold*.

        Parameters
        ----------
        threshold:
            Minimum ``overall_similarity`` score to include (0-1).
        top_n:
            Optional cap on the number of returned pairs.
        """
        if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
            raise ValueError("threshold must be a number between 0 and 1")
        if top_n is not None:
            if not isinstance(top_n, int) or isinstance(top_n, bool) or top_n < 0:
                raise ValueError("top_n must be a non-negative integer")
        matches = [pair for pair in self.closest if pair.similarity >= threshold]
        if top_n is not None:
            return matches[:top_n]
        return matches

    def to_dict(self) -> Dict[str, object]:
        """Return a plain dictionary representation."""
        return {
            "text_count": self.text_count,
            "pair_count": self.pair_count,
            "matrix": self.matrix,
            "closest_pairs": [pair.to_dict() for pair in self.closest],
            "duplicate_pairs": [{"index_a": pair.index_a, "index_b": pair.index_b} for pair in self.duplicate_pairs],
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        """Return a JSON serialization of the matrix result."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class TextSimilarityMatrix:
    """Compute pairwise similarity across a collection of Arabic texts.

    Example
    -------
    >>> matrix = TextSimilarityMatrix()
    >>> result = matrix.analyze(["نص واحد", "نص واحد آخر", "مختلف تماما"])
    >>> result.text_count
    3
    >>> result.pair_count
    3
    """

    def __init__(
        self,
        comparator: Optional[TextComparator] = None,
        score_key: str = "overall_similarity",
    ) -> None:
        self.comparator = comparator or TextComparator()
        if score_key not in _VALID_SCORE_KEYS:
            raise ValueError("score_key must be one of: " + ", ".join(sorted(_VALID_SCORE_KEYS)))
        self.score_key = score_key

    def analyze(self, texts: Iterable[str]) -> SimilarityMatrixResult:
        """Analyze the full pairwise similarity of *texts*.

        Parameters
        ----------
        texts:
            Input text collection.  Empty inputs yield a zero-dimension
            result.
        """
        items = list(texts)
        size = len(items)
        matrix: List[List[float]] = [[1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
        pairs: List[ClosestPair] = []
        for index_a in range(size):
            for index_b in range(index_a + 1, size):
                result = self.comparator.compare(items[index_a], items[index_b])
                score = getattr(result, self.score_key)
                matrix[index_a][index_b] = score
                matrix[index_b][index_a] = score
                pairs.append(
                    ClosestPair(
                        index_a=index_a,
                        index_b=index_b,
                        similarity=score,
                        verdict=result.verdict,
                        result=result,
                    )
                )
        closest = sorted(pairs, key=lambda pair: (-pair.similarity, pair.index_a, pair.index_b))
        duplicates = [pair for pair in pairs if pair.similarity >= 1.0]
        return SimilarityMatrixResult(
            text_count=size,
            pair_count=len(pairs),
            matrix=matrix,
            pairs=pairs,
            closest=closest,
            duplicate_pairs=duplicates,
        )


_VALID_SCORE_KEYS = {
    "jaccard_similarity",
    "cosine_similarity",
    "content_jaccard",
    "content_cosine",
    "overall_similarity",
}
