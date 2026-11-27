"""Serialization and aggregation contracts for operational metrics."""

import json

import pytest

from aranorm import ProcessingMetrics
from aranorm.core.metrics import ProcessingMetricsSnapshot


def test_snapshot_json_round_trip_preserves_values() -> None:
    metrics = ProcessingMetrics()
    metrics.record(success=True, elapsed_ms=2.5)
    metrics.record(success=False, elapsed_ms=1.5)

    snapshot = metrics.snapshot()
    payload = snapshot.to_json()
    restored = ProcessingMetricsSnapshot.from_json(payload)

    assert restored == snapshot
    decoded = json.loads(payload)
    assert decoded["schema_version"] == 1
    assert decoded["total_items"] == 2


def test_legacy_dict_shape_remains_available() -> None:
    snapshot = ProcessingMetricsSnapshot(
        total_items=2,
        succeeded=2,
        failed=0,
        total_time_ms=4.0,
        average_time_ms=2.0,
        throughput_per_second=500.0,
    )

    payload = snapshot.to_dict()

    assert "schema_version" not in payload
    assert ProcessingMetricsSnapshot.from_dict(payload) == snapshot


def test_to_dict_can_include_schema_for_machine_consumers() -> None:
    snapshot = ProcessingMetricsSnapshot(0, 0, 0, 0.0, 0.0, 0.0)

    payload = snapshot.to_dict(include_schema=True)

    assert payload["schema_version"] == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"total_items": 1},
        {
            "schema_version": 99,
            "total_items": 0,
            "succeeded": 0,
            "failed": 0,
            "total_time_ms": 0.0,
            "average_time_ms": 0.0,
            "throughput_per_second": 0.0,
        },
        {
            "schema_version": 1,
            "total_items": -1,
            "succeeded": 0,
            "failed": 0,
            "total_time_ms": 0.0,
            "average_time_ms": 0.0,
            "throughput_per_second": 0.0,
        },
        {
            "schema_version": 1,
            "total_items": 1,
            "succeeded": 2,
            "failed": 0,
            "total_time_ms": 1.0,
            "average_time_ms": 1.0,
            "throughput_per_second": 1000.0,
        },
    ],
)
def test_from_dict_rejects_invalid_payloads(payload: dict) -> None:
    with pytest.raises(ValueError):
        ProcessingMetricsSnapshot.from_dict(payload)


def test_from_json_rejects_non_object_payload() -> None:
    with pytest.raises(ValueError, match="object"):
        ProcessingMetricsSnapshot.from_json("[]")


def test_metrics_merge_aggregates_counts_and_time() -> None:
    left = ProcessingMetrics()
    left.record(success=True, elapsed_ms=2.0)
    right = ProcessingMetrics()
    right.record(success=False, elapsed_ms=3.0)
    right.record(success=True, elapsed_ms=5.0)

    left.merge(right.snapshot())
    snapshot = left.snapshot()

    assert snapshot.total_items == 3
    assert snapshot.succeeded == 2
    assert snapshot.failed == 1
    assert snapshot.total_time_ms == pytest.approx(10.0)
    assert snapshot.average_time_ms == pytest.approx(10.0 / 3.0, abs=0.001)


def test_metrics_merge_rejects_inconsistent_snapshot() -> None:
    metrics = ProcessingMetrics()
    invalid = ProcessingMetricsSnapshot(2, 2, 2, 1.0, 0.5, 2000.0)

    with pytest.raises(ValueError, match="consistent"):
        metrics.merge(invalid)


def test_metrics_merge_does_not_mutate_source_snapshot() -> None:
    source = ProcessingMetricsSnapshot(1, 1, 0, 2.0, 2.0, 500.0)
    metrics = ProcessingMetrics()

    metrics.merge(source)

    assert source == ProcessingMetricsSnapshot(1, 1, 0, 2.0, 2.0, 500.0)
