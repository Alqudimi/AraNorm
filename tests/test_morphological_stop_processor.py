"""Contract tests for morphology-aware stop-word processing."""

from __future__ import annotations

from aranorm.core.base import ProcessorContext
from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.processors.morphological_stop_processor import MorphologicalStopProcessor


class StubRegistry(StopWordsRegistry):
    """Small deterministic registry for processor contract tests."""

    def get_words(self, scope: str = "universal", dialect: str | None = None):
        if scope == "universal":
            return {"هذا", "من"}
        return set()


def test_removes_verb_clitic_and_pronoun_forms_with_punctuation() -> None:
    processor = MorphologicalStopProcessor(registry=StubRegistry())

    text = "كنتُ أعمل بجد معهم، وأنا أتعلم"

    assert processor.process(text) == "أعمل بجد أتعلم"


def test_definite_article_variant_is_checked_after_raw_form() -> None:
    processor = MorphologicalStopProcessor(registry=StubRegistry())

    assert processor.process("المن كتاب") == "كتاب"
    assert processor.process("الكان حاضر") == "حاضر"


def test_flags_control_clitic_and_verb_expansion() -> None:
    no_clitics = MorphologicalStopProcessor(
        registry=StubRegistry(),
        include_clitic_forms=False,
        include_verb_forms=True,
    )
    no_verbs = MorphologicalStopProcessor(
        registry=StubRegistry(),
        include_clitic_forms=True,
        include_verb_forms=False,
    )

    assert no_clitics.process("فيه كان كتاب") == "فيه كتاب"
    assert no_verbs.process("فيه كان كتاب") == "كان كتاب"


def test_pronoun_forms_are_always_included_and_registry_is_used() -> None:
    processor = MorphologicalStopProcessor(
        registry=StubRegistry(),
        include_clitic_forms=False,
        include_verb_forms=False,
    )

    assert processor.process("أنا هذا من فيه كان كتاب") == "فيه كان كتاب"
    assert processor.stop_set_size >= 1


def test_context_records_processing_step() -> None:
    context = ProcessorContext()
    processor = MorphologicalStopProcessor(registry=StubRegistry())

    assert processor.process("هذا نص", context) == "نص"
    assert processor.name in context.applied_steps


def test_empty_and_whitespace_inputs_are_stable() -> None:
    processor = MorphologicalStopProcessor(registry=StubRegistry())

    assert processor.process("") == ""
    assert processor.process("   ") == "   "
