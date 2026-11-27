"""Contract tests for bounded batch retries (Round 6).

``process_batch_retry`` guarantees that a first pass is executed with the
``collect`` failure policy, failed items are retried single-threaded up to
``max_retries`` times, and the final report cleanly separates recovered
results from definitively failed indices.
"""

from __future__ import annotations

import unittest.mock as mock

import pytest

from aranorm import ArabicNormalizationPipeline
from aranorm.core.contracts import BatchProcessingPolicy, BatchRetryReport
from aranorm.exceptions import BatchProcessingError, ConfigurationError


class TestBatchRetryBasic:
    def test_healthy_batch_recovers_nothing(self):
        hp = ArabicNormalizationPipeline()
        texts = ["مرحبا", "كيف حالك", "أخبارك إيش"]
        report = hp.process_batch_retry(texts, max_retries=2)
        assert isinstance(report, BatchRetryReport)
        assert len(report.results) == 3
        assert report.failed_indices == []
        assert report.retry_report["retry_attempts"] == 0
        assert report.retry_report["recovered_count"] == 0
        assert report.retry_report["total_inputs"] == 3

    def test_empty_input(self):
        report = ArabicNormalizationPipeline().process_batch_retry([])
        assert report.results == []
        assert report.failed_indices == []

    def test_transient_failure_recovers(self):
        hp = ArabicNormalizationPipeline()
        original = hp.process
        calls = {"seen": {}}

        def flicker(text):
            calls["seen"].setdefault(text, 0)
            calls["seen"][text] += 1
            if calls["seen"][text] == 1:
                raise RuntimeError("transient")
            return original(text)

        with mock.patch.object(hp, "process", side_effect=flicker):
            report = hp.process_batch_retry(["ok", "flaky", "ok2"], max_retries=2)
        assert report.failed_indices == []
        assert len(report.results) == 3
        assert report.retry_report["recovered_count"] == 3
        assert report.retry_report["retry_attempts"] == 0

    def test_persistent_failure_exhausts_retries(self):
        hp = ArabicNormalizationPipeline()
        original = hp.process

        def persistent(text):
            if text == "flaky":
                raise RuntimeError("persistent")
            return original(text)

        with mock.patch.object(hp, "process", side_effect=persistent):
            report = hp.process_batch_retry(["ok", "flaky", "ok2", "ok3"], max_retries=3)
        assert report.failed_indices == [1]
        assert len(report.results) == 3
        assert report.retry_report["retry_attempts"] == 3
        assert report.retry_report["recovered_count"] == 0

    def test_max_retries_zero_disables_recovery(self):
        hp = ArabicNormalizationPipeline()
        original = hp.process

        def persistent(text):
            if text == "flaky":
                raise RuntimeError("persistent")
            return original(text)

        with mock.patch.object(hp, "process", side_effect=persistent):
            report = hp.process_batch_retry(["ok", "flaky"], max_retries=0)
        assert report.failed_indices == [1]
        assert report.retry_report["retry_attempts"] == 0

    def test_order_preserved(self):
        hp = ArabicNormalizationPipeline()
        original = hp.process
        # middle item fails once then succeeds: recovered results must keep order
        calls = {"seen": {}}

        def flicker(text):
            calls["seen"].setdefault(text, 0)
            calls["seen"][text] += 1
            if text == "middle" and calls["seen"][text] <= 2:
                raise RuntimeError("transient")
            return original(text)

        with mock.patch.object(hp, "process", side_effect=flicker):
            report = hp.process_batch_retry(["a", "middle", "b", "c", "d"], max_retries=2)
        assert report.failed_indices == []
        texts = [r.original_text for r in report.results]
        assert texts == ["a", "middle", "b", "c", "d"]


class TestBatchRetryGuards:
    def test_fail_fast_policy_rejected(self):
        hp = ArabicNormalizationPipeline()
        with pytest.raises(ConfigurationError):
            hp.process_batch_retry(["x"], policy=BatchProcessingPolicy(mode="fail_fast"))

    @pytest.mark.parametrize("bad", [-1, 11, 100, True, 3.5, "x", None])
    def test_invalid_max_retries_rejected(self, bad):
        hp = ArabicNormalizationPipeline()
        with pytest.raises((ValueError, TypeError)):
            hp.process_batch_retry(["x"], max_retries=bad)

    def test_zero_max_retries_accepted(self):
        report = ArabicNormalizationPipeline().process_batch_retry(["ok"], max_retries=0)
        assert report.failed_indices == []

    def test_skip_policy_accepted(self):
        report = ArabicNormalizationPipeline().process_batch_retry(["ok"], policy=BatchProcessingPolicy(mode="skip"))
        assert report.failed_indices == []


class TestBatchRetryCancellation:
    def test_cancelled_before_start_raises(self):
        hp = ArabicNormalizationPipeline()
        token = __import__("aranorm.core.contracts", fromlist=["CancellationToken"]).CancellationToken()
        token.cancel()
        with pytest.raises(Exception):
            hp.process_batch_retry(["نص"], cancellation_token=token)


class TestBatchRetryReport:
    def test_to_dict_structure(self):
        hp = ArabicNormalizationPipeline()
        original = hp.process

        def persistent(text):
            if text == "bad":
                raise RuntimeError("x")
            return original(text)

        with mock.patch.object(hp, "process", side_effect=persistent):
            report = hp.process_batch_retry(["good", "bad"], max_retries=1)
        payload = report.to_dict()
        assert payload["failed_indices"] == [1]
        assert isinstance(payload["results"], list)
        assert len(payload["results"]) == 1
        assert isinstance(payload["results"][0], dict)
        assert payload["retry_report"]["total_inputs"] == 2
        assert "max_retries" in payload["retry_report"]
        assert "retry_attempts" in payload["retry_report"]
        assert "recovered_count" in payload["retry_report"]
        # The operational summary must not embed raw input text.
        import json

        summary = json.dumps(payload["retry_report"])
        assert "good" not in summary
        assert "bad" not in summary

    def test_immutable_fields(self):
        report = BatchRetryReport(results=[], failed_indices=[], retry_report={})
        with pytest.raises(AttributeError):
            report.results = [1]


class TestBatchProcessingErrorResults:
    def test_collect_path_carries_successful_results(self):
        hp = ArabicNormalizationPipeline()
        original = hp.process

        def persistent(text):
            if text == "bad":
                raise RuntimeError("x")
            return original(text)

        with mock.patch.object(hp, "process", side_effect=persistent):
            with pytest.raises(BatchProcessingError) as exc_info:
                hp.process_batch(["good", "bad"], policy=BatchProcessingPolicy(mode="collect"))
        exc = exc_info.value
        assert exc.failed_indices == [1]
        assert exc.results is not None
        assert len(exc.results) == 1
        assert exc.results[0].original_text == "good"

    def test_async_collect_path_carries_successful_results(self):
        import asyncio

        hp = ArabicNormalizationPipeline()
        original = hp.process

        def persistent(text):
            if text == "bad":
                raise RuntimeError("x")
            return original(text)

        async def run():
            with mock.patch.object(hp, "process", side_effect=persistent):
                await hp.process_batch_async(["good", "bad"], policy=BatchProcessingPolicy(mode="collect"))

        with pytest.raises(BatchProcessingError) as exc_info:
            asyncio.run(run())
        exc = exc_info.value
        assert exc.failed_indices == [1]
        assert exc.results is not None
        assert len(exc.results) == 1

    def test_backward_compat_no_results(self):
        """Handlers that never passed results must still see results=None."""
        exc = BatchProcessingError("old style", failed_indices=[0], errors={0: RuntimeError()})
        assert exc.results is None
        assert exc.failed_indices == [0]
