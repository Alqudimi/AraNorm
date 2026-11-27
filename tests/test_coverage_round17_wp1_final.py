"""Round 17 WP1 final gap-closure tests.

These tests target the last reachable partial branches and missing lines
identified in the final coverage audit (26 partials / 13 missing stmts).
Each test exercises a branch that was previously only partially covered.
"""

from __future__ import annotations

import importlib.metadata as metadata
from unittest import mock

import pytest

from aranorm import PipelineConfig, StopWordsConfig
from aranorm.core.config import Preset
from aranorm.utils.language_detector import LanguageDetector


class TestLanguageDetectorArabiziAndEmpty:
    """Close language_detector L169->L170 and L300-L303 arabizi branches."""

    def test_detect_detailed_empty_string_returns_unknown(self) -> None:
        detector = LanguageDetector()
        result = detector.detect_detailed("")
        assert result.label == "unknown"
        assert result.arabic_ratio == 0.0
        assert result.confidence == 0.0

    def test_detect_detailed_all_whitespace_returns_unknown(self) -> None:
        detector = LanguageDetector()
        result = detector.detect_detailed("   \t\n   ")
        assert result.label == "unknown"

    def test_detect_detailed_symbols_only_total_zero_branch(self) -> None:
        """L169->L170: text contains non-whitespace characters but none are
        arabic or latin, so total becomes zero after the char-class loop."""
        detector = LanguageDetector()
        result = detector.detect_detailed("؟؟!...###")
        assert result.label == "unknown"
        assert result.char_count == 9

    def test_arabizi_detected_when_latin_ratio_exceeds_arabic(self) -> None:
        """Arabizi branch L300->L301->L302 needs latin_ratio > arabic_ratio
        while arabizi_score >= threshold. Mixed latin + Arabic letters text
        with digit-heavy latin words pushes the arabizi score up."""
        detector = LanguageDetector(arabizi_threshold=0.1)
        # "3a2ol sh7oob" style arabizi with some Arabic letters keeps
        # latin_ratio dominant while raising the arabizi score.
        result = detector.detect_detailed("3a2ol sh7oob 9a3ed 3andek a7ki")
        assert result.label == "arabizi", f"got {result.label!r}"
        assert result.arabizi_score >= 0.1

    def test_arabizi_below_threshold_returns_latin(self) -> None:
        """L300->L301->L303: latin dominant but arabizi score below the
        configured threshold must return latin."""
        detector = LanguageDetector(arabizi_threshold=0.99)
        result = detector.detect_detailed("hello world 3a2ol sh7oob")
        assert result.label == "latin"
        assert result.arabic_ratio < result.latin_ratio

    def test_arabizi_threshold_boundary(self) -> None:
        detector_low = LanguageDetector(arabizi_threshold=0.05)
        detector_high = LanguageDetector(arabizi_threshold=0.95)
        sample = "yalla habibi 5allina nshoof 9adish mumkin 3ala 7isabi"
        r_low = detector_low.detect_detailed(sample)
        r_high = detector_high.detect_detailed(sample)
        assert r_low.arabizi_score >= 0.05
        # Low threshold classifies as arabizi, high as latin
        assert r_low.label == "arabizi"
        assert r_high.label == "latin"


class TestTextAnalyzerEmptyWordGuard:
    """Close text_analyzer L124/L129 'if w' branches (empty cleaned words)."""

    def test_analyze_tokens_cleaning_to_empty_are_filtered(self) -> None:
        """Tokens matching the arabic-word pattern but cleaning to '' hit
        the 'if w' guard inside word/content frequency loops."""
        from aranorm.analysis.text_analyzer import TextAnalyzer

        analyzer = TextAnalyzer(top_n=5)
        # Heavily diacritized tokens are matched by the arabic-word regex
        # but normalize away when cleaned, exercising the emptiness guard.
        weird = "ا\u0640\u0651\u064e\u064b"
        result = analyzer.analyze("كلمة " + weird + " نص")
        assert result.total_words >= 2
        assert "" not in result.word_frequency
        assert "" not in result.content_word_frequency


class TestCliTopWordsAndPluginFailuresBranches:
    """Close cli L228->L232 (top_words non-empty) and L469->L473
    (report.failures non-empty)."""

    def test_analyze_prints_top_words_when_present(self, capsys) -> None:
        from aranorm.cli import main

        rc = main(["analyze", "السلام عليكم أصدقاء أصدقاء أصدقاء ورحمة الله وبركاته"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Top words" in captured.out or "أصدقاء" in captured.out

    def test_analyze_empty_top_words_branch(self, capsys) -> None:
        """Close cli L228->L232: punctuation-only text cleans to an empty
        word frequency map, so stats.top_words is falsy and the print
        block is skipped."""
        from aranorm.cli import main

        rc = main(["analyze", "،،،؟؟؟!!!"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Top words" not in captured.out

    def test_plugins_failure_branch_with_broken_entrypoint(self, capsys, monkeypatch) -> None:
        """Force the plugins handler's failure loop by presenting a broken
        entry point so discover_report returns a non-empty failures tuple."""
        from aranorm.cli import main
        from aranorm.core.registry import PluginDiscoveryFailure, PluginDiscoveryReport

        broken_entry = mock.MagicMock(spec=metadata.EntryPoint)
        broken_entry.name = "broken_plugin"
        broken_entry.value = "broken.path:Cls"
        broken_entry.load.side_effect = ImportError("simulated broken plugin")

        report = PluginDiscoveryReport(
            group="aranorm.processors",
            discovered=(),
            failures=(
                PluginDiscoveryFailure(
                    "broken_plugin",
                    "aranorm.processors",
                    "ImportError",
                    "simulated broken plugin",
                ),
            ),
        )
        with mock.patch("aranorm.core.registry.ProcessorRegistry.discover_report", return_value=report):
            rc = main(["plugins"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "broken_plugin" in captured.out

    def test_plugins_no_failures_branch(self, capsys) -> None:
        """Close cli L469->L473: the 'if report.failures' jump when the
        discovery report has no failures (only the false direction)."""
        from aranorm.cli import main
        from aranorm.core.registry import PluginDiscoveryReport

        report = PluginDiscoveryReport(
            group="aranorm.processors",
            discovered=("spelling",),
            failures=(),
        )
        with mock.patch("aranorm.core.registry.ProcessorRegistry.discover_report", return_value=report):
            rc = main(["plugins"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Failures:" not in captured.out


class TestConfigPresetAndMergeBranches:
    """Close config L155 (SOCIAL_MEDIA preset path), L329->L328 and
    L335->L334 (dict overrides)."""

    def test_social_media_preset_explicit_enum(self) -> None:
        """Constructing with the Preset enum directly exercises L155 fully
        through the non-SPECIAL preset fast path."""
        cfg = PipelineConfig(preset=Preset.SOCIAL_MEDIA)
        assert cfg.clean_mentions is True
        assert cfg.clean_hashtags is False
        assert cfg.stop_words_config is not None
        assert cfg.stop_words_config.remove_filler is True

    def test_from_dict_with_stop_words_dict_override(self) -> None:
        """L329->L328: stop_words_config override supplied as a dict."""
        base = PipelineConfig(
            preset="standard",
            stop_words_config=StopWordsConfig(mode="remove", scope="universal"),
        )
        merged = base.merge({"stop_words_config": {"mode": "remove", "scope": "dialect_aware"}})
        assert merged.stop_words_config.mode == "remove"
        assert merged.stop_words_config.scope == "dialect_aware"

    def test_from_dict_with_resource_limits_dict_override(self) -> None:
        """L335->L334: resource_limits override supplied as a dict."""
        base = PipelineConfig(preset="standard")
        merged = base.merge({"resource_limits": {"max_text_length": 500000}})
        assert merged.resource_limits.max_text_length == 500000


class TestRootExtractorThreeLetterArabicRoot:
    """Close root_extractor L120->L115: matched root must be 3 arabic
    letters (the inner guard)."""

    def test_root_extraction_three_letter_arabic(self) -> None:
        from aranorm.utils.root_extractor import RootExtractor

        extractor = RootExtractor()
        root = extractor.extract("يَكْتُبُونَ")  # write: root is ك ت ب
        assert root is not None
        assert len(root) == 3
        assert all("\u0621" <= c <= "\u064a" for c in root)

    def test_root_extraction_non_word_returns_none(self) -> None:
        from aranorm.utils.root_extractor import RootExtractor

        extractor = RootExtractor()
        assert extractor.extract("1234") is None


class TestDialectNormDeviceGuard:
    """Close dialect_norm L184->L186 (self.device) with a real device
    value using mocked transformers classes."""

    def test_dialect_norm_moves_model_to_device_when_set(self, monkeypatch) -> None:
        from aranorm.stages.dialect_norm import ModelDialectStrategy

        class FakeModel:
            def __init__(self) -> None:
                self._to = None

            def to(self, device: str) -> None:
                self._to = device

            def generate(self, **kw):  # pragma: no cover
                return []

        class FakeModelClass:
            @classmethod
            def from_pretrained(cls, name, **kw):
                del name, kw
                return FakeModel()

        class FakeTokenizerClass:
            @classmethod
            def from_pretrained(cls, name, **kw):  # noqa: ARG003
                del name, kw

                class Tok:
                    def __call__(self, text, **kw):
                        return {"input_ids": [1]}

                    def decode(self, ids, **kw):
                        return ""

                return Tok()

        import sys

        fake_transformers = type(sys)("transformers")
        fake_transformers.AutoModelForSeq2SeqLM = FakeModelClass
        fake_transformers.AutoTokenizer = FakeTokenizerClass
        monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
        stage = ModelDialectStrategy(model_name="fake/model", device="cpu")
        try:
            stage.normalize("شلونك حبيبي")
        except Exception:  # noqa: BLE001 (fake model cannot return text)
            pass
        assert stage._model._to == "cpu"  # type: ignore[attr-defined]

    def test_dialect_norm_without_device_skips_move(self, monkeypatch) -> None:
        """Close dialect_norm L184->L186 (false direction): running the model
        strategy with no device configured must skip the ``.to()`` call."""
        import sys as _sys
        import types

        fake_transformers = types.ModuleType("transformers")

        class FakeModel:  # noqa: D101
            to_called = []

            @classmethod
            def from_pretrained(cls, model_name):  # noqa: ANN001, ARG003
                return cls()

            def to(self, device):  # noqa: ANN001, ARG003
                self.to_called.append(device)

            def generate(self, **kw):  # noqa: ARG003
                return [[0]]

        class FakeTokenizer:  # noqa: D101
            @classmethod
            def from_pretrained(cls, model_name):  # noqa: ANN001, ARG003
                return cls()

            def __call__(self, text, **kw):  # noqa: ANN001, ARG003
                return {"input_ids": [1]}

            def decode(self, ids, **kw):  # noqa: ANN001, ARG003
                return ""

        from aranorm.stages.dialect_norm import ModelDialectStrategy

        fake_transformers.AutoModelForSeq2SeqLM = FakeModel  # type: ignore[attr-defined]
        fake_transformers.AutoTokenizer = FakeTokenizer  # type: ignore[attr-defined]
        monkeypatch.setitem(_sys.modules, "transformers", fake_transformers)
        stage = ModelDialectStrategy("example/model")
        try:
            stage.normalize("شلونك")
        except Exception:  # noqa: BLE001 (fake model may raise downstream)
            pass
        assert stage._model.to_called == []  # type: ignore[attr-defined]


class TestFuzzyMatcherEmptyAndIndexBranches:
    """Close fuzzy_matcher L75/L77 empty ngram guards and L181->L183
    stem/root index branch."""

    def test_jaccard_ngrams_both_empty(self) -> None:
        from aranorm.utils.fuzzy_matcher import jaccard_ngrams

        assert jaccard_ngrams("", "", n=2) == 0.0

    def test_jaccard_ngrams_one_empty(self) -> None:
        from aranorm.utils.fuzzy_matcher import jaccard_ngrams

        assert jaccard_ngrams("كلمة", "", n=2) == 0.0
        assert jaccard_ngrams("", "كلمة", n=2) == 0.0

    def test_stem_and_root_index_populated(self) -> None:
        """L181->L183: building the index with morphology-enabled matcher
        exercises the 'if s' / 'if r' branches."""
        from aranorm.utils.fuzzy_matcher import FuzzyArabicMatcher

        matcher = FuzzyArabicMatcher(use_stem=True, use_root=True)
        matcher.add_many(["مكتبة", "مكتب", "كتب"])
        assert matcher._stem_index  # noqa: SLF001 (index internals)
        assert matcher._root_index  # noqa: SLF001 (index internals)


class TestStreamingFingerprintMismatch:
    """Close streaming L322->exit path: source fingerprint mutation detected
    inside the processing loop (the in-loop re-check at L392).

    The loop calls ``_assert_source_unchanged`` once per batch. The cheap
    ``_file_signature`` (mtime/size) returns equal when untouched, so to
    force the fingerprint comparison we keep the byte content and the file
    size stable while the mtime drifts — a copy-then-replace preserves
    size/bytes but changes mtime, making the loop fall back to the
    SHA-256 check at L319 which then observes the drift at L322.
    """

    def test_source_fingerprint_changed_in_loop_raises(self, tmp_path) -> None:
        from aranorm.core import streaming as streaming_mod
        from aranorm.core.streaming import (
            StreamingSession,
            StreamingSourceChangedError,
        )
        from aranorm import ArabicNormalizationPipeline, PipelineConfig

        source = tmp_path / "source.txt"
        lines = [f"سطر تجريبي رقم {index:04d} مع كلمات عربية إضافية" for index in range(2000)]
        payload = "\n".join(lines) + "\n"
        source.write_text(payload, encoding="utf-8")
        output = tmp_path / "output.txt"
        pipeline = ArabicNormalizationPipeline(PipelineConfig())

        normalizer = StreamingSession(
            pipeline=pipeline,
            source_path=str(source),
            output_path=str(output),
            checkpoint_path=str(tmp_path / "session.checkpoint.json"),
        )

        # The loop's cheap signature check only calls fingerprint_file when
        # the mtime/size signature differs. We keep the file untouched but
        # patch _file_signature so that pre-loop checks succeed while the
        # in-loop check observes a drift, forcing the SHA-256 path and the
        # L322 changed-during-streaming error.
        original_signature = streaming_mod._file_signature(str(source))
        call_count = {"n": 0}

        def _drifting_signature(path):
            call_count["n"] += 1
            dev, ino, size, mtime = original_signature
            # Let the pre-loop store succeed; drift afterwards so the loop
            # re-check falls through to the fingerprint comparison.
            if call_count["n"] <= 2:
                return original_signature
            return (dev, ino, size, mtime + 1_000_000_000)

        original_fingerprint = streaming_mod.fingerprint_file(str(source))
        mutated_fingerprint = "1" * 64
        fp_count = {"n": 0}

        def _drifting_fingerprint(path):
            fp_count["n"] += 1
            return original_fingerprint if fp_count["n"] <= 1 else mutated_fingerprint

        import unittest.mock

        with (
            unittest.mock.patch.object(streaming_mod, "_file_signature", side_effect=_drifting_signature),
            unittest.mock.patch.object(streaming_mod, "fingerprint_file", side_effect=_drifting_fingerprint),
        ):
            with pytest.raises(StreamingSourceChangedError):
                normalizer.run(resume=False)


class TestPipelineStopWordsMetadataBranch:
    """Close pipeline L541->L548 (sw_result is not None metadata path)."""

    def test_process_with_stop_words_populates_metadata(self) -> None:
        from aranorm import ArabicNormalizationPipeline

        config = PipelineConfig(
            preset="standard",
            stop_words_config=StopWordsConfig(
                mode="remove",
                scope="universal",
                remove_filler=True,
            ),
        )
        pipeline = ArabicNormalizationPipeline(config)
        result = pipeline.process("اليوم أنا سعيد جدا جدا")
        assert result.stop_words_found is not None
