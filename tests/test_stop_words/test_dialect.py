"""Tests for DialectStopProcessor and ArabiziStopProcessor."""

import pytest

from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.processors.arabizi_stop_processor import ArabiziStopProcessor
from aranorm.processors.dialect_stop_processor import DialectStopProcessor
from aranorm.processors.internet_stop_processor import InternetStopProcessor


@pytest.fixture(scope="module")
def registry() -> StopWordsRegistry:
    return StopWordsRegistry()


# ── DialectStopProcessor ──────────────────────────────────────────────────────


def test_dialect_egy_removes_keda(registry: StopWordsRegistry) -> None:
    proc = DialectStopProcessor(dialects=["EGY"], registry=registry)
    result = proc.process("أنا كده سعيد")
    assert "كده" not in result
    assert "سعيد" in result


def test_dialect_glf_removes_alhin(registry: StopWordsRegistry) -> None:
    proc = DialectStopProcessor(dialects=["GLF"], registry=registry)
    result = proc.process("الحين سعيد")
    assert "الحين" not in result
    assert "سعيد" in result


def test_dialect_combined_egy_glf(registry: StopWordsRegistry) -> None:
    """Both EGY and GLF words should be removed."""
    proc = DialectStopProcessor(dialects=["EGY", "GLF"], registry=registry)
    result = proc.process("أنا كده الحين سعيد")
    assert "سعيد" in result
    assert "كده" not in result
    assert "الحين" not in result


def test_dialect_unknown_code(registry: StopWordsRegistry) -> None:
    """Unknown dialect code should not crash; just uses MSA + empty dialect."""
    proc = DialectStopProcessor(dialects=["ZZZ"], registry=registry)
    result = proc.process("أنا سعيد")
    assert "سعيد" in result


def test_dialect_empty_text(registry: StopWordsRegistry) -> None:
    proc = DialectStopProcessor(dialects=["EGY"], registry=registry)
    assert proc.process("") == ""


def test_dialect_msa_words_always_removed(registry: StopWordsRegistry) -> None:
    """MSA stop words should be removed regardless of dialect choice."""
    proc = DialectStopProcessor(dialects=["EGY"], registry=registry)
    result = proc.process("أنا من سعيد")
    assert "أنا" not in result
    assert "من" not in result
    assert "سعيد" in result


# ── ArabiziStopProcessor ─────────────────────────────────────────────────────


def test_arabizi_removes_2na(registry: StopWordsRegistry) -> None:
    proc = ArabiziStopProcessor(registry=registry)
    result = proc.process("2na 3ndy 7aga")
    assert "2na" not in result
    assert "3ndy" not in result


def test_arabizi_keeps_non_stop(registry: StopWordsRegistry) -> None:
    proc = ArabiziStopProcessor(registry=registry)
    result = proc.process("2na 3ndy 7aga")
    assert "7aga" in result


def test_arabizi_empty(registry: StopWordsRegistry) -> None:
    proc = ArabiziStopProcessor(registry=registry)
    assert proc.process("") == ""


# ── InternetStopProcessor ─────────────────────────────────────────────────────


def test_internet_removes_lol(registry: StopWordsRegistry) -> None:
    proc = InternetStopProcessor(registry=registry)
    result = proc.process("شوف الموقع www.example.com lol")
    assert "lol" not in result
    assert "www.example.com" not in result
    assert "شوف" in result


def test_internet_removes_http(registry: StopWordsRegistry) -> None:
    proc = InternetStopProcessor(registry=registry)
    result = proc.process("تفضل https://example.com")
    assert "https://example.com" not in result
    assert "تفضل" in result


def test_internet_removes_omg_btw(registry: StopWordsRegistry) -> None:
    proc = InternetStopProcessor(registry=registry)
    result = proc.process("omg btw أنا هنا")
    assert "omg" not in result
    assert "btw" not in result
