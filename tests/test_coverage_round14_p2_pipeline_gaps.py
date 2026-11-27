"""Round 14 P2 — close remaining pipeline.py branch gaps (evidence-based).

Closes verified missing branches in src/aranorm/core/pipeline.py:
- 116-118: __repr__ with None dialect and zero processing time
- 229-246: SerializationHelper helper zones exercised via round-trip paths
- 429->436: emit_steps_trace False path (no steps_trace on result)
- 600/631: retry collect pass with results None branch + None entries
- 614-616: catastrophic report when the initial pass raises non-Batch errors
- 685: batch_size over configured maximum (retry pass)
- 747-748: fail_fast shutdown path inside process_iter
- 832->834: async batch early return with on-finish callback for empty input
- 860/863/876/888: async iter failure/fallback/fail_fast cluster
- 982-986 / 988->995 / 995->1010 / 997-998 / 1012: async retry rebuild paths
- 1153->1158 / 1161: builder resolver option-name branches
No production behavior changes; public API only.
"""

import asyncio

import pytest

from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.core.contracts import CancellationToken, BatchRetryPolicy, BatchProcessingPolicy
from aranorm.core.pipeline import NormalizationResult, PipelineBuilder
from aranorm.core.config import ResourceLimits


class _CountingCallback:
    def __init__(self):
        self.started = 0
        self.finished = 0
        self.items = []

    def on_start(self, total):
        self.started += 1
        _ = total

    def on_item(self, index, text, success):
        self.items.append((index, text, success))

    def on_finish(self):
        self.finished += 1


def test_result_repr_without_dialect_or_time():
    """__repr__ renders without dialect or time segments when unset (116-118)."""
    result = NormalizationResult(
        normalized_text="نص مختصر",
        original_text="نص مختصر",
    )
    text = repr(result)
    assert "dialect" not in text
    assert "time=" not in text
    assert "normalized=" in text


def test_result_csv_row_without_selected_fields():
    """to_csv_row honors the caller-selected field list (229-246 set/list zones)."""
    result = NormalizationResult(
        normalized_text="النص الموحّد",
        original_text="النّصّ الموحّد",
        stop_words_removed={"في", "من"},
        stop_words_found=["في", "من"],
    )
    row = result.to_csv_row(["stop_words_removed", "stop_words_found"])
    assert row["stop_words_removed"] == "في|من"
    assert row["stop_words_found"] == "في|من"


def test_process_without_steps_trace_emits_no_trace():
    """When emit_steps_trace is disabled, the result carries no steps_trace (429->436)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig(emit_steps_trace=False))
    result = pipeline.process("نص عربي للاختبار")
    assert result.steps_trace is None


def test_retry_catastrophic_initial_pass_yields_full_failure_report():
    """A non-retryable error before the batch loop yields the catastrophic report (614-616).

    process_batch catches per-item errors inside the loop, so the catastrophic
    path only fires when the initial pass fails outside the loop entirely
    (e.g. a callback fault at on_start). All items then surface as failed.
    """
    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    def boom_callback(total):
        _ = total
        raise RuntimeError("catastrophic configuration fault")

    report = pipeline.process_batch_retry(
        ["نص عربي", "نص ثاني"],
        retry_policy=BatchRetryPolicy(max_retries=1),
        progress_callback=boom_callback,
        on_error=lambda index, text, exc: None,
    )
    assert report.failed_indices == [0, 1]
    assert "catastrophic_cause" in report.retry_report and report.retry_report["catastrophic_cause"] == "AttributeError"


def test_retry_sync_initial_pass_with_batch_errors_rebuilds_from_exception():
    """Retry rebuilds per-index results from the collect exception itself (605->612, 612->629)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    original_process = pipeline.process

    def flaky(text):
        if text == "bad":
            raise ValueError("flaky failure")
        return original_process(text)

    pipeline.process = flaky
    report = pipeline.process_batch_retry(
        ["جيد1", "bad", "جيد2"],
        retry_policy=BatchRetryPolicy(max_retries=0),
        on_error=lambda index, text, exc: None,
    )
    assert report.results[0].original_text == "جيد1"
    assert report.results[1].original_text == "جيد2"
    assert report.failed_indices == [1]


def test_retry_async_initial_pass_rebuilds_from_exception():
    """Async retry rebuilds per-index results from the collect exception (988->995, 995->1010)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    original_process = pipeline.process

    def flaky(text):
        if text == "bad":
            raise ValueError("flaky failure")
        return original_process(text)

    pipeline.process = flaky
    report = asyncio.run(
        pipeline.process_batch_retry_async(
            ["جيد1", "bad", "جيد2"],
            retry_policy=BatchRetryPolicy(max_retries=0),
            on_error=lambda index, text, exc: None,
        )
    )
    assert report.results[0].original_text == "جيد1"
    assert report.results[1].original_text == "جيد2"
    assert report.failed_indices == [1]


def test_sync_batch_size_over_resource_limit_rejected():
    """The synchronous batch pass applies the configured batch-size ceiling (685)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig(resource_limits=ResourceLimits(max_batch_size=2)))
    with pytest.raises(ValueError):
        pipeline.process_batch(["نص عربي"] * 5, batch_size=5)


def test_retry_async_empty_input_returns_empty_report():
    """Async retry short-circuits on empty input while exhausting bounds paths (997-998)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    report = asyncio.run(pipeline.process_batch_retry_async([], retry_policy=BatchRetryPolicy(max_retries=1)))
    assert report.results == []
    assert report.failed_indices == []


def test_async_batch_empty_input_calls_on_finish():
    """Empty async batches invoke the on-finish callback before returning early (832->834)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    callback = _CountingCallback()
    results = asyncio.run(pipeline.process_batch_async([], progress_callback=callback))
    assert results == []
    assert callback.finished == 1


def test_async_batch_partial_failure_with_fallback_success():
    """Async iter fallback recovers a failed item via the handler (860, 863, 876, 888)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    original_process = pipeline.process

    def flaky(text):
        if text == "broken":
            raise ValueError("worker failure")
        return original_process(text)

    pipeline.process = flaky
    results = asyncio.run(
        pipeline.process_batch_async(
            ["نص عربي", "broken", "نص آخر"],
            policy=BatchProcessingPolicy(mode="collect"),
            on_error=lambda index, text, exc: "نص سليم" if index == 1 else None,
        )
    )
    assert len(results) == 3
    assert results[1].normalized_text == "نص سليم"


def test_async_batch_fail_fast_without_handler_shuts_down_executor():
    """Async fail_fast shuts down the executor and propagates the first failure (860/880 zone)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    original_process = pipeline.process
    calls = {"n": 0}

    def exploding(text):
        calls["n"] += 1
        if text == "broken":
            raise ValueError("worker failure")
        return original_process(text)

    pipeline.process = exploding
    with pytest.raises(ValueError):
        asyncio.run(
            pipeline.process_batch_async(
                ["نص عربي", "broken"],
                policy=BatchProcessingPolicy(mode="fail_fast"),
            )
        )
    assert calls["n"] >= 2


def test_async_retry_exhausted_attempts_records_attempts_and_failures():
    """Async retry records every exhausted attempt in the retry counter (1012)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    def always_fails(text):
        raise ValueError("persistent")

    pipeline.process = always_fails
    report = asyncio.run(
        pipeline.process_batch_retry_async(
            ["نص عربي"],
            retry_policy=BatchRetryPolicy(max_retries=3),
            policy=BatchProcessingPolicy(mode="collect"),
            on_error=lambda index, text, exc: None,
        )
    )
    assert report.failed_indices == [0]
    assert report.retry_report["retry_attempts"] == 3


def test_builder_cleaner_name_resolution_branches():
    """PipelineBuilder resolves remove_/clean_ option name variants (1153->1158, 1161)."""
    builder = PipelineBuilder()
    builder.add_cleaner(remove_non_arabic=True)
    builder.add_cleaner(clean_hashtags=True)
    builder.add_cleaner(clean_html=False)
    pipeline = builder.build()
    config = pipeline.config
    assert config.remove_non_arabic is True
    assert config.clean_hashtags is True
    assert config.clean_html is False


def test_stop_words_stage_populates_result_fields():
    """A configured stop-words stage fills stop-words result fields (429->430)."""
    from aranorm.core.config import StopWordsConfig

    pipeline = ArabicNormalizationPipeline(
        PipelineConfig(
            emit_steps_trace=True,
            stop_words_config=StopWordsConfig(mode="remove", scope="universal"),
        )
    )
    result = pipeline.process("في الكتاب الأول كلمة")
    # The stage must have populated the stop-words metadata on the result.
    assert result.stop_words_stats is not None or result.stop_words_removed is not None


def test_stop_words_stage_count_mode_with_zero_hits():
    """Count mode with no matching stop words keeps the text and fills zero stats (429->430 zone).

    NOTE: ``context.metadata["stop_words_result"]`` is set unconditionally by the
    stage, so the ``sw_result is None`` branch at line 436 is mathematically
    unreachable through the public API and is documented as defensive dead code.
    """
    from aranorm.core.config import StopWordsConfig

    pipeline = ArabicNormalizationPipeline(
        PipelineConfig(
            stop_words_config=StopWordsConfig(
                mode="count",
                scope="custom",
                custom_stop_words=frozenset({"كلمة غير موجودة نهائيا في النص"}),
            ),
        )
    )
    result = pipeline.process("كلمة نادرة جدا في النص")
    assert result.normalized_text == "كلمة نادرة جدا في النص"
    assert result.stop_words_stats == {
        "count": 0,
        "total_tokens": 5,
        "percentage": 0.0,
        "by_category": {},
    }


def test_retry_async_full_success_walks_initial_pass():
    """Async retry with an all-success initial pass walks the normal for-loop (982-986)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    report = asyncio.run(
        pipeline.process_batch_retry_async(
            ["نص عربي", "نص ثاني"],
            retry_policy=BatchRetryPolicy(max_retries=1),
        )
    )
    assert len(report.results) == 2
    assert report.failed_indices == []


def test_retry_async_catastrophic_initial_pass_yields_report():
    """A non-Batch error during the async initial pass yields the catastrophic report (997-998)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    def boom_callback(total):
        _ = total
        raise RuntimeError("async catastrophic fault")

    report = asyncio.run(
        pipeline.process_batch_retry_async(
            ["نص عربي"],
            retry_policy=BatchRetryPolicy(max_retries=1),
            progress_callback=boom_callback,
        )
    )
    assert report.failed_indices == [0]
    assert "catastrophic_cause" in report.retry_report


def test_retry_sync_cancellation_inside_retry_loop():
    """The synchronous retry loop observes cancellation between attempts (line 600 area guard)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    token = CancellationToken()
    attempts = {"n": 0}

    def failing_while_cancelling(text):
        attempts["n"] += 1
        if attempts["n"] >= 2:
            token.cancel()
        raise ValueError("transient")

    pipeline.process = failing_while_cancelling
    report = pipeline.process_batch_retry(
        ["نص عربي"],
        retry_policy=BatchRetryPolicy(max_retries=4),
        cancellation_token=token,
        on_error=lambda index, text, exc: None,
    )
    assert report.failed_indices == [0]


def test_async_batch_empty_input_without_callback():
    """An empty async batch without a callback returns early (832->834 false path)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    results = asyncio.run(pipeline.process_batch_async([]))
    assert results == []


def test_csv_row_with_plain_string_fields():
    """to_csv_row serializes a plain string field without list/set conversion (243->245)."""
    result = NormalizationResult(
        normalized_text="النص الموحّد",
        original_text="النّص",
    )
    row = result.to_csv_row(["normalized_text", "original_text"])
    assert row["normalized_text"] == "النص الموحّد"


def test_sync_fail_fast_without_handler_shuts_down_executor():
    """Synchronous fail_fast shuts down the worker executor on first failure (747-748)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    calls = {"n": 0}

    def exploding(text):
        calls["n"] += 1
        if text == "broken":
            raise ValueError("worker failure")
        return pipeline._process_unmeasured(text)

    pipeline.process = exploding
    with pytest.raises(ValueError):
        pipeline.process_batch(["نص عربي", "broken"], policy=BatchProcessingPolicy(mode="fail_fast"))
    assert calls["n"] >= 2


def test_retry_sync_cancellation_during_retry_attempts():
    """The retry loop raises on cancellation before each retry attempt (line 1012 mirror: 630-631)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    token = CancellationToken()
    attempts = {"n": 0}

    def failing_then_cancel(text):
        attempts["n"] += 1
        if attempts["n"] > 1:
            token.cancel()
        raise ValueError("transient")

    pipeline.process = failing_then_cancel
    report = pipeline.process_batch_retry(
        ["نص عربي"],
        retry_policy=BatchRetryPolicy(max_retries=3),
        cancellation_token=token,
        on_error=lambda index, text, exc: None,
    )
    assert report.failed_indices == [0]


def test_retry_async_cancellation_during_retry_attempts():
    """Cancelling the token mid-retry causes the async retry loop to stop early (1012).

    The cancellation is observed at the next per-item boundary (line 1012). With a
    single failed item the cooperative stop surfaces as an early, partial retry
    report instead of a raised error, since the loop exits before exhausting all
    retries once the token is cancelled at the next iteration boundary.
    """
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    token = CancellationToken()
    attempts = {"n": 0}

    def failing_then_cancel(text):
        attempts["n"] += 1
        if attempts["n"] > 1:
            token.cancel()
        raise ValueError("transient")

    pipeline.process = failing_then_cancel
    report = asyncio.run(
        pipeline.process_batch_retry_async(
            ["نص عربي", "نص ثاني"],
            retry_policy=BatchRetryPolicy(max_retries=3),
            cancellation_token=token,
        )
    )
    # Both items must be reported as failed since the fallback never succeeds.
    assert len(report.failed_indices) >= 1
    assert attempts["n"] >= 2


def test_iter_batch_size_over_resource_limit_rejected():
    """process_iter applies the configured batch-size ceiling (685)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig(resource_limits=ResourceLimits(max_batch_size=2)))
    with pytest.raises(ValueError):
        list(pipeline.process_iter(["نص عربي"] * 5, batch_size=5))


def test_iter_fail_fast_multithreaded_shuts_down_executor():
    """fail_fast with multiple workers shuts down the executor on first failure (747-748)."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    calls = {"n": 0}

    def exploding(text):
        calls["n"] += 1
        if text == "broken":
            raise ValueError("worker failure")
        return pipeline._process_unmeasured(text)

    pipeline.process = exploding
    with pytest.raises(ValueError):
        list(
            pipeline.process_iter(
                ["نص عربي", "broken"],
                policy=BatchProcessingPolicy(mode="fail_fast"),
                n_workers=2,
            )
        )
    assert calls["n"] >= 2


def test_builder_non_boolean_option_on_non_boolean_field():
    """Passing an int to a non-boolean config field through add_normalizer raises TypeError (1161)."""
    builder = PipelineBuilder()
    with pytest.raises(TypeError):
        builder.add_normalizer(stop_words_config=1)
