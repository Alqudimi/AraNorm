"""Shared pytest fixtures for the AraNorm test suite."""

from __future__ import annotations

import sys

import pytest


@pytest.fixture(autouse=True)
def _isolate_optional_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep optional-dependency fakes from leaking between tests.

    Test suites such as ``test_coverage_round16_integrations.py`` and
    ``test_coverage_round16_models.py`` inject fake modules (``nltk``,
    ``nltk.corpus``, ``spacy``, ``pandas``, ``datasets``,
    ``camel_tools`` / ``camel_tools.dialectid``, ``transformers``) into
    ``sys.modules`` to simulate a dependency being installed.  This
    function-scoped autouse fixture guarantees a clean slate for every test
    in the suite, including the negative-path contracts in
    ``test_optional_dependency_contracts.py``.
    """
    monkeypatch.delitem(sys.modules, "nltk", raising=False)
    monkeypatch.delitem(sys.modules, "nltk.corpus", raising=False)
    monkeypatch.delitem(sys.modules, "spacy", raising=False)
    monkeypatch.delitem(sys.modules, "pandas", raising=False)
    monkeypatch.delitem(sys.modules, "datasets", raising=False)
    monkeypatch.delitem(sys.modules, "camel_tools", raising=False)
    monkeypatch.delitem(sys.modules, "camel_tools.dialectid", raising=False)
    monkeypatch.delitem(sys.modules, "transformers", raising=False)
