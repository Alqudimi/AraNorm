"""Tests for StopWordsProcessor."""

import pytest

from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.processors.stop_words_processor import StopWordsProcessor


@pytest.fixture(scope="module")
def registry() -> StopWordsRegistry:
    return StopWordsRegistry()


@pytest.fixture
def processor(registry: StopWordsRegistry) -> StopWordsProcessor:
    return StopWordsProcessor(config=StopWordsConfig(), registry=registry)


# ── Remove mode ───────────────────────────────────────────────────────────────


def test_remove_basic(processor: StopWordsProcessor) -> None:
    result = processor.process_detailed("أنا سعيد جداً")
    assert "سعيد" in result.stop_words_removed


def test_remove_stop_words_found(processor: StopWordsProcessor) -> None:
    result = processor.process_detailed("أنا والله يعني سعيد جداً اليوم 😊")
    assert "أنا" in result.stop_words_found


def test_remove_stats_percentage(processor: StopWordsProcessor) -> None:
    result = processor.process_detailed("أنا من في سعيد")
    assert result.stop_words_stats["percentage"] > 0


def test_remove_empty_text(processor: StopWordsProcessor) -> None:
    assert processor.process("") == ""


def test_remove_single_stop_word(processor: StopWordsProcessor) -> None:
    assert processor.process("من") == ""


def test_remove_no_stop_words(processor: StopWordsProcessor) -> None:
    text = "سعيد برلمان محمد"
    assert processor.process(text) == text


# ── Extract mode ──────────────────────────────────────────────────────────────


def test_extract_mode(registry: StopWordsRegistry) -> None:
    cfg = StopWordsConfig(mode="extract", scope="universal")
    proc = StopWordsProcessor(config=cfg, registry=registry)
    result = proc.process_detailed("أنا سعيد من")
    # Extracted text should contain the stop words
    assert "أنا" in result.processed_text or "من" in result.processed_text


# ── Highlight mode ────────────────────────────────────────────────────────────


def test_highlight_mode(registry: StopWordsRegistry) -> None:
    cfg = StopWordsConfig(mode="highlight", scope="msa_only")
    proc = StopWordsProcessor(config=cfg, registry=registry)
    result = proc.process("سعيد من")
    assert "[[" in result and "]]" in result


# ── Count mode ────────────────────────────────────────────────────────────────


def test_count_mode_preserves_text(registry: StopWordsRegistry) -> None:
    text = "أنا سعيد من"
    cfg = StopWordsConfig(mode="count", scope="universal")
    proc = StopWordsProcessor(config=cfg, registry=registry)
    result = proc.process_detailed(text)
    # text should be unchanged
    assert result.processed_text == text
    assert result.stop_words_stats["count"] > 0


# ── Dialect-aware ─────────────────────────────────────────────────────────────


def test_dialect_aware_egy(registry: StopWordsRegistry) -> None:
    cfg = StopWordsConfig(
        mode="remove",
        scope="dialect_aware",
        dialects=frozenset(["EGY"]),
    )
    proc = StopWordsProcessor(config=cfg, registry=registry)
    result = proc.process("أنا كده سعيد")
    assert "سعيد" in result
    assert "كده" not in result


# ── Custom stop words ─────────────────────────────────────────────────────────


def test_custom_stop_words(registry: StopWordsRegistry) -> None:
    cfg = StopWordsConfig(
        mode="remove",
        scope="custom",
        custom_stop_words=frozenset(["سلام", "مرحبا"]),
    )
    proc = StopWordsProcessor(config=cfg, registry=registry)
    result = proc.process("سلام أهلاً مرحبا عالم")
    assert "سلام" not in result
    assert "مرحبا" not in result
    assert "عالم" in result


# ── Excluded stop words ───────────────────────────────────────────────────────


def test_excluded_stop_words(registry: StopWordsRegistry) -> None:
    cfg = StopWordsConfig(
        mode="remove",
        scope="msa_only",
        excluded_stop_words=frozenset(["من"]),
    )
    proc = StopWordsProcessor(config=cfg, registry=registry)
    result = proc.process("أنا سعيد من")
    assert "من" in result


# ── Preserve prepositions ─────────────────────────────────────────────────────


def test_preserve_prepositions(registry: StopWordsRegistry) -> None:
    cfg = StopWordsConfig(mode="remove", scope="universal", preserve_prepositions=True)
    proc = StopWordsProcessor(config=cfg, registry=registry)
    result = proc.process("ذهبت إلى المدرسة")
    assert "إلى" in result


# ── Filler removal ────────────────────────────────────────────────────────────


def test_remove_filler(registry: StopWordsRegistry) -> None:
    cfg = StopWordsConfig(mode="remove", scope="universal", remove_filler=True)
    proc = StopWordsProcessor(config=cfg, registry=registry)
    result = proc.process("يعني سعيد جداً")
    assert "يعني" not in result
    assert "سعيد" in result


# ── Internet tokens ───────────────────────────────────────────────────────────


def test_remove_internet(registry: StopWordsRegistry) -> None:
    cfg = StopWordsConfig(mode="remove", scope="universal", remove_internet=True)
    proc = StopWordsProcessor(config=cfg, registry=registry)
    result = proc.process("شوف lol www")
    assert "lol" not in result
    assert "www" not in result


# ── Numbers ───────────────────────────────────────────────────────────────────


def test_remove_numbers(registry: StopWordsRegistry) -> None:
    cfg = StopWordsConfig(mode="remove", scope="universal", remove_numbers=True)
    proc = StopWordsProcessor(config=cfg, registry=registry)
    result = proc.process("لدي 5 كتب")
    assert "5" not in result
    assert "كتب" in result


# ── StopWordsResult fields ────────────────────────────────────────────────────


def test_result_has_all_fields(processor: StopWordsProcessor) -> None:
    r = processor.process_detailed("أنا سعيد من")
    assert hasattr(r, "original_text")
    assert hasattr(r, "stop_words_removed")
    assert hasattr(r, "stop_words_found")
    assert hasattr(r, "stop_words_stats")
    assert hasattr(r, "stop_words_by_category")
    assert hasattr(r, "stop_words_by_dialect")
    assert hasattr(r, "applied_stop_words_steps")
