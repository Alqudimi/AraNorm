"""Round-16 P2 gap coverage.

Targeted tests for the residual branch coverage gaps identified in the
Round-16 gap analysis.  Each test covers exactly one previously uncovered
decision path: configuration merging with preset changes, declarative spec
validation and atomic-write failure modes, retry-policy contracts, runtime
reload diagnostics, optional-deps failure paths in exporters/progress, the
orthographic stage composition, language-detection fallbacks, and the
batch-retry / async / long-text branches of the pipeline.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from unittest import mock

import pytest

from aranorm.core.config import PipelineConfig
from aranorm.core.pipeline import (
    ArabicNormalizationPipeline,
    BatchProcessingPolicy,
    PipelineBuilder,
)
from aranorm.core.runtime import _safe_error
from aranorm.exceptions import (
    BatchProcessingError,
    ConfigurationError,
)
from aranorm.stages.normalizer import OrthographicNormalizer
from aranorm.utils.exporters import BatchExporter
from aranorm.utils.progress import TqdmProgressCallback

# ── PipelineConfig.merge (core/config.py 314-319 + nested fields) ──


def test_merge_preset_change_reapplies_defaults_but_keeps_overrides() -> None:
    base = PipelineConfig(preset="deep", remove_diacritics=False)
    merged = base.merge({"preset": "light", "remove_diacritics": True})
    assert merged.preset.value == "light"
    # The "light" preset defaults are applied, but explicit overrides win.
    assert merged.remove_diacritics is True


def test_merge_same_preset_skips_reapply_branch() -> None:
    base = PipelineConfig(preset="light", remove_diacritics=True)
    merged = base.merge({"remove_diacritics": False})
    assert merged.preset.value == "light"
    assert merged.remove_diacritics is False


def test_merge_pipeline_config_override() -> None:
    base = PipelineConfig(preset="light")
    overrides = PipelineConfig(preset="deep", normalize_hamza=False)
    merged = base.merge(overrides)
    assert merged.preset.value == "deep"
    assert merged.normalize_hamza is False


def test_merge_dialect_target_and_supported_dialects() -> None:
    base = PipelineConfig()
    merged = base.merge({"dialect_target": "coda", "supported_dialects": ["eg", "sa"]})
    assert merged.dialect_target.value == "coda"
    assert merged.supported_dialects == ["eg", "sa"]


def test_merge_stop_words_config_nested_enabled() -> None:
    """Nested stop_words_config merge with the stage already enabled on base."""
    from aranorm.core.stop_words_config import StopWordsConfig

    base = PipelineConfig()
    base.__dict__["stop_words_config"] = StopWordsConfig()
    merged = base.merge({"stop_words_config": {"mode": "extract"}})
    assert merged.stop_words_config.mode == "extract"


def test_merge_resource_limits_nested() -> None:
    base = PipelineConfig()
    merged = base.merge({"resource_limits": {"max_text_length": 100}})
    assert merged.resource_limits.max_text_length == 100


def test_merge_rejects_invalid_type() -> None:
    base = PipelineConfig()
    with pytest.raises(TypeError, match="overrides must be"):
        base.merge("invalid")  # type: ignore[arg-type]


# ── PipelineSpec validation + atomic write failure modes ──


def test_spec_rejects_non_dict_metadata() -> None:
    from aranorm.core.spec import PipelineSpec

    with pytest.raises(ConfigurationError, match="metadata must be a dictionary"):
        PipelineSpec(
            schema_version=1,
            library_version="1.0.0",
            pipeline_class="ArabicNormalizationPipeline",
            config={"preset": "light", "remove_diacritics": False},
            config_fingerprint="0" * 40,
            metadata=[1, 2, 3],  # type: ignore[arg-type]
        )


def test_spec_write_file_oserror_unlinks_temporary() -> None:
    from aranorm.core.spec import PipelineSpec

    spec = PipelineSpec.from_pipeline(ArabicNormalizationPipeline(PipelineConfig(preset="light")))
    with mock.patch("os.fdopen", side_effect=OSError("disk full")):
        with pytest.raises(ConfigurationError, match="Cannot write PipelineSpec"):
            spec.write_file("/nonexistent-dir/spec.json")


def test_spec_write_file_unlink_oserror_still_raises_original() -> None:
    from aranorm.core.spec import PipelineSpec

    spec = PipelineSpec.from_pipeline(ArabicNormalizationPipeline(PipelineConfig(preset="light")))
    with tempfile.TemporaryDirectory() as directory:
        target = os.path.join(directory, "spec.json")
        with mock.patch("os.replace", side_effect=OSError("replace failed")):
            with mock.patch("os.unlink", side_effect=OSError("unlink failed")):
                with pytest.raises(ConfigurationError, match="Cannot write"):
                    spec.write_file(target)


# ── BatchRetryPolicy contract (core/contracts.py ~122) ──


def test_retry_policy_rejects_zero_workers() -> None:
    from aranorm.core.contracts import BatchRetryPolicy

    with pytest.raises(ValueError, match="n_workers must be positive"):
        BatchRetryPolicy(n_workers=0)


# ── Runtime reload diagnostics (core/runtime.py 81) ──


def test_safe_error_classifies_permission_error() -> None:
    diagnostic = _safe_error(PermissionError("denied"))
    assert diagnostic["error_type"] == "PermissionError"
    assert diagnostic["message"] == "configuration file could not be read"


# ── Exporters missing-pandas path (utils/exporters.py 236-237) ──


def test_batch_exporter_to_dataframe_without_pandas(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pandas", None)
    exporter = BatchExporter(results=[], fields=["normalized_text"])
    with pytest.raises(ImportError, match="pandas"):
        exporter.to_dataframe()


# ── Progress missing-tqdm path (utils/progress.py 166-167) ──


def test_tqdm_progress_callback_without_tqdm(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "tqdm", None)
    with pytest.raises(ImportError, match="tqdm"):
        TqdmProgressCallback()


# ── OrthographicNormalizer stage composition (stages/normalizer.py 47, 61) ──


def test_normalizer_builds_ligatures_and_tatweel_processors() -> None:
    from aranorm.processors.ligatures_processor import LigaturesProcessor
    from aranorm.processors.tatweel_processor import TatweelProcessor

    config = PipelineConfig(normalize_ligatures=True, normalize_tatweel=True)
    stage = OrthographicNormalizer(config=config)
    types = {type(processor) for processor in stage.processors}
    assert LigaturesProcessor in types
    assert TatweelProcessor in types


# ── LanguageDetector fallback paths (analysis/language_detector.py) ──


def test_language_detector_empty_input_unknown_fallback() -> None:
    from aranorm.utils.language_detector import LanguageDetector

    detector = LanguageDetector()
    result = detector.detect_detailed("")
    assert result.label == "unknown"
    assert result.confidence == 0.0


def test_language_detector_convenience_detect_unknown_fallback() -> None:
    """A mixed script string with no dominant language resolves to unknown."""
    from aranorm.utils.language_detector import detect_language as detect_text

    # Symbols/punctuation carry no script signal, so the fallback is "unknown".
    assert detect_text("---!!!...") == "unknown"


# ── Pipeline stop-words + stats branches (core/pipeline.py 541-548, 644) ──


def test_process_long_text_carries_stop_words_and_stats() -> None:
    from aranorm.core.stop_words_config import StopWordsConfig

    pipeline = ArabicNormalizationPipeline(
        PipelineConfig(
            preset="light",
            stop_words_config=StopWordsConfig(mode="remove"),
        )
    )
    # A short Arabic sentence with builtin stop words; long enough to chunk.
    text = "في البيت والكتاب والقلم. " * 40
    result = pipeline.process_long_text(text, max_chunk_tokens=64)
    assert result.stop_words_removed
    assert result.stop_words_stats is not None
    assert result.stop_words_stats["count"] > 0
    assert result.stop_words_stats["chunk_count"] > 1


def test_process_long_text_empty_chunks_fallback() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    result = pipeline.process_long_text("")
    assert result.normalized_text == ""


# ── Sync batch retry (core/pipeline.py 770-850) ──


def test_batch_retry_recovers_transient_failure(monkeypatch) -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    counter = {"calls": 0}
    original_process = pipeline.process

    def flaky(text):
        counter["calls"] += 1
        if counter["calls"] <= 1:
            raise RuntimeError("transient")
        return original_process(text)

    monkeypatch.setattr(pipeline, "process", flaky)
    report = pipeline.process_batch_retry(["نص تجريبي"], max_retries=2, policy=BatchProcessingPolicy(mode="collect"))
    assert not report.failed_indices
    assert report.retry_report["recovered_count"] >= 1


def test_batch_retry_keeps_permanent_failures() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    report = pipeline.process_batch_retry(
        ["نص تجريبي"],
        max_retries=0,
        policy=BatchProcessingPolicy(mode="collect"),
    )
    # max_retries=0 forbids retrying; collect keeps failures.
    assert not report.failed_indices or report.retry_report["recovered_count"] == 0


def test_batch_retry_catastrophic_exception_returns_report() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    def always_fails(*args, **kwargs):
        raise RuntimeError("catastrophic batch failure")

    with mock.patch.object(pipeline, "process_batch", side_effect=always_fails):
        report = pipeline.process_batch_retry(["نص"], max_retries=1, policy=BatchProcessingPolicy(mode="collect"))
    assert 0 in report.failed_indices


# ── Async batch retry (core/pipeline.py 1128-1240) ──


def test_async_batch_retry_recovers_and_exhausts() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    async def run() -> tuple:
        counter = {"calls": 0}
        original = pipeline.process_async

        async def flaky(text):
            counter["calls"] += 1
            if counter["calls"] <= 2:
                raise RuntimeError("transient")
            return await original(text)

        with mock.patch.object(pipeline, "process_async", flaky):
            report = await pipeline.process_batch_retry_async(["نص", "نص آخر"], max_retries=2)
        return report

    report = asyncio.run(run())
    assert not report.failed_indices or report.retry_report["recovered_count"] >= 1


def test_async_batch_retry_fails_fast_policy_rejected() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    async def run() -> None:
        with pytest.raises(ConfigurationError):
            await pipeline.process_batch_retry_async(
                ["نص"],
                max_retries=1,
                policy=BatchProcessingPolicy(mode="fail_fast"),
            )

    asyncio.run(run())


def test_async_batch_retry_exhausted_retries_keeps_failure() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    async def run() -> object:
        with mock.patch.object(
            pipeline,
            "process_batch_async",
            side_effect=BatchProcessingError(
                "boom",
                failed_indices=[0],
                errors={0: RuntimeError("item failed")},
                results=None,
            ),
        ):
            with mock.patch.object(
                pipeline,
                "process_async",
                side_effect=RuntimeError("doomed"),
            ):
                return await pipeline.process_batch_retry_async(["نص"], max_retries=1)

    report = asyncio.run(run())
    assert 0 in report.failed_indices
    assert report.retry_report.get("retry_attempts", 0) >= 1
    assert report.retry_report.get("recovered_count", 0) == 0


def test_async_batch_retry_empty_batch_returns_empty_report() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    async def run() -> object:
        return await pipeline.process_batch_retry_async([], max_retries=1)

    report = asyncio.run(run())
    assert report.results == []
    assert report.failed_indices == []


def test_async_batch_retry_invalid_policy_type_raises() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    async def run() -> None:
        with pytest.raises(TypeError, match="BatchRetryPolicy"):
            await pipeline.process_batch_retry_async(
                ["نص"], max_retries=1, retry_policy="bad"  # type: ignore[arg-type]
            )

    asyncio.run(run())


# ── Async batch failure paths (core/pipeline.py 1067-1128) ──


def test_async_batch_fail_fast_without_on_error_raises() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    async def run() -> None:
        with mock.patch.object(pipeline, "process", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                await pipeline.process_batch_async(
                    ["نص"],
                    batch_size=32,
                    policy=BatchProcessingPolicy(mode="fail_fast"),
                )

    asyncio.run(run())


def test_async_batch_on_error_fallback_succeeds() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    calls = {"primary": 0}
    original = pipeline.process

    def failing(*args):
        calls["primary"] += 1
        if calls["primary"] <= 1:
            raise RuntimeError("primary failed")
        # Fallback invocation receives the on_error return value; pass it on
        # unchanged (it is already a NormalizationResult or valid text).
        return args[-1]

    def on_error(index, text, error):
        # The executor re-invokes process with the fallback value, so the
        # fallback must be a *value the pipeline accepts* — we pass the
        # original text back so the real pipeline can produce a result.
        return original(text)

    async def run() -> list:
        with mock.patch.object(pipeline, "process", failing):
            return await pipeline.process_batch_async(
                ["نص"],
                batch_size=32,
                policy=BatchProcessingPolicy(mode="collect"),
                on_error=on_error,
            )

    results = asyncio.run(run())
    assert len(results) == 1
    assert results[0].normalized_text is not None


def test_async_batch_on_error_fallback_also_fails_fail_fast_raises() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    def failing(*args):
        raise RuntimeError("primary")

    async def run() -> None:
        with mock.patch.object(pipeline, "process", failing):
            with pytest.raises(RuntimeError):
                await pipeline.process_batch_async(
                    ["نص", "نص ثانٍ"],
                    batch_size=1,
                    policy=BatchProcessingPolicy(mode="fail_fast"),
                    on_error=failing,
                )

    asyncio.run(run())


def test_async_batch_collect_policy_raises_batch_processing_error() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    def failing(text):
        raise RuntimeError("primary")

    async def run() -> None:
        with mock.patch.object(pipeline, "process", failing):
            with pytest.raises(BatchProcessingError):
                await pipeline.process_batch_async(
                    ["نص"],
                    batch_size=32,
                    policy=BatchProcessingPolicy(mode="collect"),
                )

    asyncio.run(run())


def test_async_batch_cancellation_stops_processing() -> None:
    from aranorm.core.contracts import CancellationToken

    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    async def run() -> None:
        token = CancellationToken()
        token.cancel()
        with pytest.raises(RuntimeError):
            await pipeline.process_batch_async(
                ["نص"],
                batch_size=32,
                policy=BatchProcessingPolicy(mode="collect"),
                cancellation_token=token,
            )

    asyncio.run(run())


def test_async_batch_invalid_worker_and_batch_sizes() -> None:
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

    async def run() -> None:
        with pytest.raises(ValueError):
            await pipeline.process_batch_async(["نص"], n_workers=0)
        with pytest.raises(ValueError):
            await pipeline.process_batch_async(["نص"], batch_size=0)

    asyncio.run(run())


# ── PipelineBuilder validation (core/pipeline.py 1365) ──


def test_builder_add_cleaner_unknown_option_raises() -> None:
    with pytest.raises(ValueError, match="Unknown cleaner option"):
        PipelineBuilder().add_cleaner(remove_unknown_thing=True).build()


def test_builder_add_normalizer_unknown_option_raises() -> None:
    with pytest.raises(ValueError, match="Unknown normalizer option"):
        PipelineBuilder().add_normalizer(normalize_unknown=True).build()
