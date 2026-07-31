"""Tests for ContextAwareProcessor."""

import pytest

from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.processors.context_aware_processor import ContextAwareProcessor


@pytest.fixture(scope="module")
def registry() -> StopWordsRegistry:
    return StopWordsRegistry()


def test_negation_true_negation_preserved(registry: StopWordsRegistry) -> None:
    """'لا' before a verb is true negation → keep."""
    proc = ContextAwareProcessor(preserve_negation=True, registry=registry)
    result = proc.process("لا أحب هذا")
    assert "لا" in result


def test_negation_idiomatic_removed(registry: StopWordsRegistry) -> None:
    """'لا شك' is idiomatic; 'لا' should be removed."""
    proc = ContextAwareProcessor(preserve_negation=True, registry=registry)
    result = proc.process("لا شك في ذلك")
    assert "لا" not in result


def test_negation_lam_preserved(registry: StopWordsRegistry) -> None:
    """لم is always a negation marker."""
    proc = ContextAwareProcessor(preserve_negation=True, registry=registry)
    result = proc.process("لم أفعل")
    assert "لم" in result


def test_context_removes_other_stop_words(registry: StopWordsRegistry) -> None:
    """Normal stop words should still be removed."""
    proc = ContextAwareProcessor(preserve_negation=True, registry=registry)
    result = proc.process("أنا سعيد جداً")
    assert "أنا" not in result
    assert "سعيد" in result


def test_emphasis_conditional_removed(registry: StopWordsRegistry) -> None:
    """'إن' before a conditional verb-like word → remove."""
    proc = ContextAwareProcessor(preserve_emphasis=False, registry=registry)
    result = proc.process("إن تحسنوا تحسنوا لأنفسكم")
    assert "إن" not in result


def test_emphasis_preserved_when_enabled(registry: StopWordsRegistry) -> None:
    """'إن' in emphatic use → keep when preserve_emphasis=True."""
    proc = ContextAwareProcessor(preserve_emphasis=True, registry=registry)
    result = proc.process("إن الله غفور رحيم")
    assert "إن" in result


def test_empty_input(registry: StopWordsRegistry) -> None:
    proc = ContextAwareProcessor(registry=registry)
    assert proc.process("") == ""


def test_whitespace_only(registry: StopWordsRegistry) -> None:
    proc = ContextAwareProcessor(registry=registry)
    assert proc.process("   ").strip() == ""
