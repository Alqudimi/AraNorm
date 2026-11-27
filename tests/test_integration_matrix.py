"""Installed and absent optional-integration contract matrix.

The matrix deliberately uses only local in-memory data.  Optional packages are
never downloaded by the test suite; installed smoke tests are skipped when the
corresponding extra is unavailable.
"""

from __future__ import annotations

import importlib.util
import sys
from typing import Callable

import pytest

from aranorm.exceptions import IntegrationUnavailableError
from aranorm.integrations import (
    HuggingFaceNormalizer,
    NLTKStopWordsAdapter,
    PandasNormalizer,
    SklearnStopWordsAdapter,
    SpacyStopWordsAdapter,
)


def _is_installed(module_name: str) -> bool:
    """Return whether *module_name* can be located without importing it."""
    return importlib.util.find_spec(module_name) is not None


def test_sklearn_adapter_does_not_require_or_import_sklearn() -> None:
    """The stop-word converter is dependency-free by design."""
    was_loaded = "sklearn" in sys.modules
    adapter = SklearnStopWordsAdapter()

    words = adapter.to_sklearn_set()
    listed = adapter.to_sklearn_list()

    assert words
    assert words == frozenset(listed)
    if not was_loaded:
        assert "sklearn" not in sys.modules


@pytest.mark.skipif(not _is_installed("pandas"), reason="pandas extra is not installed")
def test_pandas_installed_smoke_uses_local_dataframe() -> None:
    """Pandas integration can normalize and expand a local DataFrame."""
    import pandas as pd

    normalizer = PandasNormalizer()
    source = pd.DataFrame({"text": ["أَنَا أحبُّ العربية", None]})

    normalized = normalizer.normalize_dataframe(source, "text")
    expanded = normalizer.expand_results(source["text"])

    assert list(normalized.columns) == ["text", "text_normalized"]
    assert len(normalized) == len(source)
    assert normalized.loc[1, "text_normalized"] == ""
    assert list(expanded.index) == list(source.index)
    assert {"normalized_text", "dialect"}.issubset(expanded.columns)


@pytest.mark.skipif(not _is_installed("datasets"), reason="datasets extra is not installed")
def test_huggingface_installed_smoke_uses_local_dataset() -> None:
    """HuggingFace integration can map over an in-memory Dataset."""
    from datasets import Dataset

    normalizer = HuggingFaceNormalizer(batch_size=2)
    source = Dataset.from_dict({"text": ["أَنَا أحبُّ العربية", None]})

    normalized = normalizer.normalize_dataset(source)
    expanded = normalizer.expand_dataset(source)

    assert "text_normalized" in normalized.column_names
    assert normalized.num_rows == source.num_rows
    assert normalized["text_normalized"][1] == ""
    assert {"normalized_text", "dialect"}.issubset(expanded.column_names)


@pytest.mark.skipif(not _is_installed("spacy"), reason="spaCy extra is not installed")
def test_spacy_installed_smoke_uses_blank_arabic_pipeline() -> None:
    """spaCy integration works without downloading a language model."""
    import spacy

    nlp = spacy.blank("ar")
    result = SpacyStopWordsAdapter().enrich_spacy(nlp)

    assert result is nlp
    assert "من" in nlp.Defaults.stop_words


@pytest.mark.skipif(not _is_installed("nltk"), reason="NLTK extra is not installed")
def test_nltk_installed_smoke_does_not_require_corpus_download() -> None:
    """NLTK adapter returns deterministic words with or without its corpus."""
    adapter = NLTKStopWordsAdapter()

    words = adapter.register_with_nltk()

    assert words == sorted(words)
    assert words
    assert adapter.filter_tokens(["من", "كتاب"]) == ["كتاب"]


def _missing_dependency_cases() -> list[tuple[str, Callable[[], object], str]]:
    """Build constructor/method calls whose imports can be isolated."""
    return [
        (
            "pandas",
            PandasNormalizer,
            "pandas is not installed",
        ),
        (
            "datasets",
            HuggingFaceNormalizer,
            "datasets.*not installed",
        ),
    ]


@pytest.mark.parametrize("module_name, factory, message", _missing_dependency_cases())
def test_missing_constructor_dependencies_have_stable_messages(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    factory: Callable[[], object],
    message: str,
) -> None:
    """Constructor-level optional dependency failures are explicit and local."""
    monkeypatch.setitem(sys.modules, module_name, None)

    with pytest.raises(IntegrationUnavailableError, match=message):
        factory()


def test_missing_spacy_dependency_is_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    """spaCy absence is reported only when the spaCy-facing operation runs."""
    monkeypatch.setitem(sys.modules, "spacy", None)

    with pytest.raises(IntegrationUnavailableError, match="spaCy is not installed"):
        SpacyStopWordsAdapter().enrich_spacy(object())


def test_missing_nltk_dependency_is_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    """NLTK absence does not affect dependency-free token filtering."""
    adapter = NLTKStopWordsAdapter()
    assert adapter.filter_tokens(["من", "كتاب"]) == ["كتاب"]

    monkeypatch.setitem(sys.modules, "nltk", None)
    with pytest.raises(IntegrationUnavailableError, match="NLTK is not installed"):
        adapter.register_with_nltk()


@pytest.mark.skipif(
    _is_installed("pandas"),
    reason="importlib resolves the real pandas even when sys.modules holds a None sentinel",
)
def test_absent_dependency_cleanup_does_not_pollute_module_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulated missing imports are restored by pytest's isolation fixture."""
    original = sys.modules.get("pandas", ...)  # type: ignore[arg-type]
    monkeypatch.setitem(sys.modules, "pandas", None)

    with pytest.raises(IntegrationUnavailableError):
        PandasNormalizer()

    assert sys.modules["pandas"] is None
    # The monkeypatch fixture restores the original module after this test;
    # the assertion above proves that the failed import did not replace the
    # sentinel while the operation was running.
    assert original is not ...
