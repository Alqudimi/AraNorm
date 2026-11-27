"""Operational metrics tests."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from aranorm import ArabicNormalizationPipeline, InvalidTextError, ProcessingMetrics


def test_metrics_record_success_and_failure() -> None:
    metrics = ProcessingMetrics()
    metrics.record(success=True, elapsed_ms=2.5)
    metrics.record(success=False, elapsed_ms=1.5)

    snapshot = metrics.snapshot()

    assert snapshot.total_items == 2
    assert snapshot.succeeded == 1
    assert snapshot.failed == 1
    assert snapshot.total_time_ms == pytest.approx(4.0)
    assert snapshot.average_time_ms == pytest.approx(2.0)
    assert snapshot.to_dict()["total_items"] == 2


def test_metrics_reject_negative_duration() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        ProcessingMetrics().record(success=True, elapsed_ms=-0.1)


def test_metrics_are_thread_safe() -> None:
    metrics = ProcessingMetrics()

    def record_one(_: int) -> None:
        metrics.record(success=True, elapsed_ms=1.0)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(record_one, range(200)))

    snapshot = metrics.snapshot()
    assert snapshot.total_items == 200
    assert snapshot.succeeded == 200
    assert snapshot.failed == 0
    assert snapshot.total_time_ms == pytest.approx(200.0)


def test_pipeline_exposes_metrics_snapshot_for_success_and_failure() -> None:
    pipeline = ArabicNormalizationPipeline()
    pipeline.process("أحمد")
    with pytest.raises(InvalidTextError):
        pipeline.process(123)  # type: ignore[arg-type]

    snapshot = pipeline.metrics_snapshot()
    assert snapshot.total_items == 2
    assert snapshot.succeeded == 1
    assert snapshot.failed == 1


def test_metrics_reset_is_atomic_and_reusable() -> None:
    metrics = ProcessingMetrics()
    metrics.record(success=True, elapsed_ms=1.0)
    metrics.reset()
    assert metrics.snapshot().total_items == 0

    metrics.record(success=False, elapsed_ms=2.0)
    assert metrics.snapshot().failed == 1
