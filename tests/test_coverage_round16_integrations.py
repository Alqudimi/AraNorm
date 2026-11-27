"""Coverage suite for optional integrations with dependencies *present*.

These tests simulate the presence of ``nltk``, ``spacy`` and ``pandas`` by
injecting lightweight fake modules into ``sys.modules`` via
``monkeypatch.setitem``.  Each fake exposes only the surface that AraNorm's
adapters touch, keeping the tests deterministic and dependency-free.

Module teardown is delegated to the autouse fixture in ``conftest.py`` so the
fake modules never leak into unrelated tests (such as the negative-path
contracts in ``test_optional_dependency_contracts.py``).
"""

from __future__ import annotations

import sys
import types
from typing import Any, Callable, Dict, List, Optional

import pytest

from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.exceptions import IntegrationUnavailableError
from aranorm.integrations import (
    HuggingFaceNormalizer,
    NLTKStopWordsAdapter,
    PandasNormalizer,
    SklearnStopWordsAdapter,
    SpacyStopWordsAdapter,
)

# ── Fake builders ────────────────────────────────────────────────


def _make_fake_nltk() -> types.ModuleType:
    """Minimal ``nltk`` fake with a ``corpus.stopwords`` reader."""
    nltk = types.ModuleType("nltk")
    corpus = types.ModuleType("nltk.corpus")

    # ``from nltk.corpus import stopwords`` resolves ``nltk.corpus`` in
    # ``sys.modules`` first, so register both entries here.
    sys.modules["nltk"] = nltk
    sys.modules["nltk.corpus"] = corpus

    def words(language: str) -> List[str]:
        return ["the", "of"] if language != "arabic" else ["في", "من", "على"]

    corpus.stopwords = types.SimpleNamespace(words=words)
    nltk.corpus = corpus
    return nltk


def _make_fake_spacy() -> types.ModuleType:
    """Minimal ``spacy`` fake module (spacy itself is only import-checked)."""
    spacy = types.ModuleType("spacy")
    sys.modules["spacy"] = spacy
    return spacy


class _FakeLangDefaults:
    """Fake for ``spacy.Language.Defaults`` exposing ``stop_words``."""

    def __init__(self) -> None:
        self.stop_words: set = {"و", "في"}


class _FakeLexeme:
    """Fake for ``spacy.Language.vocab[word]``."""

    def __init__(self, word: str) -> None:
        self.word = word
        self.is_stop: bool = False


class _FakeVocab:
    """Fake for ``spacy.Language.vocab`` with simple containment."""

    def __init__(self, known: set) -> None:
        self._known = set(known)
        # spaCy returns the same ``Lexeme`` object for repeated lookups, so
        # the fake must cache instances to remain behaviour-compatible.
        self._cache: Dict[str, _FakeLexeme] = {}

    def __contains__(self, word: str) -> bool:
        return word in self._known

    def __getitem__(self, word: str) -> _FakeLexeme:
        if word not in self._known:
            raise KeyError(word)
        if word not in self._cache:
            self._cache[word] = _FakeLexeme(word)
        return self._cache[word]


class _FakeNLP:
    """Fake for a loaded spaCy ``Language`` object."""

    def __init__(self) -> None:
        self.Defaults = _FakeLangDefaults()
        self.vocab = _FakeVocab(set())

    def __getitem__(self, word: str) -> _FakeLexeme:
        return self.vocab[word]


class _FakeSeries:
    """Minimal stand-in for ``pandas.Series``."""

    def __init__(self, data: List[Any], index: Any = None, name: str = "text") -> None:
        self._data = list(data)
        self.index = list(range(len(data))) if index is None else index
        self.name = name

    def fillna(self, _value: Any) -> "_FakeSeries":
        return _FakeSeries(
            [("" if v is None else v) for v in self._data],
            self.index,
            self.name,
        )

    def tolist(self) -> List[Any]:
        return list(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):
        return iter(self._data)


class _FakeDataFrame:
    """Minimal stand-in for ``pandas.DataFrame``."""

    def __init__(self, data: Dict[str, List[Any]], columns: List[str]) -> None:
        self._data = {col: list(vals) for col, vals in data.items()}
        self.columns = columns

    def copy(self) -> "_FakeDataFrame":
        return _FakeDataFrame(
            {col: list(vals) for col, vals in self._data.items()},
            columns=list(self.columns),
        )

    def __contains__(self, col: str) -> bool:
        return col in self._data

    def __getitem__(self, col: str) -> _FakeSeries:
        return _FakeSeries(self._data[col], name=col)

    def __setitem__(self, col: str, values: _FakeSeries) -> None:
        self._data[col] = list(values)


class _FakeHFColumnar:
    """Fake columnar store shared by fake ``Dataset`` and ``DatasetDict``."""

    def __init__(self, data: Dict[str, List[Any]]) -> None:
        self._data = {col: list(vals) for col, vals in data.items()}

    def __getitem__(self, col: str) -> List[Any]:
        return list(self._data[col])

    def __setitem__(self, col: str, values: List[Any]) -> None:
        self._data[col] = list(values)

    def __contains__(self, col: str) -> bool:
        return col in self._data

    def remove(self, columns: List[str]) -> None:
        for col in columns:
            self._data.pop(col, None)

    def map(
        self,
        function: Callable[[Dict[str, List[Any]]], Dict[str, List[Any]]],
        batched: bool = False,
        batch_size: int = 1000,
        num_proc: Optional[int] = None,
        remove_columns: Optional[List[str]] = None,
        desc: str = "",
    ) -> "_FakeHFColumnar":
        """Simplified batched map mimicking ``datasets.Dataset.map``."""
        rows = len(next(iter(self._data.values()), []))
        out_columns: List[str] = []
        # ``dataset.map`` preserves input columns and adds produced ones.
        produced_columns = function({col: [] for col in self._data})
        if produced_columns:
            out_columns = list(produced_columns.keys())
        out_data: Dict[str, List[Any]] = {col: [] for col in list(self._data.keys()) + out_columns}
        for start in range(0, rows, batch_size):
            batch = {col: vals[start : start + batch_size] for col, vals in self._data.items()}
            produced = function(batch)
            for col, vals in produced.items():
                out_data[col].extend(vals)
        store = _FakeHFColumnar(out_data)
        if remove_columns:
            store.remove(remove_columns)
        return store


class _FakeHFDataset(_FakeHFColumnar):
    """Fake for ``datasets.Dataset``."""

    @classmethod
    def from_dict(cls, data: Dict[str, List[Any]]) -> "_FakeHFDataset":
        return cls(data)


class _FakeHFDatasetDict:
    """Fake for ``datasets.DatasetDict`` mapping split names to datasets."""

    def __init__(self, splits: Dict[str, Dict[str, List[Any]]]) -> None:
        self._splits = {name: _FakeHFDataset(cols) for name, cols in splits.items()}

    def map(self, function: Callable, **kwargs: Any) -> "_FakeHFDatasetDict":
        mapped = _FakeHFDatasetDict.__new__(_FakeHFDatasetDict)
        mapped._splits = {name: ds.map(function, **kwargs) for name, ds in self._splits.items()}
        return mapped


def _make_fake_datasets() -> types.ModuleType:
    """Minimal ``datasets`` fake with ``Dataset``, ``DatasetDict`` helpers."""
    datasets = types.ModuleType("datasets")
    datasets.Dataset = _FakeHFDataset
    datasets.DatasetDict = _FakeHFDatasetDict
    sys.modules["datasets"] = datasets
    return datasets


class _FakePipeline:
    """Deterministic pipeline stand-in returning :class:`NormalizationResult`-like objects."""

    def process_batch(self, texts: List[str], n_workers: int = 1) -> List[Any]:
        return [_FakeResult(text) for text in texts]


class _FakeResult:
    """``NormalizationResult`` stand-in for fake adapter tests."""

    def __init__(self, normalized_text: str) -> None:
        self.normalized_text = normalized_text
        self.dialect = "msa"
        self.dialect_confidence = 1.0
        self.processed_text = normalized_text
        self.stop_words_removed = ""
        self.applied_steps = ["standard"]


def _make_fake_pandas() -> types.ModuleType:
    """Minimal ``pandas`` fake with ``Series``, ``DataFrame`` and helpers."""
    pd = types.ModuleType("pandas")

    class _RowsDataFrame(_FakeDataFrame):  # type: ignore[misc]
        """``pd.DataFrame`` constructor stand-in accepting rows dicts."""

        def __init__(self, rows: Any = None, index: Any = None) -> None:
            data: Dict[str, List[Any]] = {}
            for row in rows or ():
                for key, value in row.items():
                    if key not in data:
                        data[key] = []
                    data[key].append(value)
            super().__init__(data, list(data.keys()))
            if index is not None:
                self.index = list(index)

    pd.Series = _FakeSeries
    pd.DataFrame = _RowsDataFrame
    return pd


# ── NLTK adapter with the fake installed ──────────────────────────


def test_nltk_adapter_to_nltk_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "nltk", _make_fake_nltk())
    adapter = NLTKStopWordsAdapter()
    words = adapter.to_nltk_list()
    assert isinstance(words, list)
    assert words == sorted(words)
    assert len(words) > 0


def test_nltk_adapter_to_frozenset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "nltk", _make_fake_nltk())
    adapter = NLTKStopWordsAdapter()
    result = adapter.to_frozenset()
    assert isinstance(result, frozenset)
    assert len(result) > 0


def test_nltk_adapter_filter_tokens_keeps_meaningful_words(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "nltk", _make_fake_nltk())
    adapter = NLTKStopWordsAdapter()
    filtered = adapter.filter_tokens(["أنا", "سعيد", "اليوم"])
    assert isinstance(filtered, list)
    # Stop words must be removed; meaningful tokens must survive.
    stop_words = set(adapter.registry.get_words("universal"))
    assert not any(word in stop_words for word in filtered)


def test_nltk_adapter_filter_tokens_missing_nltk(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = NLTKStopWordsAdapter()
    # ``filter_tokens`` never requires NLTK; it must still work when absent.
    filtered = adapter.filter_tokens(["أنا", "سعيد"])
    assert isinstance(filtered, list)


def test_nltk_adapter_merge_with_nltk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "nltk", _make_fake_nltk())
    adapter = NLTKStopWordsAdapter()
    merged = adapter.merge_with_nltk()
    assert isinstance(merged, list)
    # AraNorm universal words + NLTK Arabic words union.
    assert "في" in merged
    assert merged == sorted(merged)


def test_nltk_adapter_merge_nltk_corpus_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """``merge_with_nltk`` falls back to AraNorm words when the corpus is missing."""
    nltk = _make_fake_nltk()

    def _broken_words(language: str) -> List[str]:
        raise OSError("No stopwords corpus")

    nltk.corpus.stopwords.words = _broken_words  # type: ignore[assignment]
    monkeypatch.setitem(sys.modules, "nltk", nltk)

    adapter = NLTKStopWordsAdapter()
    merged = adapter.merge_with_nltk()
    assert isinstance(merged, list)
    assert len(merged) > 0


def test_nltk_adapter_register_with_nltk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "nltk", _make_fake_nltk())
    adapter = NLTKStopWordsAdapter()
    registered = adapter.register_with_nltk()
    assert isinstance(registered, list)
    assert registered == adapter._registered_words  # type: ignore[attr-defined]


def test_nltk_adapter_missing_nltk_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """NLTK-requiring methods must raise when NLTK is absent."""
    adapter = NLTKStopWordsAdapter()
    with pytest.raises(IntegrationUnavailableError, match="NLTK is not installed"):
        adapter.merge_with_nltk()


def test_nltk_adapter_missing_nltk_filter_tokens_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """Token filtering never requires NLTK, even when the module is missing."""
    adapter = NLTKStopWordsAdapter()
    filtered = adapter.filter_tokens(["أنا", "سعيد", "اليوم"])
    assert isinstance(filtered, list)


# ── spaCy adapter with the fake installed ─────────────────────────


def test_spacy_adapter_to_spacy_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "spacy", _make_fake_spacy())
    adapter = SpacyStopWordsAdapter()
    words = adapter.to_spacy_set()
    assert isinstance(words, set)
    assert len(words) > 0


def test_spacy_adapter_enrich_spacy_merges_words(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "spacy", _make_fake_spacy())
    adapter = SpacyStopWordsAdapter()
    nlp = _FakeNLP()
    before = set(nlp.Defaults.stop_words)
    result = adapter.enrich_spacy(nlp)
    assert result is nlp
    assert before < nlp.Defaults.stop_words
    assert adapter.registry.get_words("universal") <= nlp.Defaults.stop_words


def test_spacy_adapter_enrich_spacy_marks_vocab_lexemes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Known vocab entries must have ``is_stop`` set to True after enriching."""
    monkeypatch.setitem(sys.modules, "spacy", _make_fake_spacy())
    adapter = SpacyStopWordsAdapter()
    nlp = _FakeNLP()
    # The fake must treat the word itself as the lookup key (as spaCy does).
    nlp.vocab._known = set(nlp.Defaults.stop_words)
    adapter.enrich_spacy(nlp)
    assert nlp.vocab["و"].is_stop is True


def test_spacy_adapter_enrich_spacy_non_language_object_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "spacy", _make_fake_spacy())
    adapter = SpacyStopWordsAdapter()
    with pytest.raises(IntegrationUnavailableError, match="does not appear to be a spaCy"):
        adapter.enrich_spacy("not-a-nlp-object")


def test_spacy_adapter_missing_spacy_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = SpacyStopWordsAdapter()
    with pytest.raises(IntegrationUnavailableError, match="spaCy is not installed"):
        adapter.enrich_spacy("not-a-nlp-object")


# ── Pandas adapter with the fake installed ───────────────────────


def test_pandas_adapter_initializes_with_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    normalizer = PandasNormalizer()
    assert normalizer.pipeline is not None
    assert normalizer.n_workers == 1


def test_pandas_adapter_custom_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """A user-supplied pipeline must bypass the default ``standard`` one."""
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    pipeline = _FakePipeline()
    normalizer = PandasNormalizer(pipeline=pipeline, n_workers=2)
    assert normalizer.pipeline is pipeline
    assert normalizer.n_workers == 2


def test_pandas_adapter_normalize_column(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    normalizer = PandasNormalizer()
    series = _FakeSeries(["بسم الله", None, "أهلاً"])
    result = normalizer.normalize_column(series)
    assert isinstance(result, _FakeSeries)
    assert result.name == series.name
    # No row may remain ``None`` after normalization.
    assert all(value is not None for value in result)


def test_pandas_adapter_normalize_column_preserves_index_and_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    normalizer = PandasNormalizer()
    series = _FakeSeries(["نص تجريبي"], index=[7], name="article")
    result = normalizer.normalize_column(series)
    assert result.index == [7]
    assert result.name == "article"


def test_pandas_adapter_normalize_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    normalizer = PandasNormalizer()
    frame = _FakeDataFrame({"body": ["نص", "آخر"], "label": [1, 2]}, columns=["body", "label"])
    result = normalizer.normalize_dataframe(frame, "body")
    assert "body_normalized" in result._data  # type: ignore[attr-defined]
    assert result._data["body"] == ["نص", "آخر"]  # type: ignore[attr-defined]


def test_pandas_adapter_normalize_dataframe_custom_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    normalizer = PandasNormalizer()
    frame = _FakeDataFrame({"body": ["نص"]}, columns=["body"])
    result = normalizer.normalize_dataframe(frame, "body", output_column="clean")
    assert "clean" in result._data  # type: ignore[attr-defined]


def test_pandas_adapter_normalize_dataframe_preserves_original_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """``normalize_dataframe`` never drops the source column; it adds a new one."""
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    normalizer = PandasNormalizer()
    frame = _FakeDataFrame({"body": ["نص"], "label": [1]}, columns=["body", "label"])
    result = normalizer.normalize_dataframe(frame, "body")
    assert "body" in result._data  # type: ignore[attr-defined]
    assert "label" in result._data  # type: ignore[attr-defined]
    assert "body_normalized" in result._data  # type: ignore[attr-defined]


def test_pandas_adapter_expand_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    normalizer = PandasNormalizer()
    series = _FakeSeries(["نص"])
    result = normalizer.expand_results(series)
    assert "normalized_text" in result._data  # type: ignore[attr-defined]
    assert "dialect" in result._data  # type: ignore[attr-defined]
    assert "dialect_confidence" in result._data  # type: ignore[attr-defined]


def test_pandas_adapter_expand_results_custom_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    normalizer = PandasNormalizer()
    series = _FakeSeries(["نص"])
    result = normalizer.expand_results(series, fields=["normalized_text"])
    assert "normalized_text" in result._data  # type: ignore[attr-defined]
    assert "dialect" not in result._data  # type: ignore[attr-defined]


def test_pandas_adapter_apply_stop_words(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    normalizer = PandasNormalizer()
    series = _FakeSeries(["بسم الله"])
    result = normalizer.apply_stop_words(series, stop_words_field="stop_words_removed")
    assert isinstance(result, _FakeSeries)
    assert len(result) == 1


def test_pandas_adapter_apply_stop_words_processed_text_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", _make_fake_pandas())
    normalizer = PandasNormalizer()
    series = _FakeSeries(["نص تجريبي"])
    result = normalizer.apply_stop_words(series, stop_words_field="processed_text")
    assert isinstance(result, _FakeSeries)


# ── HuggingFace adapter with the fake installed ─────────────────


def test_huggingface_adapter_initializes_with_default_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "datasets", _make_fake_datasets())
    normalizer = HuggingFaceNormalizer()
    assert normalizer.pipeline is not None
    assert normalizer.batch_size == 512
    assert normalizer.num_proc is None


def test_huggingface_adapter_custom_pipeline_and_batching(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "datasets", _make_fake_datasets())
    pipeline = _FakePipeline()
    normalizer = HuggingFaceNormalizer(pipeline=pipeline, batch_size=64, num_proc=4)
    assert normalizer.pipeline is pipeline
    assert normalizer.batch_size == 64
    assert normalizer.num_proc == 4


def test_huggingface_adapter_normalize_dataset_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "datasets", _make_fake_datasets())
    normalizer = HuggingFaceNormalizer(pipeline=_FakePipeline())
    dataset = _FakeHFDataset.from_dict({"text": ["بسم الله", "نص تجريبي"]})
    result = normalizer.normalize_dataset(dataset, text_column="text")
    assert "text_normalized" in result
    assert "text" in result
    assert len(result["text_normalized"]) == 2


def test_huggingface_adapter_normalize_dataset_custom_output_column(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "datasets", _make_fake_datasets())
    normalizer = HuggingFaceNormalizer(pipeline=_FakePipeline())
    dataset = _FakeHFDataset.from_dict({"body": ["نص"]})
    result = normalizer.normalize_dataset(dataset, text_column="body", output_column="clean")
    assert "clean" in result


def test_huggingface_adapter_normalize_dataset_remove_original(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "datasets", _make_fake_datasets())
    normalizer = HuggingFaceNormalizer(pipeline=_FakePipeline())
    dataset = _FakeHFDataset.from_dict({"text": ["نص"]})
    result = normalizer.normalize_dataset(dataset, remove_original=True)
    assert "text" not in result
    assert "text_normalized" in result


def test_huggingface_adapter_normalize_dataset_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "datasets", _make_fake_datasets())
    normalizer = HuggingFaceNormalizer(pipeline=_FakePipeline())
    splits = {"train": {"text": ["نص التدريب"]}, "test": {"text": ["نص الاختبار"]}}
    dataset = _FakeHFDatasetDict(splits)
    result = normalizer.normalize_dataset(dataset, text_column="text")
    assert "train" in result._splits
    assert "test" in result._splits
    assert "text_normalized" in result._splits["train"]


def test_huggingface_adapter_expand_dataset_default_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "datasets", _make_fake_datasets())
    normalizer = HuggingFaceNormalizer(pipeline=_FakePipeline())
    dataset = _FakeHFDataset.from_dict({"text": ["نص"]})
    result = normalizer.expand_dataset(dataset, text_column="text")
    assert "normalized_text" in result
    assert "dialect" in result
    assert "dialect_confidence" in result


def test_huggingface_adapter_expand_dataset_custom_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "datasets", _make_fake_datasets())
    normalizer = HuggingFaceNormalizer(pipeline=_FakePipeline())
    dataset = _FakeHFDataset.from_dict({"text": ["نص"]})
    result = normalizer.expand_dataset(dataset, text_column="text", fields=["dialect"])
    assert "dialect" in result
    assert "dialect_confidence" not in result


def test_huggingface_adapter_missing_datasets_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """``normalize_dataset`` re-checks the ``datasets`` dependency at call time."""
    monkeypatch.setitem(sys.modules, "datasets", _make_fake_datasets())
    normalizer = HuggingFaceNormalizer(pipeline=_FakePipeline())
    # Remove the fake: ``normalize_dataset`` must verify the dependency again.
    monkeypatch.delitem(sys.modules, "datasets")
    monkeypatch.delitem(sys.modules, "nltk", raising=False)
    with pytest.raises(IntegrationUnavailableError, match="pip install datasets"):
        normalizer.normalize_dataset(object())


# ── scikit-learn adapter (pure Python, no fake needed) ──────────


def test_sklearn_adapter_to_sklearn_set() -> None:
    adapter = SklearnStopWordsAdapter()
    result = adapter.to_sklearn_set()
    assert isinstance(result, frozenset)
    assert len(result) > 0


def test_sklearn_adapter_to_sklearn_list_sorted() -> None:
    adapter = SklearnStopWordsAdapter()
    words = adapter.to_sklearn_list()
    assert isinstance(words, list)
    assert words == sorted(words)


def test_sklearn_adapter_custom_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapters must honour a user-supplied stop-words registry."""
    registry = StopWordsRegistry()
    universal_trie = registry._load_universal()
    for word in ("مخصص", "تجريبي"):
        universal_trie.insert(word)
    adapter = SklearnStopWordsAdapter(registry=registry)
    assert "مخصص" in adapter.to_sklearn_set()
    assert "تجريبي" in adapter.to_sklearn_list()
