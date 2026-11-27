"""Corpus-level analysis: stop-word statistics across multiple texts.

Provides three public classes:
* :class:`CorpusAnalyzer` — aggregate stop-word / content-word statistics,
  pairwise overlap, and per-document distinctiveness across a collection
  of texts.
* :class:`CorpusStopWordsBuilder` — derive a custom stop-word list from a
  corpus by ranking words by document frequency and inverse content value.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.processors.stop_words_processor import StopWordsProcessor

# ── Helpers ───────────────────────────────────────────────────────────────────


def _tokens(text: str) -> List[str]:
    """Return cleaned token list (strips punctuation, lowercases)."""
    return [t.strip(".,،؟!؛:()[]{}\"'«»\n\r\t") for t in text.split() if t.strip()]


# ── Result dataclasses ────────────────────────────────────────────────────────


@dataclass
class DocumentStats:
    """Per-document statistics produced by :class:`CorpusAnalyzer`."""

    index: int
    total_tokens: int
    stop_word_count: int
    content_word_count: int
    stop_word_ratio: float
    content_words: List[str]
    stop_words_found: Set[str]


@dataclass
class CorpusAnalysisResult:
    """Aggregated corpus statistics returned by :class:`CorpusAnalyzer`."""

    # Corpus-wide totals
    document_count: int
    total_tokens: int
    total_stop_words: int
    total_content_words: int
    corpus_stop_word_ratio: float

    # Frequency tables
    stop_word_frequency: Dict[str, int]  # how often each stop word appears
    content_word_frequency: Dict[str, int]  # how often each content word appears
    document_frequency: Dict[str, int]  # how many docs contain each word
    top_stop_words: List[Tuple[str, int]]  # top-N most frequent stop words
    top_content_words: List[Tuple[str, int]]  # top-N most frequent content words

    # Per-document breakdown
    documents: List[DocumentStats]

    # Diversity metrics
    stop_word_vocabulary_size: int
    content_word_vocabulary_size: int
    average_stop_word_ratio: float
    lexical_diversity: float  # unique content words / total content tokens


@dataclass
class DocumentDistinctiveness:
    """Per-document distinctiveness within a corpus.

    Measures how *unique* a document's content vocabulary is compared to the
    rest of the corpus, using the Jaccard distance against the corpus-wide
    union of content vocabulary.

    Attributes
    ----------
    index:
        Zero-based document index within the analyzed corpus.
    only_in_this_document:
        Content words that appear in this document but in no other
        document in the corpus.
    shared_vocabulary:
        Content words this document shares with other documents.
    distinctiveness:
        Share (0.0–1.0) of the document's content vocabulary that is
        exclusive to this document. Higher means more distinctive.
    """

    index: int
    only_in_this_document: List[str]
    shared_vocabulary: List[str]
    distinctiveness: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "index": self.index,
            "only_in_this_document": self.only_in_this_document,
            "shared_vocabulary": self.shared_vocabulary,
            "distinctiveness": self.distinctiveness,
        }


@dataclass
class OverlapAnalysisResult:
    """Pairwise lexical overlap between documents in a corpus.

    Attributes
    ----------
    document_count:
        Number of documents analyzed.
    overlap_matrix:
        Upper-triangular Jaccard similarity matrix as a flat dict keyed by
        ``"i,j"`` (i < j). Values in 0.0–1.0.
    most_similar_pair:
        ``(i, j, similarity)`` for the pair with the highest overlap, or
        ``None`` when the corpus has fewer than two documents.
    least_similar_pair:
        ``(i, j, similarity)`` for the pair with the lowest overlap, or
        ``None`` when the corpus has fewer than two documents.
    average_similarity:
        Mean of all pairwise similarities, 0.0 when trivially undefined.
    distinctiveness:
        Per-document distinctiveness scores.
    """

    document_count: int
    overlap_matrix: Dict[str, float]
    most_similar_pair: Optional[Tuple[int, int, float]]
    least_similar_pair: Optional[Tuple[int, int, float]]
    average_similarity: float
    distinctiveness: List[DocumentDistinctiveness]

    def to_dict(self) -> Dict[str, object]:
        return {
            "document_count": self.document_count,
            "overlap_matrix": {k: v for k, v in self.overlap_matrix.items()},
            "most_similar_pair": list(self.most_similar_pair) if self.most_similar_pair else None,
            "least_similar_pair": list(self.least_similar_pair) if self.least_similar_pair else None,
            "average_similarity": self.average_similarity,
            "distinctiveness": [d.to_dict() for d in self.distinctiveness],
        }


@dataclass
class CorpusStopWordsResult:
    """Output from :class:`CorpusStopWordsBuilder`."""

    extracted_stop_words: FrozenSet[str]
    candidate_scores: List[Tuple[str, float]]  # (word, score) sorted descending
    corpus_size: int
    vocabulary_size: int
    threshold_used: float


# ── CorpusAnalyzer ────────────────────────────────────────────────────────────


class CorpusAnalyzer:
    """Aggregate stop-word and content-word statistics across a corpus.

    Parameters
    ----------
    config:
        :class:`~aranorm.core.stop_words_config.StopWordsConfig` used to
        decide which words are stop words.  Defaults to universal removal.
    registry:
        Optional shared registry.
    top_n:
        Number of top words to include in the result (default 20).

    Example
    -------
    >>> analyzer = CorpusAnalyzer()
    >>> result = analyzer.analyze(["أنا سعيد اليوم", "هو يعمل بجد"])
    >>> result.corpus_stop_word_ratio
    0.5
    """

    def __init__(
        self,
        config: Optional[StopWordsConfig] = None,
        registry: Optional[StopWordsRegistry] = None,
        top_n: int = 20,
    ) -> None:
        self.config = config or StopWordsConfig(mode="remove", scope="universal", remove_filler=True)
        self.registry = registry or StopWordsRegistry()
        self.processor = StopWordsProcessor(config=self.config, registry=self.registry)
        self.top_n = top_n

    # ── Core ─────────────────────────────────────────────────────────────

    def analyze(self, texts: Iterable[str]) -> CorpusAnalysisResult:
        """Return a :class:`CorpusAnalysisResult` for the given corpus.

        Parameters
        ----------
        texts:
            Any iterable of strings (list, generator, file lines …).
        """
        text_list = [t for t in texts if isinstance(t, str) and t.strip()]
        if not text_list:
            return self._empty_result()

        doc_count = len(text_list)
        total_tokens = 0
        total_stops = 0
        total_content = 0

        stop_freq: Counter = Counter()
        content_freq: Counter = Counter()
        doc_freq: Counter = Counter()

        documents: List[DocumentStats] = []

        for idx, text in enumerate(text_list):
            sw_result = self.processor.process_detailed(text)
            raw_tokens = _tokens(text)
            n = len(raw_tokens)
            stop_set = sw_result.stop_words_found
            content_words = [t for t in _tokens(sw_result.stop_words_removed) if t]

            total_tokens += n
            total_stops += len(stop_set)
            total_content += len(content_words)

            for w in stop_set:
                stop_freq[w] += 1
            for w in content_words:
                content_freq[w] += 1
            for w in set(_tokens(text)):
                doc_freq[w] += 1

            documents.append(
                DocumentStats(
                    index=idx,
                    total_tokens=n,
                    stop_word_count=len(stop_set),
                    content_word_count=len(content_words),
                    stop_word_ratio=round(len(stop_set) / n, 4) if n else 0.0,
                    content_words=content_words,
                    stop_words_found=stop_set,
                )
            )

        corpus_stop_ratio = round(total_stops / total_tokens, 4) if total_tokens else 0.0
        avg_stop_ratio = round(sum(d.stop_word_ratio for d in documents) / doc_count, 4)
        unique_content = len(content_freq)
        total_content_tokens = sum(content_freq.values())
        diversity = round(unique_content / total_content_tokens, 4) if total_content_tokens else 0.0

        return CorpusAnalysisResult(
            document_count=doc_count,
            total_tokens=total_tokens,
            total_stop_words=total_stops,
            total_content_words=total_content,
            corpus_stop_word_ratio=corpus_stop_ratio,
            stop_word_frequency=dict(stop_freq.most_common()),
            content_word_frequency=dict(content_freq.most_common()),
            document_frequency=dict(doc_freq.most_common()),
            top_stop_words=stop_freq.most_common(self.top_n),
            top_content_words=content_freq.most_common(self.top_n),
            documents=documents,
            stop_word_vocabulary_size=len(stop_freq),
            content_word_vocabulary_size=unique_content,
            average_stop_word_ratio=avg_stop_ratio,
            lexical_diversity=diversity,
        )

    def overlap_analysis(self, texts: Iterable[str]) -> OverlapAnalysisResult:
        """Pairwise lexical overlap and per-document distinctiveness.

        Computes the Jaccard similarity between each document pair's content
        vocabulary (after stop-word removal), plus a distinctiveness score
        for every document: how far its vocabulary sits from the corpus-wide
        vocabulary union.

        Documents that fail the normal text filter (empty/whitespace-only)
        are skipped, so the resulting indices refer to the filtered corpus.
        """
        text_list = [t for t in texts if isinstance(t, str) and t.strip()]
        if len(text_list) < 2:
            return OverlapAnalysisResult(
                document_count=len(text_list),
                overlap_matrix={},
                most_similar_pair=None,
                least_similar_pair=None,
                average_similarity=0.0,
                distinctiveness=[],
            )

        vocabularies: List[Set[str]] = []
        for text in text_list:
            content_words = [t for t in _tokens(self.processor.process_detailed(text).stop_words_removed) if t]
            vocabularies.append(set(content_words))

        overlap_matrix: Dict[str, float] = {}
        similarities: List[float] = []
        for i in range(len(text_list)):
            for j in range(i + 1, len(text_list)):
                inter = vocabularies[i] & vocabularies[j]
                union = vocabularies[i] | vocabularies[j]
                similarity = len(inter) / len(union) if union else 0.0
                overlap_matrix[f"{i},{j}"] = round(similarity, 4)
                similarities.append(similarity)

        most = max(enumerate(similarities), key=lambda item: item[1])
        least = min(enumerate(similarities), key=lambda item: item[1])
        average = round(sum(similarities) / len(similarities), 4) if similarities else 0.0

        distinctiveness: List[DocumentDistinctiveness] = []
        for idx, vocab in enumerate(vocabularies):
            # Words shared with the rest of the corpus are those the document
            # has in common with at least one other document.
            others = set()
            for other_idx, other_vocab in enumerate(vocabularies):
                if other_idx != idx:
                    others |= other_vocab
            only_this = vocab - others
            shared = vocab - only_this
            total = len(vocab)
            dist = round(len(only_this) / total, 4) if total else 0.0
            distinctiveness.append(
                DocumentDistinctiveness(
                    index=idx,
                    only_in_this_document=sorted(only_this),
                    shared_vocabulary=sorted(shared),
                    distinctiveness=dist,
                )
            )

        return OverlapAnalysisResult(
            document_count=len(text_list),
            overlap_matrix=overlap_matrix,
            most_similar_pair=(most[0] // (len(text_list) - 1), most[0] % (len(text_list) - 1) + 1, round(most[1], 4)),
            least_similar_pair=(
                least[0] // (len(text_list) - 1),
                least[0] % (len(text_list) - 1) + 1,
                round(least[1], 4),
            ),
            average_similarity=average,
            distinctiveness=distinctiveness,
        )

    def compare(self, corpus_a: Iterable[str], corpus_b: Iterable[str]) -> Dict[str, object]:
        """Compare stop-word profiles of two corpora.

        Returns a dict with keys ``corpus_a``, ``corpus_b``, and
        ``overlap`` (stop words appearing in both).
        """
        result_a = self.analyze(corpus_a)
        result_b = self.analyze(corpus_b)
        words_a = set(result_a.stop_word_frequency)
        words_b = set(result_b.stop_word_frequency)
        return {
            "corpus_a": result_a,
            "corpus_b": result_b,
            "shared_stop_words": words_a & words_b,
            "unique_to_a": words_a - words_b,
            "unique_to_b": words_b - words_a,
            "jaccard_similarity": (len(words_a & words_b) / len(words_a | words_b) if words_a | words_b else 0.0),
        }

    # ── Private ───────────────────────────────────────────────────────────

    def _empty_result(self) -> CorpusAnalysisResult:
        return CorpusAnalysisResult(
            document_count=0,
            total_tokens=0,
            total_stop_words=0,
            total_content_words=0,
            corpus_stop_word_ratio=0.0,
            stop_word_frequency={},
            content_word_frequency={},
            document_frequency={},
            top_stop_words=[],
            top_content_words=[],
            documents=[],
            stop_word_vocabulary_size=0,
            content_word_vocabulary_size=0,
            average_stop_word_ratio=0.0,
            lexical_diversity=0.0,
        )


# ── CorpusStopWordsBuilder ────────────────────────────────────────────────────


class CorpusStopWordsBuilder:
    """Derive a domain-specific stop-word list from a corpus.

    Words are scored by their *document frequency* — how many documents they
    appear in — normalised by a TF weight.  High-DF, low-information words
    are candidates for domain stop words.

    Parameters
    ----------
    min_doc_frequency:
        Minimum number of documents a word must appear in (absolute count).
        Words below this threshold are never candidates.
    max_doc_frequency_ratio:
        Maximum fraction of documents a word may appear in before it is
        considered too common to be a content word (0.0–1.0, default 0.85).
    min_word_length:
        Discard single characters and very short strings (default 2).
    exclude_known_stop_words:
        If *True*, filter out words already in the AraNorm universal list.

    Example
    -------
    >>> builder = CorpusStopWordsBuilder(min_doc_frequency=3)
    >>> result = builder.build(texts)
    >>> frozenset_of_new_stops = result.extracted_stop_words
    """

    def __init__(
        self,
        min_doc_frequency: int = 2,
        max_doc_frequency_ratio: float = 0.85,
        min_word_length: int = 2,
        top_n: int = 100,
        exclude_known_stop_words: bool = False,
        registry: Optional[StopWordsRegistry] = None,
    ) -> None:
        self.min_doc_frequency = min_doc_frequency
        self.max_doc_frequency_ratio = max_doc_frequency_ratio
        self.min_word_length = min_word_length
        self.top_n = top_n
        self.exclude_known_stop_words = exclude_known_stop_words
        self._registry = registry or StopWordsRegistry()

    def build(self, texts: Iterable[str]) -> CorpusStopWordsResult:
        """Derive a stop-word candidate list from *texts*.

        Parameters
        ----------
        texts:
            Iterable of document strings.
        """
        text_list = [t for t in texts if isinstance(t, str) and t.strip()]
        n_docs = len(text_list)
        if n_docs == 0:
            return CorpusStopWordsResult(
                extracted_stop_words=frozenset(),
                candidate_scores=[],
                corpus_size=0,
                vocabulary_size=0,
                threshold_used=self.max_doc_frequency_ratio,
            )

        # Count document frequency and total frequency
        df: Counter = Counter()
        tf: Counter = Counter()
        for text in text_list:
            tokens_in_doc = set(_tokens(text))
            for w in tokens_in_doc:
                df[w] += 1
            for w in _tokens(text):
                tf[w] += 1

        known_stops: Set[str] = set()
        if self.exclude_known_stop_words:
            known_stops = self._registry.get_words("universal")

        # Score candidates
        candidates: List[Tuple[str, float]] = []
        threshold = self.max_doc_frequency_ratio

        for word, doc_count in df.items():
            if len(word) < self.min_word_length:
                continue
            if doc_count < self.min_doc_frequency:
                continue
            df_ratio = doc_count / n_docs
            if df_ratio > threshold:
                continue
            if self.exclude_known_stop_words and word in known_stops:
                continue
            # Score: high DF ratio → more stop-word-like
            idf = math.log((n_docs + 1) / (doc_count + 1))
            score = df_ratio / (idf + 1e-9)
            candidates.append((word, round(score, 6)))

        # Sort by score descending (most stop-word-like first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = candidates[: self.top_n]
        extracted = frozenset(w for w, _ in top_candidates)

        return CorpusStopWordsResult(
            extracted_stop_words=extracted,
            candidate_scores=top_candidates,
            corpus_size=n_docs,
            vocabulary_size=len(df),
            threshold_used=threshold,
        )
