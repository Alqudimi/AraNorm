"""Thread-safe operational metrics for normalization pipelines."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Union


@dataclass(frozen=True)
class ProcessingMetricsSnapshot:
    """Immutable point-in-time view of pipeline processing counters.

    The legacy ``to_dict()`` shape intentionally remains unchanged. Machine
    consumers can opt into the versioned envelope with ``include_schema=True``
    or use ``to_json()``.
    """

    SCHEMA_VERSION = 1

    total_items: int
    succeeded: int
    failed: int
    total_time_ms: float
    average_time_ms: float
    throughput_per_second: float

    def to_dict(self, include_schema: bool = False) -> Dict[str, Union[float, int]]:
        """Return a JSON-serialisable representation.

        Parameters
        ----------
        include_schema:
            Include the stable ``schema_version`` field for machine consumers.
            The default preserves the v1.4/v1.5 dictionary contract.
        """
        payload: Dict[str, Union[float, int]] = {
            "total_items": self.total_items,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "total_time_ms": self.total_time_ms,
            "average_time_ms": self.average_time_ms,
            "throughput_per_second": self.throughput_per_second,
        }
        if include_schema:
            payload = {"schema_version": self.SCHEMA_VERSION, **payload}
        return payload

    def to_json(self) -> str:
        """Return a stable, versioned JSON representation."""
        return json.dumps(self.to_dict(include_schema=True), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProcessingMetricsSnapshot":
        """Build a validated snapshot from a legacy or versioned mapping."""
        if not isinstance(data, Mapping):
            raise ValueError("metrics payload must be an object")
        version = data.get("schema_version", cls.SCHEMA_VERSION)
        if version != cls.SCHEMA_VERSION:
            raise ValueError(f"unsupported metrics schema version: {version}")
        fields = (
            "total_items",
            "succeeded",
            "failed",
            "total_time_ms",
            "average_time_ms",
            "throughput_per_second",
        )
        if any(field not in data for field in fields):
            raise ValueError("metrics payload is missing required fields")
        integer_fields = ("total_items", "succeeded", "failed")
        for field in integer_fields:
            value = data[field]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"metrics field {field!r} must be a non-negative integer")
        float_fields = ("total_time_ms", "average_time_ms", "throughput_per_second")
        for field in float_fields:
            value = data[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"metrics field {field!r} must be a non-negative number")
        if data["succeeded"] + data["failed"] != data["total_items"]:
            raise ValueError("metrics counters must be consistent")
        return cls(
            total_items=data["total_items"],
            succeeded=data["succeeded"],
            failed=data["failed"],
            total_time_ms=float(data["total_time_ms"]),
            average_time_ms=float(data["average_time_ms"]),
            throughput_per_second=float(data["throughput_per_second"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ProcessingMetricsSnapshot":
        """Build a validated snapshot from versioned JSON."""
        try:
            data = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid metrics JSON") from exc
        return cls.from_dict(data)


class ProcessingMetrics:
    """Low-overhead, thread-safe counters for pipeline operations.

    Metrics are observational only: recording them never changes the
    normalized output or the exception raised by the pipeline.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_items = 0
        self._succeeded = 0
        self._failed = 0
        self._total_time_ms = 0.0

    def record(self, *, success: bool, elapsed_ms: float) -> None:
        """Record one completed operation."""
        if elapsed_ms < 0:
            raise ValueError("elapsed_ms cannot be negative")
        with self._lock:
            self._total_items += 1
            if success:
                self._succeeded += 1
            else:
                self._failed += 1
            self._total_time_ms += elapsed_ms

    def snapshot(self) -> ProcessingMetricsSnapshot:
        """Return an immutable snapshot suitable for logs or telemetry."""
        with self._lock:
            total = self._total_items
            succeeded = self._succeeded
            failed = self._failed
            total_time = round(self._total_time_ms, 3)
        average = round(total_time / total, 3) if total else 0.0
        throughput = round(total / (total_time / 1000), 3) if total_time > 0 else 0.0
        return ProcessingMetricsSnapshot(
            total_items=total,
            succeeded=succeeded,
            failed=failed,
            total_time_ms=total_time,
            average_time_ms=average,
            throughput_per_second=throughput,
        )

    def merge(self, snapshot: ProcessingMetricsSnapshot) -> None:
        """Merge a validated snapshot into these counters atomically.

        This is useful when workers collect local metrics and a coordinator
        aggregates them without exposing mutable internal state.
        """
        if not isinstance(snapshot, ProcessingMetricsSnapshot):
            raise TypeError("snapshot must be a ProcessingMetricsSnapshot")
        if snapshot.succeeded + snapshot.failed != snapshot.total_items:
            raise ValueError("metrics counters must be consistent")
        if snapshot.total_time_ms < 0:
            raise ValueError("metrics total time cannot be negative")
        with self._lock:
            self._total_items += snapshot.total_items
            self._succeeded += snapshot.succeeded
            self._failed += snapshot.failed
            self._total_time_ms += snapshot.total_time_ms

    def reset(self) -> None:
        """Reset all counters atomically."""
        with self._lock:
            self._total_items = 0
            self._succeeded = 0
            self._failed = 0
            self._total_time_ms = 0.0

    def __repr__(self) -> str:
        snapshot = self.snapshot()
        return (
            "ProcessingMetrics("
            f"total={snapshot.total_items}, "
            f"succeeded={snapshot.succeeded}, "
            f"failed={snapshot.failed})"
        )
