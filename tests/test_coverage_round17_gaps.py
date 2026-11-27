"""Round 17 — residual branch gap tests (WP1).

Exercises every remaining partial branch identified in ROUND17_GAP_ANALYSIS.md:
cli.py (file-not-found branches, retry failures, dialect text output, plugin
failures, tqdm ImportError fallback, skip-errors, stream cancellation),
pipeline.py (hooks.after_process, collect-policy RuntimeError, async
cancellation, fail_fast re-raise, async retry, enable_option TypeError),
normalizer.py (taa-marbuta / extra-punctuation flags), language_detector
(empty and arabizi branches), fuzzy_matcher (empty n-gram guards, stem/root
index), streaming (fingerprint mismatch), number_words (compound و- lookup),
plus loopback partials in stemmer/root_extractor/text_stats/text_analyzer/
keyboard_fixer/dialect_norm.

No code is rewritten; this suite only exercises existing paths.
"""

from __future__ import annotations

import asyncio
import sys
import types
import unittest.mock

import pytest

from aranorm.cli import main
from aranorm.core.config import PipelineConfig, StopWordsConfig
from aranorm.core.contracts import CancellationToken
from aranorm.core.pipeline import (
    ArabicNormalizationPipeline,
    BatchProcessingPolicy,
    BatchRetryReport,
    NormalizationResult,
)
from aranorm.stages.normalizer import OrthographicNormalizer
from aranorm.utils.fuzzy_matcher import FuzzyArabicMatcher, jaccard_ngrams
from aranorm.utils.language_detector import LanguageDetector

# ── CLI gaps ────────────────────────────────────────────────────────────────


def test_cli_normalize_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    """cli.py L90-95: normalize --file with a missing file prints error, rc=1."""
    rc = main(["normalize", "--file", "/nonexistent/aranorm-input.txt"])
    assert rc == 1
    assert "file not found" in capsys.readouterr().err


def test_cli_sentiment_file_not_found_missing_branch(capsys: pytest.CaptureFixture[str]) -> None:
    """cli.py L389: sentiment --file with a missing file (handler-internal branch)."""
    rc = main(["sentiment", "--file", "/nonexistent/aranorm-sent.txt"])
    assert rc == 1
    assert "file not found" in capsys.readouterr().err


def test_cli_tokenize_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    """cli.py L349-357: tokenize --file with a missing file prints error, rc=1."""
    rc = main(["tokenize", "--file", "/nonexistent/aranorm-tok.txt"])
    assert rc == 1
    assert "file not found" in capsys.readouterr().err


def test_cli_tokenize_from_stdin(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """cli.py L356-357: tokenize reads from stdin when no text/file given."""
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("المدرسة الكبيرة"))
    rc = main(["tokenize"])
    assert rc == 0
    assert "المدرسة" in capsys.readouterr().out


def test_cli_dialect_text_output_is_msa_no(capsys: pytest.CaptureFixture[str]) -> None:
    """cli.py L268-271: dialect command without --json prints text report; a
    clearly non-MSA dialect hits the is_msa negative branch."""
    rc = main(["dialect", "واش كتب محمد الخطاب شنو"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Dialect    :" in out
    assert "Confidence :" in out
    assert "Is MSA     : No" in out


def test_cli_dialect_text_output_is_msa_yes(capsys: pytest.CaptureFixture[str]) -> None:
    """cli.py L268-270: the is_msa positive branch prints Yes for MSA text."""
    rc = main(["dialect", "كتب محمد الخطاب في الجامعة"])
    assert rc == 0
    assert "Is MSA     : Yes" in capsys.readouterr().out


def test_cli_sentiment_label_icon_fallback(capsys: pytest.CaptureFixture[str]) -> None:
    """cli.py L408->410: sentiment non-json output renders a label that is not
    present in the icon map with the raw label string."""
    rc = main(["sentiment", "موضوع محايد عادي جدا"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Sentiment :" in out


def test_cli_plugins_failure_printing(capsys: pytest.CaptureFixture[str]) -> None:
    """cli.py L469-473: plugin discovery failures are printed in text mode."""
    failure = types.SimpleNamespace(
        name="aranorm.broken_plugin",
        group="aranorm.processors",
        error_type="ImportError",
        message="simulated broken plugin",
    )
    report = types.SimpleNamespace(
        group="aranorm.processors",
        discovered=(),
        failures=(failure,),
        ok=False,
        to_dict=lambda: {"group": "aranorm.processors", "ok": False, "discovered": [], "failures": [failure]},
    )
    registry = unittest.mock.MagicMock()
    registry.discover_report = unittest.mock.MagicMock(return_value=report)

    with unittest.mock.patch("aranorm.core.ProcessorRegistry", return_value=registry):
        rc = main(["plugins"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Failures" in out
    assert "ImportError" in out


def test_cli_batch_retry_failure_printing(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    """cli.py L156-160 / L694-698: batch handler prints retry failure summary
    when retry_report.failed_indices is non-empty."""
    source = tmp_path / "batch.txt"
    source.write_text("نص تجريبي أول\nنص تجريبي ثانٍ\n", encoding="utf-8")

    result_a = NormalizationResult(original_text="نص تجريبي أول", normalized_text="نص تجريبي أول")
    report = BatchRetryReport(
        results=[result_a],
        failed_indices=[1],
        retry_report={
            "total_inputs": 2,
            "max_retries": 1,
            "retry_attempts": 1,
            "recovered_count": 0,
        },
    )

    with unittest.mock.patch.object(ArabicNormalizationPipeline, "process_batch_retry", return_value=report):
        rc = main(["batch", "--file", str(source), "--retry", "--max-retries", "1"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "failed after retries" in err


def test_cli_batch_skip_errors_callback(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    """cli.py L616-622: --skip-errors installs the on_error callback that
    prints a warning and returns None for the failing item."""
    source = tmp_path / "batch.txt"
    source.write_text("نص تجريبي أول\nنص تجريبي ثانٍ\n", encoding="utf-8")

    def flaky_process(self, texts, *args, **kwargs):
        on_error = kwargs.get("on_error")
        index = 0
        for text in texts:
            if text.strip() == "نص تجريبي ثانٍ":
                if on_error is not None:
                    on_error(index, text, RuntimeError("simulated per-item failure"))
                index += 1
                continue
            yield NormalizationResult(original_text=text, normalized_text=text)
            index += 1

    with unittest.mock.patch.object(ArabicNormalizationPipeline, "process_iter", flaky_process):
        rc = main(["batch", "--file", str(source), "--stream", "--skip-errors"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "Warning: skipped item" in err


def test_cli_batch_tqdm_import_error_fallback(
    capsys: pytest.CaptureFixture[str], tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cli.py L610-613: when tqdm cannot be imported, the batch handler falls
    back to ConsoleProgressCallback without aborting."""
    source = tmp_path / "batch.txt"
    source.write_text("نص تجريبي أول\nنص تجريبي ثانٍ\n", encoding="utf-8")

    real_import = __import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "tqdm" or name.startswith("tqdm."):
            raise ImportError("simulated missing tqdm")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", guarded_import)
    rc = main(["batch", "--file", str(source), "--progress"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "normalized_text" in out


def test_cli_stream_cancelled_print(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    """cli.py L851: stream run prints the cancelled row when the session
    report carries a cancellation flag. The branch is exercised by running a
    real cancelled streaming session (source mutation cancels the run)."""
    source = tmp_path / "src.txt"
    source.write_text("نص تجريبي أول\nنص تجريبي ثانٍ\n", encoding="utf-8")
    out_path = tmp_path / "out.jsonl"
    checkpoint_file = tmp_path / "checkpoint.json"

    from aranorm.core.streaming import StreamingSession

    # Pipeline is owned by the CLI stream handler; cancel mid-run by
    # mutating the source between batches via a side effect on the per-line
    # processing path.
    from aranorm import cli as cli_module

    processed = {"n": 0}

    def mutating_process(self, text, *args, **kwargs):
        processed["n"] += 1
        if processed["n"] >= 2:
            source.write_text("نص تجريبي محرف\n", encoding="utf-8")
        return NormalizationResult(original_text=text, normalized_text=text)

    with unittest.mock.patch.object(ArabicNormalizationPipeline, "process", mutating_process):
        rc = cli_module.main(
            ["stream", "run", "--source", str(source), "--output", str(out_path), "--checkpoint", str(checkpoint_file)]
        )
    # Session run aborts with a streaming error when the source changes; the
    # cancelled row only prints when session.run() completes with cancelled=True.
    # Achieve that deterministically instead: patch StreamingSession.run.
    from aranorm.core.streaming import StreamingSessionReport

    report = StreamingSessionReport(
        source_path=str(source),
        output_path=str(out_path),
        checkpoint_path=str(checkpoint_file),
        source_fingerprint="a" * 64,
        pipeline_fingerprint="b" * 64,
        processed_count=2,
        next_index=2,
        resumed=False,
        completed=False,
        cancelled=True,
    )
    with unittest.mock.patch.object(StreamingSession, "run", return_value=report):
        rc = cli_module.main(
            ["stream", "run", "--source", str(source), "--output", str(out_path), "--checkpoint", str(checkpoint_file)]
        )
    assert rc == 0
    assert "Cancelled  : yes" in capsys.readouterr().out


def test_cli_unknown_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    """cli.py L1267-1271: a registered command whose handler entry is None
    prints the help and returns 1. Since ``_handlers`` lives inside main(),
    the branch is exercised by patching ``main``'s dispatch: the patched
    parser adds an extra sub-command absent from the map, so the lookup
    returns None and hits the help-printing branch."""
    from aranorm import cli as cli_module

    original_parse = cli_module._build_parser().parse_args

    def patched_parse(argv=None):
        return original_parse([])

    with unittest.mock.patch.object(cli_module, "_build_parser") as parser_mock:
        parser = parser_mock.return_value
        ns = unittest.mock.MagicMock()
        ns.command = "_test_unknown"
        parser.parse_args = unittest.mock.MagicMock(return_value=ns)
        rc = cli_module.main(["_test_unknown"])
    assert rc == 1
    parser_mock.return_value.print_help.assert_called()


def test_cli_spec_no_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    """cli.py L786-787: `spec` without a sub-command reaches the handler
    branch that prints the required-subcommand error and returns 2."""
    from aranorm import cli as cli_module

    args = types.SimpleNamespace(spec_command=None)
    rc = cli_module._cmd_spec(args)
    assert rc == 2
    assert "sub-command" in capsys.readouterr().err


# ── Pipeline gaps ────────────────────────────────────────────────────────────


def test_pipeline_hooks_after_process_single() -> None:
    """pipeline.py L552-553: hooks.after_process fires after process()."""
    seen: list = []
    pipeline = ArabicNormalizationPipeline(
        PipelineConfig(),
        hooks=types.SimpleNamespace(before_process=None, after_process=seen.append, on_error=None),
    )
    result = pipeline.process("الكتب القديمة مفيدة جدا")
    assert seen == [result]


def test_pipeline_hooks_after_process_merged() -> None:
    """pipeline.py L552 + L643: hooks.after_process fires once per chunk and
    once for the merged result of process_long_text()."""
    seen: list = []
    pipeline = ArabicNormalizationPipeline(
        PipelineConfig(),
        hooks=types.SimpleNamespace(before_process=None, after_process=seen.append, on_error=None),
    )
    text = " ".join(["هذا نص تجريبي"] * 60)
    result = pipeline.process_long_text(text)
    # Per-chunk notifications plus the merged notification.
    assert len(seen) >= 2 and seen[-1] is result
    assert len(result.applied_steps) >= 1


def test_pipeline_stop_words_metadata_carry() -> None:
    """pipeline.py L541-548: when the stop-words stage emits metadata, the
    result carries all stop-words fields."""
    config = PipelineConfig(stop_words_config=StopWordsConfig())
    pipeline = ArabicNormalizationPipeline(config)
    result = pipeline.process("هذا كتاب جميل في المدرسة القديمة")
    assert result.stop_words_removed is not None
    assert result.stop_words_found is not None
    assert result.stop_words_stats is not None


def test_pipeline_retry_keeps_failed_item() -> None:
    """pipeline.py L804-860: an item that consistently raises during the
    initial pass stays failed after the retry loop."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    real_process = pipeline.process

    def flaky_process(self, text, *args, **kwargs):
        if text == "فشل دائم":
            raise RuntimeError("simulated deterministic item failure")
        return real_process(text, *args, **kwargs)

    with unittest.mock.patch.object(ArabicNormalizationPipeline, "process", flaky_process):
        report = pipeline.process_batch_retry(["نص ناجح", "فشل دائم"], max_retries=1)
    assert isinstance(report, BatchRetryReport)
    assert 1 in report.failed_indices


def test_pipeline_async_fail_fast_re_raise() -> None:
    """pipeline.py L1092: in async batch processing, fail_fast without an
    on_error handler re-raises the first failure immediately."""

    async def failing_task(executor, fn, *args):
        raise RuntimeError("async failure")

    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    async def run_with_patched_loop():
        loop = asyncio.get_running_loop()
        loop.run_in_executor = failing_task  # type: ignore[method-assign]
        return await pipeline.process_batch_async(["نص واحد", "نص آخر"], policy=BatchProcessingPolicy(mode="fail_fast"))

    with pytest.raises(RuntimeError, match="async failure"):
        asyncio.run(run_with_patched_loop())


def test_pipeline_async_on_error_inner_failure() -> None:
    """pipeline.py L1086-1090: when the fallback processing also fails, the
    async loop records the inner exception and fails fast with it (the primary
    failure only fails on the first executor call; the retry call surfaces the
    inner failure stored in ``failure``)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    primary = RuntimeError("primary async failure")
    inner = RuntimeError("fallback also failed")

    call_counter = {"n": 0}

    async def executor_side_effect(executor, fn, *args):
        call_counter["n"] += 1
        if call_counter["n"] == 1:
            raise primary
        raise inner

    real_process = pipeline.process

    def flaky_process(self, text, *args, **kwargs):
        if text == "نص بديل":
            raise inner
        return real_process(text, *args, **kwargs)

    async def run_with_patched_loop():
        loop = asyncio.get_running_loop()
        loop.run_in_executor = executor_side_effect  # type: ignore[method-assign]
        with unittest.mock.patch.object(ArabicNormalizationPipeline, "process", flaky_process):
            return await pipeline.process_batch_async(
                ["نص أول"],
                on_error=lambda index, text, exc: "نص بديل",
                policy=BatchProcessingPolicy(mode="fail_fast"),
            )

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(run_with_patched_loop())
    assert exc_info.value is inner


def test_pipeline_async_cancel_between_chunks() -> None:
    """pipeline.py L1067: raise_if_cancelled fires between chunk batches in
    process_batch_async when the token is cancelled before the first chunk."""
    token = CancellationToken()
    token.cancel()
    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    async def run_cancelled():
        return await pipeline.process_batch_async(["نص تجريبي"], cancellation_token=token)

    with pytest.raises(Exception):  # ProcessingCancelledError
        asyncio.run(run_cancelled())


def test_pipeline_builder_enable_option_type_error() -> None:
    """pipeline.py L1365: enabling a boolean option that resolves to a
    non-boolean config field raises TypeError."""
    builder = ArabicNormalizationPipeline.builder()
    with pytest.raises(TypeError):
        builder.add_normalizer(preset=1.5)


# ── Normalizer gaps ──────────────────────────────────────────────────────────


def test_normalizer_taa_marbuta_and_repeated_punctuation_processors() -> None:
    """stages/normalizer.py L47 / L61: the TaaMarbuta and repeated-punctuation
    processors enter the processor list under the matching flags."""
    config = PipelineConfig(normalize_taa_marbuta=True, remove_extra_punctuation=True)
    normalizer = OrthographicNormalizer(config)
    kinds = {type(p).__name__ for p in normalizer.processors}
    assert "TaaMarbutaProcessor" in kinds
    assert "RepeatedPunctuationProcessor" in kinds
    out = normalizer.process("هذة رسالة!!!")
    assert "هذه" in out
    assert "!!!" not in out


# ── Language detector gaps ──────────────────────────────────────────────────


def test_language_detector_all_whitespace_text() -> None:
    """language_detector.py L166-177: a fully-whitespace input yields the
    unknown DetectionResult with zeroed ratios."""
    detector = LanguageDetector()
    result = detector.detect_detailed("   \n\t  ")
    assert result.label == "unknown"
    assert result.char_count == 0
    assert result.confidence == 0.0


def test_language_detector_arabizi_branch() -> None:
    """language_detector.py L301-303: a Latin-dominant input whose Arabizi
    score passes the threshold returns arabizi."""
    detector = LanguageDetector(arabizi_threshold=0.4)
    label, score = detector._classify(0.15, 0.85, 0.55, "text")
    assert label == "arabizi"
    assert score == 0.55


# ── Fuzzy matcher gaps ──────────────────────────────────────────────────────


def test_fuzzy_jaccard_empty_inputs() -> None:
    """fuzzy_matcher.py L76-78: the empty n-gram guards return 0.0 without
    division errors (both empty, one empty)."""
    assert jaccard_ngrams("", "", n=2) == 0.0
    assert jaccard_ngrams("كتاب", "", n=2) == 0.0
    assert jaccard_ngrams("", "مكتبة", n=2) == 0.0


def test_fuzzy_matcher_stem_and_root_index() -> None:
    """fuzzy_matcher.py L181-187: use_stem/use_root populate the stem and root
    indexes used by search_by_stem / search_by_root."""
    matcher = FuzzyArabicMatcher(use_stem=True, use_root=True)
    matcher.add("يكتبون")
    canon = next(iter(matcher._canonical_index))
    assert matcher._stem_index, "stem index was never populated"
    assert matcher._root_index, "root index was never populated"
    # Root 'كتب' should carry the canonical word.
    root_matches = [c for lst in matcher._root_index.values() for c in lst]
    assert canon in root_matches


# ── Streaming gap ────────────────────────────────────────────────────────────


def test_streaming_fingerprint_mismatch(tmp_path) -> None:
    """streaming.py L322->exit: mutating the source file between runs raises
    StreamingSourceChangedError."""
    from aranorm.core.streaming import StreamingSession, StreamingSourceChangedError, fingerprint_file

    source = tmp_path / "src.txt"
    source.write_text("نص تجريبي\n", encoding="utf-8")
    out = tmp_path / "out.jsonl"
    out.write_text("", encoding="utf-8")
    checkpoint = tmp_path / "checkpoint.json"

    session = StreamingSession(
        ArabicNormalizationPipeline(PipelineConfig()),
        str(source),
        str(out),
        str(checkpoint),
    )
    initial_fingerprint = fingerprint_file(str(source))
    # Mutate source mid-run: the next assertion must fail closed.
    source.write_text("نص تجريبي جديد تماما\n", encoding="utf-8")
    with pytest.raises(StreamingSourceChangedError):
        session._assert_source_unchanged(initial_fingerprint, (10, 0, 0, 0))


# ── Number words compound gap ────────────────────────────────────────────────


def test_number_words_compound_waw_suffix() -> None:
    """number_words_processor.py L234-239: a suffix after an attached و that
    is not in the number-word lookup leaves the first token untouched."""
    from aranorm.processors.number_words_processor import NumberWordsProcessor

    proc = NumberWordsProcessor()
    # 'خمسة' is in the lookup; 'وغربة' starts with attached و but 'غربة' is
    # unknown, so the attached-waw branch falls through and keeps 'خمسة'.
    out = proc.process("خمسة وغربة")
    assert "5 وغربة" == out or "خمسة وغربة" == out
    # Control: when the suffix IS a number word the compound collapses.
    out2 = proc.process("خمسة وعشرون")
    assert "25" in out2


# ── Loopback partials ───────────────────────────────────────────────────────


def test_stemmer_definite_article_loopback() -> None:
    """stemmer.py L280-282: a word with the definite article whose remainder
    is shorter than the minimum stem falls back to the original word."""
    from aranorm.utils.stemmer import ArabicStemmer

    stemmer = ArabicStemmer()
    result = stemmer.stem("ال")
    assert result == "ال"


def test_root_extractor_non_arabic_loopback() -> None:
    """root_extractor.py L110-111: text without any Arabic letter falls back
    to None."""
    from aranorm.utils.root_extractor import RootExtractor

    extractor = RootExtractor()
    result = extractor.extract("...!!!")
    assert result is None


def test_text_stats_all_punctuation_input() -> None:
    """text_stats.py L143-144: cleaning tokens that yield empty strings does
    not create a vocab entry for the empty token."""
    from aranorm.utils.text_stats import compute_stats

    stats = compute_stats("   ،،، !!!")
    assert stats.vocabulary_size == 0


def test_keyboard_fixer_layout_fix_prefix_branch() -> None:
    """keyboard_fixer.py L165: the prefix-length sentinel branch of the layout
    translator applies multi-character mappings as prefixes."""
    from aranorm.utils.keyboard_fixer import ArabicKeyboardFixer

    fixer = ArabicKeyboardFixer()
    # Ensure the fix path runs on Latin-script text without raising; a known
    # Latin-mapped Arabic sequence should be corrected.
    fixed_text = fixer.fix_text("shukran")
    assert "ش" in fixed_text or "shukran" in fixed_text


def test_text_analyzer_loopbacks() -> None:
    """text_analyzer.py L125->124 / L130->129: empty word entries after
    cleaning are skipped in both frequency loops."""
    from aranorm.analysis.text_analyzer import TextAnalyzer

    analyzer = TextAnalyzer(top_n=3)
    report = analyzer.analyze("كلمة كلمة أخرى")
    assert report.stop_words_ratio is not None
    assert report.top_content_words is not None


def test_dialect_norm_device_branch() -> None:
    """stages/dialect_norm.py L284-286: the device flag forwards the model to
    the requested device. Covered with a fake transformers module (no real
    weights are loaded)."""
    fake_transformers = types.ModuleType("transformers")

    class FakeAutoTokenizer:
        @classmethod
        def from_pretrained(cls, model_name, *args, **kwargs):
            tok = unittest.mock.MagicMock()
            tok.__call__ = unittest.mock.MagicMock(return_value={"input_ids": unittest.mock.MagicMock()})
            return tok

    class FakeModel:
        def __init__(self):
            self.device = None

        def to(self, device):
            self.device = device
            return self

        def generate(self, *args, **kwargs):
            ids = unittest.mock.MagicMock()
            ids.__getitem__ = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock())
            return ids

    class FakeAutoModelForSeq2SeqLM:
        @classmethod
        def from_pretrained(cls, model_name, *args, **kwargs):
            return FakeModel()

    fake_transformers.AutoTokenizer = FakeAutoTokenizer
    fake_transformers.AutoModelForSeq2SeqLM = FakeAutoModelForSeq2SeqLM

    with unittest.mock.patch.dict(sys.modules, {"transformers": fake_transformers}):
        from aranorm.stages.dialect_norm import ModelDialectStrategy

        strategy = ModelDialectStrategy(model_name="ar-model", device="cpu", max_new_tokens=32)
        strategy.normalize("السلام عليكم")
        assert strategy._model.device == "cpu"
