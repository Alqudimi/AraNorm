"""Contract tests for multi-word stop phrase processing."""

from __future__ import annotations

import pytest

from aranorm.core.base import ProcessorContext
from aranorm.processors.phrase_stop_processor import PhraseStopProcessor


def test_longest_registered_phrase_wins_and_found_is_consistent() -> None:
    processor = PhraseStopProcessor(registry=[("في", "الحقيقة"), ("في", "الحقيقة", "الموضوع")])

    text = "هذا في الحقيقة الموضوع مهم"

    assert processor.process(text) == "هذا مهم"
    assert processor.get_phrases_found(text) == ["في الحقيقة الموضوع"]


def test_punctuation_is_ignored_for_matching_but_preserved_in_marked_modes() -> None:
    processor = PhraseStopProcessor(
        registry=[("من", "جهة", "أخرى")],
        mode="highlight",
    )

    assert processor.process("من جهة أخرى، نكمل") == "{{من جهة أخرى،}} نكمل"

    tagged = PhraseStopProcessor(registry=[("في", "الحقيقة")], mode="tag")
    assert tagged.process("في الحقيقة، رأيي") == "<phrase>في الحقيقة،</phrase> رأيي"


def test_replace_with_is_used_for_remove_mode() -> None:
    processor = PhraseStopProcessor(
        registry=[("إن", "شاء", "الله")],
        replace_with="[PHRASE]",
    )

    assert processor.process("إن شاء الله سنبدأ") == "[PHRASE] سنبدأ"


def test_extra_phrases_do_not_mutate_external_registry() -> None:
    registry = [("في", "الحقيقة")]
    processor = PhraseStopProcessor(
        registry=registry,
        extra_phrases=["من جهة أخرى"],
    )

    assert processor.phrase_count == 2
    assert registry == [("في", "الحقيقة")]
    assert processor.process("في الحقيقة من جهة أخرى") == ""


def test_context_records_processor_execution() -> None:
    context = ProcessorContext()
    processor = PhraseStopProcessor(registry=[("في", "الحقيقة")])

    assert processor.process("هذا في الحقيقة نص", context) == "هذا نص"
    assert processor.name in context.applied_steps


@pytest.mark.parametrize("mode", ["unknown", "remove_with_tag"])
def test_invalid_mode_is_rejected(mode: str) -> None:
    with pytest.raises(ValueError, match="mode"):
        PhraseStopProcessor(mode=mode)


def test_empty_input_is_returned_without_unexpected_tokens() -> None:
    processor = PhraseStopProcessor(registry=[("في", "الحقيقة")])

    assert processor.process("") == ""
    assert processor.process("   ") == "   "


def test_phrase_file_reader_handles_missing_comments_and_singletons(tmp_path) -> None:
    from aranorm.processors.phrase_stop_processor import _read_phrases

    missing = tmp_path / "missing.txt"
    assert _read_phrases(str(missing)) == []

    phrase_file = tmp_path / "phrases.txt"
    phrase_file.write_text("# comment\n\nفي الحقيقة\nمفرد\n من جهة أخرى \n", encoding="utf-8")
    assert _read_phrases(str(phrase_file)) == [("في", "الحقيقة"), ("من", "جهة", "أخرى")]


def test_incomplete_and_unmatched_phrase_candidates_are_not_consumed() -> None:
    processor = PhraseStopProcessor(registry=[("في", "الحقيقة")])

    assert processor.get_phrases_found("في") == []
    assert processor.get_phrases_found("في السر") == []
    assert processor.process("في السر") == "في السر"
