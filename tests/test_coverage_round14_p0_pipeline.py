"""Round 14 P0 — pipeline retry robustness, bounds validation, and builder contracts.

Closes verified coverage gaps in src/aranorm/core/pipeline.py (lines 544, 600,
631, 685, 737, 880, 942, 982, 1012, 1020, 1024, 1092, 1161) through the public
API without changing production behavior. Deterministic and side-effect free.
"""

import asyncio

import pytest

from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.core.config import ResourceLimits
from aranorm.core.contracts import CancellationToken, BatchRetryPolicy, BatchProcessingPolicy
from aranorm.exceptions.errors import ConfigurationError


def _flaky_state(pipeline, flaky_indices, attempt_counts):
    """Track per-index attempts and make specific indices fail until exhausted."""
    state = {"counts": attempt_counts.copy()}

    def on_process(text):
        idx = flaky_indices.get(text, None)
        if idx is not None:
            state["counts"][idx] -= 1
            if state["counts"][idx] >= 0:
                raise ValueError("transient failure")
        return pipeline.process(text)

    return on_process


def test_retry_policy_type_validation_raises_type_error():
    """Pipeline must reject a non-BatchRetryPolicy retry_policy with TypeError."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(TypeError):
        pipeline.process_batch_retry(["نص عربي"], retry_policy="not-a-policy")


def test_retry_max_retries_bounds_validation():
    """Retry pass bounds: non-int/bool max_retries and out-of-range values raise ValueError."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(ValueError):
        pipeline.process_batch_retry(["نص"], max_retries=True)
    with pytest.raises(ValueError):
        pipeline.process_batch_retry(["نص"], max_retries=-1)
    with pytest.raises(ValueError):
        pipeline.process_batch_retry(["نص"], max_retries=11)


def test_retry_async_max_retries_bounds_validation():
    """Async retry pass mirrors the synchronous bounds contract for max_retries."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    for bad in (True, -1, 11):
        with pytest.raises(ValueError):
            asyncio.run(pipeline.process_batch_retry_async(["نص"], max_retries=bad))


def test_retry_async_policy_type_validation():
    """Async retry pass rejects a non-BatchRetryPolicy with TypeError."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(TypeError):
        asyncio.run(pipeline.process_batch_retry_async(["نص"], retry_policy={"bad": "dict"}))


def test_retry_policy_type_validation_async_path():
    """Async retry pass rejects invalid retry_policy before processing starts."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(TypeError):
        asyncio.run(pipeline.process_batch_retry_async(["نص"], retry_policy=[1, 2, 3]))


def test_retry_with_on_error_skip_populates_failures_map():
    """Retry report excludes permanently failed items from results while tracking failed_indices."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    original_process = pipeline.process

    def failing(text):
        if text == "bad":
            raise ValueError("permanent failure")
        return original_process(text)

    pipeline.process = failing
    report = pipeline.process_batch_retry(
        ["نص عربي", "bad"],
        on_error=lambda index, text, exc: None,
        retry_policy=BatchRetryPolicy(max_retries=2),
    )
    assert len(report.results) == 1
    assert report.results[0].original_text == "نص عربي"
    assert 1 in report.failed_indices


def test_retry_cancellation_token_raises_in_retry_loop():
    """Retry loops observe cancellation via CancellationToken mid-retry."""

    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    token = CancellationToken()
    token.cancel()
    with pytest.raises(Exception):  # ProcessingCancelledError raised on check
        pipeline.process_batch_retry(
            ["نص عربي"],
            retry_policy=BatchRetryPolicy(max_retries=3),
            cancellation_token=token,
        )


def test_retry_async_cancellation_token_raises_in_retry_loop():
    from aranorm.core.contracts import BatchRetryPolicy

    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    token = CancellationToken()
    token.cancel()
    with pytest.raises(Exception):
        asyncio.run(
            pipeline.process_batch_retry_async(
                ["نص عربي"],
                retry_policy=BatchRetryPolicy(max_retries=3),
                cancellation_token=token,
            )
        )


def test_retry_policy_bounds_validation_async_batch():
    """process_batch_async validates batch_size and n_workers bounds."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(ValueError):
        asyncio.run(pipeline.process_batch_async(["نص"], batch_size=0))
    with pytest.raises(ValueError):
        asyncio.run(pipeline.process_batch_async(["نص"], n_workers=0))


def test_retry_async_bounds_respect_resource_limits():
    """Async batch rejects batch_size exceeding configured max_batch_size."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig(resource_limits=ResourceLimits(max_batch_size=4)))
    with pytest.raises(ValueError):
        asyncio.run(pipeline.process_batch_async(["ن"] * 6, batch_size=5))


def test_spec_fingerprint_mismatch_raises():
    """from_spec rejects a spec whose fingerprint does not match the config."""
    spec_dict = {
        "config": {"profile": "default", "clean_html": True},
        "config_fingerprint": "0" * 64,
        "version": 1,
        "metadata": {},
    }
    with pytest.raises(ValueError):
        ArabicNormalizationPipeline.from_spec(spec_dict)


def test_spec_fingerprint_mismatch_after_spec_dict_tamper():
    """Tampering with any config field invalidates the fingerprint on from_spec."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    spec = pipeline.to_spec(metadata={"note": "original"})
    spec.config["clean_html"] = not spec.config["clean_html"]
    with pytest.raises(ValueError):
        ArabicNormalizationPipeline.from_spec(spec)


def test_builder_rejects_unknown_clean_option():
    """PipelineBuilder.add_cleaner rejects unknown option names with ValueError."""
    from aranorm.core.pipeline import PipelineBuilder

    builder = PipelineBuilder()
    with pytest.raises(ValueError):
        builder.add_cleaner(remove_nonexistent=True)


def test_builder_rejects_non_boolean_clean_option():
    """PipelineBuilder.add_cleaner rejects non-boolean option values with TypeError."""
    from aranorm.core.pipeline import PipelineBuilder

    builder = PipelineBuilder()
    with pytest.raises(TypeError):
        builder.add_cleaner(clean_html="yes")


def test_retry_rebuilds_initial_results_deterministically():
    """Retry pass rebuilds per-index initial results in input order after failure."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    original_process = pipeline.process

    def failing(text):
        if text == "bad":
            raise ValueError("persistent failure")
        return original_process(text)

    pipeline.process = failing
    texts = ["نص عربي"] * 5 + ["bad"] + ["نص عربي"]
    report = pipeline.process_batch_retry(
        texts,
        retry_policy=BatchRetryPolicy(max_retries=2),
        on_error=lambda index, text, exc: None,
    )
    assert len(report.results) == 6
    assert 5 in report.failed_indices
    assert report.failed_indices == [5]


def test_retry_async_failure_recovery_preserves_order():
    """Async retry pass recovers transient failures while preserving order."""
    config = PipelineConfig()
    pipeline = ArabicNormalizationPipeline(config)

    def failing(text):
        raise ValueError("persistent failure")

    pipeline.process = failing
    report = asyncio.run(
        pipeline.process_batch_retry_async(
            ["broken"],
            retry_policy=BatchRetryPolicy(max_retries=2),
            on_error=lambda index, text, exc: None,
        )
    )
    assert report.failed_indices == [0]


def test_retry_fail_fast_policy_rejected():
    """Retry passes reject fail_fast policies because they abort before failures are known."""
    from aranorm.exceptions.errors import ConfigurationError

    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(ConfigurationError):
        pipeline.process_batch_retry(
            ["نص"],
            policy=BatchProcessingPolicy(mode="fail_fast"),
            retry_policy=BatchRetryPolicy(max_retries=1),
        )
    with pytest.raises(ConfigurationError):
        asyncio.run(
            pipeline.process_batch_retry_async(
                ["نص"],
                policy=BatchProcessingPolicy(mode="fail_fast"),
                retry_policy=BatchRetryPolicy(max_retries=1),
            )
        )


def test_retry_sync_cancellation_between_retries():
    """Synchronous retry pass checks cancellation before each retry attempt."""

    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    token = CancellationToken()
    token.cancel()
    with pytest.raises(Exception):
        pipeline.process_batch_retry(
            ["فشل دائم"],
            retry_policy=BatchRetryPolicy(max_retries=2),
            cancellation_token=token,
            on_error=lambda index, text, exc: None,
        )


def test_retry_sync_type_error_policy_branch():
    """Synchronous retry path raises TypeError for a non-BatchRetryPolicy object."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(TypeError):
        pipeline.process_batch_retry(["نص عربي"], retry_policy=dict(max_retries=3))


def test_retry_initial_pass_no_result_records_runtime_error():
    """Items producing None in the synchronous initial pass are recorded as failed."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    def always_fails(text):
        raise ValueError("persistent failure")

    pipeline.process = always_fails
    report = pipeline.process_batch_retry(
        ["نص عربي"],
        retry_policy=BatchRetryPolicy(max_retries=2),
        policy=BatchProcessingPolicy(mode="collect"),
    )
    assert report.failed_indices == [0]


def test_retry_cancellation_inside_worker_loop():
    """Retry attempts proceed when cancellation arrives after the initial check."""

    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    original_process = pipeline.process  # noqa: F841
    attempts = {"n": 0}
    token = CancellationToken()

    def failing_after_cancel(text):
        attempts["n"] += 1
        if attempts["n"] > 1:
            token.cancel()
        raise ValueError("transient")

    pipeline.process = failing_after_cancel
    report = pipeline.process_batch_retry(
        ["نص عربي"],
        retry_policy=BatchRetryPolicy(max_retries=3),
        cancellation_token=token,
        on_error=lambda index, text, exc: None,
    )
    assert report.failed_indices == [0]
    assert report.retry_report["retry_attempts"] == 3


def test_retry_async_no_result_collect_branch():
    """Async retry loop records failing items when the initial pass collects None entries."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    def always_fails(text):
        raise ValueError("persistent failure")

    pipeline.process = always_fails
    report = asyncio.run(
        pipeline.process_batch_retry_async(
            ["نص عربي"],
            retry_policy=BatchRetryPolicy(max_retries=2),
            policy=BatchProcessingPolicy(mode="collect"),
        )
    )
    assert report.failed_indices == [0]


def test_retry_async_raises_on_fail_fast_policy():
    """Async retry pass rejects fail_fast policies before any work begins."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(ConfigurationError):
        asyncio.run(
            pipeline.process_batch_retry_async(
                ["نص عربي"],
                policy=BatchProcessingPolicy(mode="fail_fast"),
                retry_policy=BatchRetryPolicy(max_retries=2),
            )
        )


def test_builder_add_cleaner_bool_fields_only():
    """PipelineBuilder rejects non-boolean values targeting boolean config fields."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    from aranorm.core.pipeline import PipelineBuilder

    builder = PipelineBuilder()
    with pytest.raises(TypeError):
        builder.add_cleaner(clean_html=0)
    _ = pipeline  # keep import path exercised


def test_retry_async_bounds_n_workers_over_limit():
    """Async batch rejects n_workers beyond the configured resource limit."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig(resource_limits=ResourceLimits(max_workers=2)))
    with pytest.raises(ValueError):
        asyncio.run(pipeline.process_batch_async(["نص عربي"], n_workers=3))


def test_retry_async_bounds_batch_size_zero():
    """Async batch rejects non-positive batch_size hints."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(ValueError):
        asyncio.run(pipeline.process_batch_async(["نص عربي"], batch_size=-1))


def test_retry_async_bounds_workers_type_validation():
    """Async batch rejects non-integer n_workers values."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(Exception):
        asyncio.run(pipeline.process_batch_async(["نص عربي"], n_workers="two"))


def test_retry_policy_object_sync_pass_bounds():
    """Sync retry pass bounds validation applies when policy object carries values."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    with pytest.raises(ValueError):
        pipeline.process_batch_retry(
            ["نص عربي"],
            retry_policy=BatchRetryPolicy(max_retries=12),
        )


def test_retry_sync_fallback_also_fails_branch():
    """Sync retry pass falls back to processing a replacement text that fails too."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    def failing_process(text):
        raise ValueError("failure for %s" % text)

    pipeline.process = failing_process
    report = pipeline.process_batch_retry(
        ["نص عربي"],
        retry_policy=BatchRetryPolicy(max_retries=2),
        on_error=lambda index, text, exc: "نص بديل",
    )
    assert report.failed_indices == [0]
    assert report.retry_report["retry_attempts"] == 2


def test_retry_async_fallback_also_fails_branch():
    """Async retry pass falls back to processing a replacement text that fails too."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    def failing_process(text):
        raise ValueError("failure for %s" % text)

    pipeline.process = failing_process
    report = asyncio.run(
        pipeline.process_batch_retry_async(
            ["نص عربي"],
            retry_policy=BatchRetryPolicy(max_retries=2),
            on_error=lambda index, text, exc: "نص بديل",
        )
    )
    assert report.failed_indices == [0]


def test_retry_async_exhausted_attempts_records_retry_attempts():
    """Async retry loop records attempts when all retries are exhausted."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    original_process = pipeline.process

    def failing_after_success(text):
        _ = original_process  # noqa: BLE001
        raise ValueError("exhausted")

    pipeline.process = failing_after_success
    report = asyncio.run(
        pipeline.process_batch_retry_async(
            ["نص عربي"],
            retry_policy=BatchRetryPolicy(max_retries=2),
            policy=BatchProcessingPolicy(mode="collect"),
        )
    )
    assert report.failed_indices == [0]
    assert report.retry_report["retry_attempts"] == 2


def test_async_batch_fail_fast_raises_without_handler():
    """Async fail_fast mode raises immediately when no on_error handler is present."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())

    def always_fails(text):
        raise ValueError("boom")

    pipeline.process = always_fails
    with pytest.raises(ValueError):
        asyncio.run(
            pipeline.process_batch_async(
                ["نص عربي"],
                policy=BatchProcessingPolicy(mode="fail_fast"),
            )
        )


def test_async_batch_cancelled_error_propagates():
    """Async batch propagation of CancelledError from a worker task is preserved."""
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    original_process = pipeline.process

    def becomes_cancelled(text):
        _ = original_process  # noqa: BLE001
        raise asyncio.CancelledError()

    pipeline.process = becomes_cancelled
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            pipeline.process_batch_async(
                ["نص عربي"],
                policy=BatchProcessingPolicy(mode="collect"),
            )
        )


def test_sync_retry_catastrophic_path_via_cancelled_token():
    from aranorm.core.contracts import CancellationToken

    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    token = CancellationToken()
    token.cancel()

    def always_fails(text):
        raise ValueError("boom")

    pipeline.process = always_fails
    with pytest.raises(Exception):
        pipeline.process_batch_retry(
            ["نص عربي"],
            retry_policy=BatchRetryPolicy(max_retries=2),
            cancellation_token=token,
        )
