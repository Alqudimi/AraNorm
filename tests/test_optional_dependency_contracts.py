"""Deterministic contracts for optional integrations when dependencies are absent."""

from __future__ import annotations

import sys

import pytest

from aranorm.exceptions import IntegrationUnavailableError
from aranorm.integrations import (
    HuggingFaceNormalizer,
    NLTKStopWordsAdapter,
    PandasNormalizer,
    SpacyStopWordsAdapter,
)


def test_pandas_adapter_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", None)

    with pytest.raises(IntegrationUnavailableError, match="pandas is not installed"):
        PandasNormalizer()


def test_huggingface_adapter_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "datasets", None)

    with pytest.raises(IntegrationUnavailableError, match="datasets.*not installed"):
        HuggingFaceNormalizer()


def test_spacy_adapter_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "spacy", None)

    with pytest.raises(IntegrationUnavailableError, match="spaCy is not installed"):
        SpacyStopWordsAdapter().enrich_spacy(object())


def test_nltk_adapter_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "nltk", None)

    with pytest.raises(IntegrationUnavailableError, match="NLTK is not installed"):
        NLTKStopWordsAdapter().register_with_nltk()
