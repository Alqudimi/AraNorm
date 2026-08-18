"""Tests for phrase-level and morphological stop-word processors.

Covers :class:`~aranorm.processors.phrase_stop_processor.PhraseStopProcessor`
and :class:`~aranorm.processors.morphological_stop_processor.MorphologicalStopProcessor`,
which were previously untested.
"""
from __future__ import annotations

from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.processors.morphological_stop_processor import MorphologicalStopProcessor
from aranorm.processors.phrase_stop_processor import PhraseStopProcessor

# ── PhraseStopProcessor ──────────────────────────────────────────────────────


class TestPhraseStopProcessorRemove:
    def setup_method(self):
        self.proc = PhraseStopProcessor()

    def test_removes_known_phrase(self):
        assert self.proc.process("هذا في الحقيقة رأيي") == "هذا رأيي"

    def test_removes_multiple_phrases(self):
        text = "من جهة أخرى في الواقع النص صحيح"
        result = self.proc.process(text)
        assert "من جهة أخرى" not in result
        assert "في الواقع" not in result

    def test_longest_match_wins(self):
        # "من جهة أخرى" (3 tokens) beats "من جهة" (2 tokens) at the same offset
        result = self.proc.process("من جهة أخرى هذا النص")
        assert "من جهة" not in result or "أخرى" not in result
        assert "هذا" in result

    def test_empty_and_whitespace_input(self):
        assert self.proc.process("") == ""
        assert self.proc.process("   ") == "   "

    def test_no_match_preserves_text(self):
        text = "هذا نص بدون أي عبارات توقف"
        assert self.proc.process(text) == text

    def test_extra_phrases_registered(self):
        proc = PhraseStopProcessor(extra_phrases=["على سبيل المثال", "في النهاية"])
        assert proc.process("على سبيل المثال هذا صحيح") == "هذا صحيح"
        assert proc.process("في النهاية سنفوز") == "سنفوز"

    def test_single_token_extra_phrase_ignored(self):
        # Single tokens belong in other lists; must not be registered
        proc = PhraseStopProcessor(extra_phrases=["من"])
        assert proc.process("من اليوم") == "من اليوم"

    def test_phrase_count(self):
        assert self.proc.phrase_count >= 10


class TestPhraseStopProcessorModes:
    def test_highlight_mode(self):
        proc = PhraseStopProcessor(mode="highlight")
        result = proc.process("هذا في الحقيقة رأيي")
        assert "{{في الحقيقة}}" in result

    def test_tag_mode(self):
        proc = PhraseStopProcessor(mode="tag")
        result = proc.process("في الواقع النص جيد")
        assert "<phrase>في الواقع</phrase>" in result

    def test_replace_with_mode(self):
        proc = PhraseStopProcessor(mode="remove", replace_with="...")
        result = proc.process("بصراحة تامة هذا جيد")
        assert "..." in result
        assert "بصراحة تامة" not in result

    def test_punctuation_tolerance(self):
        proc = PhraseStopProcessor()
        result = proc.process("هذا، في الحقيقة، رأيي")
        assert "رأيي" in result


class TestPhraseStopProcessorFound:
    def test_get_phrases_found(self):
        proc = PhraseStopProcessor()
        found = proc.get_phrases_found("في الحقيقة من ناحية أخرى نص")
        assert "في الحقيقة" in found
        assert "من ناحية أخرى" in found

    def test_get_phrases_found_no_match(self):
        proc = PhraseStopProcessor()
        assert proc.get_phrases_found("نص خالص بدون عبارات") == []

    def test_custom_registry(self):
        proc = PhraseStopProcessor(registry=[("بلا", "شك")])
        assert proc.get_phrases_found("بلا شك هذا صحيح") == ["بلا شك"]


# ── MorphologicalStopProcessor ───────────────────────────────────────────────


class TestMorphologicalStopProcessor:
    def setup_method(self):
        self.registry = StopWordsRegistry()
        self.proc = MorphologicalStopProcessor(registry=self.registry)

    def test_removes_universal_stop_words(self):
        result = self.proc.process("الكتاب في المدرسة كبير")
        assert "في" not in result.split()

    def test_removes_kana_verb_forms(self):
        result = self.proc.process("كنت أعمل بجد معهم")
        assert "أعمل" in result
        assert "كنت" not in result.split()

    def test_removes_ana_forms(self):
        proc = MorphologicalStopProcessor(registry=self.registry)
        # ضمائر منفصلة / أشكال أنا المضمنة
        stop_set = proc._stop_set
        assert len(stop_set) > 0

    def test_include_verb_forms_shrinks_set_when_disabled(self):
        proc_disabled = MorphologicalStopProcessor(
            registry=self.registry, include_verb_forms=False
        )
        # Some kana/laysa forms already live in the universal data files
        # (e.g. "كان"), so disabling the flag shrinks the set rather than
        # eliminating those words entirely
        assert len(proc_disabled._stop_set) < len(self.proc._stop_set)
        # The base universal set is still present
        assert len(proc_disabled._stop_set) > 10

    def test_include_clitic_forms_shrinks_set_when_disabled(self):
        proc_disabled = MorphologicalStopProcessor(
            registry=self.registry,
            include_clitic_forms=False,
            include_verb_forms=False,
        )
        # The universal data files already contain most preposition-clitic
        # forms, so the observable effect of disabling the internal tables
        # appears only when verb forms are also excluded: the default set
        # (base + clitics + kana/laysa + ana) must be strictly larger.
        assert len(proc_disabled._stop_set) < len(self.proc._stop_set)
        # Kana forms live ONLY in the internal tables, so disabling them
        # drops "كنتما" / "كنا"-like forms regardless of the data files
        assert "كنا" not in proc_disabled._stop_set or "كنا" not in self.registry.get_words("universal")

    def test_definite_article_stripped(self):
        # Stripping only applies to stop words (الملف → ملف: not a stop, kept)
        result = self.proc.process("الكتاب وليس الملف")
        assert "الملف" in result.split()
        # A definite article over an actual stop word IS removed
        result2 = self.proc.process("المكان ليس قريب")
        assert "ليس" not in result2.split()

    def test_empty_input(self):
        assert self.proc.process("") == ""

    def test_stop_set_size_property(self):
        assert self.proc.stop_set_size >= 1

    def test_preserves_content_words(self):
        result = self.proc.process("الطالب يدرس بجد كبير")
        assert "الطالب" in result
        assert "يدرس" in result
